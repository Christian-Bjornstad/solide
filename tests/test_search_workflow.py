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
