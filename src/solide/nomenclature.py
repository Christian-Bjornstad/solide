from __future__ import annotations
import re
from urllib.parse import quote
import requests
from ._vendor.archer.services.system_trust import system_trust_session
from .models import Variant
from .quality import MANE_TARGETS


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
        match=re.fullmatch(r'(?:chr)?([\dXYM]+)-(\d+)-([ACGT]+)-([ACGT]+)',v.controlled_genomic,re.I)
        if not match:
            raise ValueError('Reviewed genomic variant must use chr-pos-REF-ALT.')
        return f'chr{match[1]}-{match[2]}-{match[3].upper()}-{match[4].upper()}'
    if v.corrected_hgvs:
        raise ValueError('Reviewed HGVS requires matching reviewed GRCh37 chr-pos-REF-ALT for genomic searches.')
    match = re.fullmatch(r'(?:chr)?([\dXYM]+):(\d+)', v.locus, re.I)
    if not match or not re.fullmatch('[ACGT]+', v.ref.upper()) or not re.fullmatch('[ACGT]+', v.alt.upper()):
        raise ValueError('Genomic searches require chromosome:position and explicit REF/ALT.')
    return f'chr{match[1]}-{match[2]}-{v.ref.upper()}-{v.alt.upper()}'


def normalize_variant(v: Variant, http=None) -> dict:
    http = http or system_trust_session()
    description = hgvs_query(v)
    response = http.get('https://mutalyzer.nl/api/normalize/' + quote(description, safe=''), timeout=45)
    response.raise_for_status()
    data = response.json()
    result = {'original': description, 'normalization': data}
    target = MANE_TARGETS.get(v.gene)
    if target and target[0] in v.transcript:
        response = http.get('https://mutalyzer.nl/api/map/', params={
            'description': data.get('normalized_description', description),
            'reference_id': target[1], 'filter_out': 'true'}, timeout=45)
        response.raise_for_status()
        result['mane_target'] = target[1]
        result['mapping'] = response.json()
    return result


def spliceai_variant(v: Variant, http=None) -> dict:
    http = http or system_trust_session()
    variant = genomic_query(v)
    response = http.get('https://spliceai-37-xwkwwwxdwq-uc.a.run.app/spliceai/', params={
        'hg': 37, 'variant': variant, 'distance': 500, 'mask': 1}, timeout=120)
    response.raise_for_status()
    data = response.json()
    if data.get('error') or data.get('errors'):
        raise ValueError(str(data.get('error') or data.get('errors')))
    if data.get('variant') != variant:
        raise ValueError('SpliceAI did not confirm the requested variant.')
    return {'query': variant, 'hg': 37, 'distance': 500, 'mask': 1, 'response': data}


def spliceai_summary(data: dict) -> str:
    rows=data.get('response',{}).get('scores',[])
    parts=[]
    for row in rows:
        values=[f'{key}={row[key]}' for key in ('DS_AG','DS_AL','DS_DG','DS_DL','DP_AG','DP_AL','DP_DG','DP_DL') if key in row]
        if values:parts.append(str(row.get('gene_name') or row.get('symbol') or row.get('transcript_id') or '')+': '+', '.join(values))
    return '\n'.join(parts) or 'No scores returned; manual review required.'
