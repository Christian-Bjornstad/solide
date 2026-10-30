from dataclasses import replace
from pathlib import Path

import pytest

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import parse_oncokb_page


def nf1():
    return VariantRecord(Path('synthetic.tsv'),1,'SOURCE','NF1',
        'NM_001042492.3:c.6147+2T>A',transcript='NM_001042492.3',
        genomic_location='chr17:29663493',ref_allele='T',alt_allele='A')


URL='https://www.oncokb.org/hgvsg/17:g.29663493T%3EA?refGenome=GRCh37'
BODY=('GRCh37\n17:g.29663493T>A\nNF1\nX2028_splice\nSomatic\n'
      'Variant Overview\nThe NF1 X2028_splice variant.\nMutation Effect\n'
      'Oncogenicity\nLikely Oncogenic\nBiological Effect\nLikely Loss-of-function\nHighest Level of Evidence')


@pytest.mark.parametrize('coding',['NM_001042492.3:c.6147+2T>A',
    'NC_000017.10(NM_001042492.3):c.6147+2T>A','NC_000017.10:g.29663493T>A'])
def test_returned_genomic_identity_allows_oncokb_canonical_splice_label(coding):
    result=parse_oncokb_page(BODY,replace(nf1(),hgvsc=coding),URL)
    assert result.status=='found'
    assert result.clinical_significance=='Likely Oncogenic'
    identity=result.raw['identity_verification']
    assert identity['accepted'] is True and identity['requested']==identity['returned']
    assert result.raw['oncokb_alteration']=='X2028_splice'


@pytest.mark.parametrize('old,new',[
    ('GRCh37','GRCh38'),('29663493T>A','29663493T>G'),('29663493T>A','29663494T>A'),('NF1','TERT')])
def test_requested_route_or_source_name_in_prose_cannot_override_other_returned_allele(old,new):
    result=parse_oncokb_page(BODY.replace(old,new)+'\nNF1 c.6147+2T>A',nf1(),URL)
    assert result.status=='identity_mismatch'
    assert not result.clinical_significance


def test_requested_url_alone_cannot_certify_canonical_splice_alias():
    result=parse_oncokb_page(BODY.replace('GRCh37\n17:g.29663493T>A\n',''),nf1(),URL)
    assert result.status=='identity_mismatch'
