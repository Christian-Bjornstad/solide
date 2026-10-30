from dataclasses import replace
from pathlib import Path

import pytest

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import (
    BrowserReviewService, _mtbp_row_genomic_state, _mtbp_screenshot_row_matches,
    parse_mtbp_report,
)


def variant():
    return VariantRecord(Path('synthetic.tsv'), 1, 'SYNTHETIC', 'KIT',
        'NC_000004.11:g.55593599_55593614delinsG',
        genomic_location='chr4:55593599', ref_allele='ACAGTGGAAGGTTGTT', alt_allele='G')


REPORTED = 'chr4:55593598 TACAGTGGAAGGTTGTT/TG (GRCh37/hg19)'


def test_report_vcf_padding_is_trimmed_before_exact_dna_comparison():
    v = variant()
    assert _mtbp_row_genomic_state(REPORTED, v) is True
    assert _mtbp_screenshot_row_matches('KIT p.Gln556_Val560del ' + REPORTED, v)


@pytest.mark.parametrize('reported', [
    REPORTED.replace('GRCh37/hg19', 'GRCh38/hg38'),
    REPORTED.replace('GRCh37/hg19', 'GRCh37/hg38'),
    REPORTED.replace('GRCh37/hg19', 'GRCh38/hg19'),
    REPORTED.replace('chr4:', 'chr5:'),
    REPORTED.replace('55593598', '55593599'),
    REPORTED.replace('/TG', '/TA'),
    REPORTED.replace('TACAG', 'TATAG'),
])
def test_explicit_reported_dna_conflicts_cannot_be_overridden_by_protein(reported):
    v = replace(variant(), hgvsp='p.Gln556_Val560del')
    assert _mtbp_row_genomic_state(reported, v) is False
    assert not _mtbp_screenshot_row_matches('KIT p.Gln556_Val560del ' + reported, v)


def test_unlabelled_assembly_cannot_verify_genomic_variant():
    assert _mtbp_row_genomic_state(REPORTED.replace(' (GRCh37/hg19)', ''), variant()) is None


def test_two_kit_rows_match_only_the_exact_genomic_event():
    v = variant()
    rows = [dict(gene='KIT', identity_text=identity, alteration=protein,
                 section='Reported variants') for identity, protein in [
        (REPORTED, 'p.Gln556_Val560del'),
        ('chr4:55593602 GTGGAAGGTTGTT/G (GRCh37/hg19)', 'p.Trp557_Val560del'),
    ]]
    evidence = parse_mtbp_report('', rows, [v], 'synthetic', cancer_type='Blood')[BrowserReviewService.variant_key(v)]
    assert evidence.status == 'found'
    assert evidence.raw['match_basis'] == 'genomic_grch37'
    assert evidence.raw['alteration'] == 'p.Gln556_Val560del'


def test_genomic_only_complex_does_not_fall_back_to_a_gene_without_dna():
    v = variant()
    evidence = parse_mtbp_report('', [dict(gene='KIT', alteration='Mutation')],
        [v], 'synthetic', cancer_type='Blood', complete_submission=True)[BrowserReviewService.variant_key(v)]
    assert evidence.status == 'manual_review'


def test_exact_genomic_hgvs_is_labelled_as_genomic_matching():
    v = variant()
    evidence = parse_mtbp_report('', [dict(gene='KIT', identity_text='chr4:g.55593599_55593614delinsG (GRCh37)')],
        [v], 'synthetic', cancer_type='Blood')[BrowserReviewService.variant_key(v)]
    assert evidence.status == 'found'
    assert evidence.raw['match_basis'] == 'genomic_grch37'
