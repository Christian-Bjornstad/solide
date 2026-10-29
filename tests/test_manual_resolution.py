"""Public-reference checks for manually interpreted, synthetic HGVS variants."""
from copy import deepcopy
from urllib.parse import unquote

import pytest
import requests

from solide.annotations import annotation_resolution_current
from solide.models import Variant
from solide.nomenclature import confirmed_protein, genomic_query
from solide.manual_resolution import resolve_manual_variant


TRANSCRIPT = 'NM_000314.8'
REFERENCE = 'NC_000010.10'


def manual(**changes):
    inputs = dict(gene='PTEN', transcript=TRANSCRIPT, coding='c.1A>T',
                  protein='', locus='', parent_ids=['source-a', 'source-b'], created_at='2026-10-29')
    inputs.update(changes)
    return Variant(**{key: inputs[key] for key in ('gene', 'transcript', 'coding', 'protein', 'locus')},
                   assembly='GRCh37', raw={'_manual_variant': inputs})


class Resolver:
    def resolve(self, names):
        return {name: dict(status='resolved', source='NCBI RefSeq', transcript=name,
                           gene='PTEN', protein='NP_000305.3') for name in names}


def response(payload=None, *, text=None, status=200):
    import json
    result = requests.Response()
    result.status_code = status
    result._content = (text if text is not None else json.dumps(payload)).encode()
    return result


class PublicHttp:
    """Fake only the HTTP boundary, keeping real nomenclature validation."""
    def __init__(self, *, start=99, end=100, inserted='T', genomic='g.100A>T', sequence='A'):
        self.start, self.end, self.inserted = start, end, inserted
        self.genomic = REFERENCE + ':' + genomic
        self.sequence = sequence
        self.calls = []
        self.mapping_reference = REFERENCE
        self.mapping_transcript = TRANSCRIPT
        self.mapping_errors = []
        self.model_changes = {}
        self.normalize_changes = {}
        self.intronic = False
        self.fasta_header = None
        self.fail = None

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.fail:
            raise self.fail
        if '/normalize/' in url:
            query = unquote(url.split('/normalize/', 1)[1])
            if ':g.' in query:
                value = dict(input_description=query, normalized_description=self.genomic, normalized_model={})
            else:
                value = dict(input_description=query, normalized_description=query, gene_id='PTEN',
                             normalized_model={}, protein={'description':
                                 TRANSCRIPT + '(NP_000305.3):p.(Met1Leu)'},
                             equivalent_descriptions={'g': [{'description': self.genomic}]})
                if self.intronic and not query.startswith('NC_'):
                    value = dict(input_description=query, errors=[dict(code='EINTRONIC',
                        assemblies={'GRCh37': {TRANSCRIPT: {'chr_id': REFERENCE}}})])
            value.update(self.normalize_changes)
            return response(value)
        if '/map/' in url:
            return response(dict(mapped_description=self.mapping_reference + '(' + self.mapping_transcript + '):c.1A>T',
                                 genomic_description=self.mapping_reference + ':' + self.genomic.split(':')[1],
                                 ref_seq_differences=False, errors=self.mapping_errors))
        if '/delins_model/' in url:
            query = unquote(url.split('/delins_model/', 1)[1])
            event = dict(location={'start': {'position': self.start}, 'end': {'position': self.end}},
                         inserted=[{'sequence': self.inserted}])
            value = dict(input_description=query, delins_model={'reference': {'id': REFERENCE},
                         'coordinate_system': 'i', 'variants': [event]})
            value.update(self.model_changes)
            return response(value)
        if 'efetch.fcgi' in url:
            params = kwargs['params']
            header = self.fasta_header or f'{REFERENCE}:{params["seq_start"]}-{params["seq_stop"]}'
            return response(text='>' + header + ' Homo sapiens chromosome 10\n' + self.sequence + '\n')
        raise AssertionError(url)


