"""BRCA Exchange evidence with exact variant identity checks.

API reference: https://brcaexchange.org/about/api
https://github.com/BRCAChallenge/brca-exchange/blob/master/website/content/api_docs/api_overview.md
The API is internal and may change. Its current implementation uses repeated
``include``, ``filter`` and ``filterValue`` keys, without the docs' ``[]`` suffix:
https://github.com/BRCAChallenge/brca-exchange/blob/master/django/data/views.py
These request keys and both lookup paths were checked against the live API
on 2026-10-09 using the public NM_007294.4:c.68_69del example.

Only the explicitly assembly-labelled hg37 coordinate is used for genomic
matching. The unlabelled Chr/Pos/Ref/Alt fields belong to another assembly.
Representations are never shifted, reverse complemented or accession-swapped.
"""
from __future__ import annotations

import re

import requests

from ._vendor.archer.services.system_trust import system_trust_session
from .models import Variant
from .nomenclature import genomic_query, hgvs_query


API = 'https://brcaexchange.org/backend/data/'
SOURCE_URL = 'https://brcaexchange.org/variants'
SUPPORTED_GENES = {'BRCA1': '17', 'BRCA2': '13'}
PAGE_SIZE = 100
_HGVS = re.compile(r'(?:NM|NR|NC|NG)_\d+\.\d+:(?:c|n|g)\.[0-9*()_+\-ACGTacgtdelinsupv>=?.]+')
_GENOMIC = re.compile(r'(?:chr)?(\d+)(?:-([1-9]\d*)-([ACGT]+)-([ACGT]+)|:g\.([1-9]\d*):([ACGT]+)>([ACGT]+))', re.I)


def _text(value) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ''
    result = str(value).strip()
    return '' if result in {'', '-', 'None', 'null'} else result


def _genomic(value) -> str:
    match = _GENOMIC.fullmatch(_text(value))
    if not match:
        return ''
    chrom = str(int(match[1]))
    pos, ref, alt = match.group(2, 3, 4) if match[2] else match.group(5, 6, 7)
    return f'chr{chrom}-{int(pos)}-{ref.upper()}-{alt.upper()}'


def _returned_hgvs(row: dict) -> set[str]:
    values = set()
    for field in ('HGVS_cDNA', 'Genomic_HGVS_37'):
        value = _text(row.get(field))
        # Some historical data separate the accession from the cDNA description.
        if field == 'HGVS_cDNA' and value.startswith(('c.', 'n.')):
            value = _text(row.get('Reference_Sequence')) + ':' + value
        if _HGVS.fullmatch(value):
            values.add(value)
    return values


def _request(v: Variant) -> tuple[str, dict, str, dict]:
    if v.assembly != 'GRCh37':
        raise ValueError('Confirm GRCh37 / hg19 before searching BRCA Exchange.')
    if v.corrected_hgvs and not v.nomenclature_verified:
        raise ValueError('Approve corrected HGVS before searching BRCA Exchange.')
    hgvs = ''
    try:
        hgvs = hgvs_query(v)
    except ValueError:
        pass
    if hgvs and (len(hgvs) > 500 or not _HGVS.fullmatch(hgvs)):
        raise ValueError('Enter one complete, versioned nucleotide HGVS description for review.')
    if hgvs.startswith('NC_'):
        accession = hgvs.split(':')[0]
        if accession != f'NC_{int(SUPPORTED_GENES[v.gene]):06d}.10':
            raise ValueError('Genomic HGVS accession does not confirm the requested gene on GRCh37.')
    genomic = ''
    # Reviewed HGVS supersedes original genomic alleles. Only the separately
    # approved controlled_genomic field may accompany corrected HGVS.
    if v.controlled_genomic or (not v.corrected_hgvs and v.locus and v.ref and v.alt):
        genomic = _genomic(genomic_query(v))
        if not genomic or genomic.split('-')[0] != 'chr' + SUPPORTED_GENES[v.gene]:
            raise ValueError('Genomic chromosome does not match the requested BRCA gene.')
    params = {'format': 'json', 'include': 'all', 'page_size': PAGE_SIZE, 'page_num': 0,
              'filter': ['Gene_Symbol'], 'filterValue': [v.gene]}
    requested = {'gene': v.gene, 'assembly': 'GRCh37'}
    if genomic:
        chrom, pos, ref, alt = genomic.split('-')
        params['filter'].append('Genomic_Coordinate_hg37')
        params['filterValue'].append(f'{chrom}:g.{pos}:{ref}>{alt}')
        requested['genomic'] = genomic
        return 'genomic_grch37', params, hgvs, requested
    if not hgvs:
        raise ValueError('BRCA Exchange requires complete HGVS or explicit GRCh37 chromosome / position / REF / ALT.')
    params['search_term'] = hgvs
    requested['hgvs'] = hgvs
    return 'full_hgvs', params, hgvs, requested


