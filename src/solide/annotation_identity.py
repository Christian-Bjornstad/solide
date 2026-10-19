"""Exact public RefSeq transcript identities, fetched only on explicit resolution.

NCBI EFetch contract: https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.EFetch
No sample fields, gene guesses, accession upgrades, or persistent cache are used.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from itertools import islice
import math
import re
import time
import xml.etree.ElementTree as ET

import requests

from ._vendor.archer.services.system_trust import system_trust_session

_EFETCH = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
_TRANSCRIPT = re.compile(r'(?:NM|NR)_\d{6,9}\.[1-9]\d{0,3}')
_PROTEIN = re.compile(r'NP_\d{6,9}\.[1-9]\d{0,3}')
_GENE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
_MAX_ACCESSIONS = 64
_MAX_XML_BYTES = 2 * 1024 * 1024
_TRANSIENT_COOLDOWN_SECONDS = 30


def _unresolved(accession: str, reason: str) -> dict:
    return {'transcript': accession, 'status': 'unresolved', 'reason': reason}


def _qualifiers(feature: ET.Element, name: str) -> set[str]:
    return {item.findtext('GBQualifier_value', '').strip()
            for item in feature.findall('./GBFeature_quals/GBQualifier')
            if item.findtext('GBQualifier_name') == name}


def _parse_identity(accession: str, content: bytes) -> dict:
    if len(content) > _MAX_XML_BYTES:
        return _unresolved(accession, 'oversized_response')
    # ElementTree does not retrieve external DTDs. Reject internal entity
    # declarations as well; the standard NCBI external DOCTYPE remains allowed.
    if b'<!ENTITY' in content.upper():
        return _unresolved(accession, 'invalid_xml')
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, ValueError):
        return _unresolved(accession, 'invalid_xml')
    records = [root] if root.tag == 'GBSeq' else list(root.findall('./GBSeq'))
    matches = [record for record in records
               if record.findtext('GBSeq_accession-version') == accession]
    if not matches:
        return _unresolved(accession, 'reference_mismatch' if records else 'missing_reference')
    if len(matches) != 1:
        return _unresolved(accession, 'duplicate_reference')
    record = matches[0]
    if record.findtext('GBSeq_organism') != 'Homo sapiens':
        return _unresolved(accession, 'nonhuman_reference')
    features = record.findall('./GBSeq_feature-table/GBFeature')
    gene_features = [item for item in features if item.findtext('GBFeature_key') == 'gene']
    gene_names = set().union(*(_qualifiers(item, 'gene') for item in gene_features))
    if not gene_names:
        return _unresolved(accession, 'missing_gene')
    all_genes = set().union(*(_qualifiers(item, 'gene') for item in features))
    if len(gene_names) != 1 or all_genes != gene_names:
        return _unresolved(accession, 'conflicting_gene')
    gene = next(iter(gene_names))
    if not _GENE.fullmatch(gene):
        return _unresolved(accession, 'invalid_gene')
    gene_ids = {value.removeprefix('GeneID:') for item in features
                for value in _qualifiers(item, 'db_xref') if value.startswith('GeneID:')}
    if len(gene_ids) > 1 or any(not re.fullmatch('[1-9][0-9]*', value) for value in gene_ids):
        return _unresolved(accession, 'conflicting_gene_id')
    cds = [item for item in features if item.findtext('GBFeature_key') == 'CDS']
    if accession.startswith('NM_'):
        if not cds or any(_qualifiers(item, 'gene') != {gene} for item in cds):
            return _unresolved(accession, 'missing_cds_gene')
    elif cds:
        return _unresolved(accession, 'noncoding_cds_conflict')
    proteins = set().union(*(_qualifiers(item, 'protein_id') for item in cds))
    if len(proteins) > 1:
        return _unresolved(accession, 'conflicting_protein')
    if any(not _PROTEIN.fullmatch(value) for value in proteins):
        return _unresolved(accession, 'invalid_protein_reference')
    return {
        'transcript': accession, 'gene': gene, 'protein': next(iter(proteins), ''),
        'gene_id': next(iter(gene_ids), ''), 'status': 'resolved',
        'source': 'NCBI RefSeq', 'reference_url': f'https://www.ncbi.nlm.nih.gov/nuccore/{accession}',
    }


class TranscriptIdentityResolver:
    """Reusable, bounded per-run lookup with no requests until ``resolve``.

    ``checkpoint`` is called immediately before each uncached network request;
    its exceptions propagate so the caller's pause/cancel mechanism is kept.
    Service failures are explicit per-reference results and never retried here.
    A failed service request stops further requests in that call and suppresses
    uncached lookups for 30 seconds across calls on this instance. Cached exact
    identities remain usable. No background retry or cooldown sleep is made.
    """

    def __init__(self, http=None, *, timeout=15, cache_size=256, checkpoint=None,
                 request_interval=0.34):
        if not isinstance(cache_size, int) or isinstance(cache_size, bool) or not 1 <= cache_size <= 4096:
            raise ValueError('cache_size must be between 1 and 4096.')
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError('timeout must be greater than zero and at most 120 seconds.')
        if (not isinstance(request_interval, (int, float)) or not math.isfinite(request_interval)
                or request_interval < 0 or request_interval > 60):
            raise ValueError('request_interval must be between zero and 60 seconds.')
        self._http = http
        self._owns_http = http is None
        self._timeout = timeout
        self._cache_size = cache_size
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._checkpoint = checkpoint
        self._request_interval = request_interval
        self._last_request = None
        self._cooldown_until = 0.0
        self._cooldown_reason = ''
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self) -> None:
        if not self._closed and self._owns_http and self._http is not None:
            self._http.close()
        self._cache.clear()
        self._cooldown_until = 0.0
        self._cooldown_reason = ''
        self._closed = True

    def _fetch(self, accession: str) -> tuple[dict, bool]:
        if self._last_request is not None:
            remaining = self._request_interval - (time.monotonic() - self._last_request)
            if remaining > 0:
                time.sleep(remaining)
        if self._checkpoint is not None:
            self._checkpoint()
        if self._http is None:
            self._http = system_trust_session()
        self._last_request = time.monotonic()
        try:
            response = self._http.get(_EFETCH, params={
                'db': 'nuccore', 'id': accession, 'rettype': 'gb', 'retmode': 'xml', 'tool': 'solide',
            }, timeout=self._timeout, allow_redirects=False)
            if response.status_code == 429:
                return _unresolved(accession, 'rate_limited'), True
            if response.status_code != 200:
                # An invalid or removed accession must not make independent
                # valid references look unavailable. Authentication, redirects,
                # server failures and rate limits concern the service instead.
                reference_rejection = response.status_code in {400, 404, 410, 422}
                return _unresolved(accession, 'http_error'), not reference_rejection
            return _parse_identity(accession, response.content), False
        except requests.Timeout:
            return _unresolved(accession, 'timeout'), True
        except requests.RequestException:
            return _unresolved(accession, 'network_error'), True

    def resolve(self, accessions) -> dict[str, dict]:
        if self._closed:
            raise RuntimeError('Transcript identity resolver is closed.')
        if isinstance(accessions, str):
            accessions = [accessions]
        # Consume only enough entries to enforce the cap, including for a
        # malformed/infinite iterator. Never issue a partial over-limit query.
        candidates = list(islice(iter(accessions), _MAX_ACCESSIONS + 1))
        if len(candidates) > _MAX_ACCESSIONS:
            raise ValueError('At most 64 transcript references may be resolved per call.')
        if any(not isinstance(value, str) for value in candidates):
            raise ValueError('Transcript references must be strings.')
        results = {}
        if time.monotonic() >= self._cooldown_until:
            self._cooldown_until = 0.0
            self._cooldown_reason = ''
        service_failure = self._cooldown_reason
        for accession in dict.fromkeys(candidates):
            if not _TRANSCRIPT.fullmatch(accession):
                results[accession] = _unresolved(accession, 'invalid_accession')
                continue
            if accession in self._cache:
                self._cache.move_to_end(accession)
                results[accession] = deepcopy(self._cache[accession])
                continue
            if service_failure:
                results[accession] = _unresolved(accession, service_failure)
                continue
            value, unavailable = self._fetch(accession)
            results[accession] = deepcopy(value)
            if unavailable:
                service_failure = value['reason']
                self._cooldown_reason = service_failure
                self._cooldown_until = time.monotonic() + _TRANSIENT_COOLDOWN_SECONDS
                continue
            self._cache[accession] = value
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return results


def resolve_transcript_genes(accessions, http=None) -> dict[str, dict]:
    """One-call convenience; reuse a resolver instance for per-run caching."""
    with TranscriptIdentityResolver(http=http) as resolver:
        return resolver.resolve(accessions)
