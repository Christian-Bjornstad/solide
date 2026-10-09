from solide.models import Session,Variant
from solide.assessment import save_assessment
from solide.session import save_session,load_session


def test_manual_assessment_persists_without_changing_source_or_search_identity(tmp_path):
    v=Variant(patient='DEMO',gene='BRCA1',raw={'ClinVar':'Imported annotation'},selected=True)
    s=Session(variants=[v]);identity=v.fingerprint('Other')
    save_assessment(s,v,classification='VUS',decision='Include',reviewer='DEMO reviewer',comment='Reviewed evidence')
    assert v.raw=={'ClinVar':'Imported annotation'} and v.fingerprint('Other')==identity
    path=tmp_path/'demo.solide.json';save_session(s,path);loaded=load_session(path)
    restored=loaded.variants[0]
    assert (restored.classification,restored.report_decision,restored.comment)==('VUS','Include','Reviewed evidence')
    assert restored.reviewed_at and restored.reviewer=='DEMO reviewer'
    save_assessment(loaded,restored,classification='Custom laboratory classification',decision='Exclude',reviewer='DEMO reviewer',comment='Updated')
    event=loaded.history[-1]
    assert event['before']['classification']=='VUS' and event['after']['report_decision']=='Exclude'


def test_legacy_sessions_default_to_pending_assessment(tmp_path):
    import json
    path=tmp_path/'legacy.solide.json'
    path.write_text(json.dumps({'schema_version':1,'variants':[{'id':'demo','patient':'DEMO','gene':'EGFR'}]}))
    v=load_session(path).variants[0]
    assert v.report_decision=='Pending' and not v.classification
