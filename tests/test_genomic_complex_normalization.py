from copy import deepcopy
import pytest
from solide.nomenclature import normalize_variant,apply_confirmed_normalization
from solide.evidence import query_record
from test_mutalyzer_identity import variant,genomic_http,G


def source():
    return variant(gene='EGFR',coding='c.2235_2250delinsA',protein='p.Old',kind='complex',
        raw={'_columns':['Coding'],'_values':['c.2235_2250delinsA']})


def test_genomically_verified_complex_without_transcript_can_use_checked_genomic_name():
    row=source();raw=deepcopy(row.raw)
    data=normalize_variant(row,http=genomic_http())
    assert data['nomenclature_assessment']['status']=='Unchanged'
    assert apply_confirmed_normalization(row,data)
    assert row.corrected_hgvs==G and row.nomenclature_verified
    assert query_record(row,'MTBP').hgvsc==G
    assert row.coding=='c.2235_2250delinsA' and row.raw==raw
    assert not row.transcript


def test_queue_captures_the_adopted_genomic_name_before_downstream_searches(monkeypatch,tmp_path):
    from unittest.mock import Mock
    import solide.evidence as module
    from solide.models import Session
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    from solide._vendor.archer.core.models import DatabaseEvidence
    row=source();row.patient='00OUM00001';row.selected=True
    data=normalize_variant(row,http=genomic_http());capture=Mock(return_value={});queries=[]
    class Browser:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,records,sources,root,*,progress,checkpoint,prior_evidence=None):
            queries.extend(records)
            checkpoint({self.variant_key(r):[DatabaseEvidence('ClinVar','not_found','No record')] for r in records})
    monkeypatch.setattr(module,'normalize_variant',lambda v:data)
    monkeypatch.setattr(module,'capture_mutalyzer',capture)
    monkeypatch.setattr(module,'BrowserReviewService',Browser)
    module.run_queue(Session(variants=[row]),['Mutalyzer','ClinVar'],tmp_path,module.QueueControl(),lambda *args:None,lambda text:None)
    capture.assert_called_once()
    assert row.evidence['Mutalyzer']['status']=='verified'
    assert len(queries)==1 and queries[0].hgvsc==G


@pytest.mark.parametrize('issue',['simple','unconfirmed','wrong_basis','missing_event','stale_allele'])
def test_genomic_adoption_does_not_bypass_existing_normalization_guards(issue):
    row=source();data=normalize_variant(row,http=genomic_http())
    if issue=='simple':row.kind='DEL';row.coding='c.2235_2249del'
    if issue=='unconfirmed':data['nomenclature_assessment']['identity_confirmed']=False
    if issue=='wrong_basis':data['query_basis']='full_hgvs'
    if issue=='missing_event':data['genomic_identity_check'].clear()
    if issue=='stale_allele':row.alt='T'
    assert not apply_confirmed_normalization(row,data)
