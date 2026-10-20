from __future__ import annotations
import csv
import hashlib
import io
import math
import re
from pathlib import Path
from .models import Variant, ImportResult


SOLIDE_REPORT_IDENTIFIER = 'solide:variant-review-report'


def oum_numbers(value: str) -> list[str]:
    return list(dict.fromkeys(match.upper() for match in re.findall(
        r'(?<![A-Za-z0-9])\d{2}OUM(?:\d+|X+)(?![A-Za-z0-9])',str(value),re.I)))


def detect_analysis(headers,metadata):
    """Separate the report schema from the assay; explicit assay metadata wins."""
    workflow=' '.join(str(metadata.get(key) or '') for key in ('workflowName','assayName'))
    columns={name.casefold() for name in headers}
    if re.search(r'oncomine\s+precision|\bopa\b',workflow,re.I):
        return 'OPA','Oncomine Precision Assay','Oncomine Precision Assay is named in the file.'
    if {'genes','transcript'}<=columns:
        assay='Childhood' if 'childhood' in workflow.lower() else 'BRCA/HRR' if re.search(r'brca|hrr',workflow,re.I) else workflow.strip() or 'Unknown'
        return 'Ion Torrent',assay,'Ion Reporter columns: Genes and Transcript.'
    if 'gene' in columns and columns & {'nuc change','nucleotide change'}:
        return 'OPA','Oncomine Precision Assay','Genexus/OPA column layout. Confirm the assay in Import details if different.'
    return 'Unassigned',workflow.strip() or 'Unknown','Analysis type is not established by these columns. Choose it in Import details.'


def text(value) -> str:
    return '' if value is None else str(value).strip()


def _variant_header(row) -> bool:
    names = {text(cell).casefold() for cell in row}
    return 'type' in names and bool(names & {'gene', 'genes'})


def _checked_headers(row) -> list[str]:
    headers = [text(cell) for cell in row]
    named = [name.casefold() for name in headers if name]
    if len(named) != len(set(named)):
        raise ValueError('Duplicate column names found. Choose the original variant export instead of a reviewed worksheet.')
    # Alias columns cannot silently compete for one interpreted field.
    for aliases in ({'gene', 'genes'}, {'transcript', 'gene isoform'},
                    {'coding', 'nucleotide change', 'nuc change'}, {'amino acid change', 'aa change'}):
        if len(set(named) & aliases) > 1:
            raise ValueError('Flere kolonner beskriver samme annotasjonsfelt. Kontroller kolonneoppsettet i eksporten.')
    return headers


_TRANSCRIPT = re.compile(r'(?:(?:NM|NR|XM|XR)_\d+(?:\.\d+)?|ENST\d+(?:\.\d+)?|LRG_\d+t\d+)')
_REFERENCE = re.compile(r'(?:(?:N[CGMPRTWZ]|X[MRP]|AC|AP)_\d+(?:\.\d+)?|ENS[A-Z]*\d+(?:\.\d+)?|LRG_\d+(?:[tp]\d+)?)')
_GENE_SYMBOL = re.compile(r'[A-Za-z][A-Za-z0-9]*(?:[-.][A-Za-z0-9]+)*')


