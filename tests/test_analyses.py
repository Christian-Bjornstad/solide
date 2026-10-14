from copy import deepcopy
from dataclasses import asdict
import json

import pytest

from solide.analyses import add_analysis, analysis_scoped_session, ensure_analyses
from solide.models import Analysis, ImportResult, Session, Variant
from solide.session import load_session, save_session


def imported_source(source='source.tsv', source_hash='source-sha', platform='Genexus'):
    return ImportResult(variants=[Variant(id='original-row', gene='EGFR', source_file=source,
        source_hash=source_hash, source_row=2, platform=platform, raw={'Gene':'EGFR'})],
        metadata={'workflowName':'Source workflow'}, assembly='Unknown')


def test_two_files_for_one_sample_are_independent_analyses():
    session=Session()
    a=add_analysis(session,imported_source(),'SAMPLE','GRCh37','OPA','Precision')
    b=add_analysis(session,imported_source('other.tsv','other-sha','Ion Reporter'),
                   'SAMPLE','GRCh37','Ion Torrent','Childhood')
    assert a.id!=b.id and session.patients==['SAMPLE']
    assert session.analysis(a.id) is a and session.analysis(b.id) is b
    assert len(session.analysis_variants(a.id))==len(session.analysis_variants(b.id))==1
    assert all(v.analysis_id==a.id for v in session.analysis_variants(a.id))
    assert session.schema_version==2


def test_identical_bytes_for_distinct_samples_do_not_collide_or_rebind_source():
    source=imported_source();original=asdict(source)
    session=Session()
    a=add_analysis(session,source,'SAMPLE-A','Unknown','OPA','Unknown')
    b=add_analysis(session,source,'SAMPLE-B','Unknown','OPA','Unknown')
    assert a.id!=b.id and a.source_hash==b.source_hash
    rows=session.analysis_variants(a.id)+session.analysis_variants(b.id)
    assert len({v.id for v in rows})==2
    assert [v.patient for v in rows]==['SAMPLE-A','SAMPLE-B']
    assert all(v.raw['_source_row_id']=='original-row' for v in rows)
    assert asdict(source)==original


def test_import_binding_preserves_metadata_and_does_not_confirm_missing_assembly():
    source=imported_source();source.metadata['nested']={'value':['original']}
    session=Session()
    analysis=add_analysis(session,source,'SAMPLE','Unknown','OPA','')
    assert analysis.profile=='OPA' and analysis.assay=='Unknown'
    assert analysis.source_format=='Genexus' and analysis.source_file=='source.tsv'
    assert analysis.metadata==source.metadata and analysis.metadata is not source.metadata
    assert analysis.assembly==session.analysis_variants(analysis.id)[0].assembly=='Unknown'
    analysis.metadata['nested']['value'].append('edited')
    assert source.metadata['nested']['value']==['original']


@pytest.mark.parametrize('patient,assembly,profile', [
    ('','GRCh37','OPA'),('SAMPLE','hg19','OPA'),('SAMPLE','GRCh37','Guessed profile')])
def test_invalid_binding_fails_without_mutating_session_or_source(patient,assembly,profile):
    source=imported_source();session=Session()
    original=asdict(source)
    with pytest.raises(ValueError):
        add_analysis(session,source,patient,assembly,profile,'Unknown')
    assert not session.variants and not session.analyses and asdict(source)==original


def test_one_import_cannot_hide_multiple_original_source_files():
    source=imported_source()
    source.variants.append(Variant(id='second',source_file='other.tsv',source_hash='other-sha'))
    session=Session()
    with pytest.raises(ValueError,match='one source'):
        add_analysis(session,source,'SAMPLE','GRCh37','OPA','Unknown')
    assert not session.analyses and not session.variants


def test_unknown_analysis_is_an_error_rather_than_all_patient_rows():
    session=Session()
    with pytest.raises(ValueError,match='Unknown analysis'):
        session.analysis('missing')
    with pytest.raises(ValueError,match='Unknown analysis'):
        session.analysis_variants('missing')


