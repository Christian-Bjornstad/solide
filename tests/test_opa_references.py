"""OPA reporting references follow the laboratory's versioned Excel list."""
import pytest
from solide.analyses import add_analysis
from solide.importing import load_file
from solide.models import Session,Variant,ImportResult
from solide.nomenclature import hgvs_query,normalize_variant
from solide.quality import review_reasons


def test_opa_import_uses_lab_nm_reference_and_retains_source_cells(tmp_path):
    source=tmp_path/'opa.tsv'
    source.write_text('##reference=hg19\nGene\tType\tNuc Change\tAA Change\tGene Isoform\tCall\n'
        'BRAF\tsnp\tc.1415A>G\tp.Y472C\t\tPRESENT\n',encoding='utf8')
    imported=load_file(source);session=Session()
    add_analysis(session,imported,'00OUM00001','GRCh37','OPA','Precision')
    v=session.variants[0]
    assert v.transcript=='NM_004333.6'
    assert hgvs_query(v)=='NM_004333.6:c.1415A>G'
    assert v.raw['Gene Isoform']==''
    assert v.raw['_values']==imported.variants[0].raw['_values']
    assert v.raw['_opa_reference']['source']=='Variantformatering OPA.xlsx / NM-nummer'
    assert not v.nomenclature_verified and not v.corrected_hgvs


@pytest.mark.parametrize('gene,transcript',[
    ('MET','NM_001127500.3'),('FGFR1','NM_001174067.1'),('TP53','NM_000546.5'),
    ('CDKN2A','NM_001195132.1'),('ESR1','NM_001122740.1')])
def test_exact_lab_versions_are_used_without_a_mane_override(gene,transcript):
    session=Session()
    add_analysis(session,ImportResult([Variant(gene=gene,coding='c.1A>T',kind='snp')]),
        '00OUM00001','GRCh37','OPA','Precision')
    v=session.variants[0]
    assert v.transcript==transcript
    assert 'MANE' not in review_reasons(v)


@pytest.mark.parametrize('profile,gene,transcript,kind,coding',[
    ('Ion Torrent','EGFR','','snp','c.1A>T'),
    ('OPA','UNKNOWN','','snp','c.1A>T'),
    ('OPA','EGFR','NM_005228.4','snp','c.1A>T'),
    ('OPA','EGFR','','CNV',''),('OPA','EGFR','','Fusion',''),
    ('OPA','EGFR','','snp','NC_000007.13:g.55249071C>T')])
def test_default_does_not_replace_explicit_references_or_invent_unsupported_ones(profile,gene,transcript,kind,coding):
    session=Session()
    add_analysis(session,ImportResult([Variant(gene=gene,transcript=transcript,kind=kind,coding=coding)]),
        '00OUM00001','GRCh37',profile,'Assay')
    assert session.variants[0].transcript==transcript


def test_opa_normalizer_checks_lab_transcript_against_source_genome():
    from test_mutalyzer_identity import Http,normalized,delins
    tx='NM_001127500.3:c.3736G>A';g='NC_000007.13:g.116423407G>A'
    session=Session()
    add_analysis(session,ImportResult([Variant(gene='MET',coding='c.3736G>A',kind='snp',
        locus='chr7:116423407',ref='G',alt='A')]),'00OUM00001','GRCh37','OPA','Precision')
    http=Http({'normalize/'+tx:normalized(tx,tx,'MET'),
        'normalize/'+g:normalized(g,g),
        'map/'+tx:dict(mapped_description='NC_000007.13(NM_001127500.3):c.3736G>A',
            genomic_description=g,ref_seq_differences=False),
        'delins_model/'+g:delins(g,start=116423406,end=116423407,inserted='A')})
    result=normalize_variant(session.variants[0],http=http)
    assert result['original']==tx
    assert result['nomenclature_assessment']['identity_confirmed'] is True
    assert result['nomenclature_assessment']['suggested_hgvs']==tx
    assert 'mane_target' not in result


def test_opa_missing_source_alleles_remains_reviewable():
    from test_mutalyzer_identity import Http,normalized
    session=Session();tx='NM_004333.6:c.1415A>G'
    add_analysis(session,ImportResult([Variant(gene='BRAF',coding='c.1415A>G',kind='snp')]),
        '00OUM00001','GRCh37','OPA','Precision')
    result=normalize_variant(session.variants[0],http=Http({'normalize/'+tx:normalized(tx,tx,'BRAF')}))
    assert result['original']==tx
    assert result['nomenclature_assessment']['identity_confirmed'] is False
