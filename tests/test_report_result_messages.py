import pytest
from solide.reporting import _vpm_compact,export_analysis
from solide.models import Variant
from test_vpm_analysis_reports import make_session,result,capture,load_workbook


@pytest.mark.parametrize('status,raw,expected',[
    ('timeout',{},'Tidsavbrudd'),('login_required',{},'Innlogging kreves'),
    ('authentication_failed',{},'Innlogging mislyktes'),('unauthorized',{},'Tilgang avvist'),
    ('rate_limited',{},'For mange forespørsler'),('quota_exhausted',{},'Kvoten er brukt opp'),
    ('token_required',{},'API-nøkkel mangler'),('layout_changed',{},'Nettsiden er endret'),
    ('ambiguous_result',{},'Flere mulige treff'),('unsupported_query',{},'Søketypen støttes ikke'),
    ('manual_review',{'failure_kind':'identity_mismatch'},'Variantidentitet ikke bekreftet'),
    ('network_error',{'failure':{'type':'EdgeCdpProfileInUse'}},'Edge-profil i bruk'),
    ('error',{'failure':{'type':'EdgeCdpProfileInUse'}},'Edge-profil i bruk'),
    ('rate_limited',{'failure':{'http_status':429}},'For mange forespørsler'),
    ('unauthorized',{'failure':{'http_status':403}},'Tilgang avvist'),
    ('needs_review',{'blocked_by_annotations':['row']},'Annotasjon uavklart'),
])
def test_problem_cells_state_the_actual_failure(status,raw,expected):
    session,rows=make_session(Variant(gene='NF1',selected=True));v=rows[0]
    v.evidence['OncoKB']=result(v,source='OncoKB',status=status,raw=raw)
    text=_vpm_compact(v,'OncoKB',session)
    assert expected in text and 'Kontroller resultat' not in text


def test_no_cosmic_id_is_skipped_not_silent_no_hit():
    session,rows=make_session(Variant(gene='NF1',selected=True));v=rows[0]
    v.evidence['COSMIC']=result(v,source='COSMIC',status='not_applicable',summary='ingen COSMIC-ID')
    assert _vpm_compact(v,'COSMIC',session)=='COSMIC-ID mangler'


def test_clinvar_cell_keeps_all_aggregate_classification_types(tmp_path):
    session,rows=make_session(Variant(gene='TERT',selected=True));v=rows[0]
    v.evidence['ClinVar']=result(v,capture(tmp_path),source='ClinVar',
        clinical_significance='Conflicting classifications of pathogenicity',
        raw={'screenshots':[{'path':str(capture(tmp_path))}],
             'classifications':{'germline':'Conflicting classifications of pathogenicity',
                'somatic_clinical_impact':'Tier I - Strong','oncogenicity':'Oncogenic'}})
    with load_workbook(export_analysis(session,'analysis-a',tmp_path).report) as book:
        text=book['Oversikt']['K8'].value
        assert text=='Arvelig: Conflicting classifications of pathogenicity\nSomatisk: Tier I - Strong\nOnkogenisitet: Oncogenic'
        heading=next(c for row in book['TERT'] for c in row if str(c.value).startswith('ClinVar –'))
        assert heading.alignment.wrap_text and book['TERT'].row_dimensions[heading.row].height>=48


def test_verified_api_classification_is_retained_when_only_image_is_missing():
    session,rows=make_session(Variant(gene='TERT',selected=True));v=rows[0]
    item=result(v,source='ClinVar',clinical_significance='Conflicting classifications of pathogenicity',
        raw={'assembly_verified':'GRCh37','matched_location':{'position':1295228}})
    v.evidence['ClinVar']=item
    assert _vpm_compact(v,'ClinVar',session)=='Conflicting classifications of pathogenicity\nBilde mangler'
    item['raw']={}
    assert _vpm_compact(v,'ClinVar',session)=='Bilde mangler'


def test_rejected_identity_never_leaks_a_retained_api_classification():
    session,rows=make_session(Variant(gene='TERT',selected=True));v=rows[0]
    v.evidence['ClinVar']=result(v,source='ClinVar',status='error',clinical_significance='Pathogenic',
        raw={'assembly_verified':'GRCh37','matched_location':{'position':1295228},
             'failure_stage':'result_rendering','identity_verification':{'accepted':False}})
    assert _vpm_compact(v,'ClinVar',session)=='Feil variant – treff utelatt'


def test_genomic_oncokb_hit_after_normalization_is_exported_with_image(tmp_path):
    from dataclasses import asdict
    from vendor.test_oncokb_genomic_identity import nf1,BODY,URL
    from solide._vendor.archer.services.browser_review import parse_oncokb_page
    session,rows=make_session(Variant(gene='NF1',transcript='NM_001042492.3',coding='c.6147+2T>A',
        corrected_hgvs='NC_000017.10(NM_001042492.3):c.6147+2T>A',nomenclature_verified=True,
        locus='chr17:29663493',ref='T',alt='A',assembly='GRCh37',selected=True))
    v=rows[0];item=asdict(parse_oncokb_page(BODY,nf1(),URL))
    item['raw']['screenshots']=[{'path':str(capture(tmp_path))}]
    item['fingerprint']=v.fingerprint('Other');v.evidence['OncoKB']=item
    with load_workbook(export_analysis(session,'analysis-a',tmp_path).report) as book:
        assert book['Oversikt']['I8'].value=='Likely Oncogenic'
        assert len(book['NF1']._images)==1
        assert v.coding=='c.6147+2T>A' and v.protein==''


def test_retained_oncokb_answer_is_retryable_and_exported_when_only_capture_failed(tmp_path, monkeypatch):
    from dataclasses import asdict
    from types import SimpleNamespace
    from vendor.test_oncokb_genomic_identity import nf1,BODY,URL
    from solide._vendor.archer.services import browser_review
    from solide.evidence import assess_evidence,build_search_plan
    session,rows=make_session(Variant(gene='NF1',transcript='NM_001042492.3',coding='c.6147+2T>A',
        locus='chr17:29663493',ref='T',alt='A',assembly='GRCh37',selected=True))
    page=SimpleNamespace(url=URL,locator=lambda _:SimpleNamespace(inner_text=lambda **_:BODY))
    service=browser_review.BrowserReviewService(profile_root=tmp_path)
    monkeypatch.setattr(browser_review,'dismiss_known_overlays',lambda _:None)
    monkeypatch.setattr(service,'_reject_oncokb_cookies',lambda _:None)
    def failed(*args,**kwargs):raise TimeoutError('Capture timeout')
    monkeypatch.setattr(browser_review,'capture_source_panel',failed)
    item=asdict(service._capture_result('OncoKB',nf1(),page,tmp_path))
    v=rows[0];item['fingerprint']=v.fingerprint('Other');v.evidence['OncoKB']=item
    assert assess_evidence(v,item,session).label=='Missing capture'
    assert build_search_plan(session,['OncoKB'],mode='failed')=={(v.id,'OncoKB')}
    with load_workbook(export_analysis(session,'analysis-a',tmp_path).report) as book:
        assert book['Oversikt']['I8'].value=='Likely Oncogenic\nBilde mangler'
        assert not book['NF1']._images