def legacy_payload(variants):
    rows=[]
    for variant in variants:
        row=asdict(variant);row.pop('analysis_id',None);rows.append(row)
    return dict(schema_version=1,variants=rows,tissues={'SAMPLE':'Other'},history=[{'event':'original'}])


def test_legacy_migration_separates_sources_and_preserves_ids_clinical_fields_and_evidence(tmp_path):
    variants=[Variant(id=f'row-{i}',patient='SAMPLE',source_file=source,source_hash=source,
        platform=platform,assembly='GRCh37',gene='EGFR',coding='c.1A>T',selected=True,
        comment='Original review',classification='Original classification',report_decision='Include',
        reviewer='Reviewer',corrected_hgvs='NM_005228.5:c.1A>T',nomenclature_verified=True,
        evidence={'ClinVar':{'status':'found','fingerprint':'retained','raw':{'private':'original'}}})
        for i,(source,platform) in enumerate([('first.tsv','Ion Reporter'),('first.tsv','Ion Reporter'),
                                             ('other.tsv','Genexus')])]
    expected=[asdict(v) for v in variants]
    fingerprints=[v.fingerprint('Other') for v in variants]
    path=tmp_path/'legacy.json';path.write_text(json.dumps(legacy_payload(variants)),encoding='utf8')
    session=load_session(path)
    assert session.schema_version==2 and len(session.analyses)==2
    assert [a.profile for a in session.analyses]==['Ion Torrent','Unassigned']
    assert all(a.assay=='Unknown' for a in session.analyses)
    for variant,old,fingerprint in zip(session.variants,expected,fingerprints):
        actual=asdict(variant);actual.pop('analysis_id');old.pop('analysis_id')
        assert actual==old and variant.fingerprint('Other')==fingerprint
    assert session.history==[{'event':'original'}] and session.tissue('SAMPLE')=='Other'
    assert len(session.analysis_variants(session.analyses[0].id))==2


def test_legacy_same_source_bytes_for_different_sample_bindings_are_separate(tmp_path):
    variants=[Variant(id=str(i),patient=patient,source_file='same.tsv',source_hash='same-sha',platform='Genexus')
              for i,patient in enumerate(['A','B'])]
    path=tmp_path/'legacy.json';path.write_text(json.dumps(legacy_payload(variants)),encoding='utf8')
    session=load_session(path)
    assert len(session.analyses)==2 and len({v.analysis_id for v in session.variants})==2
    assert [a.patient for a in session.analyses]==['A','B']


def test_unbound_legacy_rows_are_not_assigned_to_another_sample(tmp_path):
    variants=[Variant(id='bound',patient='SAMPLE',source_file='sample.tsv'),
              Variant(id='unbound',source_file='unbound.tsv',platform='Genexus')]
    path=tmp_path/'legacy.json';path.write_text(json.dumps(legacy_payload(variants)),encoding='utf8')
    session=load_session(path)
    unbound=session.analysis(session.variants[1].analysis_id)
    assert unbound.patient=='' and unbound.profile=='Unassigned'
    assert session.patients==['SAMPLE']


def test_legacy_retained_metadata_is_preserved_without_inventing_an_assay(tmp_path):
    metadata={'workflowName':'Oncomine Childhood','analysisName':'Original analysis'}
    v=Variant(id='row',patient='SAMPLE',platform='Ion Reporter',raw={'_source_metadata':metadata})
    path=tmp_path/'legacy.json';path.write_text(json.dumps(legacy_payload([v])),encoding='utf8')
    session=load_session(path)
    assert session.analyses[0].metadata==metadata
    assert session.analyses[0].assay=='Oncomine Childhood'


def test_save_and_reload_preserves_analysis_ids_and_source_metadata(tmp_path):
    session=Session();analysis=add_analysis(session,imported_source(),'SAMPLE','GRCh37','OPA','Precision')
    before=asdict(session)
    path=tmp_path/'session.json';save_session(session,path)
    restored=load_session(path)
    assert asdict(restored)==before
    assert json.loads(path.read_text(encoding='utf8'))['schema_version']==2
    assert restored.analysis(analysis.id).metadata['workflowName']=='Source workflow'