def _annotation_columns(gene_value, transcript_value, coding_value, protein_value, raw: dict) -> tuple[str, str, str]:
    """Repair only a proven field-type inversion, retaining every source cell."""
    gene, transcript = text(gene_value), text(transcript_value)
    if any(value is not None and not isinstance(value, str)
           for value in (gene_value, transcript_value, coding_value, protein_value)):
        return gene, transcript, 'Annotasjonsfelt inneholder andre celletyper enn tekst. Kontroller kilderaden.'
    genes = [part.strip() for part in re.split(r'[,;|]', gene)]
    transcripts = [part.strip() for part in re.split(r'[,;|]', transcript)]
    gene_references = [_REFERENCE.fullmatch(part) is not None for part in genes]
    if all(_TRANSCRIPT.fullmatch(part) for part in genes) and all(_GENE_SYMBOL.fullmatch(part) for part in transcripts):
        raw['_annotation_column_repair'] = {
            'method': 'unambiguous_gene_transcript_swap',
            'source_gene': gene, 'source_transcript': transcript,
        }
        return transcript, gene, ''
    if any(gene_references):
        return gene, transcript, 'Referansesekvens i genkolonnen; gen og transkript kan ikke kobles entydig.'
    if transcript not in {'', '-', '.'} and any(_GENE_SYMBOL.fullmatch(part) for part in transcripts):
        return gene, transcript, 'Gennavn i transkriptkolonnen; kontroller gen- og transkriptfeltene.'
    if any(part not in {'', '-', '.'} and not (_TRANSCRIPT.fullmatch(part) or _REFERENCE.fullmatch(part))
           for part in transcripts):
        return gene, transcript, 'Ukjent eller ugyldig referanse i transkriptkolonnen; kontroller kilderaden.'
    return gene, transcript, ''


def number(value) -> float | None:
    try:
        n = float(text(value).replace('%', '').replace(',', '.'))
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def normalize_assembly(value: str) -> str:
    return {'hg19': 'GRCh37', 'grch37': 'GRCh37', 'hg38': 'GRCh38',
            'grch38': 'GRCh38'}.get(text(value).lower(), 'Unknown')


def _count(value) -> int | None:
    value = text(value)
    if not re.fullmatch(r'[0-9]+', value):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def export_scope(metadata: dict, exported_variant_count: int) -> dict | None:
    """Retain source counts without inferring completeness from missing metadata."""
    names = {
        'total_variant_count': 'totalVariantCount',
        'filtered_in_count': 'filterInCount',
        'filtered_out_count': 'filteredOutCount',
        'hidden_variant_count': 'hiddenVariantCount',
    }
    counts = {name: _count(metadata.get(source)) for name, source in names.items()}
    if all(value is None for value in counts.values()):
        return None
    counts['exported_variant_count'] = exported_variant_count
    counts['filtered_export'] = (
        (counts['total_variant_count'] is not None and counts['total_variant_count'] > exported_variant_count)
        or (counts['filtered_out_count'] or 0) > 0
        or (counts['hidden_variant_count'] or 0) > 0
    )
    return counts


def export_scope_warning(scope: dict) -> str:
    if not scope.get('filtered_export'):
        return ''
    details = [f"{scope['exported_variant_count']:,} imported rows"]
    total = scope.get('total_variant_count')
    if total is not None:
        details.append(f'{total:,} total source variants')
    for key, label in [('filtered_out_count', 'filtered out'), ('hidden_variant_count', 'hidden')]:
        value = scope.get(key)
        if value:
            details.append(f'{value:,} {label}')
    return 'Filtered export: ' + ', '.join(details) + '. QC covers imported rows only.'


def _is_solide_report(identifier, tables) -> bool:
    if text(identifier) == SOLIDE_REPORT_IDENTIFIER:
        return True
    # Older reports lack a document identifier; their title and paired metadata
    # establish their origin even when only Raw data remains import-eligible.
    for _, rows in tables:
        if not rows or not rows[0] or text(rows[0][0]).casefold() != 'solide':
            continue
        pairs = {
            text(row[index]).casefold(): text(row[index + 1])
            for row in rows[:12] for index in range(len(row) - 1)
        }
        version = pairs.get('app version', '')
        report_format = _count(pairs.get('report format'))
        if re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?', version) and report_format:
            return True
    return False


