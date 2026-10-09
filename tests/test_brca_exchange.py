from copy import deepcopy
from unittest.mock import Mock

import pytest
import requests

from solide.brca_exchange import brca_exchange_variant
from solide.models import Variant


def variant(**changes):
    fields = dict(gene='BRCA1', transcript='NM_007294.4', coding='c.68_69del',
                  assembly='GRCh37', locus='chr17:41276044', ref='ACT', alt='A',
                  patient='PRIVATE-PATIENT', source_file='private.xlsx', comment='private note')
    fields.update(changes)
    return Variant(**fields)


def record(**changes):
    fields = dict(id=1396149, Gene_Symbol='BRCA1', Reference_Sequence='NM_007294.4',
                  HGVS_cDNA='NM_007294.4:c.68_69del',
                  Genomic_Coordinate_hg37='chr17:g.41276044:ACT>A',
                  Genomic_HGVS_37='NC_000017.10:g.41276045_41276046del',
                  Pathogenicity_expert='Pathogenic', Clinical_significance_ENIGMA='Pathogenic',
                  Date_last_evaluated_ENIGMA='2024-06-11', Source='ENIGMA,ClinVar',
                  Data_Release_id=76)
    fields.update(changes)
    return fields


def http_for(rows, *, count=None, detail=None):
    search = {'count': len(rows) if count is None else count, 'data': rows, 'releaseName': None}
    if detail is None:
        detail = deepcopy(rows)
        for row in detail:
            row['Data_Release'] = {'id': 76, 'name': 70, 'date': '2026-03-08T06:00:00Z'}
    http = Mock()
    responses = []
    for payload in (search, {'data': detail}):
        response = Mock(status_code=200)
        response.json.return_value = payload
        responses.append(response)
    http.get.side_effect = responses
    return http


def test_exact_genomic_match_uses_verified_api_params_and_retains_release():
    http = http_for([record()])
    result = brca_exchange_variant(variant(), http=http)
    assert result['status'] == 'found'
    assert result['url'] == 'https://brcaexchange.org/variant/1396149'
    assert result['clinical_significance'] == 'Pathogenic'
    assert result['accession'] == '1396149'
    assert result['raw']['release']['name'] == 70
    assert result['raw']['classification']['expert_date'] == '2024-06-11'
    identity = result['raw']['identity_verification']
    assert identity['accepted'] is True
    assert identity['requested'] == identity['returned']
    assert identity['requested']['genomic'] == 'chr17-41276044-ACT-A'
    assert 'ENIGMA' in result['summary'] and 'ClinVar' in result['summary']
    http.get.assert_any_call('https://brcaexchange.org/backend/data/', params={
        'format': 'json', 'include': 'all', 'page_size': 100, 'page_num': 0,
        'filter': ['Gene_Symbol', 'Genomic_Coordinate_hg37'],
        'filterValue': ['BRCA1', 'chr17:g.41276044:ACT>A'],
    }, timeout=45, allow_redirects=False)
    http.get.assert_any_call('https://brcaexchange.org/backend/data/variant/',
                            params={'variant_id': 1396149}, timeout=45, allow_redirects=False)
    assert all(secret not in str(http.get.call_args_list)
               for secret in ('PRIVATE-PATIENT', 'private.xlsx', 'private note'))


@pytest.mark.parametrize('gene', ['TP53', 'BRCA3', '', 'BRCA1,BRCA2'])
def test_non_brca_gene_never_queries(gene):
    http = Mock()
    assert brca_exchange_variant(variant(gene=gene), http=http)['status'] == 'not_applicable'
    http.get.assert_not_called()


def test_brca2_is_supported_with_its_exact_chromosome():
    row = record(Gene_Symbol='BRCA2', HGVS_cDNA='NM_000059.4:c.1A>G',
                 Genomic_Coordinate_hg37='chr13:g.32900001:A>G')
    result = brca_exchange_variant(variant(gene='BRCA2', transcript='NM_000059.4',
        coding='c.1A>G', locus='chr13:32900001', ref='A', alt='G'), http=http_for([row]))
    assert result['status'] == 'found'


