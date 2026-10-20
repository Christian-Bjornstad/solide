from copy import deepcopy
import hashlib

import pytest

from solide.analyses import analysis_scoped_session
from solide.models import Analysis, Session, Variant
from solide.evidence import batch_fingerprint, build_search_plan, evidence_is_current, query_record, run_queue, QueueControl
from solide._vendor.archer.core.models import DatabaseEvidence
from solide._vendor.archer.services.browser_review import BrowserReviewService


def review_session(*, identical=False):
    analyses = [Analysis(id='local-ion', patient='SYNTHETIC-PATIENT', profile='Ion Torrent',
        assay='Childhood', assembly='GRCh37', source_format='Ion Reporter'),
        Analysis(id='local-opa', patient='SYNTHETIC-PATIENT', profile='OPA',
        assay='Oncomine Precision Assay', assembly='GRCh37', source_format='Genexus')]
    variants = [Variant(analysis_id=analysis.id, patient=analysis.patient,
        gene='EGFR', transcript='NM_005228.5', coding='c.2573T>G' if identical or index == 0 else 'c.2582T>A',
        assembly='GRCh37', selected=True, source_file='private.tsv', source_hash=analysis.id)
        for index, analysis in enumerate(analyses)]
    return Session(variants=variants, analyses=analyses)


def test_chosen_mtbp_rerun_expands_only_its_analysis_for_the_same_patient():
    session = review_session()
    first, other = session.variants
    companion = deepcopy(first); companion.id='companion'; companion.coding='c.2155G>A'
    session.variants.append(companion)
    plan = build_search_plan(session, ['MTBP'], 'chosen', {(first.id,'MTBP')})
    assert plan == {(first.id,'MTBP'),(companion.id,'MTBP')}
    assert (other.id,'MTBP') not in plan


def test_identical_variant_sets_in_two_analyses_have_different_mtbp_batches():
    session = review_session(identical=True)
    assert batch_fingerprint(session,'SYNTHETIC-PATIENT','local-ion') != batch_fingerprint(
        session,'SYNTHETIC-PATIENT','local-opa')
    scope = analysis_scoped_session(session,'local-ion')
    assert batch_fingerprint(scope,'SYNTHETIC-PATIENT') == batch_fingerprint(
        session,'SYNTHETIC-PATIENT','local-ion')


def test_unscoped_multi_analysis_batch_cannot_silently_merge_same_patient():
    session = review_session()
    with pytest.raises(ValueError,match='analysis'):
        batch_fingerprint(session,'SYNTHETIC-PATIENT')


def test_mtbp_cache_is_independent_of_selection_in_the_other_analysis():
    session = review_session()
    first, other = session.variants
    cached = dict(database='MTBP', status='not_found', analysis_id=first.analysis_id,
        fingerprint=first.fingerprint('Other'),mtbp_batch=batch_fingerprint(session,first.patient,first.analysis_id))
    other.selected=False
    assert evidence_is_current(first,cached,'Other',session)
    copied = {**cached,'fingerprint':other.fingerprint('Other')}
    assert not evidence_is_current(other,copied,'Other',session)


def test_legacy_mtbp_batch_keeps_old_hash_but_cannot_be_applied_to_a_new_analysis():
    variant=Variant(patient='LEGACY',gene='TP53',selected=True)
    session=Session(variants=[variant])
    expected=hashlib.sha256(variant.fingerprint('Other').encode()).hexdigest()
    assert batch_fingerprint(session,'LEGACY') == expected
    cached=dict(database='MTBP',fingerprint=variant.fingerprint('Other'),mtbp_batch=expected)
    assert evidence_is_current(variant,cached,'Other',session)
    variant.analysis_id='tagged';session.analyses=[Analysis(id='tagged',patient='LEGACY')]
    assert not evidence_is_current(variant,cached,'Other',session)


def test_analysis_tissue_does_not_change_the_other_analysis_cache():
    session=review_session()
    session.tissues={'local-ion':'Brain','local-opa':'Lung','SYNTHETIC-PATIENT':'Other'}
    first,other=session.variants
    cached=dict(database='ClinVar',status='not_found',fingerprint=first.fingerprint('Brain'))
    assert evidence_is_current(first,cached,session.tissue_for(first),session)
    session.tissues['local-opa']='Other'
    assert evidence_is_current(first,cached,session.tissue_for(first),session)
    first.evidence['ClinVar']=cached
    assert build_search_plan(session,['ClinVar']) == {(other.id,'ClinVar')}


