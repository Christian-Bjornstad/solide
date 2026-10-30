from copy import deepcopy

import pytest
from PIL import Image,ImageDraw

from solide.models import Session
from test_automatic_nomenclature import variant,checked_result
from test_normalization_plan import fake_sources


def capture_result(tmp_path):
    image=Image.new('RGB',(400,150),'white')
    ImageDraw.Draw(image).rectangle((0,0,200,150),fill='green')
    path=tmp_path/'retried-normalizer.png';image.save(path)
    return {'screenshots':[{'path':str(path),'label':'Mutalyzer'}]}


def rerun(module,session,tmp_path):
    module.run_queue(session,['Mutalyzer'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None)


def unchanged_result(v):
    data=checked_result();data['original']=v.corrected_hgvs
    data['normalization'].update(input_description=v.corrected_hgvs,normalized_description=v.corrected_hgvs)
    data['nomenclature_assessment'].update(status='Unchanged',suggested_hgvs=v.corrected_hgvs)
    return data


def test_successful_capture_retry_finishes_previously_applied_normalization(monkeypatch,tmp_path):
    module,_=fake_sources(monkeypatch);v=variant();session=Session(variants=[v])
    rerun(module,session,tmp_path)
    previous=deepcopy(v.evidence['Mutalyzer']['raw']['nomenclature_application'])
    assert module.assess_evidence(v,v.evidence['Mutalyzer'],session).label=='Missing capture'
    data=unchanged_result(v)
    monkeypatch.setattr(module,'normalize_variant',lambda row:deepcopy(data))
    monkeypatch.setattr(module,'capture_mutalyzer',lambda *args,**kwargs:capture_result(tmp_path))
    rerun(module,session,tmp_path)
    result=v.evidence['Mutalyzer']
    assert result['status']=='verified'
    assert result['raw']['nomenclature_application']==previous
    assert result['raw']['original']==v.corrected_hgvs
    assert module.assess_evidence(v,result,session).label=='Verified match'
    assert not module.build_search_plan(session,['Mutalyzer'])


@pytest.mark.parametrize('change',['none','wrong_input','wrong_allele','wrong_event','unconfirmed','stale_previous'])
def test_retry_requires_fresh_confirmation_and_valid_capture(monkeypatch,tmp_path,change):
    module,_=fake_sources(monkeypatch);v=variant();session=Session(variants=[v])
    rerun(module,session,tmp_path);data=unchanged_result(v)
    if change=='wrong_input':data['original']='NM_005228.5:c.1A>T'
    elif change=='wrong_allele':data['nomenclature_assessment']['source_genomic_query']='chr7-55242464-A-T'
    elif change=='wrong_event':data['genomic_identity_check']['matched_event']['inserted']='C'
    elif change=='unconfirmed':data['nomenclature_assessment']['identity_confirmed']=False
    elif change=='stale_previous':v.evidence['Mutalyzer']['fingerprint']='stale'
    monkeypatch.setattr(module,'normalize_variant',lambda row:deepcopy(data))
    rerun(module,session,tmp_path)
    evidence=v.evidence['Mutalyzer']
    if change=='none':
        assert evidence['status']=='verified'
        assert module.assess_evidence(v,evidence,session).label=='Missing capture'
    else:
        assert evidence['status']=='needs_review'
        assert 'nomenclature_application' not in evidence['raw']
    assert module.build_search_plan(session,['Mutalyzer'])=={(v.id,'Mutalyzer')}


def test_original_unchanged_name_is_not_automatically_approved(monkeypatch,tmp_path):
    module,_=fake_sources(monkeypatch);v=variant()
    v.coding='c.2235_2249del';session=Session(variants=[v])
    data=checked_result();data['original']='NM_005228.5:'+v.coding
    data['normalization'].update(input_description=data['original'])
    data['nomenclature_assessment']['status']='Unchanged'
    monkeypatch.setattr(module,'normalize_variant',lambda row:data)
    monkeypatch.setattr(module,'capture_mutalyzer',lambda *args,**kwargs:capture_result(tmp_path))
    rerun(module,session,tmp_path)
    assert not v.nomenclature_verified and not v.corrected_hgvs
    assert v.evidence['Mutalyzer']['status']=='verified'
    assert module.assess_evidence(v,v.evidence['Mutalyzer'],session).label=='Verified match'