def test_snv_without_locus_derives_explicit_alleles_and_same_event_protein():
    variant = manual()
    inputs = deepcopy(variant.raw['_manual_variant'])
    http = PublicHttp()
    assert resolve_manual_variant(variant, Resolver(), http=http)
    assert (variant.locus, variant.ref, variant.alt) == ('chr10:100', 'A', 'T')
    assert variant.transcript == TRANSCRIPT
    assert variant.corrected_hgvs == TRANSCRIPT + ':c.1A>T'
    assert genomic_query(variant) == 'chr10-100-A-T'
    assert variant.nomenclature_verified and annotation_resolution_current(variant)
    assert confirmed_protein(variant) == 'p.(Met1Leu)'
    assert variant.raw['_manual_variant'] == inputs
    proof = variant.raw['_annotation_resolution']
    assert proof['provenance'] == 'manual HGVS mapped to GRCh37'
    assert proof['independent_source_alleles'] is False
    assert variant.af_percent is None and variant.coverage is None
    assert not any('efetch' in url for url, _ in http.calls)


@pytest.mark.parametrize('coding,start,end,inserted,genomic,sequence,expected', [
    ('c.1_2del', 99, 101, '', 'g.100_101del', 'CAT', ('chr10:99', 'CAT', 'C')),
    ('c.1_2insGT', 100, 100, 'GT', 'g.100_101insGT', 'A', ('chr10:100', 'A', 'AGT')),
    ('c.1_2delinsGT', 99, 101, 'GT', 'g.100_101delinsGT', 'AC', ('chr10:100', 'AC', 'GT')),
    ('c.1dup', 100, 100, 'A', 'g.100dup', 'A', ('chr10:100', 'A', 'AA')),
    ('c.1del', 0, 1, '', 'g.1del', 'AC', ('chr10:1', 'AC', 'C')),
    ('c.1_2insGT', 0, 0, 'GT', 'g.0_1insGT', 'A', ('chr10:1', 'A', 'GTA')),
])
def test_indels_fetch_only_bounded_exact_reference(coding, start, end, inserted, genomic, sequence, expected):
    variant = manual(coding=coding)
    http = PublicHttp(start=start, end=end, inserted=inserted, genomic=genomic, sequence=sequence)
    assert resolve_manual_variant(variant, Resolver(), http=http)
    assert (variant.locus, variant.ref, variant.alt) == expected
    requests_made = [kwargs['params'] for url, kwargs in http.calls if 'efetch' in url]
    assert len(requests_made) == 1
    query = requests_made[0]
    assert query['id'] == REFERENCE and query['strand'] == 1
    assert 0 < query['seq_start'] <= query['seq_stop'] <= max(end + 1, 101)


@pytest.mark.parametrize('locus', ['chr10:99', '10:100'])
def test_optional_deletion_locus_accepts_anchor_or_first_changed_base(locus):
    variant = manual(coding='c.1_2del', locus=locus)
    assert resolve_manual_variant(variant, Resolver(), http=PublicHttp(
        end=101, inserted='', genomic='g.100_101del', sequence='CAT'))
    assert variant.locus == 'chr10:99'


def assert_preserved(variant, before):
    proof = variant.raw.pop('_annotation_resolution')
    original = deepcopy(before)
    original.raw.pop('_annotation_resolution', None)
    assert variant == original
    assert proof['status'] == 'unresolved'
    variant.raw['_annotation_resolution'] = proof
    return proof


@pytest.mark.parametrize('changes', [
    {'gene': 'WRONG'}, {'transcript': 'NM_000314'}, {'coding': 'c.[1A>T;2G>C]'},
    {'coding': 'c.(1A>T)'}, {'coding': 'c.1A>?'}, {'coding': 'c.1A>T,c.2G>C'},
    {'locus': 'chr11:100'}, {'locus': 'chr10:101'}, {'locus': 'chr10:0'},
    {'coding': 'NM_000314.9:c.1A>T'}, {'coding': 'NC_000010.11(NM_000314.8):c.1A>T'},
])
def test_invalid_or_conflicting_input_preserves_all_user_fields(changes):
    variant = manual(**changes)
    before = deepcopy(variant)
    assert not resolve_manual_variant(variant, Resolver(), http=PublicHttp())
    assert assert_preserved(variant, before)['reason']


def test_gene_can_be_omitted_and_is_resolved_from_exact_transcript():
    variant = manual(gene='')
    assert resolve_manual_variant(variant, Resolver(), http=PublicHttp())
    assert variant.gene == 'PTEN'


