from unittest.mock import Mock

import pytest
import requests

from solide.models import Variant
from solide.nomenclature import normalize_variant, spliceai_summary, spliceai_variant


def response(payload, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(response=result)
    return result


def splice_payload(**changes):
    result = dict(variant='chr17-7577609-C-T', hg='37', genomeVersion='37',
        chrom='17', pos=7577609, ref='C', alt='T', distance=500, mask=1,
        scores=[dict(g_name='TP53', t_id='ENST00000269305.9_11',
            t_refseq_ids=['NM_000546.6'], t_priority='MS',
            DS_AG='0.000', DS_AL='0.999', DS_DG='0.000', DS_DL='0.001',
            DP_AG=0, DP_AL=0, DP_DG=12, DP_DL=-3)])
    result.update(changes)
    return result


def splice_input(**changes):
    fields = dict(gene='TP53', locus='chr17:7577609', ref='C', alt='T', assembly='GRCh37')
    fields.update(changes)
    return Variant(**fields)


def test_mutalyzer_explicit_genomic_input_can_normalize_without_a_transcript():
    http = Mock()
    http.get.return_value = response(dict(input_description='NC_000017.10:g.7577539G>A',
        normalized_description='NC_000017.10:g.7577539G>A'))
    variant = Variant(gene='TP53', locus='chr17:7577539', ref='G', alt='A', assembly='GRCh37')
    result = normalize_variant(variant, http=http)
    assert result['original'] == 'NC_000017.10:g.7577539G>A'
    assert result['query_basis'] == 'genomic_grch37'
    assert result['normalization']['normalized_description'] == result['original']


def test_mutalyzer_genomic_deletion_removes_vcf_anchor_without_shifting_a_repeat():
    http = Mock()
    http.get.return_value = response(dict(normalized_description='NC_000007.13:g.55242465_55242479del'))
    result = normalize_variant(Variant(gene='EGFR', locus='chr7:55242464',
        ref='AGGAATTAAGAGAAGC', alt='A', assembly='GRCh37'), http=http)
    assert result['original'] == 'NC_000007.13:g.55242465_55242479del'


@pytest.mark.parametrize('changes', [dict(assembly='Unknown'), dict(ref='', alt=''),
    dict(locus='chr0:1'), dict(locus='chr23:1'), dict(locus='chr17:0'), dict(ref='C', alt='C')])
def test_mutalyzer_does_not_guess_missing_or_invalid_genomic_identity(changes):
    http = Mock()
    with pytest.raises(ValueError):
        normalize_variant(splice_input(**changes), http=http)
    http.get.assert_not_called()


def test_mane_mapping_failure_retains_valid_normalization_and_source_reason():
    http = Mock()
    normalized = dict(normalized_description='NM_001174067.1:c.1A>G')
    rejection = dict(custom=dict(errors=[dict(code='ELENGTHSDIFFERENCE', details='Limit exceeded.')]))
    http.get.side_effect = [response(normalized), response(rejection, 422)]
    result = normalize_variant(Variant(gene='FGFR1', transcript='NM_001174067.1',
        coding='c.1A>G', assembly='GRCh37'), http=http)
    assert result['normalization'] == normalized
    assert result['mane_target'] == 'NM_023110.3'
    assert 'ELENGTHSDIFFERENCE' in result['mapping_issue']
    assert result['mapping_response'] == rejection
    assert 'mapping' not in result


def test_mane_mapping_timeout_does_not_discard_normalization():
    http = Mock()
    normalized = dict(normalized_description='NM_001127500.3:c.1A>G')
    http.get.side_effect = [response(normalized), requests.Timeout('server timeout')]
    result = normalize_variant(Variant(gene='MET', transcript='NM_001127500.3',
        coding='c.1A>G', assembly='GRCh37'), http=http)
    assert result['normalization'] == normalized
    assert 'mapping' not in result
    assert 'Timeout' in result['mapping_issue']


@pytest.mark.parametrize('payload', [dict(custom=None), dict(custom=['unexpected']),
    dict(mapped_description='NM_000245.3:c.1A>G'), dict(mapped_description={'unexpected':'value'})])
def test_unusable_mapping_response_preserves_normalization_without_a_target_candidate(payload):
    http = Mock()
    normalized = dict(normalized_description='NM_001127500.3:c.1A>G')
    http.get.side_effect = [response(normalized), response(payload)]
    result = normalize_variant(Variant(gene='MET', transcript='NM_001127500.3', coding='c.1A>G'), http=http)
    assert result['normalization'] == normalized
    assert result['mapping_issue'] and 'mapping' not in result


def test_normalization_errors_do_not_trigger_mane_mapping():
    http = Mock()
    http.get.return_value = response(dict(errors=[dict(code='EREFERENCE')]))
    result = normalize_variant(Variant(gene='MET', transcript='NM_001127500.3',
        coding='c.1A>G'), http=http)
    assert result['normalization']['errors']
    http.get.assert_called_once()


def test_mutalyzer_http_422_reference_error_retains_the_actual_validation_reason():
    http = Mock()
    source = dict(input_description='NM_007294.4:c.68T>G', errors=[dict(
        code='ESEQUENCEMISMATCH', details='T was not found; A was found instead.')])
    http.get.return_value = response(dict(custom=source, message='Errors encountered.'), 422)
    result = normalize_variant(Variant(gene='BRCA1', transcript='NM_007294.4', coding='c.68T>G'), http=http)
    assert result['normalization'] == source
    assert result['normalization_http_status'] == 422
    assert 'normalized_description' not in result['normalization']


def test_mutalyzer_http_failure_without_validation_details_remains_a_transport_failure():
    http = Mock()
    http.get.return_value = response(dict(message='Unavailable'), 503)
    with pytest.raises(requests.HTTPError):
        normalize_variant(Variant(transcript='NM_007294.4', coding='c.68_69del'), http=http)


@pytest.mark.parametrize('gene,original,target,mapped', [
    ('FGFR1', 'NM_001174067.1', 'NM_023110.3', 'NM_023110.3:c.1862A>C'),
    ('MET', 'NM_001127500.3', 'NM_000245.4', 'NM_000245.4:c.3682G>A')])
def test_confirmed_mane_mapping_is_a_candidate_and_preserves_source_accession(gene,original,target,mapped):
    http = Mock()
    http.get.side_effect = [response(dict(normalized_description=original+':c.1A>G')),
                           response(dict(mapped_description=mapped))]
    variant = Variant(gene=gene, transcript=original, coding='c.1A>G')
    result = normalize_variant(variant, http=http)
    assert result['mapping']['mapped_description'] == mapped
    assert result['mane_target'] == target
    assert result['original'] == original + ':c.1A>G'
    assert variant.transcript == original and not variant.nomenclature_verified


def test_spliceai_current_api_includes_gene_transcript_and_refseq_in_summary():
    payload = splice_payload()
    summary = spliceai_summary(dict(response=payload))
    assert 'TP53' in summary and 'ENST00000269305.9_11' in summary
    assert 'NM_000546.6' in summary and 'DS_AL=0.999' in summary


def test_spliceai_legacy_identity_fields_remain_readable():
    payload = splice_payload()
    payload['scores'][0] = dict(gene_name='TP53', transcript_id='ENST00000269305', DS_AL='0.999')
    assert 'TP53' in spliceai_summary(dict(response=payload))


@pytest.mark.parametrize('changes', [dict(genomeVersion='38'), dict(hg='38'),
    dict(distance=50), dict(mask=0), dict(ref='G'), dict(pos=7577610),
    dict(scores='unavailable'), dict(scores=[{}]), dict(scores=[dict(DS_AL='nan')])])
def test_spliceai_rejects_mismatched_settings_identity_or_unusable_scores(changes):
    http = Mock()
    http.get.return_value = response(splice_payload(**changes))
    with pytest.raises(ValueError):
        spliceai_variant(splice_input(), http=http)


def test_spliceai_accepts_documented_trimming_and_retains_scored_location():
    http = Mock()
    payload = splice_payload(variant='chr17-7577608-AC-AT')
    http.get.return_value = response(payload)
    result = spliceai_variant(splice_input(locus='chr17:7577608', ref='AC', alt='AT'), http=http)
    assert result['query'] == 'chr17-7577608-AC-AT'
    assert result['scored_variant'] == 'chr17-7577609-C-T'
    assert result['response'] == payload


def test_owned_sessions_close_on_success_and_failure(monkeypatch):
    http = Mock()
    http.get.return_value = response(splice_payload())
    monkeypatch.setattr('solide.nomenclature.system_trust_session', lambda: http)
    spliceai_variant(splice_input())
    http.close.assert_called_once()
    http.reset_mock()
    http.get.side_effect = requests.Timeout()
    with pytest.raises(requests.Timeout):
        spliceai_variant(splice_input())
    http.close.assert_called_once()


def test_source_identifiers_and_comments_are_never_sent():
    http = Mock()
    http.get.return_value = response(splice_payload())
    spliceai_variant(splice_input(patient='PRIVATE-ID', source_file='private.tsv', comment='private note'), http=http)
    request = str(http.get.call_args_list)
    assert all(value not in request for value in ['PRIVATE-ID', 'private.tsv', 'private note'])
