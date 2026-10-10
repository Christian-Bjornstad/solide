from __future__ import annotations
import math
import re
from urllib.parse import quote
import requests
from ._vendor.archer.services.system_trust import system_trust_session
from ._vendor.archer.services.genomic_notation import format_mtbp_grch37
from .models import Variant
from .quality import MANE_TARGETS


# NCBI GRCh37.p13 assembly report, primary assembled molecules only:
# https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/001/405/GCF_000001405.25_GRCh37.p13/GCF_000001405.25_GRCh37.p13_assembly_report.txt
_GRCH37_REFERENCES = dict(zip(
    [str(n) for n in range(1, 23)] + ['X', 'Y', 'M'],
    ['NC_000001.10', 'NC_000002.11', 'NC_000003.11', 'NC_000004.11',
     'NC_000005.9', 'NC_000006.11', 'NC_000007.13', 'NC_000008.10',
     'NC_000009.11', 'NC_000010.10', 'NC_000011.9', 'NC_000012.11',
     'NC_000013.10', 'NC_000014.8', 'NC_000015.9', 'NC_000016.9',
     'NC_000017.10', 'NC_000018.9', 'NC_000019.9', 'NC_000020.10',
     'NC_000021.8', 'NC_000022.10', 'NC_000023.10', 'NC_000024.9', 'NC_012920.1']))
_CHROMOSOME = r'(?:[1-9]|1[0-9]|2[0-2]|X|Y|M)'
_FULL_HGVS = re.compile(
    r'(?:NM|NR|NC|NG)_\d+\.\d+(?:\((?:NM|NR)_\d+\.\d+\))?:'
    r'[cgnm]\.[0-9*()_+\-ACGTNacgtn;\[\]delinsupv>=?.]+')
_SPLICE_SCORES = ('DS_AG', 'DS_AL', 'DS_DG', 'DS_DL')
_SPLICE_POSITIONS = ('DP_AG', 'DP_AL', 'DP_DG', 'DP_DL')


def hgvs_query(v: Variant) -> str:
    if v.corrected_hgvs:
        return v.corrected_hgvs.strip()
    if ':' in v.coding and re.match(r'(NM_|NC_|NG_)', v.coding):
        return v.coding
    if re.fullmatch(r'(?:NM_|NR_|NC_|NG_)[\w.]+',v.transcript) and v.coding:
        return f'{v.transcript}:{v.coding}'
    raise ValueError('Missing or ambiguous transcript / reference. Enter full HGVS for review.')


def genomic_query(v: Variant) -> str:
    if v.assembly != 'GRCh37':
        raise ValueError('Genomic searches require confirmed GRCh37 / hg19.')
    if v.controlled_genomic:
        if not v.nomenclature_verified:
            raise ValueError('Approve the reviewed genomic variant before searching.')
        match=re.fullmatch(rf'(?:chr)?({_CHROMOSOME})-([1-9]\d*)-([ACGT]+)-([ACGT]+)',v.controlled_genomic,re.I)
        if not match:
            raise ValueError('Reviewed genomic variant must use chr-pos-REF-ALT.')
        if match[3].upper() == match[4].upper():
            raise ValueError('REF and ALT must describe a sequence change.')
        return f'chr{match[1].upper()}-{match[2]}-{match[3].upper()}-{match[4].upper()}'
    if v.corrected_hgvs:
        raise ValueError('Reviewed HGVS requires matching reviewed GRCh37 chr-pos-REF-ALT for genomic searches.')
    match = re.fullmatch(rf'(?:chr)?({_CHROMOSOME}):([1-9]\d*)', v.locus, re.I)
    if not match or not re.fullmatch('[ACGT]+', v.ref.upper()) or not re.fullmatch('[ACGT]+', v.alt.upper()):
        raise ValueError('Genomic searches require chromosome:position and explicit REF/ALT.')
    if v.ref.upper() == v.alt.upper():
        raise ValueError('REF and ALT must describe a sequence change.')
    return f'chr{match[1].upper()}-{match[2]}-{v.ref.upper()}-{v.alt.upper()}'


