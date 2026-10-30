from copy import deepcopy
import pytest
from solide.public_capture import (spliceai_url, validate_spliceai_capture,validate_mutalyzer_capture,
    validate_spliceai_dom,validate_pangolin_capture)


def result():
    row={key:'0.10' for key in ('DS_AG','DS_AL','DS_DG','DS_DL')}
    row.update({key:1 for key in ('DP_AG','DP_AL','DP_DG','DP_DL')})
    row.update(g_name='PTEN',t_id='ENST1.2',t_priority='MS',t_refseq_ids=['NM_000314.8'])
    response=dict(variant='chr10-89692769-G-A',hg='37',genomeVersion='37',distance=500,mask=1,
                  chrom='10',pos=89692769,ref='G',alt='A',scores=[row],bc='basic')
    return dict(query=response['variant'],hg=37,distance=500,mask=1,response=response)


def test_capture_url_uses_exact_api_variant_and_interpretation_settings():
    data=result();url=spliceai_url(data)
    assert 'variant=chr10-89692769-G-A' in url
    assert 'hg=37' in url and 'mask=1' in url and 'distance=500' in url and 'ra=1' in url
    assert validate_spliceai_capture(data,deepcopy(data['response'])) is None
    browser=deepcopy(data['response']);browser['variant']=browser['variant'].removeprefix('chr')
    validate_spliceai_capture(data,browser)


@pytest.mark.parametrize('change',[
    lambda r:r.update(mask=0),lambda r:r.update(hg=38),lambda r:r.update(variant='chr10-89692769-G-T'),
    lambda r:r['scores'][0].update(DS_AG='0.99'),lambda r:r['scores'][0].update(t_id='OTHER'),
    lambda r:r.update(scores=[]),lambda r:r.update(bc='comprehensive'),
    lambda r:r['scores'][0].update(t_priority='C'),
])
def test_browser_capture_must_match_validated_api_identity_settings_and_scores(change):
    data=result();browser=deepcopy(data['response']);change(browser)
    with pytest.raises(ValueError):validate_spliceai_capture(data,browser)


def test_failed_screenshot_retains_valid_prediction_and_can_be_retried(monkeypatch,tmp_path):
    import solide.evidence as module
    from solide.models import Variant,Session
    data=result()
    v=Variant(patient='SOURCE',gene='PTEN',transcript='NM_000314.8',coding='c.254-1G>A',
        locus='chr10:89692769',ref='G',alt='A',assembly='GRCh37',selected=True)
    session=Session(variants=[v])
    monkeypatch.setattr(module,'spliceai_variant',lambda variant:data)
    def unavailable(*args,**kwargs):raise ValueError('Source page did not finish')
    monkeypatch.setattr(module,'capture_spliceai',unavailable)
    module.run_queue(session,['SpliceAI'],tmp_path,module.QueueControl(),lambda *args:None,lambda text:None)
    evidence=v.evidence['SpliceAI']
    assert evidence['status']=='found' and evidence['raw']['response']==data['response']
    assert 'capture_issue' in evidence['raw']
    assert module.assess_evidence(v,evidence,session).label=='Missing capture'
    assert module.build_search_plan(session,['SpliceAI'],'failed')=={(v.id,'SpliceAI')}


def test_mutalyzer_conflict_blocks_downstream_search_without_changing_source():
    from solide.models import Variant
    from solide.evidence import query_record
    v=Variant(gene='EGFR',transcript='NM_005228.5',coding='c.2573T>G',assembly='GRCh37')
    v.evidence['Mutalyzer']={'fingerprint':v.fingerprint('Other'),'tissue':'Other',
        'raw':{'nomenclature_assessment':{'status':'Conflict'}}}
    with pytest.raises(ValueError,match='conflict'):query_record(v,'ClinVar')
    assert v.coding=='c.2573T>G' and not v.nomenclature_verified


def test_reviewed_genomic_name_keeps_original_intronic_spliceai_trigger():
    from solide.quality import review_reasons
    from solide.models import Variant
    v=Variant(gene='PTEN',coding='c.254-1G>A',corrected_hgvs='NC_000010.10:g.89692769G>A')
    assert 'SpliceAI' in review_reasons(v)


@pytest.mark.parametrize('coding', ['c.254-100G>A','c.2350-15A>T','c.5346+5C>A'])
def test_intronic_window_triggers_source_splicing_review(coding):
    from solide.quality import review_reasons
    from solide.models import Variant
    assert 'SpliceAI' in review_reasons(Variant(coding=coding))


@pytest.mark.parametrize('coding', ['c.254-101G>A','c.100A>T','c.*4228_*4242del'])
def test_exonic_utr_or_outside_configured_window_does_not_auto_trigger(coding):
    from solide.quality import review_reasons
    from solide.models import Variant
    assert 'SpliceAI' not in review_reasons(Variant(coding=coding))


def test_mutalyzer_green_panel_must_confirm_both_query_and_normalized_name():
    data={'original':'NM_1.1:c.2delA','normalization':{'normalized_description':'NM_1.1:c.2del'}}
    validate_mutalyzer_capture(data,{'input':data['original'],'normalized':'NM_1.1:c.2del'})
    for state in [{'input':'NM_1.1:c.3del','normalized':'NM_1.1:c.2del'},
                  {'input':data['original'],'normalized':'NM_1.1:c.3del'}]:
        with pytest.raises(ValueError):validate_mutalyzer_capture(data,state)


