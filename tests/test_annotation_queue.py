"""Annotation resolution is mandatory before every selected provider request."""
from copy import deepcopy
import os

import pytest

from solide.models import Session,Variant
from solide._vendor.archer.core.models import DatabaseEvidence
from solide._vendor.archer.services.browser_review import BrowserReviewService,BrowserReviewCancelled


def candidate(**changes):
    values=dict(patient='00OUM00001',gene='TP53',transcript='NM_000546.6',
        coding='c.375+1G>A',locus='chr17:7578554',ref='C',alt='T',assembly='GRCh37',
        selected=True,source_file='synthetic.tsv',source_hash='synthetic',source_row=2,
        raw={'_annotation_group':{'parent_id':'source-parent','count':2,'index':0},
             '_columns':['Genes'],'_values':['TP53,OTHER']})
    values.update(changes)
    return Variant(**values)


def services(monkeypatch,*,resolved=True,changed_gene=None,stop=None):
    import solide.annotations as annotations
    import solide.evidence as module
    resolutions=[];browser=[];identities=[];events=[]
    def needs(v):return bool(v.raw.get('_annotation_group'))
    def current(v):
        proof=v.raw.get('_annotation_resolution',{})
        return proof.get('status')=='verified' and proof.get('fingerprint')==v.fingerprint('')
    def require(v):
        if needs(v) and not current(v):raise ValueError('Uavklart annotasjon')
    for owner in (annotations,module):
        monkeypatch.setattr(owner,'needs_annotation_resolution',needs)
        monkeypatch.setattr(owner,'annotation_resolution_current',current)
    monkeypatch.setattr(annotations,'require_resolved_annotations',require)
    class Resolver:
        def __init__(self,**kwargs):self.checkpoint=kwargs['checkpoint'];identities.append(self)
        def __enter__(self):return self
        def __exit__(self,*args):events.append('closed')
    def resolve(v,resolver,checkpoint):
        checkpoint();resolutions.append(v.id)
        if stop:stop()
        checkpoint()
        if resolved and changed_gene:v.gene=changed_gene
        v.raw['_annotation_resolution']={'status':'verified' if resolved else 'unresolved',
            'reason':'Kontroller annotasjonene' if not resolved else '',
            'fingerprint':v.fingerprint('')}
        return resolved
    class Browser:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,records,sources,root,*,progress,checkpoint,prior_evidence=None):
            events.append('provider');browser.append((sources[0],list(records)))
            checkpoint({self.variant_key(record):[DatabaseEvidence(sources[0],'not_found','No match')]
                for record in records})
    monkeypatch.setattr(module,'TranscriptIdentityResolver',Resolver)
    monkeypatch.setattr(module,'resolve_annotation',resolve)
    monkeypatch.setattr(module,'BrowserReviewService',Browser)
    monkeypatch.setattr(module,'spliceai_variant',lambda v:pytest.fail('Unresolved SpliceAI request'))
    monkeypatch.setattr(module,'brca_exchange_variant',lambda v:pytest.fail('Unresolved BRCA request'))
    def normalize(v):
        if needs(v):pytest.fail('Unresolved Mutalyzer request')
        return {'normalization':{'errors':['Synthetic validation rejection']}}
    monkeypatch.setattr(module,'normalize_variant',normalize)
    return module,resolutions,browser,identities,events


def test_selected_resolution_runs_even_without_mutalyzer_and_emits_identity_first(monkeypatch,tmp_path):
    module,resolutions,browser,resolvers,events=services(monkeypatch)
    chosen=candidate();other=candidate(selected=False);before=deepcopy(other)
    session=Session(variants=[chosen,other]);updates=[]
    def identity(row_id,payload):
        events.append('identity');updates.append((row_id,payload))
    module.run_queue(session,['ClinVar'],tmp_path,module.QueueControl(),lambda *args:events.append('evidence'),
        lambda message:None,identity_resolved=identity)
    assert resolutions==[chosen.id] and len(resolvers)==1 and other==before
    assert browser[0][0]=='ClinVar' and len(browser[0][1])==1
    assert events.index('identity')<events.index('provider')<events.index('evidence')
    assert updates[0][0]==chosen.id and updates[0][1]['variant'] is not chosen
    assert chosen.evidence['ClinVar']['annotation_resolution']['fingerprint']==chosen.raw['_annotation_resolution']['fingerprint']
    assert module.evidence_is_current(chosen,chosen.evidence['ClinVar'],'Other',session)


