from pathlib import Path
from solide.models import Session, Variant
from solide.evidence import build_search_plan, assess_evidence
from solide.accounts import write_password, browser_credentials, remove_password
from solide.activity import ActivityLog
from PIL import Image, ImageDraw
import pytest


def image_file(path):
    image=Image.new('RGB',(400,150),'white');ImageDraw.Draw(image).rectangle((0,0,200,150),fill='green')
    image.save(path);return path


def sample(gene='EGFR'):
    return Variant(patient='DEMO',gene=gene,assembly='GRCh37',selected=True)


def result(v, status, **raw):
    return {'database':'ClinVar','status':status,'fingerprint':v.fingerprint('Other'),'raw':raw}


def test_retry_failed_does_not_search_new_or_successful_rows(tmp_path):
    a,b,c=sample(),sample('TP53'),sample('BRAF')
    a.evidence['ClinVar']=result(a,'error')
    b.evidence['ClinVar']=result(b,'not_found')
    assert build_search_plan(Session(variants=[a,b,c]),['ClinVar'],'failed')=={(a.id,'ClinVar')}


def test_selected_rerun_preserves_full_mtbp_batch():
    a,b,c=sample(),sample('TP53'),sample('BRAF');c.patient='OTHER'
    plan=build_search_plan(Session(variants=[a,b,c]),['MTBP','ClinVar'],'chosen',{(a.id,'MTBP')})
    assert plan=={(a.id,'MTBP'),(b.id,'MTBP')}


def test_ambiguous_mtbp_match_retries_complete_patient_batch():
    a,b=sample(),sample('TP53')
    a.evidence['MTBP']={**result(a,'ambiguous_result'),'database':'MTBP'}
    assert build_search_plan(Session(variants=[a,b]),['MTBP'],'failed')=={(a.id,'MTBP'),(b.id,'MTBP')}


def test_found_is_not_automatically_a_verified_match(tmp_path):
    v=sample();image=image_file(tmp_path/'capture.png')
    e=result(v,'found',screenshots=[{'path':str(image)}])
    assert assess_evidence(v,e,Session(variants=[v])).label=='Review match'
    e['raw'].update(assembly_verified='GRCh37',matched_location={'position':1})
    assert assess_evidence(v,e,Session(variants=[v])).label=='Verified match'
    image.unlink()
    assert assess_evidence(v,e,Session(variants=[v])).label=='Missing capture'


def test_cdna_only_franklin_hit_requires_transcript_review(tmp_path):
    v=sample();image=image_file(tmp_path/'capture.png')
    e={'database':'Franklin','status':'found','fingerprint':v.fingerprint('Other'),
       'raw':{'query_basis':'gene_cdna','screenshots':[{'path':str(image)}],
              'assembly_verified':'GRCh37','matched_location':{'position':1}}}
    assert assess_evidence(v,e,Session(variants=[v])).label=='Review match'


def test_explicit_identity_failure_is_not_a_valid_match(tmp_path):
    v=sample();image=image_file(tmp_path/'capture.png')
    e=result(v,'found',screenshots=[{'path':str(image)}],identity_verification={'accepted':False})
    assert assess_evidence(v,e,Session(variants=[v])).label=='Identity mismatch'


def test_passwords_use_separate_vault_and_are_not_config_fields():
    class Vault:
        entries={}
        def set_password(self,service,user,password):self.entries[service,user]=password
        def get_password(self,service,user):return self.entries.get((service,user))
        def delete_password(self,service,user):del self.entries[service,user]
    vault=Vault();write_password('MTBP','demo@example.org','secret',vault)
    assert browser_credentials({'MTBP':'demo@example.org'},vault)=={
        'mtbp_email':'demo@example.org','mtbp_password':'secret'}
    assert ('Solide/MTBP','demo@example.org') in vault.entries
    remove_password('MTBP','demo@example.org',vault);assert not vault.entries


def test_activity_log_redacts_credentials(tmp_path):
    log=ActivityLog(tmp_path/'activity.log');log.secrets.add('very-secret')
    text=log.write('password=very-secret token=other-secret')
    assert '[redacted]' in log.tail()
    log.close()
    assert 'very-secret' not in text and 'other-secret' not in text
    assert '[redacted]' in (tmp_path/'activity.log').read_text()


def test_capture_validation_cache_refreshes_when_file_changes(monkeypatch,tmp_path):
    import solide.evidence as module
    image=image_file(tmp_path/'cache.png');calls=[]
    original=module.validate_capture
    def validate(path):calls.append(path);return original(path)
    monkeypatch.setattr(module,'validate_capture',validate)
    assert module.valid_capture(image) and module.valid_capture(image)
    assert len(calls)==1
    image.write_bytes(b'corrupt')
    assert not module.valid_capture(image) and len(calls)==2


