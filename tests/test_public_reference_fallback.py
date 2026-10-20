from copy import deepcopy
from unittest.mock import Mock

import pytest
import requests

from solide.annotation_identity import TranscriptIdentityResolver


def model():
    return {'annotations': {'id': 'NM_000314.8', 'type': 'record', 'qualifiers': {'dbxref': 'taxon:9606'},
        'features': [{'type': 'gene', 'id': 'PTEN', 'qualifiers': {'name': 'PTEN'}, 'features': [
            {'type': 'mRNA', 'id': 'NM_000314.8', 'features': [{'type': 'CDS', 'id': 'NP_000305.3'}]}]}]}}


def setup(payload):
    ncbi = Mock()
    ncbi.get.side_effect = requests.ConnectionError('Synthetic NCBI unavailable')
    fallback = Mock()
    response = Mock(status_code=200, content=b'public reference')
    response.json.return_value = payload
    fallback.get.return_value = response
    return ncbi, fallback


def test_unreachable_ncbi_can_resolve_exact_reference_through_mutalyzer():
    ncbi, fallback = setup(model())
    with TranscriptIdentityResolver(http=ncbi, fallback_http=fallback, request_interval=0) as resolver:
        result = resolver.resolve(['NM_000314.8'])['NM_000314.8']
        assert resolver.resolve(['NM_000314.8'])['NM_000314.8'] == result
    assert result['status'] == 'resolved' and result['gene'] == 'PTEN'
    assert result['transcript'] == 'NM_000314.8' and result['protein'] == 'NP_000305.3'
    assert result['source'] == 'Mutalyzer RefSeq'
    assert fallback.get.call_count == 1
    assert fallback.get.call_args.kwargs['params'] == {'reference_id': 'NM_000314.8'}


@pytest.mark.parametrize('issue', ['version', 'organism', 'gene', 'duplicate_gene', 'transcript', 'cds'])
def test_reference_fallback_rejects_conflicting_or_incomplete_identity(issue):
    data = model()
    root = data['annotations']; gene = root['features'][0]; tx = gene['features'][0]
    if issue == 'version': root['id'] = 'NM_000314.9'
    if issue == 'organism': root['qualifiers']['dbxref'] = 'taxon:10090'
    if issue == 'gene': gene['qualifiers']['name'] = 'PTENP1'
    if issue == 'duplicate_gene': root['features'].append(deepcopy(gene))
    if issue == 'transcript': tx['id'] = 'NM_000314.9'
    if issue == 'cds': tx['features'] = []
    ncbi, fallback = setup(data)
    with TranscriptIdentityResolver(http=ncbi, fallback_http=fallback, request_interval=0) as resolver:
        result = resolver.resolve(['NM_000314.8'])['NM_000314.8']
    assert result['status'] == 'unresolved' and not result.get('gene')


def test_confirmed_ncbi_reference_conflict_never_uses_a_second_opinion():
    ncbi, fallback = setup(model())
    response = requests.Response(); response.status_code = 200
    response._content = b'<GBSet><GBSeq><GBSeq_accession-version>NM_000314.9</GBSeq_accession-version></GBSeq></GBSet>'
    ncbi.get.side_effect = None; ncbi.get.return_value = response
    with TranscriptIdentityResolver(http=ncbi, fallback_http=fallback, request_interval=0) as resolver:
        assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['reason'] == 'reference_mismatch'
    fallback.get.assert_not_called()


def test_ncbi_tls_initialization_failure_can_still_use_the_public_reference_model(monkeypatch):
    import solide.annotation_identity as module
    _,fallback=setup(model())
    monkeypatch.setattr(module,'system_trust_session',Mock(side_effect=OSError('Synthetic unavailable Windows trust store')))
    with TranscriptIdentityResolver(fallback_http=fallback) as resolver:
        assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['gene']=='PTEN'


def test_noncoding_fallback_preserves_the_nr_identity_without_a_protein():
    payload=model();root=payload['annotations'];root['id']='NR_126420.1'
    gene=root['features'][0];gene['id']='TET2-AS1';gene['qualifiers']['name']='TET2-AS1'
    gene['features']=[{'type':'ncRNA','id':'NR_126420.1','features':[]}]
    ncbi,fallback=setup(payload)
    with TranscriptIdentityResolver(http=ncbi,fallback_http=fallback) as resolver:
        result=resolver.resolve(['NR_126420.1'])['NR_126420.1']
    assert result['status']=='resolved' and result['gene']=='TET2-AS1' and result['protein']==''


def test_mixed_organism_reference_is_never_accepted():
    payload=model();payload['annotations']['qualifiers']['dbxref']=['taxon:9606','taxon:10090']
    ncbi,fallback=setup(payload)
    with TranscriptIdentityResolver(http=ncbi,fallback_http=fallback) as resolver:
        assert resolver.resolve(['NM_000314.8'])['NM_000314.8']['status']=='unresolved'