def test_exact_genomic_transcript_context_is_supported():
    variant = manual(coding=REFERENCE + '(' + TRANSCRIPT + '):c.1A>T')
    assert resolve_manual_variant(variant, Resolver(), http=PublicHttp())
    assert variant.corrected_hgvs == REFERENCE + '(' + TRANSCRIPT + '):c.1A>T'


def test_intronic_name_uses_explicit_returned_grch37_context_without_locus():
    variant = manual(coding='c.1+1A>T')
    http = PublicHttp()
    http.intronic = True
    assert resolve_manual_variant(variant, Resolver(), http=http)
    assert variant.corrected_hgvs == REFERENCE + '(' + TRANSCRIPT + '):c.1+1A>T'
    result = variant.raw['_annotation_resolution']['normalization']
    assert result['normalization']['errors'][0]['code'] == 'EINTRONIC'
    assert result['contextual_normalization']['original'] == variant.corrected_hgvs
    assert confirmed_protein(variant) == 'p.(Met1Leu)'


@pytest.mark.parametrize('protein_reference,expected', [
    (REFERENCE + '(NP_000305.3)', 'p.(Met1Leu)'),
    (REFERENCE + '(' + TRANSCRIPT + '(NP_000305.3))', 'p.(Met1Leu)'),
    ('NC_000010.11(NP_000305.3)', ''),
    (REFERENCE + '(NP_000305.4)', ''),
])
def test_genomic_context_protein_keeps_exact_nc_and_np_versions(protein_reference, expected):
    variant = manual(coding=REFERENCE + '(' + TRANSCRIPT + '):c.1A>T')
    http = PublicHttp()
    http.normalize_changes = {'protein': {'description': protein_reference + ':p.(Met1Leu)'}}
    assert resolve_manual_variant(variant, Resolver(), http=http)
    assert variant.protein == expected


def test_nr_transcript_is_mapped_without_inventing_protein():
    transcript = 'NR_163974.1'
    variant = manual(transcript=transcript, coding='n.1A>T')
    http = PublicHttp()
    http.mapping_transcript = transcript
    assert resolve_manual_variant(variant, Resolver(), http=http)
    assert variant.transcript == transcript and variant.coding == 'n.1A>T'
    assert variant.protein == ''


def test_reference_identity_outage_is_retryable_without_normalizer_request():
    class Offline:
        def resolve(self, names):
            return {names[0]: {'status': 'unresolved', 'reason': 'timeout'}}
    variant = manual()
    before = deepcopy(variant)
    http = PublicHttp()
    assert not resolve_manual_variant(variant, Offline(), http=http)
    assert assert_preserved(variant, before)['retryable']
    assert not http.calls


def test_uncertain_internal_coordinates_are_rejected_even_if_positions_are_present():
    variant = manual()
    http = PublicHttp()
    http.model_changes = dict(delins_model={'reference': {'id': REFERENCE}, 'coordinate_system': 'i',
        'variants': [dict(location={'start': {'position': 99, 'uncertain': True},
                                    'end': {'position': 100}}, inserted=[{'sequence': 'T'}])]})
    before = deepcopy(variant)
    assert not resolve_manual_variant(variant, Resolver(), http=http)
    assert_preserved(variant, before)


@pytest.mark.parametrize('field,value', [
    ('mapping_reference', 'NC_000010.11'), ('mapping_transcript', 'NM_000314.9'),
    ('mapping_errors', [{'code': 'ECONFLICT'}]),
    ('normalize_changes', {'input_description': 'NM_000314.9:c.1A>T'}),
    ('normalize_changes', {'gene_id': 'OTHER'}),
    ('normalize_changes', {'errors': [{'code': 'EREFERENCE'}]}),
    ('normalize_changes', {'normalized_model': None}),
    ('model_changes', {'delins_model': {'coordinate_system': 'i', 'reference': {'id': REFERENCE}, 'variants': []}}),
])
def test_api_identity_conflict_never_changes_variant(field, value):
    variant = manual()
    http = PublicHttp()
    setattr(http, field, value)
    before = deepcopy(variant)
    assert not resolve_manual_variant(variant, Resolver(), http=http)
    assert_preserved(variant, before)