def test_unresolved_annotations_block_all_providers_and_whole_mtbp_batch(monkeypatch,tmp_path):
    module,resolutions,browser,resolvers,_=services(monkeypatch,resolved=False)
    unresolved=candidate(gene='BRCA1')
    ordinary=Variant(patient=unresolved.patient,gene='TP53',transcript='NM_000546.6',coding='c.215C>G',
        assembly='GRCh37',selected=True)
    session=Session(variants=[unresolved,ordinary])
    sources=['SpliceAI','BRCA Exchange','Mutalyzer','MTBP','ClinVar']
    module.run_queue(session,sources,tmp_path,module.QueueControl(),lambda *args:None,lambda message:None)
    assert resolutions==[unresolved.id] and len(resolvers)==1
    assert all(unresolved.evidence[source]['status']=='needs_review' for source in sources)
    assert ordinary.evidence['MTBP']['status']=='needs_review'
    assert not any(source=='MTBP' for source,_ in browser)
    assert [(source,len(records)) for source,records in browser]==[('ClinVar',1)]


def test_cancellation_during_resolution_preserves_identity_and_queries_nothing(monkeypatch,tmp_path):
    import solide.evidence as module
    control=module.QueueControl()
    _,_,browser,_,events=services(monkeypatch,stop=control.stopped.set)
    row=candidate();before=deepcopy(row);updates=[]
    with pytest.raises(BrowserReviewCancelled):
        module.run_queue(Session(variants=[row]),['ClinVar'],tmp_path,control,lambda *args:None,
            lambda message:None,identity_resolved=lambda *args:updates.append(args))
    assert row==before and not browser and not updates and events==['closed']