def _normalization_query(v: Variant) -> tuple[str, str]:
    try:
        description = hgvs_query(v)
    except ValueError:
        chrom, pos, ref, alt = genomic_query(v).removeprefix('chr').split('-')
        genomic_hgvs = format_mtbp_grch37(f'chr{chrom}:{pos}', ref, alt)
        if not genomic_hgvs:
            raise ValueError('Cannot construct HGVS from the supplied GRCh37 alleles.')
        description = _GRCH37_REFERENCES[chrom] + ':' + genomic_hgvs.split(':', 1)[1]
        return description, 'genomic_grch37'
    if len(description) > 500 or not _FULL_HGVS.fullmatch(description):
        raise ValueError('Enter one complete, versioned nucleotide HGVS description for review.')
    return description, 'full_hgvs'


def _map_normalization(http, result: dict, target: str) -> None:
    result['mane_target'] = target
    try:
        response = http.get('https://mutalyzer.nl/api/map/', params={
            'description': result['normalization']['normalized_description'],
            'reference_id': target, 'filter_out': 'true'}, timeout=45)
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            result['mapping_response'] = payload
        response.raise_for_status()
        mapped = payload.get('mapped_description') if isinstance(payload, dict) else None
        if not isinstance(mapped, str) or not mapped.startswith(target + ':'):
            raise ValueError('No unambiguous target description returned.')
        result['mapping'] = payload
    except (requests.RequestException, ValueError) as exc:
        # Mapping is optional. Preserve valid normalization when the remote
        # mapper rejects sequence differences or times out; never swap accessions.
        payload = result.get('mapping_response', {})
        custom = payload.get('custom')
        errors = payload.get('errors') or (custom.get('errors') if isinstance(custom, dict) else None)
        errors = errors if isinstance(errors, list) else []
        codes = [str(item.get('code')) for item in errors if isinstance(item, dict) and item.get('code')]
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        reason = f'HTTP {status}' if isinstance(status, int) else type(exc).__name__
        if codes:
            reason += '; ' + ', '.join(codes)
        result['mapping_issue'] = f'MANE mapping unavailable ({reason}). Review the target transcript manually.'


def normalize_variant(v: Variant, http=None) -> dict:
    description, basis = _normalization_query(v)
    owned_session = http is None
    if owned_session:
        http = system_trust_session()
    try:
        # Current API schema: https://mutalyzer.nl/api/swagger.json
        response = http.get('https://mutalyzer.nl/api/normalize/' + quote(description, safe=''), timeout=45)
        if response.status_code != 422:
            response.raise_for_status()
        data = response.json()
        # Validation rejections use HTTP 422 and put the normalizer output in
        # custom. They are useful review evidence, not a lost network response.
        if response.status_code == 422:
            custom = data.get('custom') if isinstance(data, dict) else None
            if not isinstance(custom, dict) or not custom.get('errors'):
                response.raise_for_status()
            data = custom
        if not isinstance(data, dict) or not (data.get('normalized_description') or data.get('errors')):
            raise ValueError('Mutalyzer returned no normalization or error details.')
        if data.get('input_description') and data['input_description'] != description:
            raise ValueError('Mutalyzer did not confirm the requested HGVS description.')
        result = {'original': description, 'query_basis': basis, 'normalization': data}
        if response.status_code == 422:
            result['normalization_http_status'] = 422
        target = MANE_TARGETS.get(v.gene)
        if target and target[0] in v.transcript and not data.get('errors'):
            _map_normalization(http, result, target[1])
        return result
    finally:
        if owned_session:
            http.close()


def _trim_spliceai_alleles(pos: int, ref: str, alt: str) -> tuple[int, str, str]:
    # Follow Broad's documented spelling exactly; preserve the VCF anchor.
    # https://github.com/broadinstitute/SpliceAI-lookup/blob/master/google_cloud_run_services/server.py
    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
        pos, ref, alt = pos + 1, ref[1:], alt[1:]
    return pos, ref, alt