def _verify(row: dict, requested: dict, basis: str, hgvs: str) -> dict:
    returned = {'gene': _text(row.get('Gene_Symbol')), 'assembly': 'GRCh37'}
    if basis == 'genomic_grch37':
        returned['genomic'] = _genomic(row.get('Genomic_Coordinate_hg37'))
    else:
        values = _returned_hgvs(row)
        returned['hgvs'] = hgvs if hgvs in values else ', '.join(sorted(values))
    identity = {'requested': requested, 'returned': returned, 'accepted': None, 'method': basis}
    if not returned['gene'] or not returned.get('genomic', returned.get('hgvs')):
        identity['reason'] = 'Returned record lacks a verifiable variant identity.'
    elif returned != requested:
        identity.update(accepted=False, reason='Returned gene or variant identity differs from the request.')
    elif basis == 'genomic_grch37' and hgvs and any(
            value.split(':')[0] == hgvs.split(':')[0] and value != hgvs
            for value in _returned_hgvs(row)):
        identity.update(accepted=False, reason='The genomic match conflicts with HGVS on the same versioned accession.')
    else:
        identity.update(accepted=True, reason='Exact gene and ' + ('GRCh37 genomic allele' if basis == 'genomic_grch37' else 'versioned HGVS') + ' match.')
    return identity


def _rows(payload) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
        raise ValueError('Unexpected BRCA Exchange response format.')
    if not all(isinstance(row, dict) for row in payload['data']):
        raise ValueError('Unexpected BRCA Exchange variant format.')
    return payload['data']


