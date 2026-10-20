from unittest.mock import Mock
from xml.sax.saxutils import escape

import pytest
import requests

from solide.annotation_identity import TranscriptIdentityResolver, resolve_transcript_genes


def feature(key, **qualifiers):
    values = ''.join(
        '<GBQualifier><GBQualifier_name>' + escape(name) + '</GBQualifier_name>'
        '<GBQualifier_value>' + escape(value) + '</GBQualifier_value></GBQualifier>'
        for name, value in qualifiers.items())
    return ('<GBFeature><GBFeature_key>' + key + '</GBFeature_key>'
            '<GBFeature_quals>' + values + '</GBFeature_quals></GBFeature>')


def record(accession='NM_000314.8', gene='PTEN', *, protein='NP_000305.3',
           gene_feature=True, cds_gene=None, organism='Homo sapiens', extra=''):
    features = feature('source', organism=organism)
    if gene_feature:
        features += feature('gene', gene=gene, db_xref='GeneID:5728')
    if accession.startswith('NM_'):
        fields = dict(gene=gene if cds_gene is None else cds_gene)
        if protein:
            fields['protein_id'] = protein
        features += feature('CDS', **fields)
    return ('<GBSeq><GBSeq_accession-version>' + accession + '</GBSeq_accession-version>'
            '<GBSeq_organism>' + organism + '</GBSeq_organism>'
            '<GBSeq_feature-table>' + features + extra + '</GBSeq_feature-table></GBSeq>')


def response(*records, status=200, text=None):
    result = requests.Response()
    result.status_code = status
    result._content = (text if text is not None else '<GBSet>' + ''.join(records) + '</GBSet>').encode()
    return result


def resolver_for(*responses, **kwargs):
    http = Mock()
    http.get.side_effect = list(responses)
    return TranscriptIdentityResolver(http=http, request_interval=0, **kwargs), http


def test_exact_identity_keeps_gene_and_protein_reference_and_only_sends_accession():
    resolver, http = resolver_for(response(record()))
    value = resolver.resolve(['NM_000314.8'])['NM_000314.8']
    assert value['status'] == 'resolved'
    assert value['transcript'] == 'NM_000314.8'
    assert value['gene'] == 'PTEN'
    assert value['protein'] == 'NP_000305.3'
    assert value['gene_id'] == '5728'
    http.get.assert_called_once_with('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
        params={'db': 'nuccore', 'id': 'NM_000314.8', 'rettype': 'gb', 'retmode': 'xml', 'tool': 'solide'},
        timeout=15, allow_redirects=False)


def test_nr_reference_has_no_invented_coding_protein():
    resolver, _ = resolver_for(response(record('NR_163974.1', 'LOC115308161')))
    value = resolver.resolve(['NR_163974.1'])['NR_163974.1']
    assert value['gene'] == 'LOC115308161'
    assert value['protein'] == ''


@pytest.mark.parametrize('xml, reason', [
    (record('NM_000314.9'), 'reference_mismatch'),
    (record(cds_gene='PTENP1'), 'conflicting_gene'),
    (record(gene_feature=False), 'missing_gene'),
    (record(gene='PTEN,PTENP1'), 'invalid_gene'),
    (record(organism='Mus musculus'), 'nonhuman_reference'),
    (record(extra=feature('gene', gene='PTENP1')), 'conflicting_gene'),
    (record(protein='NP_000305'), 'invalid_protein_reference'),
    (record(extra=feature('CDS', gene='PTEN', protein_id='NP_000305.4')), 'conflicting_protein'),
    (record(extra=feature('gene', gene='PTEN', db_xref='GeneID:9999')), 'conflicting_gene_id'),
    (record() + record(), 'duplicate_reference'),
    ('', 'missing_reference'),
])
def test_uncertain_reference_identity_fails_closed(xml, reason):
    resolver, _ = resolver_for(response(text='<GBSet>' + xml + '</GBSet>'))
    value = resolver.resolve(['NM_000314.8'])['NM_000314.8']
    assert value['status'] == 'unresolved'
    assert value['reason'] == reason
    assert not value.get('gene') and not value.get('protein')