@pytest.mark.parametrize('assembly', ['Unknown', 'GRCh38', 'hg19'])
def test_assembly_requires_confirmed_application_grch37(assembly):
    http = Mock()
    assert brca_exchange_variant(variant(assembly=assembly), http=http)['status'] == 'needs_review'
    http.get.assert_not_called()


@pytest.mark.parametrize('changes', [
    {'transcript': '', 'coding': '', 'locus': '', 'ref': '', 'alt': ''},
    {'corrected_hgvs': 'NM_007294.4:c.68_69del', 'nomenclature_verified': False},
    {'locus': 'chr13:41276044'},
    {'corrected_hgvs': 'NC_000017.11:g.43124028_43124029del', 'nomenclature_verified': True},
    {'corrected_hgvs': 'NM_007294.4:c.68_69del private note', 'nomenclature_verified': True},
])
def test_unsafe_or_missing_identity_requires_review_before_request(changes):
    http = Mock()
    assert brca_exchange_variant(variant(**changes), http=http)['status'] == 'needs_review'
    http.get.assert_not_called()


def test_corrected_hgvs_discards_unreviewed_original_genomic_alleles():
    http = http_for([record()])
    result = brca_exchange_variant(variant(corrected_hgvs='NM_007294.4:c.68_69del',
        nomenclature_verified=True, locus='chr17:1', ref='A', alt='T'), http=http)
    assert result['status'] == 'found'
    assert result['raw']['query_basis'] == 'full_hgvs'
    assert 'matched_location' not in result['raw']
    assert http.get.call_args_list[0].kwargs['params'] == {
        'format': 'json', 'include': 'all', 'page_size': 100, 'page_num': 0,
        'filter': ['Gene_Symbol'], 'filterValue': ['BRCA1'],
        'search_term': 'NM_007294.4:c.68_69del',
    }


def test_reviewed_genomic_identity_can_use_other_transcript_without_accession_swap():
    row = record(HGVS_cDNA='NM_007298.4:c.68_69del', Reference_Sequence='NM_007298.4')
    result = brca_exchange_variant(variant(corrected_hgvs='NM_007294.4:c.68_69del',
        nomenclature_verified=True, controlled_genomic='chr17-41276044-ACT-A'), http=http_for([row]))
    assert result['status'] == 'found'
    assert result['raw']['query_basis'] == 'genomic_grch37'


def test_hgvs_accession_version_mismatch_is_not_equivalence():
    row = record(HGVS_cDNA='NM_007294.3:c.68_69del', Reference_Sequence='NM_007294.3')
    http = http_for([row])
    result = brca_exchange_variant(variant(locus='', ref='', alt=''), http=http)
    assert result['status'] == 'identity_mismatch'
    assert result['raw']['identity_verification']['accepted'] is False
    assert result['clinical_significance'] == ''
    assert http.get.call_count == 1


def test_same_accession_different_coding_with_matching_coordinate_is_a_conflict():
    row = record(HGVS_cDNA='NM_007294.4:c.100A>T')
    result = brca_exchange_variant(variant(), http=http_for([row]))
    assert result['status'] == 'identity_mismatch'


def test_hg38_or_raw_vcf_fields_cannot_establish_grch37_match():
    row = record(Genomic_Coordinate_hg37='chr17:g.1:ACT>A',
                 Genomic_Coordinate_hg38='chr17:g.41276044:ACT>A',
                 Chr='17', Pos='41276044', Ref='ACT', Alt='A')
    result = brca_exchange_variant(variant(), http=http_for([row]))
    assert result['status'] == 'identity_mismatch'


def test_exact_candidate_is_selected_by_identity_not_first_search_result():
    wrong = record(id=1, Genomic_Coordinate_hg37='chr17:g.1:ACT>A')
    result = brca_exchange_variant(variant(), http=http_for([wrong, record()]))
    assert result['status'] == 'found'
    assert result['accession'] == '1396149'


