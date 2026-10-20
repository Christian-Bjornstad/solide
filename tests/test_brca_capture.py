from copy import deepcopy
import pytest


def evidence():
    identity={'gene':'BRCA1','assembly':'GRCh37','hgvs':'NM_007294.4:c.68_69del'}
    return {'database':'BRCA Exchange','status':'found','accession':'1396149',
        'url':'https://brcaexchange.org/variant/1396149','clinical_significance':'Pathogenic',
        'raw':{'variant':{'id':1396149,'Gene_Symbol':'BRCA1','HGVS_cDNA':'NM_007294.4:c.68_69del',
                        'Reference_Sequence':'NM_007294.4','Genomic_HGVS_37':'NC_000017.10:g.41276045_41276046del',
                        'Pathogenicity_expert':'Pathogenic','Date_last_evaluated_ENIGMA':'2024-06-11'},
               'identity_verification':{'accepted':True,'requested':identity,'returned':dict(identity)}}}


def state():
    return {'url':'https://brcaexchange.org/variant/CA003783',
        'gene':'BRCA1','transcript':'NM_007294.4','coding':'c.68_69del',
        'genomic_grch37':'NC_000017.10:g.41276045_41276046del','classification':'Pathogenic',
        'evaluated':'11 June 2024','names_visible':True,'classification_visible':True}


def test_brca_capture_allows_canonical_redirect_only_with_exact_visible_identity():
    from solide.public_capture import validate_brca_exchange_capture
    validate_brca_exchange_capture(evidence(),state())


@pytest.mark.parametrize('change',[
    {'gene':'BRCA2'},{'transcript':'NM_007294.3'},{'coding':'c.69_70del'},
    {'genomic_grch37':'NC_000017.11:g.43124028_43124029del'},
    {'classification':'Benign'},{'evaluated':'12 June 2024'},
    {'url':'https://example.org/variant/CA003783'},
    {'names_visible':False},{'classification_visible':False},
])
def test_brca_capture_rejects_wrong_or_hidden_current_record(change):
    from solide.public_capture import validate_brca_exchange_capture
    with pytest.raises(ValueError):validate_brca_exchange_capture(evidence(),{**state(),**change})


def test_brca_capture_never_trusts_a_rejected_api_identity():
    from solide.public_capture import validate_brca_exchange_capture
    e=evidence();e['raw']['identity_verification']['accepted']=False
    with pytest.raises(ValueError):validate_brca_exchange_capture(e,state())


def test_brca_capture_failure_keeps_api_result_and_is_retryable(monkeypatch,tmp_path):
    import solide.evidence as module
    from solide.models import Variant,Session
    v=Variant(patient='DEMO',gene='BRCA1',transcript='NM_007294.4',coding='c.68_69del',assembly='GRCh37',selected=True)
    session=Session(variants=[v]);e=evidence()
    monkeypatch.setattr(module,'brca_exchange_variant',lambda v:deepcopy(e))
    def fail(*args,**kwargs):raise ValueError('Source screenshot unavailable')
    monkeypatch.setattr(module,'capture_brca_exchange',fail,raising=False)
    module.run_queue(session,['BRCA Exchange'],tmp_path,module.QueueControl(),lambda *args:None,lambda text:None)
    item=v.evidence['BRCA Exchange']
    assert item['status']=='found'
    assert item['clinical_significance']=='Pathogenic'
    assert item['raw']['identity_verification']['accepted'] is True
    assert module.assess_evidence(v,item,session).label=='Missing capture'
    assert module.build_search_plan(session,['BRCA Exchange'],'failed')=={(v.id,'BRCA Exchange')}


def test_deleted_brca_screenshot_is_not_accepted_as_complete():
    from solide.models import Variant,Session
    from solide.evidence import assess_evidence
    v=Variant(patient='DEMO',gene='BRCA1',selected=True)
    e=evidence();e['fingerprint']=v.fingerprint('Other')
    e['raw']['capture']={'identity_confirmed':True,'classification_confirmed':True}
    e['raw']['screenshots']=[]
    assert assess_evidence(v,e,Session(variants=[v])).label=='Missing capture'