def test_legacy_mtbp_gene_rows_are_rechecked_without_mutating_saved_result():
    from solide.models import Session,Variant
    from solide.evidence import assess_evidence,batch_fingerprint,build_search_plan
    v=Variant(patient='SOURCE',gene='EGFR',selected=True);session=Session(variants=[v])
    e={'database':'MTBP','status':'not_found','fingerprint':v.fingerprint('Other'),
       'mtbp_batch':batch_fingerprint(session,v.patient),'raw':{'gene_candidate_count':1}}
    v.evidence['MTBP']=e;before=deepcopy(e)
    assert assess_evidence(v,e,session).label=='Recheck required'
    assert build_search_plan(session,['MTBP'],'pending')=={(v.id,'MTBP')}
    assert build_search_plan(session,['MTBP'],'failed')=={(v.id,'MTBP')}
    assert e==before
    e['raw']['identity_matching_version']=3
    assert assess_evidence(v,e,session).label=='No match'


def mane_state():
    return {'input':'chr10-89692769-G-A','hg':'37','bc':'basic','distance':'500',
        'mask':True,'ref_alt':True,
        'panels':{'spliceai':{'visible':True,'transcripts':['ENST1.2']*4},
                  'pangolin':{'visible':True,'transcripts':['ENST1.2']*2},
                  'consequences':{'visible':True,'transcripts':['ENST1.2'],
                      'method':'SAI-10k-calc','output':'No prediction'}}}


def complete_result():
    data=result()
    data['response']['sai10kPredictions']={'transcript_id':'ENST1.2','aberrations':[]}
    data['pangolin_response']={**deepcopy(data['response']),'mask':'True',
        'scores':[{'t_id':'ENST1.2','t_priority':'MS','DS_SL':'-0.89','DS_SG':'0.19','DP_SL':-2,'DP_SG':-62}]}
    return data


def test_spliceai_dom_requires_mane_only_and_all_three_complete_panels():
    data=complete_result();state=mane_state()
    # Keep the full API evidence, but hide every non-MANE transcript in the picture.
    other=deepcopy(data['response']['scores'][0]);other.update(t_id='ENST2.1',t_priority='MP')
    data['response']['scores'].append(other)
    validate_spliceai_dom(data,state)
    for field,value in [('hg','38'),('mask',False),('ref_alt',False)]:
        with pytest.raises(ValueError):validate_spliceai_dom(data,{**state,field:value})
    for panel in state['panels']:
        for key,value in [('visible',False),('transcripts',[]),('transcripts',['ENST2.1'])]:
            changed=deepcopy(state);changed['panels'][panel][key]=value
            with pytest.raises(ValueError):validate_spliceai_dom(data,changed)
    for output in ('','Loading...'):
        changed=deepcopy(state);changed['panels']['consequences']['output']=output
        with pytest.raises(ValueError):validate_spliceai_dom(data,changed)


def test_mane_capture_does_not_fall_back_to_canonical_or_another_prediction_transcript():
    data=complete_result();data['response']['scores'][0]['t_priority']='C'
    with pytest.raises(ValueError,match='MANE'):validate_spliceai_dom(data,mane_state())
    data=complete_result();data['response']['sai10kPredictions']['transcript_id']='ENST2.1'
    with pytest.raises(ValueError):validate_spliceai_dom(data,mane_state())
    data=complete_result();data['response']['sai10kPredictionsError']='Service failed'
    with pytest.raises(ValueError):validate_spliceai_dom(data,mane_state())


@pytest.mark.parametrize('mutation',[
    {'variant':'chr10-89692769-G-T'},{'pos':89692770},{'hg':'38'},{'distance':10000},
    {'mask':0},{'bc':'comprehensive'},{'error':'Unavailable'},{'scores':[]},
    {'scores':[{'t_id':'ENST1.2','t_priority':'MS','DS_SL':'nan','DS_SG':0,'DP_SL':0,'DP_SG':0}]},
])
def test_pangolin_must_confirm_same_allele_settings_and_finite_scores(mutation):
    data=complete_result();validate_pangolin_capture(data,data['pangolin_response'])
    with pytest.raises(ValueError):validate_pangolin_capture(data,{**data['pangolin_response'],**mutation})


def test_mane_dom_handles_multiple_mane_transcripts_without_selecting_first_gene():
    data=complete_result();state=mane_state()
    for key in ('response','pangolin_response'):
        other=deepcopy(data[key]['scores'][0]);other['t_id']='ENST3.1'
        data[key]['scores'].append(other)
    state['panels']['spliceai']['transcripts']+=['ENST3.1']*4
    state['panels']['pangolin']['transcripts']+=['ENST3.1']*2
    validate_spliceai_dom(data,state)


def test_old_spliceai_picture_and_incomplete_panels_are_retriable(tmp_path):
    from test_report_source_sequence import full_results
    from solide.evidence import assess_evidence,build_search_plan
    session,v=full_results(tmp_path);item=v.evidence['SpliceAI'];capture=item['raw']['capture']
    assert assess_evidence(v,item,session).label=='Verified match'
    del capture['capture_version']
    assert assess_evidence(v,item,session).label=='Missing capture'
    assert (v.id,'SpliceAI') in build_search_plan(session,['SpliceAI'],'failed')
    capture['capture_version']=2
    capture['panels']['pangolin']['visible']=False
    assert assess_evidence(v,item,session).label=='Missing capture'