def test_alias_is_never_used_as_equivalence_for_conflicting_gene():
    extra = feature('gene', gene='PTENP1', gene_synonym='PTEN')
    resolver, _ = resolver_for(response(record(extra=extra)))
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['reason'] == 'conflicting_gene'


def test_noncoding_record_with_cds_is_not_accepted():
    xml = record('NR_126420.1', 'TET2-AS1', extra=feature('CDS', gene='TET2-AS1'))
    resolver, _ = resolver_for(response(xml))
    assert resolver.resolve(['NR_126420.1'])['NR_126420.1']['reason'] == 'noncoding_cds_conflict'


def test_missing_cds_gene_does_not_invent_protein_association():
    xml = record().replace(feature('CDS', gene='PTEN', protein_id='NP_000305.3'),
                      feature('CDS', protein_id='NP_000305.3'))
    resolver, _ = resolver_for(response(xml))
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['reason'] == 'missing_cds_gene'


def test_standard_ncbi_external_doctype_does_not_trigger_external_network():
    xml = ('<?xml version="1.0"?><!DOCTYPE GBSet PUBLIC "-//NCBI//NCBI GBSeq/EN" '
           '"https://www.ncbi.nlm.nih.gov/dtd/NCBI_GBSeq.dtd"><GBSet>' + record() + '</GBSet>')
    resolver, http = resolver_for(response(text=xml))
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['gene'] == 'PTEN'
    assert http.get.call_count == 1


def test_closed_resolver_never_fetches():
    resolver, http = resolver_for()
    resolver.close()
    with pytest.raises(RuntimeError, match='closed'):
        resolver.resolve(['NM_000314.8'])
    http.get.assert_not_called()


@pytest.mark.parametrize('accession', ['NM_000314', 'nm_000314.8', 'NC_000010.10',
    'NP_000305.3', 'NM_000314.8:private note', 'NM_000314.8,NM_001126049.2', '', 'OUM00001'])
def test_invalid_or_unversioned_accessions_never_reach_network(accession):
    resolver, http = resolver_for()
    assert resolver.resolve([accession])[accession]['reason'] == 'invalid_accession'
    http.get.assert_not_called()


def test_duplicate_input_is_looked_up_once_and_cache_returns_independent_values():
    resolver, http = resolver_for(response(record()))
    first = resolver.resolve(['NM_000314.8', 'NM_000314.8'])
    first['NM_000314.8']['gene'] = 'WRONG'
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['gene'] == 'PTEN'
    assert http.get.call_count == 1


def test_cache_evicts_least_recent_reference_and_never_closes_injected_http():
    resolver, http = resolver_for(response(record()), response(record('NR_126420.1', 'TET2-AS1')),
        response(record()), cache_size=1)
    resolver.resolve(['NM_000314.8'])
    resolver.resolve(['NR_126420.1'])
    resolver.resolve(['NM_000314.8'])
    resolver.close()
    assert http.get.call_count == 3
    http.close.assert_not_called()


@pytest.mark.parametrize('status, reason', [(429, 'rate_limited'), (500, 'http_error'),
    (302, 'http_error'), (403, 'http_error')])
def test_service_failure_stops_further_requests_until_cooldown_expires(status, reason, monkeypatch):
    now = [100.0]
    monkeypatch.setattr('solide.annotation_identity.time.monotonic', lambda: now[0])
    resolver, http = resolver_for(response(status=status), response(record()))
    result = resolver.resolve(['NM_000314.8', 'NR_126420.1'])
    assert all(value['reason'] == reason for value in result.values())
    assert http.get.call_count == 1
    assert resolver.resolve(['NR_039676.1'])['NR_039676.1']['reason'] == reason
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['reason'] == reason
    assert http.get.call_count == 1
    now[0] += 30
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['gene'] == 'PTEN'
    assert http.get.call_count == 2


@pytest.mark.parametrize('error, reason', [(requests.Timeout(), 'timeout'),
    (requests.ConnectionError('PRIVATE'), 'network_error')])