def test_save_materializes_analysis_boundary_for_existing_in_memory_rows(tmp_path):
    session=Session(variants=[Variant(id='old',patient='SAMPLE',platform='Genexus')])
    before_fingerprint=session.variants[0].fingerprint('Other')
    path=tmp_path/'session.json';save_session(session,path)
    restored=load_session(path)
    assert len(session.analyses)==len(restored.analyses)==1
    assert restored.variants[0].id=='old' and restored.variants[0].analysis_id
    assert restored.variants[0].fingerprint('Other')==before_fingerprint
    assert restored.analyses[0].profile=='Unassigned'


@pytest.mark.parametrize('invalid', ['duplicate_analysis','dangling_variant','patient_conflict','invalid_profile','duplicate_variant'])
def test_invalid_analysis_boundaries_are_rejected_on_load(tmp_path,invalid):
    session=Session();analysis=add_analysis(session,imported_source(),'SAMPLE','GRCh37','OPA','Precision')
    data=asdict(session)
    if invalid=='duplicate_analysis':data['analyses'].append(deepcopy(data['analyses'][0]))
    elif invalid=='dangling_variant':data['variants'][0]['analysis_id']='missing'
    elif invalid=='patient_conflict':data['variants'][0]['patient']='ANOTHER'
    elif invalid=='invalid_profile':data['analyses'][0]['profile']='Guessed'
    elif invalid=='duplicate_variant':data['variants'].append(deepcopy(data['variants'][0]))
    path=tmp_path/'invalid.json';path.write_text(json.dumps(data),encoding='utf8')
    with pytest.raises(ValueError):load_session(path)


def test_ensure_analyses_is_idempotent_and_keeps_assigned_rows_in_their_analysis():
    session=Session();analysis=add_analysis(session,imported_source(),'SAMPLE','GRCh37','OPA','Precision')
    before=asdict(session)
    ensure_analyses(session);ensure_analyses(session)
    assert asdict(session)==before and session.analysis(analysis.id) is analysis


def test_reimport_same_sample_hash_profile_and_assay_reuses_analysis_without_duplicate_rows():
    source=imported_source();session=Session()
    first=add_analysis(session,source,'SAMPLE','GRCh37','OPA','Precision')
    original=asdict(session)
    second=add_analysis(session,source,'SAMPLE','GRCh37','OPA','Precision')
    assert second is first and asdict(session)==original


@pytest.mark.parametrize('profile,assay',[('Ion Torrent','Precision'),('OPA','Other assay')])
def test_different_profile_or_assay_does_not_silently_reuse_source_analysis(profile,assay):
    source=imported_source();session=Session()
    first=add_analysis(session,source,'SAMPLE','GRCh37','OPA','Precision')
    second=add_analysis(session,source,'SAMPLE','GRCh37',profile,assay)
    assert first.id!=second.id and len(session.variants)==2
    assert len({v.id for v in session.variants})==2


def test_reimport_cannot_silently_change_existing_assembly():
    source=imported_source();session=Session()
    add_analysis(session,source,'SAMPLE','Unknown','OPA','Precision')
    before=asdict(session)
    with pytest.raises(ValueError,match='different assembly'):
        add_analysis(session,source,'SAMPLE','GRCh37','OPA','Precision')
    assert asdict(session)==before


