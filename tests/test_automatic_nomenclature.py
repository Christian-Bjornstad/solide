from copy import deepcopy

import pytest

from solide.models import Session, Variant
from solide.nomenclature import apply_confirmed_normalization


def variant():
    return Variant(patient='26OUM00000', gene='EGFR', transcript='NM_005228.5',
        coding='c.2235_2250delinsA', protein='p.Old', locus='chr7:55242464',
        ref='AGGAATTAAGAGAAGC', alt='A', assembly='GRCh37', selected=True,
        raw={'Gene': 'EGFR', 'Coding': 'c.2235_2250delinsA'})


def checked_result():
    original='NM_005228.5:c.2235_2250delinsA'
    normalized='NM_005228.5:c.2235_2249del'
    return {'original':original, 'normalization':{'input_description':original,
        'normalized_description':normalized}, 'nomenclature_assessment':{
        'status':'Normalized', 'identity_confirmed':True, 'suggested_hgvs':normalized,
        'source_genomic_query':'chr7-55242464-AGGAATTAAGAGAAGC-A',
        'candidates':[{'description':normalized,'transcript':'NM_005228.5','label':'Source transcript'}]},
        'genomic_identity_check':{'matched_event':{'reference':'NC_000007.13',
            'start':55242464,'end':55242479,'inserted':''}}}


def test_confirmed_normalized_name_is_used_without_changing_imported_data():
    v=variant(); original_raw=deepcopy(v.raw); data=checked_result()
    assert apply_confirmed_normalization(v,data)
    assert v.corrected_hgvs=='NM_005228.5:c.2235_2249del'
    assert v.nomenclature_verified and v.controlled_genomic=='chr7-55242464-AGGAATTAAGAGAAGC-A'
    assert v.coding=='c.2235_2250delinsA' and v.protein=='p.Old' and v.raw==original_raw
    assert data['nomenclature_application']['from_hgvs']==data['original']
    assert data['nomenclature_application']['to_hgvs']==v.corrected_hgvs
    assert not apply_confirmed_normalization(v,data)


def test_unchanged_verified_name_finishes_without_an_unneeded_screenshot(monkeypatch,tmp_path):
    import solide.evidence as module
    from unittest.mock import Mock
    v=variant();v.coding='c.2235_2249del';v.kind='INDEL'
    data=checked_result();data['original']='NM_005228.5:c.2235_2249del'
    data['normalization']['input_description']=data['original']
    data['nomenclature_assessment']['status']='Unchanged'
    session=Session(variants=[v]);capture=Mock()
    monkeypatch.setattr(module,'normalize_variant',lambda row:data)
    monkeypatch.setattr(module,'capture_mutalyzer',capture)
    module.run_queue(session,['Mutalyzer'],tmp_path,module.QueueControl(),lambda *args:None,lambda text:None)
    evidence=v.evidence['Mutalyzer']
    assert evidence['status']=='verified'
    assert module.assess_evidence(v,evidence,session).label=='Verified match'
    assert not module.build_search_plan(session,['Mutalyzer'])
    capture.assert_not_called()


@pytest.mark.parametrize('change', ['conflict','unconfirmed','missing_event','wrong_allele',
    'old_input','unlisted_name','ambiguous_gene','ambiguous_transcript','unchanged',
    'malformed_check','wrong_reference','unconfirmed_transcript'])
def test_unconfirmed_stale_or_ambiguous_normalization_is_never_applied(change):
    v=variant(); data=checked_result(); assessment=data['nomenclature_assessment']
    if change=='conflict':assessment['status']='Conflict'
    elif change=='unconfirmed':assessment['identity_confirmed']=False
    elif change=='missing_event':data['genomic_identity_check'].clear()
    elif change=='wrong_allele':assessment['source_genomic_query']='chr7-55242464-A-T'
    elif change=='old_input':data['original']='NM_005228.5:c.1A>T'
    elif change=='unlisted_name':assessment['candidates']=[]
    elif change=='ambiguous_gene':v.gene='EGFR, MET'
    elif change=='ambiguous_transcript':v.transcript+=' ,NM_001346897.2'
    elif change=='malformed_check':data['genomic_identity_check']=None
    elif change=='wrong_reference':data['genomic_identity_check']['matched_event']['reference']='NC_000007.14'
    elif change=='unconfirmed_transcript':
        assessment['suggested_hgvs']='NM_001346897.2:c.2235_2249del'
        assessment['candidates']=[{'description':assessment['suggested_hgvs'],'label':'Source transcript'}]
    else:assessment['status']='Unchanged'
    before=deepcopy(v)
    assert not apply_confirmed_normalization(v,data)
    assert v==before


@pytest.mark.parametrize('has_capture',[False,True])
def test_queue_applies_confirmed_name_before_database_searches(monkeypatch,tmp_path,has_capture):
    import solide.evidence as module
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    v=variant(); session=Session(variants=[v]); records=[]
    class Service:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,rows,sources,root,progress,checkpoint):
            records.extend(rows)
            checkpoint({self.variant_key(row):[DatabaseEvidence(sources[0],'not_found','No record')] for row in rows})
    monkeypatch.setattr(module,'BrowserReviewService',Service)
    monkeypatch.setattr(module,'normalize_variant',lambda row:checked_result())
    captured={}
    if has_capture:
        from PIL import Image,ImageDraw
        image=Image.new('RGB',(400,150),'white')
        ImageDraw.Draw(image).rectangle((0,0,200,150),fill='green')
        path=tmp_path/'normalizer.png';image.save(path)
        captured={'screenshots':[{'path':str(path),'label':'Mutalyzer'}]}
    monkeypatch.setattr(module,'capture_mutalyzer',lambda *args,**kwargs:captured)
    module.run_queue(session,['Mutalyzer','ClinVar'],tmp_path,module.QueueControl(),
        lambda *args:None,lambda message:None)
    assert len(records)==1 and records[0].hgvsc=='NM_005228.5:c.2235_2249del'
    assert records[0].hgvsp=='' and v.coding=='c.2235_2250delinsA'
    assert module.evidence_is_current(v,v.evidence['Mutalyzer'],'Other',session)
    assert module.evidence_is_current(v,v.evidence['ClinVar'],'Other',session)
    assert v.evidence['Mutalyzer']['raw']['original']=='NM_005228.5:c.2235_2250delinsA'
    assert v.evidence['Mutalyzer']['status']=='verified'
    assessment=module.assess_evidence(v,v.evidence['Mutalyzer'],session)
    assert assessment.label==('Verified match' if has_capture else 'Missing capture')
    assert assessment.retryable is (not has_capture)
    assert ((v.id,'Mutalyzer') in module.build_search_plan(session,['Mutalyzer'])) is (not has_capture)
