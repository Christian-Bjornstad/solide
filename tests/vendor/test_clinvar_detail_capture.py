from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from solide._vendor.archer.core.models import DatabaseEvidence, VariantRecord
from solide._vendor.archer.services import browser_review
from solide.report_language import capture_caption


@pytest.mark.parametrize('initially_visible', [True, False])
def test_clinvar_capture_opens_details_and_retains_api_classification(tmp_path, monkeypatch, initially_visible):
    visible=[initially_visible];clicks=[]
    class Locator:
        def __init__(self,selector):self.selector=selector
        def is_visible(self):return visible[0]
        def inner_text(self,**kwargs):return 'ClinVar result'
        def wait_for(self,**kwargs):
            if self.selector=='#variant-details-table':assert visible[0]
        def click(self):
            assert self.selector=='#new-variant-details .new-icon-down'
            visible[0]=True;clicks.append(self.selector)
    page=SimpleNamespace(url='https://www.ncbi.nlm.nih.gov/clinvar/variation/1/',locator=Locator)
    record=VariantRecord(Path('synthetic.tsv'),1,'SOURCE','TP53','NM_000546.6:c.524G>A')
    api=DatabaseEvidence('ClinVar','found','Source aggregate',accession='VCV000000001.1',
        clinical_significance='Benign',raw={'classifications':{'germline':'Benign'},'assembly_verified':'GRCh37'})
    original=deepcopy(api)
    service=browser_review.BrowserReviewService(profile_root=tmp_path)
    def wait_for_result(_):
        # Record readiness reads visible identifiers/location inside Details.
        assert visible[0]
    monkeypatch.setattr(service,'_wait_for_clinvar_result',wait_for_result)
    monkeypatch.setattr(browser_review,'capture_source_panel',lambda *args,**kwargs:
        {'text':'Germline Benign','details_text':'Identifiers Variation ID: 1 Location Timeline in ClinVar HGVS'})
    result=service._capture_clinvar_result(record,api,page,tmp_path)
    assert len(clicks)==int(not initially_visible)
    assert api==original and result.clinical_significance=='Benign'
    assert result.raw['classifications']==api.raw['classifications']
    assert 'HGVS' in result.raw['variant_details']
    assert result.raw['clinvar_capture']['panels']==['classification_summary','variant_details']
    assert len(result.raw['screenshots'])==1
    assert capture_caption(result.raw['screenshots'][0]['label'])=='Klassifikasjon og variantdetaljer'


def test_clinvar_browser_verification_is_not_no_hit_or_a_layout_error(tmp_path):
    from solide._vendor.archer.services.provider_failures import ProviderLookupError
    service=browser_review.BrowserReviewService(profile_root=tmp_path)
    page=SimpleNamespace(locator=lambda _:SimpleNamespace(inner_text=lambda **_:
        'Checking your browser before accessing www.ncbi.nlm.nih.gov ...'))
    with pytest.raises(ProviderLookupError) as exc:
        service._capture_clinvar_result(None,None,page,tmp_path)
    assert exc.value.kind.value=='verification_required'
    assert exc.value.diagnostics['capture_issue']=='browser_verification'