def load_file(path: Path) -> ImportResult:
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    source_path=str(path.resolve())
    metadata, hint, warnings = {}, '', []
    tsv_rows=None
    if path.suffix.lower() == '.xlsx':
        from openpyxl import load_workbook
        w = load_workbook(path, read_only=True, data_only=True)
        try:
            tables = [(sheet.title, list(sheet.values)) for sheet in w]
            if _is_solide_report(w.properties.identifier, tables):
                raise ValueError('Solide report detected. Choose the original TSV/XLSX export instead of a generated report.')
        finally:
            w.close()
    elif path.suffix.lower() == '.tsv':
        payload = path.read_bytes()
        try:
            decoded = payload.decode('utf-8-sig')
        except UnicodeDecodeError:
            decoded = payload.decode('cp1252')
        rows,tsv_rows=[],[]
        reader=csv.reader(io.StringIO(decoded,newline=''),delimiter='\t',strict=True)
        header_seen=False
        try:
            while True:
                source_row=reader.line_num+1
                try:row=next(reader)
                except StopIteration:break
                if row and row[0].startswith('##'):
                    key,sep,value=row[0][2:].partition('=')
                    if sep:
                        if header_seen:
                            raise ValueError('Flere eksportblokker i TSV-filen. Eksporter én prøve per fil.')
                        if key in metadata and metadata[key]!=value:
                            raise ValueError('Motstridende metadata i TSV-filen. Kontroller eksporten.')
                        metadata[key]=value
                if _variant_header(row):header_seen=True
                rows.append(row);tsv_rows.append(source_row)
        except csv.Error as exc:
            raise ValueError(f'Ugyldig TSV ved linje {reader.line_num}: {exc}') from exc
        tables = [('', rows)]
        hint = metadata.get('sampleNames', '')
    else:
        raise ValueError('Choose a TSV or XLSX file.')
    assembly = normalize_assembly(metadata.get('reference', ''))
    variants = []
    eligible=[(sheet,rows) for sheet,rows in tables if any(_variant_header(row) for row in rows)]
    if len(eligible)>1:
        raise ValueError('Multiple variant tables found. Export the original variant sheet separately to avoid duplicate review copies.')
    for sheet_name, rows in tables:
        header_index = next((i for i, r in enumerate(rows) if _variant_header(r)), None)
        if header_index is None:
            continue
        if not hint:
            # A hint only; the UI must ask the user to confirm patient binding.
            for row in rows[:header_index]:
                for cell in row:
                    if re.fullmatch(r'\d{2}[A-Za-z]{3}\d+(?:_\w+)?', text(cell)):
                        hint = text(cell)
        headers = _checked_headers(rows[header_index])
        schema = sorted(name.casefold() for name in headers)
        platform = 'Ion Reporter' if {'transcript', 'genes'} <= set(schema) else 'Genexus'
        for offset, row in enumerate(rows[header_index + 1:], header_index + 1):
            index=tsv_rows[offset] if tsv_rows is not None else offset+1
            if _variant_header(row):
                repeated = _checked_headers(row)
                if sorted(name.casefold() for name in repeated) != schema:
                    raise ValueError(f'Rad {index}: endret kolonneoppsett i gjentatt overskrift. Eksporter én opprinnelig varianttabell.')
                headers = repeated
                continue
            if any(text(value) for value in row[len(headers):]):
                raise ValueError(f'Rad {index} har flere kolonner enn overskriften. Kontroller eksporten.')
            raw = {h: cell for h, cell in zip(headers, row) if h}
            lookup = {name.casefold(): value for name, value in raw.items()}
            def get(*names):
                return next((lookup[name.casefold()] for name in names if name.casefold() in lookup), None)
            if not text(get('Type')) or not text(get('Genes', 'Gene')):
                continue
            af = number(get('Allele Frequency %', 'Allele Frequency (%)', 'Allele Frequency'))
            if af is not None and 'allele frequency' in lookup:
                af = round(af * 100, 10)
            if af is not None and not 0 <= af <= 100:
                warnings.append(f'Row {index}: allele frequency outside 0–100%.')
                af = None
            raw['_sheet'] = sheet_name
            raw['_columns'] = headers
            raw['_values'] = list(row[:len(headers)]) + [None]*max(0,len(headers)-len(row))
            gene, transcript, issue = _annotation_columns(
                get('Genes', 'Gene'), get('Transcript', 'Gene Isoform'),
                get('Coding', 'Nucleotide Change', 'Nuc Change'), get('Amino Acid Change', 'AA Change'), raw)
            if issue:
                raw['_annotation_issue'] = issue
                warnings.append(f'Rad {index}: {issue}')
            elif raw.get('_annotation_column_repair'):
                warnings.append(f'Rad {index}: gen- og transkriptfeltene var byttet og er tolket etter celleinnholdet. Originalcellene er beholdt.')
            call = text(get('Call')) or text(get('Genotype'))
            variants.append(Variant(
                id=hashlib.sha256(f'{digest}:{sheet_name}:{index}'.encode()).hexdigest()[:24],
                gene=gene, transcript=transcript,
                coding=text(get('Coding', 'Nucleotide Change', 'Nuc Change')),
                protein=text(get('Amino Acid Change', 'AA Change')), locus=text(get('Locus')),
                ref=text(get('Ref')), alt=text(get('Alt', 'Observed Allele')),
                kind=text(get('Type')), call=call, af_percent=af,
                coverage=number(get('Coverage')), copy_number=number(get('Copy Number')),
                variant_id=text(get('Variant ID')), assembly=assembly, platform=platform,
                source_file=source_path, source_hash=digest, source_row=index,
                selected=not issue and call.upper().startswith('PRESENT') and text(get('Type')).lower() in
                {'snp', 'snv', 'del', 'ins', 'indel', 'mnp', 'complex'}, raw=raw))
    if not variants:
        raise ValueError('No variant table with Type and Gene/Genes found. Check the export format.')
    scope = export_scope(metadata, len(variants))
    if scope is not None:
        for variant in variants:
            variant.raw['_export_scope'] = dict(scope)
        warning = export_scope_warning(scope)
        if warning:
            warnings.append(warning)
    if assembly == 'Unknown':
        warnings.append('Assembly missing. Confirm hg19 before genomic searches.')
    if metadata.get('analysisName') and hint and hint not in metadata['analysisName']:
        warnings.append('Sample metadata differs from the analysis name. Confirm sample identity.')
    warnings.append('Coverage describes individual exported rows, not whole-gene coverage.')
    sample_metadata=text(metadata.get('sampleNames') or metadata.get('sampleName'))
    if len(oum_numbers(sample_metadata))>1 or len([part for part in re.split(r'[,;]',sample_metadata) if part.strip()])>1:
        raise ValueError('Multiple samples are named in this export. Choose one original sample TSV per import.')
    sample_columns={'sample','samplename','sampleid','samplenames'}
    row_samples={}
    for variant in variants:
        for key,value in variant.raw.items():
            name=re.sub(r'[\s_-]','',key).casefold()
            if name in sample_columns and text(value) not in {'','-'}:
                row_samples.setdefault(name,set()).add(text(value).casefold())
    row_oum=list(dict.fromkeys(number for values in row_samples.values() for value in values for number in oum_numbers(value)))
    if any(len(values)>1 for values in row_samples.values()) or len(row_oum)>1:
        raise ValueError('Flere prøver i TSV-filen. Eksporter én prøve per fil.')
    metadata_ids=list(dict.fromkeys(number for key in ('sampleNames','sampleName') for number in oum_numbers(text(metadata.get(key)))))
    if len(set(metadata_ids+row_oum))>1:
        raise ValueError('Flere prøver i TSV-filen. Kontroller prøvefeltene.')
    candidates=list(dict.fromkeys(metadata_ids+row_oum+oum_numbers(hint)+oum_numbers(path.stem)))
    if len(candidates)>1:
        warnings.append('Conflicting OUM numbers in the source and filename. Confirm the correct sample before import.')
        hint=''
    elif candidates:hint=candidates[0]
    profile,assay,reason=detect_analysis(variants[0].raw['_columns'],metadata)
    return ImportResult(variants,metadata,warnings,assembly,hint,profile,assay,reason,candidates)