def test_duplicate_exact_candidates_require_review_and_hide_classification():
    http = http_for([record(), record(id=2)])
    result = brca_exchange_variant(variant(), http=http)
    assert result['status'] == 'needs_review'
    assert result['clinical_significance'] == ''
    http.get.assert_called_once()


def test_incomplete_result_page_cannot_be_accepted():
    result = brca_exchange_variant(variant(), http=http_for([record()], count=101))
    assert result['status'] == 'needs_review'


def test_zero_results_are_not_found_with_request_basis_retained():
    result = brca_exchange_variant(variant(), http=http_for([]))
    assert result['status'] == 'not_found'
    assert result['raw']['request']['params']['filterValue'][0] == 'BRCA1'


def test_missing_result_identity_requires_review():
    row = record()
    del row['Genomic_Coordinate_hg37']
    result = brca_exchange_variant(variant(), http=http_for([row]))
    assert result['status'] == 'needs_review'


def test_unverifiable_candidate_alongside_exact_candidate_is_not_unambiguous():
    unknown = record(id=2)
    del unknown['Genomic_Coordinate_hg37']
    result = brca_exchange_variant(variant(), http=http_for([record(), unknown]))
    assert result['status'] == 'needs_review'
    assert result['clinical_significance'] == ''


def test_detail_response_must_reconfirm_selected_version_and_identity():
    result = brca_exchange_variant(variant(), http=http_for([record()],
        detail=[record(Genomic_Coordinate_hg37='chr17:g.1:ACT>A')]))
    assert result['status'] == 'identity_mismatch'
    assert result['clinical_significance'] == ''


def test_detail_history_matches_exact_selected_id():
    newer = record(id=2, Pathogenicity_expert='Benign')
    selected = record(Data_Release={'id': 76, 'name': 70})
    result = brca_exchange_variant(variant(), http=http_for([record()], detail=[newer, selected]))
    assert result['status'] == 'found'
    assert result['clinical_significance'] == 'Pathogenic'


def test_not_yet_reviewed_is_not_replaced_by_clinvar_interpretation():
    row = record(Pathogenicity_expert='Not Yet Reviewed', Clinical_significance_ENIGMA='-',
                 Clinical_Significance_ClinVar='Uncertain_significance')
    result = brca_exchange_variant(variant(), http=http_for([row]))
    assert result['status'] == 'found'
    assert result['clinical_significance'] == 'Not Yet Reviewed'
    assert 'Uncertain_significance' not in result['summary']


@pytest.mark.parametrize('failure', [requests.Timeout('PRIVATE-PATIENT'),
    requests.ConnectionError('private.xlsx'), ValueError('private note')])
def test_network_and_json_errors_are_masked(failure):
    http = Mock()
    http.get.side_effect = failure
    result = brca_exchange_variant(variant(), http=http)
    assert result['status'] == 'error'
    assert all(secret not in str(result) for secret in ('PRIVATE-PATIENT', 'private.xlsx', 'private note'))


def test_unexpected_payload_shape_is_error_instead_of_not_found():
    http = http_for([])
    response = Mock(status_code=200)
    response.json.return_value = {'results': []}
    http.get.side_effect = [response]
    assert brca_exchange_variant(variant(), http=http)['status'] == 'error'


def test_redirect_is_not_followed_or_reported_as_absent():
    response = Mock(status_code=302)
    http = Mock()
    http.get.return_value = response
    result = brca_exchange_variant(variant(), http=http)
    assert result['status'] == 'error'
    response.json.assert_not_called()


def test_owned_session_uses_system_trust_and_is_closed(monkeypatch):
    http = http_for([record()])
    monkeypatch.setattr('solide.brca_exchange.system_trust_session', lambda: http)
    assert brca_exchange_variant(variant())['status'] == 'found'
    http.close.assert_called_once()


def test_session_initialization_failure_is_masked(monkeypatch):
    def fail():
        raise requests.RequestException('PRIVATE-PATIENT')
    monkeypatch.setattr('solide.brca_exchange.system_trust_session', fail)
    result = brca_exchange_variant(variant())
    assert result['status'] == 'error'
    assert 'PRIVATE-PATIENT' not in str(result)
