import pytest
from solide.models import Variant, Session
from solide.evidence import query_record, evidence_is_current
from solide.nomenclature import hgvs_query, genomic_query

def test_external_record_has_no_local_identifiers():
    v=Variant(patient='PRIVATE-ID',source_file='PRIVATE-file',gene='MET',coding='c.1A>T',
              transcript='NM_000245.4',assembly='GRCh37')
    r=query_record(v)
    assert r.sample != v.patient and 'PRIVATE' not in repr(r)
    assert r.hgvsc=='NM_000245.4:c.1A>T'

def test_multigene_query_blocked():
    with pytest.raises(ValueError): query_record(Variant(gene='TET2,TET2-AS1'))

def test_unverified_delins_blocked():
    with pytest.raises(ValueError): query_record(Variant(gene='MET',coding='c.1_2delinsTT'))

def test_mane_does_not_swap_accession():
    v=Variant(gene='MET',transcript='NM_001174067.1',coding='c.1A>T')
    with pytest.raises(ValueError): query_record(v)
    assert hgvs_query(v)=='NM_001174067.1:c.1A>T'

def test_genomic_query_requires_assembly_and_alleles():
    v=Variant(locus='chr7:123',ref='A',alt='T',assembly='GRCh37')
    assert genomic_query(v)=='chr7-123-A-T'
    v.assembly='Ukjent'
    with pytest.raises(ValueError): genomic_query(v)

def test_evidence_staleness():
    v=Variant(gene='MET')
    e={'fingerprint':v.fingerprint('Other'),'status':'found'}
    assert evidence_is_current(v,e,'Other')
    v.corrected_hgvs='NM_1.1:c.1A>T'
    assert not evidence_is_current(v,e,'Other')