@pytest.mark.parametrize('header,sequence', [
    ('NC_000010.11:99-101', 'CAT'), ('NC_000010.10:100-102', 'CAT'),
    ('NC_000010.10:99-101', 'CA'), ('NC_000010.10:99-101', 'CNN'),
    ('NC_000010.10:99-101', 'CAT\n>NC_000010.10:99-101\nCAT'),
])
def test_reference_accession_range_or_sequence_mismatch_is_rejected(header, sequence):
    variant = manual(coding='c.1_2del')
    http = PublicHttp(end=101, inserted='', genomic='g.100_101del', sequence=sequence)
    http.fasta_header = header
    before = deepcopy(variant)
    assert not resolve_manual_variant(variant, Resolver(), http=http)
    assert_preserved(variant, before)


@pytest.mark.parametrize('start,end,inserted', [(99, 10100, ''), (0, 0, 'A' * 10001)])
def test_large_event_is_rejected_before_reference_fetch(start, end, inserted):
    variant = manual(coding='c.1del')
    http = PublicHttp(start=start, end=end, inserted=inserted, genomic='g.100del')
    before = deepcopy(variant)
    assert not resolve_manual_variant(variant, Resolver(), http=http)
    assert_preserved(variant, before)
    assert not any('efetch' in url for url, _ in http.calls)


def test_bounded_ten_kilobase_deletion_avoids_oversized_explicit_ref_url():
    variant = manual(coding='c.1_10000del')
    http = PublicHttp(start=99, end=10099, inserted='', genomic='g.100_10099del', sequence='C' + 'A' * 10000)
    assert resolve_manual_variant(variant, Resolver(), http=http)
    assert variant.ref == 'C' + 'A' * 10000 and variant.alt == 'C'
    assert max(len(url) for url, _ in http.calls) < 5000


def test_reviewed_correction_replaces_derived_locus_without_using_old_coding():
    variant = manual()
    assert resolve_manual_variant(variant, Resolver(), http=PublicHttp())
    variant.corrected_hgvs = TRANSCRIPT + ':c.2A>T'
    assert resolve_manual_variant(variant, Resolver(),
        http=PublicHttp(start=199, end=200, genomic='g.200A>T'))
    assert variant.coding == 'c.2A>T' and variant.locus == 'chr10:200'
    assert variant.raw['_manual_variant']['coding'] == 'c.1A>T'


def test_unreviewed_corrected_hgvs_is_retained_for_user_review():
    variant = manual()
    variant.corrected_hgvs = TRANSCRIPT + ':c.2A>T'
    before = deepcopy(variant)
    assert not resolve_manual_variant(variant, Resolver(), http=PublicHttp())
    assert_preserved(variant, before)


def test_user_entered_locus_remains_constraint_after_reviewed_correction():
    variant = manual(locus='chr10:100')
    assert resolve_manual_variant(variant, Resolver(), http=PublicHttp())
    variant.corrected_hgvs = TRANSCRIPT + ':c.2A>T'
    before = deepcopy(variant)
    assert not resolve_manual_variant(variant, Resolver(),
        http=PublicHttp(start=199, end=200, genomic='g.200A>T'))
    assert_preserved(variant, before)


def test_new_reviewed_genomic_constraint_must_agree_with_mapped_alleles():
    variant = manual()
    assert resolve_manual_variant(variant, Resolver(), http=PublicHttp())
    variant.controlled_genomic = 'chr10-100-A-G'
    before = deepcopy(variant)
    assert not resolve_manual_variant(variant, Resolver(), http=PublicHttp())
    assert_preserved(variant, before)


def test_network_failure_is_retryable_and_keeps_input():
    variant = manual()
    before = deepcopy(variant)
    http = PublicHttp()
    http.fail = requests.Timeout()
    assert not resolve_manual_variant(variant, Resolver(), http=http)
    assert assert_preserved(variant, before)['retryable'] is True


def test_cancellation_after_remote_response_prevents_every_commit():
    class Cancelled(RuntimeError):
        pass
    variant = manual(coding='c.1_2del')
    before = deepcopy(variant)
    http = PublicHttp(end=101, inserted='', genomic='g.100_101del', sequence='CAT')
    def checkpoint():
        if any('efetch' in url for url, _ in http.calls):
            raise Cancelled()
    with pytest.raises(Cancelled):
        resolve_manual_variant(variant, Resolver(), http=http, checkpoint=checkpoint)
    assert variant == before