def test_analysis_tissues_override_shared_sample_preferences_and_roundtrip(tmp_path):
    source=imported_source();session=Session(tissues={'SAMPLE':'Other'})
    a=add_analysis(session,source,'SAMPLE','GRCh37','OPA','Precision')
    b=add_analysis(session,source,'SAMPLE','GRCh37','Ion Torrent','Childhood')
    session.tissues[a.id]='Lung';session.tissues[b.id]='Breast'
    assert session.tissue('SAMPLE')=='Other'
    assert session.tissue_for(session.analysis_variants(a.id)[0])=='Lung'
    assert session.tissue_for(session.analysis_variants(b.id)[0])=='Breast'
    path=tmp_path/'tissues.json';save_session(session,path)
    restored=load_session(path)
    assert restored.tissue_for(restored.analysis_variants(a.id)[0])=='Lung'
    assert restored.tissue_for(restored.analysis_variants(b.id)[0])=='Breast'
    assert restored.tissue_for(Variant(patient='SAMPLE'))=='Other'


def test_scoped_session_retains_all_analysis_rows_and_same_objects_without_other_dataset():
    source=imported_source();source.variants.append(Variant(id='unselected',gene='MET',
        source_file='source.tsv',source_hash='source-sha',platform='Genexus',selected=False))
    session=Session(tissues={'SAMPLE':'Other','ANOTHER':'Private tissue'})
    a=add_analysis(session,source,'SAMPLE','GRCh37','OPA','Precision')
    b=add_analysis(session,source,'SAMPLE','GRCh37','Ion Torrent','Childhood')
    session.tissues[a.id]='Lung';session.tissues[b.id]='Breast'
    scoped=analysis_scoped_session(session,a.id)
    assert scoped.analyses==[a] and scoped.analyses[0] is a
    assert len(scoped.variants)==2
    assert all(actual is original for actual,original in zip(scoped.variants,session.analysis_variants(a.id)))
    assert scoped.tissues=={'SAMPLE':'Lung',a.id:'Lung'}
    assert scoped.tissue('SAMPLE')==scoped.tissue_for(scoped.variants[0])=='Lung'
    scoped.variants[0].comment='Shared assessment'
    assert session.analysis_variants(a.id)[0].comment=='Shared assessment'
    assert session.analysis_variants(b.id)[0].comment==''


def test_empty_analysis_cannot_be_projected_as_a_complete_source():
    analysis=Analysis(patient='SAMPLE',profile='OPA')
    session=Session(analyses=[analysis])
    with pytest.raises(ValueError,match='No source rows'):
        analysis_scoped_session(session,analysis.id)


def test_analysis_projection_rejects_conflicting_row_sample():
    session=Session();analysis=add_analysis(session,imported_source(),'SAMPLE','GRCh37','OPA','Precision')
    session.variants[0].patient='OTHER'
    with pytest.raises(ValueError,match='differs'):
        analysis_scoped_session(session,analysis.id)


def test_analysis_projection_does_not_bind_unrelated_legacy_rows():
    session=Session();analysis=add_analysis(session,imported_source(),'SAMPLE','GRCh37','OPA','Precision')
    legacy=Variant(id='legacy',patient='ANOTHER')
    session.variants.append(legacy)
    before=asdict(session)
    scoped=analysis_scoped_session(session,analysis.id)
    assert asdict(session)==before and legacy.analysis_id==''
    assert len(scoped.variants)==1 and scoped.variants[0] is session.variants[0]


def test_legacy_migration_separates_different_assemblies_for_one_source(tmp_path):
    variants=[Variant(id=str(index),patient='SAMPLE',source_file='same.tsv',source_hash='same-sha',
        platform='Ion Reporter',assembly=assembly,comment='Original review',
        evidence={'ClinVar':{'fingerprint':'retained','summary':'Original evidence'}})
        for index,assembly in enumerate(['GRCh37','GRCh38','Unknown'])]
    path=tmp_path/'mixed-context.json';path.write_text(json.dumps(legacy_payload(variants)),encoding='utf8')
    session=load_session(path)
    assert len(session.analyses)==3 and len({v.analysis_id for v in session.variants})==3
    for v,original in zip(session.variants,variants):
        assert session.analysis(v.analysis_id).assembly==v.assembly==original.assembly
        assert v.id==original.id and v.comment==original.comment and v.evidence==original.evidence
        assert v.fingerprint('Other')==original.fingerprint('Other')
