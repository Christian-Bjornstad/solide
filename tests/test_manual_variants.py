from copy import deepcopy
import pytest
from solide.models import Analysis,Session,Variant
import solide.manual_variants as manual


def session():
    source=Variant(id='parent',patient='SAMPLE',analysis_id='a',gene='PTEN,OTHER',
        transcript='NM_000314.8,NR_123456.1',coding='c.19G>A',protein='p.Glu7Lys',
        locus='chr10:89624245',ref='G',alt='A',af_percent=12,coverage=1000,
        variant_id='COSM123',evidence={'COSMIC':{'status':'found'}},selected=True)
    return Session(analyses=[Analysis(id='a',patient='SAMPLE',profile='Ion Torrent',assembly='GRCh37')],variants=[source])


def test_manual_interpretation_has_separate_identity_and_preserves_parents():
    s=session();original=deepcopy(s.variants[0])
    v=manual.add_manual_variant(s,'a',transcript='NM_000314.8',coding='c.19G>A',
        protein='p.Glu7Lys',gene='PTEN',parent_ids=['parent'])
    assert v in s.variants and v.id!='parent' and v.selected
    assert (v.patient,v.analysis_id,v.assembly)==('SAMPLE','a','GRCh37')
    assert (v.ref,v.alt,v.locus,v.variant_id,v.evidence)==('','','','',{})
    assert v.af_percent is None and v.coverage is None
    assert s.variants[0]==original
    assert v.raw['_manual_variant']['parent_ids']==['parent']
    assert not v.nomenclature_verified


def test_transcript_and_coding_suffice_for_entry_without_gene_or_locus(tmp_path):
    from solide.session import save_session,load_session
    s=session()
    v=manual.add_manual_variant(s,'a',transcript='NM_000314.8',coding='c.19G>A')
    assert v.gene==v.locus==''
    path=tmp_path/'session.json';save_session(s,path)
    loaded=load_session(path).variants[-1]
    assert loaded==v


@pytest.mark.parametrize('changes',[
    {'transcript':''},{'transcript':'NM_000314'},{'transcript':'NM_000314.8,NR_123456.1'},
    {'coding':''},{'coding':'c.[19G>A;20G>T]'},{'coding':'c.19G>?'},
    {'coding':'NM_000546.6:c.19G>A'},{'locus':'chr10:wrong'},
    {'protein':'NM_000314.8:c.19G>A'},{'gene':'PTEN,OTHER'},
])
def test_invalid_entry_does_not_add_or_change_any_row(changes):
    s=session();before=deepcopy(s)
    fields=dict(transcript='NM_000314.8',coding='c.19G>A');fields.update(changes)
    with pytest.raises(ValueError):manual.add_manual_variant(s,'a',**fields)
    assert s==before


def test_parent_rows_must_belong_to_the_active_analysis():
    s=session();s.analyses.append(Analysis(id='b',patient='OTHER',profile='OPA'))
    with pytest.raises(ValueError):manual.add_manual_variant(s,'b',transcript='NM_000314.8',coding='c.19G>A',parent_ids=['parent'])
    assert len(s.variants)==1


def test_manual_variant_requires_resolution_before_export_or_query():
    from solide.annotations import require_resolved_annotations,needs_annotation_resolution
    from solide.evidence import query_record
    s=session();v=manual.add_manual_variant(s,'a',transcript='NM_000314.8',coding='c.19G>A')
    assert needs_annotation_resolution(v)
    with pytest.raises(ValueError):require_resolved_annotations(v)
    with pytest.raises(ValueError):query_record(v,'OncoKB')


def test_manual_mapping_is_dispatched_before_database_queries(monkeypatch):
    from test_manual_resolution import PublicHttp,Resolver
    from solide.annotation_resolution import resolve_annotation
    from solide.annotations import annotation_resolution_current
    from solide.evidence import query_record
    s=session();v=manual.add_manual_variant(s,'a',transcript='NM_000314.8',coding='c.1A>T')
    http=PublicHttp();http.close=lambda:None
    monkeypatch.setattr('solide.manual_resolution.public_api_session',lambda:http)
    assert resolve_annotation(v,Resolver())
    assert annotation_resolution_current(v)
    record=query_record(v,'ClinVar')
    assert record.symbol=='PTEN' and record.hgvsc=='NM_000314.8:c.1A>T'
    assert record.genomic_location=='chr10:100'


def test_manual_exact_transcript_does_not_trigger_automatic_mane_replacement():
    from solide.quality import review_reasons
    s=session();v=manual.add_manual_variant(s,'a',transcript='NM_001127500.3',coding='c.1A>T',gene='MET')
    assert 'MANE' not in review_reasons(v)
