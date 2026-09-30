import pytest
from solide.models import Variant,Session
from solide.evidence import query_record,evidence_is_current,run_queue,QueueControl
from solide.nomenclature import genomic_query
from solide.quality import review_reasons
from solide.reporting import export_patient
from solide._vendor.archer.services.browser_review import BrowserReviewService
from openpyxl import load_workbook

def test_controlled_hgvs_never_keeps_unverified_original_genomic_alleles():
    v=Variant(patient='DEMO',gene='MET',transcript='NM_000245.4',coding='c.100+101A>T',
              corrected_hgvs='NM_000245.4:c.100+50A>G',nomenclature_verified=True,
              locus='chr7:100',ref='A',alt='T',assembly='GRCh37')
    record=query_record(v)
    assert not record.genomic_location and not record.ref_allele and not record.alt_allele
    assert 'SpliceAI' in review_reasons(v)
    with pytest.raises(ValueError): genomic_query(v)

def test_genomic_only_records_have_distinct_keys():
    records=[query_record(Variant(patient='DEMO',gene='EGFR',locus=f'chr7:{p}',ref='A',alt='T',assembly='GRCh37')) for p in (100,200)]
    assert BrowserReviewService.variant_key(records[0])!=BrowserReviewService.variant_key(records[1])

def test_mtbp_batch_freshness_changes_with_selection():
    a=Variant(patient='DEMO',gene='MET',selected=True)
    b=Variant(patient='DEMO',gene='EGFR',selected=True)
    s=Session(variants=[a,b])
    from solide.evidence import batch_fingerprint
    evidence={'database':'MTBP','fingerprint':a.fingerprint('Other'),
              'mtbp_batch':batch_fingerprint(s,'DEMO')}
    assert evidence_is_current(a,evidence,'Other',s)
    b.selected=False
    assert not evidence_is_current(a,evidence,'Other',s)

def test_report_contains_genome_assembly(tmp_path):
    v=Variant(patient='DEMO',gene='MET',selected=True,assembly='Ukjent')
    w=load_workbook(export_patient(Session(variants=[v]),'DEMO',tmp_path))
    assert any('Genom' in str(c.value) for row in w['Oversikt'] for c in row)
    assert any('Ukjent'==c.value for row in w['Oversikt'] for c in row)

def test_queue_batches_patients_and_preserves_checkpoint(monkeypatch,tmp_path):
    from solide._vendor.archer.core.models import DatabaseEvidence
    import solide.evidence as module
    calls=[];results=[]
    class FakeService:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,records,sources,root,progress,checkpoint):
            calls.append((sources,[r.sample for r in records]))
            checkpoint({self.variant_key(r):[DatabaseEvidence(sources[0],'not_found','No match')] for r in records})
    monkeypatch.setattr(module,'BrowserReviewService',FakeService)
    variants=[Variant(patient=p,gene='EGFR',transcript='NM_005228.5',coding='c.1A>T',assembly='GRCh37',selected=True) for p in ['LOCAL-A','LOCAL-B']]
    run_queue(Session(variants=variants),['ClinVar'],tmp_path,QueueControl(),lambda *args:results.append(args),lambda msg:None)
    assert len(calls)==2 and len(results)==2
    assert 'LOCAL' not in str(calls)
    assert all(e[2]['status']=='not_found' for e in results)

def test_empty_provider_result_is_error_not_success(monkeypatch,tmp_path):
    import solide.evidence as module
    results=[]
    class EmptyService:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,*args,**kwargs):return {}
    monkeypatch.setattr(module,'BrowserReviewService',EmptyService)
    v=Variant(patient='DEMO',gene='EGFR',transcript='NM_005228.5',coding='c.1A>T',assembly='GRCh37',selected=True)
    run_queue(Session(variants=[v]),['ClinVar'],tmp_path,QueueControl(),lambda *args:results.append(args),lambda msg:None)
    assert results[0][2]['status']=='error'

def test_unapproved_correction_cannot_be_queried():
    v=Variant(gene='EGFR',assembly='GRCh37',corrected_hgvs='NM_005228.5:c.1A>T')
    with pytest.raises(ValueError):query_record(v)

def test_transcript_field_requires_reference_accession():
    from solide.nomenclature import hgvs_query
    with pytest.raises(ValueError):hgvs_query(Variant(transcript='1',coding='c.1A>T'))

def test_genexus_protein_queries_supported_without_guessing_transcript():
    v=Variant(patient='DEMO',gene='EGFR',coding='c.2573T>G',protein='p.L858R',assembly='GRCh37')
    r=query_record(v,'MTBP')
    assert r.hgvsp=='p.L858R' and not r.hgvsc and not r.transcript
    with pytest.raises(ValueError):query_record(v,'ClinVar')
    other=Variant(patient='DEMO',gene='EGFR',protein='p.T790M',assembly='GRCh37')
    assert BrowserReviewService.variant_key(r)!=BrowserReviewService.variant_key(query_record(other,'OncoKB'))

def test_cancellation_preserves_provisional_capture(monkeypatch,tmp_path):
    import solide.evidence as module
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.evidence_audit import audit_digest
    from solide._vendor.archer.services.browser_review import BrowserReviewCancelled
    captures=[]
    class CancelService:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        _write_audit=staticmethod(lambda evidence,path:None)
        def search_variants(self,records,sources,root,**kwargs):
            digest=audit_digest(sources[0],records[0])
            self._write_audit(DatabaseEvidence(sources[0],'found','Captured'),root/f'{digest}.audit.json')
            raise BrowserReviewCancelled()
    monkeypatch.setattr(module,'BrowserReviewService',CancelService)
    v=Variant(patient='DEMO',gene='EGFR',transcript='NM_005228.5',coding='c.1A>T',assembly='GRCh37',selected=True)
    with pytest.raises(BrowserReviewCancelled):
        run_queue(Session(variants=[v]),['ClinVar'],tmp_path,QueueControl(),lambda *args:captures.append(args),lambda msg:None)
    assert captures and captures[0][2]['status']=='partial_capture'

def test_mtbp_retry_regenerates_complete_selected_patient_batch(monkeypatch,tmp_path):
    import solide.evidence as module
    from solide._vendor.archer.core.models import DatabaseEvidence
    calls=[]
    class FakeService:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,records,sources,root,progress,checkpoint):
            calls.append(records)
            checkpoint({self.variant_key(r):[DatabaseEvidence('MTBP','not_found')] for r in records})
    monkeypatch.setattr(module,'BrowserReviewService',FakeService)
    variants=[Variant(patient='DEMO',gene=g,protein=p,assembly='GRCh37',selected=True) for g,p in [('EGFR','p.L858R'),('TP53','p.R248W')]]
    s=Session(variants=variants)
    image=tmp_path/'capture.png';image.write_bytes(b'placeholder')
    variants[0].evidence['MTBP']={'database':'MTBP','status':'found','fingerprint':variants[0].fingerprint('Other'),
        'mtbp_batch':module.batch_fingerprint(s,'DEMO'),'raw':{'screenshots':[{'path':str(image)}],'patient_report_screenshot':str(image)}}
    run_queue(s,['MTBP'],tmp_path,module.QueueControl(),lambda *args:None,lambda msg:None)
    assert len(calls[0])==2
