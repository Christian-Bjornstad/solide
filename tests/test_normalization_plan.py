from copy import deepcopy

import pytest

from solide.models import Analysis,Session,Variant
from solide.evidence import build_search_plan,batch_fingerprint,evidence_is_current
from test_automatic_nomenclature import variant,checked_result


def completed(v,source,session):
    result={'database':source,'status':'not_found','fingerprint':v.fingerprint('Other'),
        'analysis_id':v.analysis_id,'summary':'Previous completed search','raw':{}}
    if source=='MTBP':result['mtbp_batch']=batch_fingerprint(session,v.patient,v.analysis_id)
    return result


def fake_sources(monkeypatch):
    import solide.evidence as module
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    calls=[]
    class Service:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,rows,sources,root,progress,checkpoint):
            calls.append((sources[0],[(row.symbol,row.hgvsc) for row in rows]))
            checkpoint({self.variant_key(row):[DatabaseEvidence(sources[0],'not_found','Updated checked search')] for row in rows})
    monkeypatch.setattr(module,'BrowserReviewService',Service)
    monkeypatch.setattr(module,'normalize_variant',lambda row:checked_result())
    monkeypatch.setattr(module,'capture_mutalyzer',lambda *args,**kwargs:{})
    return module,calls


@pytest.mark.parametrize('expand',[True,False])
def test_normalized_name_refreshes_completed_requested_sources_except_chosen_mode(monkeypatch,tmp_path,expand):
    module,calls=fake_sources(monkeypatch)
    v=variant(); unselected=deepcopy(v);unselected.id='unselected';unselected.selected=False
    other=Variant(patient='26OUM00001',gene='BRAF',transcript='NM_004333.6',coding='c.1799T>A',
        assembly='GRCh37',selected=True)
    session=Session(variants=[v,unselected,other])
    for row in session.variants:
        for source in ('ClinVar','Franklin'):row.evidence[source]=completed(row,source,session)
    before_other=deepcopy(other.evidence);before_unselected=deepcopy(unselected.evidence)
    sources=['Mutalyzer','ClinVar'];plan={(v.id,'Mutalyzer')};changes=[]
    module.run_queue(session,sources,tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,
        plan=plan,plan_changed=changes.append,expand_after_normalization=expand)
    assert v.corrected_hgvs=='NM_005228.5:c.2235_2249del'
    if expand:
        assert calls==[('ClinVar',[('EGFR',v.corrected_hgvs)])]
        assert changes==[{(v.id,'Mutalyzer'),(v.id,'ClinVar')}]
        assert evidence_is_current(v,v.evidence['ClinVar'],'Other',session)
    else:
        assert not calls and not changes
        assert not evidence_is_current(v,v.evidence['ClinVar'],'Other',session)
    assert v.evidence['Franklin']['summary']=='Previous completed search'
    assert unselected.evidence==before_unselected and other.evidence==before_other
    assert plan=={(v.id,'Mutalyzer')}


def test_changed_normalization_refreshes_only_selected_mtbp_rows_in_same_analysis(monkeypatch,tmp_path):
    module,calls=fake_sources(monkeypatch)
    a=Analysis(id='a',patient='26OUM00000',profile='OPA')
    b=Analysis(id='b',patient=a.patient,profile='Ion Torrent')
    v=variant();v.analysis_id=a.id
    companion=Variant(analysis_id=a.id,patient=a.patient,gene='TP53',transcript='NM_000546.6',
        coding='c.818G>A',assembly='GRCh37',selected=True)
    unselected=deepcopy(companion);unselected.id='unselected';unselected.selected=False
    other_analysis=deepcopy(companion);other_analysis.id='other-analysis';other_analysis.analysis_id=b.id
    session=Session(analyses=[a,b],variants=[v,companion,unselected,other_analysis])
    for row in session.variants:row.evidence['MTBP']=completed(row,'MTBP',session)
    unselected_before=deepcopy(unselected.evidence);other_before=deepcopy(other_analysis.evidence)
    changes=[]
    module.run_queue(session,['Mutalyzer','MTBP'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,
        plan={(v.id,'Mutalyzer')},plan_changed=changes.append)
    assert calls==[('MTBP',[('EGFR',v.corrected_hgvs),('TP53','NM_000546.6:c.818G>A')])]
    assert changes==[{(v.id,'Mutalyzer'),(v.id,'MTBP'),(companion.id,'MTBP')}]
    for row in (v,companion):assert evidence_is_current(row,row.evidence['MTBP'],'Other',session)
    assert unselected.evidence==unselected_before and other_analysis.evidence==other_before


def test_conflicting_normalization_does_not_expand_the_plan(monkeypatch,tmp_path):
    module,calls=fake_sources(monkeypatch);v=variant();session=Session(variants=[v]);changes=[]
    v.evidence['ClinVar']=completed(v,'ClinVar',session)
    data=checked_result();data['nomenclature_assessment'].update(status='Conflict',identity_confirmed=False)
    monkeypatch.setattr(module,'normalize_variant',lambda row:data)
    module.run_queue(session,['Mutalyzer','ClinVar'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,
        plan={(v.id,'Mutalyzer')},plan_changed=changes.append)
    assert not calls and not changes and not v.corrected_hgvs