def test_pending_brca_candidate_is_resolved_before_source_applicability(monkeypatch,tmp_path):
    module,_,browser,_,_=services(monkeypatch,changed_gene='TP53')
    row=candidate(gene='UNKNOWN');session=Session(variants=[row])
    assert module.build_search_plan(session,['BRCA Exchange'])=={(row.id,'BRCA Exchange')}
    module.run_queue(session,['BRCA Exchange'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None)
    assert row.gene=='TP53' and row.evidence['BRCA Exchange']['status']=='not_applicable' and not browser


def test_resolution_change_invalidates_old_results_even_without_name_change(monkeypatch,tmp_path):
    module,_,_,_,_=services(monkeypatch)
    row=candidate();session=Session(variants=[row])
    old={'database':'ClinVar','status':'not_found','fingerprint':row.fingerprint('Other')}
    row.evidence['ClinVar']=old
    assert not module.evidence_is_current(row,old,'Other',session)
    module.run_queue(session,['ClinVar'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None)
    assert not module.evidence_is_current(row,old,'Other',session)
    assert module.evidence_is_current(row,row.evidence['ClinVar'],'Other',session)


def test_resolution_expands_mtbp_and_checks_newly_requested_companion_with_same_resolver(monkeypatch,tmp_path):
    module,resolutions,browser,resolvers,_=services(monkeypatch)
    first=candidate();companion=candidate(coding='c.376G>A',source_row=3)
    session=Session(variants=[first,companion]);changes=[]
    module.run_queue(session,['ClinVar','MTBP'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,
        plan={(first.id,'ClinVar')},plan_changed=changes.append)
    assert resolutions==[first.id,companion.id] and len(resolvers)==1
    assert {source for source,_ in browser}=={'ClinVar','MTBP'}
    assert len(next(records for source,records in browser if source=='MTBP'))==2
    assert all((row.id,'MTBP') in changes[-1] for row in session.variants)


def test_chosen_scope_resolves_only_the_requested_child(monkeypatch,tmp_path):
    module,resolutions,browser,resolvers,_=services(monkeypatch)
    first=candidate();other=candidate(coding='c.376G>A',source_row=3);before=deepcopy(other)
    module.run_queue(Session(variants=[first,other]),['ClinVar','MTBP'],tmp_path,module.QueueControl(),
        lambda *args:None,lambda message:None,plan={(first.id,'ClinVar')},expand_after_normalization=False)
    assert resolutions==[first.id] and len(resolvers)==1 and other==before
    assert [(source,len(records)) for source,records in browser]==[('ClinVar',1)]


def test_resolution_connection_failure_is_contained_to_selected_candidate(monkeypatch,tmp_path):
    import requests
    module,_,browser,_,events=services(monkeypatch)
    first=candidate();ordinary=Variant(patient=first.patient,gene='EGFR',transcript='NM_005228.5',
        coding='c.2573T>G',selected=True,assembly='GRCh37')
    before=deepcopy(first)
    def fail(*args,**kwargs):raise requests.ConnectionError('Synthetic service unavailable')
    monkeypatch.setattr(module,'resolve_annotation',fail)
    module.run_queue(Session(variants=[first,ordinary]),['ClinVar'],tmp_path,module.QueueControl(),
        lambda *args:None,lambda message:None)
    assert first.gene==before.gene and first.coding==before.coding and first.raw['_values']==before.raw['_values']
    assert first.evidence['ClinVar']['status']=='needs_review'
    assert browser[0][1][0].symbol=='EGFR' and 'closed' in events


def test_retry_failed_recovers_the_whole_mtbp_batch_after_transient_annotation_outage(monkeypatch,tmp_path):
    module,_,browser,_,_=services(monkeypatch)
    overlap=candidate();ordinary=Variant(patient=overlap.patient,gene='EGFR',transcript='NM_005228.5',
        coding='c.2573T>G',selected=True,assembly='GRCh37')
    session=Session(variants=[overlap,ordinary]);offline=True
    def resolve(row,resolver,checkpoint):
        if offline:
            row.raw['_annotation_resolution']={'status':'unresolved','retryable':True,'reason':'Mutalyzer: nettverksfeil.'}
            return False
        row.raw['_annotation_resolution']={'status':'verified','fingerprint':row.fingerprint('')}
        return True
    monkeypatch.setattr(module,'resolve_annotation',resolve)
    module.run_queue(session,['MTBP'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None)
    assert not browser
    assert 'NM_000546.6' in ordinary.evidence['MTBP']['summary']
    retry=module.build_search_plan(session,['MTBP'],'failed')
    assert retry=={(overlap.id,'MTBP'),(ordinary.id,'MTBP')}
    offline=False
    module.run_queue(session,['MTBP'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None,plan=retry)
    assert len(browser)==1 and len(browser[0][1])==2


def test_mtbp_does_not_submit_a_partial_batch_when_one_query_is_invalid(monkeypatch,tmp_path):
    module,_,browser,_,_=services(monkeypatch)
    first=candidate();invalid=Variant(patient=first.patient,gene='TP53',selected=True,assembly='GRCh37')
    session=Session(variants=[first,invalid])
    module.run_queue(session,['MTBP'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None)
    assert not browser
    assert all(row.evidence['MTBP']['status']=='needs_review' for row in session.variants)


def test_gui_applies_worker_identity_before_accepting_fresh_evidence(monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PyQt6.QtWidgets import QApplication
    import solide.gui as gui
    module,_,_,_,_=services(monkeypatch)
    monkeypatch.setattr(gui,'annotation_resolution_current',module.annotation_resolution_current)
    app=QApplication.instance() or QApplication([]);view=gui.MainWindow()
    original=candidate();worker=deepcopy(original);worker.gene='BRCA1'
    worker.raw['_annotation_resolution']={'status':'verified','fingerprint':worker.fingerprint('')}
    view.session=Session(variants=[original]);view.variant_model.set_variants(view.session.variants)
    payload={'variant':worker,'input_fingerprint':original.fingerprint(''),'analysis_id':original.analysis_id}
    try:
        view.accept_identity_resolution(original.id,payload)
        assert original.gene=='BRCA1' and original.selected
        assert original.raw['_values']==['TP53,OTHER']
        item={'database':'ClinVar','status':'not_found','fingerprint':worker.fingerprint('Other'),
              'annotation_resolution':module._annotation_evidence_stamp(worker)}
        view.accept_evidence(original.id,'ClinVar',item)
        assert module.evidence_is_current(original,original.evidence['ClinVar'],'Other',view.session)
        stale=deepcopy(payload);stale['variant'].gene='OTHER';stale['variant'].raw['_annotation_resolution']['fingerprint']='invalid'
        view.accept_identity_resolution(original.id,stale)
        assert original.gene=='BRCA1'
        wrong_source={'variant':deepcopy(original),'input_fingerprint':original.fingerprint(''),'analysis_id':original.analysis_id}
        wrong_source['variant'].source_hash='another-file'
        wrong_source['variant'].gene='WRONG'
        view.accept_identity_resolution(original.id,wrong_source)
        assert original.gene=='BRCA1'
    finally:view.close()