@pytest.mark.parametrize('field,value',[('profile','OPA'),('assay','Different assay')])
def test_profile_or_assay_change_invalidates_the_analysis_mtbp_batch(field,value):
    session=review_session()
    first=session.variants[0]
    previous=batch_fingerprint(session,first.patient,first.analysis_id)
    setattr(session.analyses[0],field,value)
    assert batch_fingerprint(session,first.patient,first.analysis_id) != previous


def fake_browser(monkeypatch):
    import solide.evidence as module
    calls=[]
    class Browser:
        def __init__(self,**kwargs):self.kwargs=kwargs
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,records,sources,root,*,progress,checkpoint,prior_evidence=None):
            calls.append(dict(records=list(records),sources=sources,root=root,
                tissue=self.kwargs['mtbp_cancer_type'],prior=prior_evidence))
            checkpoint({self.variant_key(record):[DatabaseEvidence(sources[0],'not_found','No match')]
                for record in records})
    monkeypatch.setattr(module,'BrowserReviewService',Browser)
    return calls


def test_direct_backend_run_keeps_two_analyses_separate_in_batches_captures_and_tissues(monkeypatch,tmp_path):
    session=review_session(identical=True)
    session.tissues={'local-ion':'Brain','local-opa':'Lung'}
    calls=fake_browser(monkeypatch)
    run_queue(session,['MTBP'],tmp_path,QueueControl(),lambda *args:None,lambda message:None)
    assert len(calls)==2 and {call['tissue'] for call in calls} == {'Brain','Lung'}
    assert all(len(call['records'])==1 for call in calls)
    assert len({str(call['root']) for call in calls})==2
    assert all('analyses' in call['root'].parts for call in calls)
    assert len({call['records'][0].sample for call in calls})==1
    for call in calls:
        assert all(secret not in repr(call['records']) for secret in ['SYNTHETIC-PATIENT','local-ion','local-opa','private.tsv'])
    for variant in session.variants:
        evidence=variant.evidence['MTBP']
        assert evidence['analysis_id']==variant.analysis_id
        assert evidence_is_current(variant,evidence,session.tissue_for(variant),session)


def test_recovery_uses_only_the_selected_analysis_previous_submission(monkeypatch,tmp_path):
    session=review_session()
    first,other=session.variants
    for variant in session.variants:
        variant.evidence['MTBP']=dict(database='MTBP',status='submission_unknown',analysis_id=variant.analysis_id,
            fingerprint=variant.fingerprint('Other'),mtbp_batch=batch_fingerprint(session,variant.patient,variant.analysis_id),
            raw={'analysis_id':'SOLIDE-'+variant.analysis_id})
    calls=fake_browser(monkeypatch)
    plan=build_search_plan(session,['MTBP'],'chosen',{(first.id,'MTBP')})
    run_queue(session,['MTBP'],tmp_path,QueueControl(),lambda *args:None,lambda message:None,plan=plan)
    assert len(calls)==1
    prior=next(iter(calls[0]['prior'].values()))[0]
    assert prior.raw['analysis_id']=='SOLIDE-local-ion'
    assert other.evidence['MTBP']['status']=='submission_unknown'


def test_invalid_analysis_patient_boundary_stops_before_any_provider_call(monkeypatch,tmp_path):
    session=review_session();session.variants[0].patient='WRONG-SAMPLE'
    calls=fake_browser(monkeypatch)
    with pytest.raises(ValueError,match='sample'):
        run_queue(session,['ClinVar'],tmp_path,QueueControl(),lambda *args:None,lambda message:None)
    assert not calls


def test_mixed_legacy_and_tagged_analysis_batches_preserve_unbound_row_identity(monkeypatch,tmp_path):
    session=review_session()
    session.variants=session.variants[:1];session.analyses=session.analyses[:1]
    legacy=Variant(patient=session.variants[0].patient,gene='TP53',transcript='NM_000546.6',
        coding='c.818G>A',assembly='GRCh37',selected=True)
    session.variants.append(legacy)
    calls=fake_browser(monkeypatch)
    run_queue(session,['MTBP'],tmp_path,QueueControl(),lambda *args:None,lambda message:None)
    assert len(calls)==2 and legacy.analysis_id==''
    assert len(session.analyses)==1
    expected=hashlib.sha256(legacy.fingerprint('Other').encode()).hexdigest()
    assert legacy.evidence['MTBP']['mtbp_batch']==expected


def test_external_variant_record_does_not_include_analysis_metadata():
    session=review_session();record=query_record(session.variants[0],'MTBP')
    assert record.sample.startswith('S')
    assert all(value not in repr(record) for value in ['local-ion','Childhood','private.tsv','SYNTHETIC-PATIENT'])