def test_vault_errors_do_not_echo_password():
    class BrokenVault:
        def set_password(self,*args):raise RuntimeError('secret-password')
    with pytest.raises(RuntimeError) as error:
        write_password('MTBP','demo@example.org','secret-password',BrokenVault())
    assert 'secret-password' not in str(error.value)


def test_forced_rerun_does_not_overwrite_other_completed_sources(monkeypatch,tmp_path):
    import solide.evidence as module
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    calls=[]
    class Service:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,records,sources,root,progress,checkpoint):
            calls.append(sources)
            checkpoint({self.variant_key(r):[DatabaseEvidence(sources[0],'not_found','Fresh search')] for r in records})
    monkeypatch.setattr(module,'BrowserReviewService',Service)
    v=Variant(patient='DEMO',gene='EGFR',transcript='NM_005228.5',coding='c.1A>T',assembly='GRCh37',selected=True)
    v.evidence['ClinVar']=result(v,'not_found');v.evidence['Franklin']={**result(v,'not_found'),'database':'Franklin','summary':'Keep me'}
    session=Session(variants=[v]);plan=build_search_plan(session,['ClinVar','Franklin'],'chosen',{(v.id,'ClinVar')})
    module.run_queue(session,['ClinVar','Franklin'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,plan=plan)
    assert calls==[['ClinVar']] and v.evidence['Franklin']['summary']=='Keep me'
    assert v.evidence['ClinVar']['summary']=='Fresh search'


@pytest.mark.parametrize('source',['Mutalyzer','SpliceAI'])
def test_missing_identity_requires_review_instead_of_repeated_network_retry(tmp_path,source):
    import solide.evidence as module
    v=Variant(patient='SOURCE',gene='EGFR',coding='c.1498+22A>T',assembly='GRCh37',selected=True)
    session=Session(variants=[v])
    module.run_queue(session,[source],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,
                     plan={(v.id,source)})
    assert v.evidence[source]['status']=='needs_review'
    assert not assess_evidence(v,v.evidence[source],session).retryable
    assert not build_search_plan(session,[source],'failed')


def test_mutalyzer_validation_and_mapping_issues_remain_reviewable(monkeypatch,tmp_path):
    import solide.evidence as module
    v=Variant(patient='SOURCE',gene='FGFR1',selected=True)
    session=Session(variants=[v])
    monkeypatch.setattr(module,'normalize_variant',lambda v:{'normalization':{'errors':[
        {'code':'ESEQUENCEMISMATCH','details':'Reference mismatch'}]},'mapping_issue':'Target mapping unavailable'})
    module.run_queue(session,['Mutalyzer'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,plan={(v.id,'Mutalyzer')})
    evidence=v.evidence['Mutalyzer']
    assert evidence['status']=='needs_review'
    assert 'ESEQUENCEMISMATCH' in evidence['summary'] and 'Target mapping unavailable' in evidence['summary']
    assert not assess_evidence(v,evidence,session).retryable


def test_spliceai_match_requires_complete_hg19_response():
    v=Variant(patient='SOURCE',gene='TP53',locus='chr17:7577609',ref='C',alt='T',assembly='GRCh37',selected=True)
    score={**{key:'0.0' for key in ('DS_AG','DS_AL','DS_DG','DS_DL')},
           **{key:0 for key in ('DP_AG','DP_AL','DP_DG','DP_DL')}}
    response={'variant':'chr17-7577609-C-T','chrom':'17','pos':7577609,'ref':'C','alt':'T',
              'hg':37,'genomeVersion':'37','distance':500,'mask':1,'scores':[score]}
    evidence={'database':'SpliceAI','status':'found','fingerprint':v.fingerprint('Other'),
              'raw':{'query':response['variant'],'response':response}}
    session=Session(variants=[v])
    assert assess_evidence(v,evidence,session).label=='Verified match'
    response['hg']=38
    assert assess_evidence(v,evidence,session).label=='Review required'


def test_spliceai_validation_responses_keep_request_spacing(monkeypatch,tmp_path):
    import solide.evidence as module
    waits=[]
    variants=[Variant(patient='SOURCE',gene='TP53',coding='c.673-1G>A',locus='chr17:7577609',
        ref='C',alt='T',assembly='GRCh37',selected=True) for _ in range(2)]
    class Control(module.QueueControl):
        def wait(self,seconds):waits.append(seconds)
    def invalid_response(v):raise ValueError('Response was incomplete')
    monkeypatch.setattr(module,'spliceai_variant',invalid_response)
    session=Session(variants=variants)
    module.run_queue(session,['SpliceAI'],tmp_path,Control(),lambda *args:None,lambda message:None,
        plan={(v.id,'SpliceAI') for v in variants})
    assert len(waits)==2 and waits[1]>29
    assert all(v.evidence['SpliceAI']['status']=='needs_review' for v in variants)


def test_brca_plan_and_queue_never_query_other_genes(monkeypatch,tmp_path):
    import solide.evidence as module
    calls=[]
    def lookup(v):
        calls.append(v.gene)
        identity={'gene':v.gene,'assembly':'GRCh37','hgvs':f'{v.transcript}:{v.coding}'}
        return {'status':'found','clinical_significance':'Source assertion','raw':{'query_basis':'full_hgvs',
            'identity_verification':{'accepted':True,'requested':identity,'returned':identity,'method':'full_hgvs'}}}
    monkeypatch.setattr(module,'brca_exchange_variant',lookup)
    variants=[Variant(patient='DEMO',gene=gene,transcript='NM_1.1',coding='c.1A>T',assembly='GRCh37',selected=True)
        for gene in ('BRCA1','BRCA2','EGFR','BRCA1,BRCA2')]
    s=Session(variants=variants);sources=['BRCA Exchange']
    plan=build_search_plan(s,sources,'all')
    assert plan=={(v.id,'BRCA Exchange') for v in variants[:2]}
    module.run_queue(s,sources,tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,plan=plan)
    assert calls==['BRCA1','BRCA2']
    assert all(not v.evidence for v in variants[2:])
    evidence=variants[0].evidence['BRCA Exchange'];assessment=assess_evidence(variants[0],evidence,s)
    assert assessment.label=='Verified match' and 'versioned HGVS' in assessment.reason
    assert not variants[0].classification and variants[0].report_decision=='Pending'


@pytest.mark.parametrize('status',['submission_unknown','timeout','partial_capture'])
def test_uncertain_mtbp_submission_is_passed_to_retry_reconciliation(monkeypatch,tmp_path,status):
    import solide.evidence as module
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    calls=[]
    class Service:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,records,sources,root,progress,checkpoint,prior_evidence):
            calls.append(prior_evidence)
            checkpoint({self.variant_key(r):[DatabaseEvidence('MTBP','not_found','Reconciled')] for r in records})
    monkeypatch.setattr(module,'BrowserReviewService',Service)
    v=Variant(patient='DEMO',gene='EGFR',protein='p.L858R',assembly='GRCh37',selected=True)
    s=Session(variants=[v]);v.evidence['MTBP']={'database':'MTBP','status':status,
        'summary':'Wait for report','fingerprint':v.fingerprint('Other'),'mtbp_batch':module.batch_fingerprint(s,'DEMO'),
        'raw':{'analysis_id':'SOLIDE_DEMO'}}
    plan=build_search_plan(s,['MTBP'],'failed')
    module.run_queue(s,['MTBP'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,plan=plan)
    assert len(calls)==1 and next(iter(calls[0].values()))[0].raw['analysis_id']=='SOLIDE_DEMO'
    assert v.evidence['MTBP']['summary'].startswith('Reconciled')


@pytest.mark.parametrize('status',['layout_changed','ambiguous','transient','submission_unknown','deferred'])
def test_provider_retry_states_are_visible_and_retryable(status):
    v=sample();v.evidence['ClinVar']=result(v,status)
    s=Session(variants=[v]);assert assess_evidence(v,v.evidence['ClinVar'],s).retryable
    assert build_search_plan(s,['ClinVar'],'failed')=={(v.id,'ClinVar')}


def test_mtbp_provider_exception_retains_interim_report_id(monkeypatch,tmp_path):
    import solide.evidence as module
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    emitted=[]
    class Service:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,records,sources,root,progress,checkpoint):
            checkpoint({self.variant_key(records[0]):[DatabaseEvidence('MTBP','submission_unknown',raw={
                'analysis_id':'SOLIDE-DEMO','provisional_status':'submission_unknown'})]})
            raise TimeoutError('Provider interrupted')
    monkeypatch.setattr(module,'BrowserReviewService',Service)
    v=Variant(patient='DEMO',gene='EGFR',protein='p.L858R',selected=True,assembly='GRCh37')
    module.run_queue(Session(variants=[v]),['MTBP'],tmp_path,module.QueueControl(),lambda *args:emitted.append(args),lambda message:None)
    assert len(emitted)==2
    assert emitted[0][2]['raw']['provisional_status']=='submission_unknown'
    final=v.evidence['MTBP'];assert final['status']=='submission_unknown'
    assert final['raw']['analysis_id']=='SOLIDE-DEMO' and 'provisional_status' not in final['raw']