def _get(http, endpoint: str, params: dict) -> dict:
    response = http.get(endpoint, params=params, timeout=45, allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise requests.RequestException('Unexpected HTTP response.')
    return response.json()


def _result(status: str, summary: str, raw: dict, *, url: str = SOURCE_URL,
            classification: str = '', accession: str = '') -> dict:
    return {'status': status, 'summary': summary, 'url': url, 'raw': raw,
            'clinical_significance': classification, 'accession': accession}


def brca_exchange_variant(v: Variant, http=None) -> dict:
    """Return evidence; no network request is made for genes outside BRCA1/BRCA2.

    Status is found, not_found, not_applicable, needs_review, identity_mismatch,
    or error. Only found exposes classification, with accepted identity and
    the source's exact variant version. ``http`` allows offline test sessions.
    No sample identifiers, filenames, comments or worksheet data are sent.
    """
    raw = {'dataset': 'BRCA Exchange live database', 'release': None,
           'api_documentation': 'https://brcaexchange.org/about/api',
           'identity_verification': {'accepted': None, 'requested': None, 'returned': None}}
    if v.gene not in SUPPORTED_GENES:
        return _result('not_applicable', 'BRCA Exchange applies only to BRCA1 and BRCA2.', raw)
    try:
        basis, params, hgvs, requested = _request(v)
    except ValueError as exc:
        return _result('needs_review', str(exc), raw)
    raw.update(query_basis=basis, request={'endpoint': API, 'params': params},
               identity_verification={'accepted': None, 'requested': requested, 'returned': None})
    owned_session = http is None
    try:
        if owned_session:
            http = system_trust_session()
        payload = _get(http, API, params)
        rows = _rows(payload)
        raw['response'] = payload
        count = payload.get('count')
        if not isinstance(count, int) or isinstance(count, bool) or count < len(rows):
            raise ValueError('Invalid result count.')
        if count > len(rows):
            return _result('needs_review', 'BRCA Exchange returned an incomplete result page; review the source.', raw)
        if not rows:
            return _result('not_found', 'No matching variant was returned by BRCA Exchange.', raw)
        checks = [_verify(row, requested, basis, hgvs) for row in rows]
        raw['candidate_verification'] = checks
        matching = [(row, check) for row, check in zip(rows, checks) if check['accepted'] is True]
        if len(matching) != 1 or any(check['accepted'] is None for check in checks):
            if not matching and all(check['accepted'] is False for check in checks):
                raw['identity_verification'] = checks[0] if len(checks) == 1 else {
                    'accepted': False, 'requested': requested, 'returned': None,
                    'reason': 'No returned record matches the requested identity.'}
                return _result('identity_mismatch', 'Returned BRCA Exchange records do not match the requested identity.', raw)
            return _result('needs_review', 'BRCA Exchange did not return one unambiguous, verifiable match.', raw)
        row, check = matching[0]
        variant_id = row.get('id')
        if not isinstance(variant_id, int) or isinstance(variant_id, bool) or variant_id <= 0:
            return _result('needs_review', 'BRCA Exchange match has no valid source variant ID.', raw)
        raw['detail_request'] = {'endpoint': API + 'variant/', 'params': {'variant_id': variant_id}}
        detail = _get(http, API + 'variant/', {'variant_id': variant_id})
        raw['detail_response'] = detail
        versions = [version for version in _rows(detail)
                    if type(version.get('id')) is int and version['id'] == variant_id]
        if len(versions) != 1:
            return _result('needs_review', 'BRCA Exchange did not confirm the selected variant version.', raw)
        row = versions[0]
        check = _verify(row, requested, basis, hgvs)
        raw['identity_verification'] = check
        if check['accepted'] is not True:
            status = 'identity_mismatch' if check['accepted'] is False else 'needs_review'
            return _result(status, 'BRCA Exchange detail response did not confirm the requested identity.', raw)
        raw['variant'] = row
        raw['release'] = row.get('Data_Release') or {'id': row.get('Data_Release_id')}
        classification = _text(row.get('Pathogenicity_expert'))
        sources = _text(row.get('Source'))
        raw['classification'] = {'expert': classification,
            'expert_source': 'ENIGMA', 'expert_date': _text(row.get('Date_last_evaluated_ENIGMA')),
            'enigma_clinical_significance': _text(row.get('Clinical_significance_ENIGMA')),
            'assertion_method': _text(row.get('Assertion_method_ENIGMA')),
            'citations': _text(row.get('Clinical_significance_citations_ENIGMA')),
            'record_sources': sources}
        if basis == 'genomic_grch37':
            chrom, pos, ref, alt = requested['genomic'].split('-')
            raw.update(assembly_verified='GRCh37', matched_location={
                'chromosome': chrom, 'position': int(pos), 'ref': ref, 'alt': alt})
        summary = f'ENIGMA expert classification: {classification or "Not provided"}.'
        if sources:
            summary += '\nRecord sources: ' + sources.replace(',', ', ') + '.'
        return _result('found', summary, raw, url=f'https://brcaexchange.org/variant/{variant_id}',
                       classification=classification, accession=str(variant_id))
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        # HTTP exceptions can echo request details or response text. Retain only
        # their class and a numeric HTTP status, never arbitrary exception text.
        error = {'type': type(exc).__name__}
        code = getattr(getattr(exc, 'response', None), 'status_code', None)
        if isinstance(code, int) and 100 <= code <= 599:
            error['http_status'] = code
        raw['error'] = error
        return _result('error', 'BRCA Exchange lookup failed. Open the source and retry.', raw)
    finally:
        if owned_session and http is not None:
            http.close()
