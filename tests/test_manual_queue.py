"""A manual HGVS row takes the complete queue-to-report path without a locus."""
from copy import deepcopy
from contextlib import closing
from openpyxl import load_workbook
from test_manual_resolution import PublicHttp,Resolver
from solide.models import Session,Analysis
from solide.manual_variants import add_manual_variant
from solide.annotations import annotation_resolution_current
from solide._vendor.archer.core.models import DatabaseEvidence
from solide._vendor.archer.services.browser_review import BrowserReviewService


def test_no_locus_manual_variant_is_mapped_before_provider_and_export(monkeypatch,tmp_path):
    import solide.evidence as evidence
    from solide.reporting import export_analysis
    s=Session(analyses=[Analysis(id='a',patient='PRIVATE-SAMPLE',profile='Ion Torrent',assembly='GRCh37')])
    v=add_manual_variant(s,'a',transcript='NM_000314.8',coding='c.1A>T',protein='p.Manual')
    http=PublicHttp();http.close=lambda:None
    monkeypatch.setattr('solide.manual_resolution.public_api_session',lambda:http)
    class References(Resolver):
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(evidence,'TranscriptIdentityResolver',References)
    records=[];updates=[]
    class Browser:
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def __init__(self,**kwargs):pass
        def search_variants(self,variants,sources,root,*,progress,checkpoint,**kwargs):
            records.extend(variants)
            assert annotation_resolution_current(v)
            checkpoint({self.variant_key(record):[DatabaseEvidence('ClinVar','not_found','No match')]
                        for record in variants})
    monkeypatch.setattr(evidence,'BrowserReviewService',Browser)
    evidence.run_queue(s,['ClinVar'],tmp_path,evidence.QueueControl(),lambda *args:None,
        lambda message:None,identity_resolved=lambda *args:updates.append(deepcopy(args)))
    assert len(records)==len(updates)==1
    assert records[0].genomic_location=='chr10:100'
    assert records[0].hgvsp=='p.(Met1Leu)'
    assert evidence.evidence_is_current(v,v.evidence['ClinVar'],'Other',s)
    assert 'PRIVATE-SAMPLE' not in str(http.calls)
    with closing(load_workbook(export_analysis(s,'a',tmp_path).report)) as book:
        assert book['Oversikt']['E8'].value=='NM_000314.8(PTEN): c.1A>T; p.Met1Leu'
        assert book['PTEN']['B4'].value==book['Oversikt']['E8'].value
        raw=list(book['Rådata'].values)
        origin=raw[0].index('Origin');coding=raw[0].index('Coding')
        assert raw[1][origin]=='Manuelt registrert' and raw[1][coding]=='c.1A>T'
        provenance='\n'.join(str(cell.value) for row in book['Kilder'] for cell in row if cell.value is not None)
        assert '"independent_source_alleles": false' in provenance
        assert '"created_at":' in provenance and '"parent_ids":' in provenance


def test_unresolved_manual_row_blocks_provider_and_retains_inputs(monkeypatch,tmp_path):
    import solide.evidence as evidence
    s=Session(analyses=[Analysis(id='a',patient='SAMPLE',profile='Ion Torrent',assembly='GRCh37')])
    v=add_manual_variant(s,'a',transcript='NM_000314.8',coding='c.1A>T',gene='WRONG')
    before=deepcopy(v)
    class References(Resolver):
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(evidence,'TranscriptIdentityResolver',References)
    monkeypatch.setattr('solide.manual_resolution.public_api_session',lambda:(_ for _ in ()).throw(AssertionError('Gene mismatch before HTTP')))
    class Browser:
        def __init__(self,**kwargs):pass
        def search_variants(self,*args,**kwargs):raise AssertionError('Unresolved manual variant queried')
    monkeypatch.setattr(evidence,'BrowserReviewService',Browser)
    evidence.run_queue(s,['ClinVar'],tmp_path,evidence.QueueControl(),lambda *args:None,lambda message:None)
    assert v.evidence['ClinVar']['status']=='needs_review'
    assert v.gene==before.gene and v.coding==before.coding and v.ref=='' and v.alt==''
    assert v.raw['_manual_variant']==before.raw['_manual_variant']


def test_mutalyzer_verifies_already_mapped_manual_name_on_first_run_and_rerun(monkeypatch,tmp_path):
    import solide.evidence as evidence
    from solide.manual_resolution import resolve_manual_variant
    from solide.report_identity import report_variant_text
    s=Session(analyses=[Analysis(id='a',patient='SAMPLE',profile='Ion Torrent',assembly='GRCh37')])
    v=add_manual_variant(s,'a',transcript='NM_000314.8',coding='c.1A>T')
    assert resolve_manual_variant(v,Resolver(),http=PublicHttp())
    data=deepcopy(v.raw['_annotation_resolution']['normalization'])
    monkeypatch.setattr(evidence,'normalize_variant',lambda *args,**kwargs:deepcopy(data))
    monkeypatch.setattr(evidence,'capture_mutalyzer',lambda *args,**kwargs:None)
    for _ in range(2):
        evidence.run_queue(s,['Mutalyzer'],tmp_path,evidence.QueueControl(),lambda *args:None,
            lambda message:None,plan={(v.id,'Mutalyzer')})
        assert v.evidence['Mutalyzer']['status']=='verified'
        assert evidence.evidence_is_current(v,v.evidence['Mutalyzer'],'Other',s)
        assert report_variant_text(v,s)=='NM_000314.8(PTEN): c.1A>T; p.Met1Leu'