def test_network_failure_cooldown_covers_separate_resolve_calls(error, reason, monkeypatch):
    now = [100.0]
    monkeypatch.setattr('solide.annotation_identity.time.monotonic', lambda: now[0])
    resolver, http = resolver_for(error, response(record()))
    assert resolver.resolve(['NR_126420.1'])['NR_126420.1']['reason'] == reason
    now[0] += 29
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['reason'] == reason
    assert http.get.call_count == 1
    now[0] += 1
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['gene'] == 'PTEN'
    assert http.get.call_count == 2


def test_cached_success_remains_usable_while_provider_is_cooling_down():
    resolver, http = resolver_for(response(record()), response(status=429))
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['gene'] == 'PTEN'
    assert resolver.resolve(['NR_126420.1'])['NR_126420.1']['reason'] == 'rate_limited'
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['gene'] == 'PTEN'
    assert resolver.resolve(['NR_039676.1'])['NR_039676.1']['reason'] == 'rate_limited'
    assert http.get.call_count == 2


@pytest.mark.parametrize('status', [400, 404, 410, 422])
def test_reference_specific_http_rejection_does_not_block_other_references(status):
    resolver, http = resolver_for(response(status=status), response(record()))
    result = resolver.resolve(['NR_126420.1', 'NM_000314.8'])
    assert result['NR_126420.1']['reason'] == 'http_error'
    assert result['NM_000314.8']['gene'] == 'PTEN'
    assert resolver.resolve(['NR_126420.1'])['NR_126420.1']['reason'] == 'http_error'
    assert http.get.call_count == 2


def test_malformed_reference_response_does_not_poison_provider_for_other_accessions():
    resolver, http = resolver_for(response(text='<broken>'), response(record()))
    assert resolver.resolve(['NR_126420.1'])['NR_126420.1']['reason'] == 'invalid_xml'
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['gene'] == 'PTEN'
    assert http.get.call_count == 2


@pytest.mark.parametrize('error, reason', [(requests.Timeout(), 'timeout'),
    (requests.ConnectionError('PRIVATE'), 'network_error')])
def test_network_failures_are_explicit_and_never_echo_exception_details(error, reason):
    resolver, _ = resolver_for(error)
    value = resolver.resolve(['NM_000314.8'])['NM_000314.8']
    assert value['reason'] == reason
    assert 'PRIVATE' not in str(value)


def test_cancel_checkpoint_exception_is_propagated_and_prevents_fetch():
    checkpoint = Mock(side_effect=InterruptedError('cancel'))
    resolver, http = resolver_for(response(record()), checkpoint=checkpoint)
    with pytest.raises(InterruptedError):
        resolver.resolve(['NM_000314.8'])
    http.get.assert_not_called()


def test_candidate_cap_is_checked_before_any_network_or_unbounded_materialization():
    resolver, http = resolver_for()
    with pytest.raises(ValueError, match='64'):
        resolver.resolve((f'NM_{index:06}.1' for index in range(65)))
    http.get.assert_not_called()


@pytest.mark.parametrize('body', ['<broken>', '<!DOCTYPE GBSet [<!ENTITY x "data">]><GBSet/>',
    '<GBSet>' + 'x' * (2 * 1024 * 1024) + '</GBSet>'], ids=['malformed', 'entity', 'oversized'])
def test_malformed_or_oversized_payload_cannot_produce_identity(body):
    resolver, _ = resolver_for(response(text=body))
    assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['status'] == 'unresolved'


def test_owned_session_is_closed_by_context_manager_and_created_lazily(monkeypatch):
    http = Mock()
    http.get.return_value = response(record())
    factory = Mock(return_value=http)
    monkeypatch.setattr('solide.annotation_identity.system_trust_session', factory)
    with TranscriptIdentityResolver(request_interval=0) as resolver:
        factory.assert_not_called()
        resolver.resolve(['NM_000314.8'])
    factory.assert_called_once_with()
    http.close.assert_called_once_with()


def test_convenience_api_accepts_fake_http_without_mutating_it():
    http = Mock()
    http.get.return_value = response(record())
    assert resolve_transcript_genes(['NM_000314.8'], http=http)['NM_000314.8']['gene'] == 'PTEN'
    http.close.assert_not_called()