def validate_spliceai_response(data: dict, variant: str) -> str:
    """Confirm requested hg19 settings, allele identity and usable prediction rows.

    Return the actual scored chr-pos-REF-ALT spelling. Broad may trim shared
    bases while preserving the VCF anchor; delta positions refer to that spelling.
    An empty score list is valid but is not evidence of a prediction match.
    """
    if not isinstance(data, dict):
        raise ValueError('SpliceAI returned an unexpected response format.')
    if data.get('error') or data.get('errors'):
        raise ValueError(str(data.get('error') or data.get('errors')))
    if data.get('variant') != variant:
        raise ValueError('SpliceAI did not confirm the requested variant.')
    if any(str(data.get(key)) != '37' for key in ('hg', 'genomeVersion')):
        raise ValueError('SpliceAI did not confirm GRCh37 / hg19.')
    if data.get('distance') != 500 or data.get('mask') != 1:
        raise ValueError('SpliceAI did not confirm distance=500 and mask=1.')
    chrom, pos, ref, alt = variant.removeprefix('chr').split('-')
    returned = (str(data.get('chrom')).removeprefix('chr'), data.get('pos'), data.get('ref'), data.get('alt'))
    original = (chrom, int(pos), ref, alt)
    trimmed = (chrom, *_trim_spliceai_alleles(int(pos), ref, alt))
    if returned not in (original, trimmed):
        raise ValueError('SpliceAI scored alleles differ from the requested variant.')
    rows = data.get('scores')
    if not isinstance(rows, list):
        raise ValueError('SpliceAI returned an unexpected score format.')
    for row in rows:
        if not isinstance(row, dict) or not all(key in row for key in _SPLICE_SCORES + _SPLICE_POSITIONS):
            raise ValueError('SpliceAI returned incomplete prediction scores.')
        try:
            scores = [float(row[key]) for key in _SPLICE_SCORES]
            positions = [float(row[key]) for key in _SPLICE_POSITIONS]
        except (TypeError, ValueError):
            raise ValueError('SpliceAI returned invalid prediction values.') from None
        if any(not math.isfinite(score) or not 0 <= score <= 1 for score in scores) or any(
                not math.isfinite(pos) or not pos.is_integer() for pos in positions):
            raise ValueError('SpliceAI returned invalid prediction values.')
    return f'chr{returned[0]}-{returned[1]}-{returned[2]}-{returned[3]}'


def spliceai_variant(v: Variant, http=None) -> dict:
    variant = genomic_query(v)
    owned_session = http is None
    if owned_session:
        http = system_trust_session()
    try:
        response = http.get('https://spliceai-37-xwkwwwxdwq-uc.a.run.app/spliceai/', params={
            'hg': 37, 'variant': variant, 'distance': 500, 'mask': 1}, timeout=120)
        response.raise_for_status()
        data = response.json()
        scored = validate_spliceai_response(data, variant)
        return {'query': variant, 'hg': 37, 'distance': 500, 'mask': 1,
                'scored_variant': scored, 'response': data}
    finally:
        if owned_session:
            http.close()


def spliceai_summary(data: dict) -> str:
    rows=data.get('response',{}).get('scores',[])
    parts=[]
    for row in rows:
        values=[f'{key}={row[key]}' for key in _SPLICE_SCORES + _SPLICE_POSITIONS if key in row]
        gene = row.get('g_name') or row.get('gene_name') or row.get('symbol') or 'Unlabelled gene'
        transcript = row.get('t_id') or row.get('transcript_id') or ''
        refseq = row.get('t_refseq_ids') or []
        label = str(gene) + (f' / {transcript}' if transcript else '')
        if isinstance(refseq, list) and refseq:
            label += ' (' + ', '.join(str(item) for item in refseq) + ')'
        if values:parts.append(label+': '+', '.join(values))
    return '\n'.join(parts) or 'No scores returned; manual review required.'
