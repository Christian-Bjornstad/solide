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


def intronic_input(**changes):
    fields = dict(gene='PTEN', transcript='NM_000314.8', coding='c.254-1G>A',
        locus='chr10:89692769', ref='G', alt='A', assembly='GRCh37')
    fields.update(changes)
    return Variant(**fields)


def intronic_error(**changes):
    error = dict(code='EINTRONIC', details='mRNA reference does not contain introns.',
        assemblies={'GRCh37': {'NM_000314.8': {'chr_id':'NC_000010.10'}}})
    result = dict(input_description='NM_000314.8:c.254-1G>A', errors=[error])
    result.update(changes)
    return result


def genomic_candidate(**changes):
    result = dict(input_description='NC_000010.10:g.89692769G>A',
        normalized_description='NC_000010.10:g.89692769G>A',
        equivalent_descriptions={'c':[{'description':'NC_000010.10(NM_000314.8):c.254-1G>A'}]})
    result.update(changes)
    return result


def test_intronic_mrna_error_retains_original_and_separate_exact_hg19_candidate():
    http = Mock()
    original = intronic_error()
    candidate = genomic_candidate()
    http.get.side_effect = [response(dict(custom=original), 422), response(candidate)]
    variant = intronic_input(patient='PRIVATE-ID', source_file='private.tsv', comment='private note')
    result = normalize_variant(variant, http=http)
    assert result['normalization'] == original
    assert result['genomic_normalization'] == dict(original='NC_000010.10:g.89692769G>A',
        query_basis='genomic_grch37', normalization=candidate)
    assert not variant.nomenclature_verified and not variant.corrected_hgvs
    assert variant.transcript == 'NM_000314.8' and variant.coding == 'c.254-1G>A'
    assert all(value not in str(http.get.call_args_list) for value in ['PRIVATE-ID','private.tsv','private note'])


@pytest.mark.parametrize('changes', [dict(ref='', alt=''), dict(assembly='Unknown'),
    dict(locus='chr17:89692769'), dict(corrected_hgvs='NM_000314.8:c.254-1G>A'),
    dict(controlled_genomic='chr10-89692769-G-A', nomenclature_verified=True)])
def test_intronic_fallback_never_uses_missing_conflicting_or_superseded_original_alleles(changes):
    http = Mock()
    http.get.return_value = response(dict(custom=intronic_error()), 422)
    result = normalize_variant(intronic_input(**changes), http=http)
    assert result['normalization']['errors']
    assert 'genomic_normalization' not in result
    http.get.assert_called_once()


@pytest.mark.parametrize('errors', [[dict(code='ESEQUENCEMISMATCH')],
    [dict(code='EINTRONIC'),dict(code='ESEQUENCEMISMATCH')]])
def test_other_validation_errors_never_trigger_genomic_fallback(errors):
    http = Mock()
    http.get.return_value = response(dict(custom=intronic_error(errors=errors)), 422)
    result = normalize_variant(intronic_input(), http=http)
    assert 'genomic_normalization' not in result
    http.get.assert_called_once()


@pytest.mark.parametrize('assemblies', [None, [], {'GRCh37':None}, {'GRCh37':[]},
    {'GRCh37':{'NM_000314.8':{'chr_id':'NC_000010.11'}}}])
def test_missing_or_malformed_hg19_transcript_context_keeps_original_error(assemblies):
    http = Mock()
    original = intronic_error(errors=[dict(code='EINTRONIC',assemblies=assemblies)])
    http.get.return_value = response(dict(custom=original), 422)
    result = normalize_variant(intronic_input(), http=http)
    assert result['normalization'] == original
    assert 'genomic_normalization' not in result
    http.get.assert_called_once()


@pytest.mark.parametrize('candidate', [genomic_candidate(errors=[dict(code='ESEQUENCEMISMATCH')]),
    genomic_candidate(normalized_description='NC_000010.11:g.89692769G>A'),
    genomic_candidate(input_description='NC_000010.10:g.1G>A'),
    genomic_candidate(input_description=None),
    genomic_candidate(equivalent_descriptions={'c':[{'description':'NC_000010.10(NM_000314.8):c.254-1G>T'}]}),
    genomic_candidate(equivalent_descriptions=[]), genomic_candidate(equivalent_descriptions={'c':'unavailable'})])
def test_genomic_fallback_failure_or_known_cdna_conflict_cannot_be_offered(candidate):
    http = Mock()
    original = intronic_error()
    http.get.side_effect = [response(dict(custom=original), 422), response(candidate)]
    result = normalize_variant(intronic_input(), http=http)
    assert result['normalization'] == original
    assert 'genomic_normalization' not in result
    assert result['genomic_normalization_issue']


def test_genomic_fallback_network_failure_retains_the_original_review_details():
    http = Mock()
    original = intronic_error()
    http.get.side_effect = [response(dict(custom=original), 422), requests.Timeout('private note')]
    result = normalize_variant(intronic_input(), http=http)
    assert result['normalization'] == original
    assert 'genomic_normalization' not in result
    assert 'Timeout' in result['genomic_normalization_issue']
    assert 'private note' not in str(result)


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
