from __future__ import annotations
import csv
import hashlib
import math
import re
from pathlib import Path
from .models import Variant, ImportResult


def text(value) -> str:
    return '' if value is None else str(value).strip()


def number(value) -> float | None:
    try:
        n = float(text(value).replace('%', '').replace(',', '.'))
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def normalize_assembly(value: str) -> str:
    return {'hg19': 'GRCh37', 'grch37': 'GRCh37', 'hg38': 'GRCh38',
            'grch38': 'GRCh38'}.get(text(value).lower(), 'Unknown')


def load_file(path: Path) -> ImportResult:
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata, hint, warnings = {}, '', []
    if path.suffix.lower() == '.xlsx':
        from openpyxl import load_workbook
        w = load_workbook(path, read_only=True, data_only=True)
        tables = [(sheet.title, list(sheet.values)) for sheet in w]
        w.close()
    elif path.suffix.lower() == '.tsv':
        payload = path.read_bytes()
        try:
            lines = payload.decode('utf-8-sig').splitlines()
        except UnicodeDecodeError:
            lines = payload.decode('cp1252').splitlines()
        rows = []
        for line in lines:
            if line.startswith('##'):
                key, sep, value = line.split('\t', 1)[0][2:].partition('=')
                if sep:
                    metadata[key] = value
            rows.append(next(csv.reader([line], delimiter='\t')))
        tables = [('', rows)]
        hint = metadata.get('sampleNames', '')
    else:
        raise ValueError('Choose a TSV or XLSX file.')
    assembly = normalize_assembly(metadata.get('reference', ''))
    variants = []
    for sheet_name, rows in tables:
        header_index = next((i for i, r in enumerate(rows)
                             if 'Type' in r and ('Gene' in r or 'Genes' in r)), None)
        if header_index is None:
            continue
        if not hint:
            # A hint only; the UI must ask the user to confirm patient binding.
            for row in rows[:header_index]:
                for cell in row:
                    if re.fullmatch(r'\d{2}[A-Za-z]{3}\d+(?:_\w+)?', text(cell)):
                        hint = text(cell)
        headers = [text(h) for h in rows[header_index]]
        platform = 'Ion Reporter' if 'Transcript' in headers and 'Genes' in headers else 'Genexus'
        for index, row in enumerate(rows[header_index + 1:], header_index + 2):
            raw = {h: cell for h, cell in zip(headers, row) if h}
            if not text(raw.get('Type')) or not text(raw.get('Gene', raw.get('Genes'))):
                continue
            def get(*names):
                return next((raw[n] for n in names if n in raw), None)
            af = number(get('Allele Frequency %', 'Allele Frequency (%)', 'Allele Frequency'))
            if af is not None and 'Allele Frequency' in headers:
                af = round(af * 100, 10)
            if af is not None and not 0 <= af <= 100:
                warnings.append(f'Row {index}: allele frequency outside 0–100%.')
                af = None
            raw['_sheet'] = sheet_name
            call = text(get('Call', 'Genotype'))
            variants.append(Variant(
                id=hashlib.sha256(f'{digest}:{sheet_name}:{index}'.encode()).hexdigest()[:24],
                gene=text(get('Genes', 'Gene')), transcript=text(get('Transcript', 'Gene Isoform')),
                coding=text(get('Coding', 'Nucleotide Change', 'Nuc Change')),
                protein=text(get('Amino Acid Change', 'AA Change')), locus=text(get('Locus')),
                ref=text(get('Ref')), alt=text(get('Alt', 'Observed Allele')),
                kind=text(get('Type')), call=call, af_percent=af,
                coverage=number(get('Coverage')), copy_number=number(get('Copy Number')),
                variant_id=text(get('Variant ID')), assembly=assembly, platform=platform,
                source_file=str(path.resolve()), source_hash=digest, source_row=index,
                selected=call.upper().startswith('PRESENT') and text(get('Type')).lower() in
                {'snp', 'snv', 'del', 'ins', 'indel', 'mnp', 'complex'}, raw=raw))
    if not variants:
        raise ValueError('No variant table with Type and Gene/Genes found. Check the export format.')
    if assembly == 'Unknown':
        warnings.append('Assembly missing. Confirm hg19 before genomic searches.')
    if metadata.get('analysisName') and hint and hint not in metadata['analysisName']:
        warnings.append('Sample metadata differs from the analysis name. Confirm sample identity.')
    warnings.append('Coverage describes individual exported rows, not whole-gene coverage.')
    return ImportResult(variants, metadata, warnings, assembly, hint)
