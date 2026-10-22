from pathlib import Path
from dataclasses import replace
from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import _franklin_queries,_mtbp_variant_query


def genomic_complex():
    return VariantRecord(Path('synthetic.tsv'),2,'SYNTHETIC','KIT',
        'NC_000004.11:g.55593599_55593614delinsG',genomic_location='chr4:55593599',
        ref_allele='ACAGTGGAAGGTTGTT',alt_allele='G')


def test_franklin_genomic_name_never_becomes_gene_colon_genomic_position():
    queries=_franklin_queries(genomic_complex())
    assert queries==['chr4-55593599 ACAGTGGAAGGTTGTT>G']


def test_mtbp_genomic_name_uses_explicit_chromosome_from_checked_source():
    assert _mtbp_variant_query(genomic_complex())=='chr4:g.55593599_55593614delinsG'


def test_transcript_cdna_queries_keep_the_existing_versioned_reference():
    row=replace(genomic_complex(),hgvsc='NM_000222.3:c.1674_1676delinsTGG',transcript='NM_000222.3')
    assert _franklin_queries(row)[0]=='KIT:c.1674_1676delinsTGG'
    assert _mtbp_variant_query(row)=='NM_000222.3:c.1674_1676delinsTGG'
