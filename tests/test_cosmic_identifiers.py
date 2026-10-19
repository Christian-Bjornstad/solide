import pytest
from solide.models import Variant
from solide.evidence import query_record

@pytest.mark.parametrize('value,expected',[
    ('COSM476','COSM476'),('cosm476','COSM476'),('COSV56056643','COSV56056643'),
    ('catalog: COSM476, cosv56056643','COSM476,COSV56056643'),
])
def test_supported_cosmic_identifiers_are_not_lost_before_browser_search(value,expected):
    v=Variant(gene='BRAF',assembly='GRCh37',variant_id=value)
    assert query_record(v,'COSMIC').cosmic_id==expected
