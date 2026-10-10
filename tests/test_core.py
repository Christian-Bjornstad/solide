from pathlib import Path
import pytest
from solide.importing import load_file
from solide.models import Variant, Session
from solide.quality import qc_flags, review_reasons
from solide.session import save_session, load_session

def test_fraction_and_percent(tmp_path):
    a = tmp_path / 'a.tsv'
    a.write_text('Gene\tType\tAllele Frequency\tCoverage\tCall\nEGFR\tsnp\t0.211\t499\tPRESENT\n', encoding='utf8')
    v = load_file(a).variants[0]
    assert v.af_percent == 21.1
    assert any(f.category == 'Coverage' for f in qc_flags(v))
    a.write_text('Genes\tType\tAllele Frequency %\tCoverage\nEGFR\tSNV\t21.1\t500\n', encoding='utf8')
    assert load_file(a).variants[0].af_percent == 21.1
    assert not qc_flags(load_file(a).variants[0])

@pytest.mark.parametrize('kind,call,cn,category', [
    ('CNV','ABSENT',0.9,'CNV'), ('CNV','ABSENT',1,'CNV review'),
    ('RNA Exon Tiles','NO CALL',None,'Expression imbalance'),
    ('RNAExonVariant','ABSENT',None,'RNAExonVariant')])
def test_qc_independent_of_selection(kind, call, cn, category):
    v = Variant(gene='MET', kind=kind, call=call, copy_number=cn, selected=False)
    assert any(f.category == category for f in qc_flags(v))

def test_unknown_cnv_not_pass():
    assert qc_flags(Variant(gene='MET',kind='CNV'))[0].status == 'Unknown'

def test_splice_and_transcript_guards():
    assert 'SpliceAI' in review_reasons(Variant(coding='c.2350-100A>T'))
    assert 'SpliceAI' not in review_reasons(Variant(coding='c.2350-101A>T'))
    assert 'Mutalyzer' in review_reasons(Variant(coding='c.10_12delinsAA'))
    assert 'MANE' in review_reasons(Variant(gene='MET',transcript='NM_001127500.3'))


@pytest.mark.parametrize('gene,original,target',[
    ('FGFR1','NM_001174067.1','NM_023110.3'),('MET','NM_001127500.3','NM_000245.4')])
def test_mane_targets_use_gene_correct_ncbi_accessions(gene,original,target):
    from solide.quality import MANE_TARGETS
    assert MANE_TARGETS[gene]==(original,target)
    assert 'MANE' in review_reasons(Variant(gene=gene,transcript=original))
    assert 'MANE' not in review_reasons(Variant(gene=gene,transcript=target))

def test_metadata_and_malformed_file(tmp_path):
    p=tmp_path/'x.tsv'
    p.write_text('##reference=hg19\n##totalVariantCount=3385\nTranscript\tGenes\tCoding\tType\nNM_1.1\tMET\tc.1A>T\tSNV\n',encoding='utf8')
    r=load_file(p)
    assert len(r.variants)==1 and r.assembly=='GRCh37'
    p.write_text('random\tcolumns\n1\t2',encoding='utf8')
    with pytest.raises(ValueError): load_file(p)

def test_session_roundtrip(tmp_path):
    s=Session(variants=[Variant(gene='MET', patient='DEMO', comment='Behold')])
    p=tmp_path/'session.json'
    save_session(s,p)
    assert load_session(p).variants[0].comment=='Behold'


def test_legacy_unknown_assembly_session_preserves_user_data(tmp_path):
    s=Session(variants=[Variant(patient='DEMO',assembly='Ukjent',comment='Behold',raw={'Gen':'original'})])
    p=tmp_path/'legacy.json';save_session(s,p)
    restored=load_session(p).variants[0]
    assert restored.assembly=='Unknown'
    assert restored.comment=='Behold' and restored.raw=={'Gen':'original'}

def test_local_reference_formats():
    root=Path(__file__).parents[1]
    if not (root/'Snvindel.tsv').exists(): pytest.skip('Local reference files absent')
    assert len(load_file(root/'Snvindel.tsv').variants)==2
    ion=next(root.glob('26OUM*.tsv'))
    assert len(load_file(ion).variants)==8
    x=load_file(next(root.glob('*.xlsx')))
    assert len(x.variants)==3204
    flags=[f for v in x.variants for f in qc_flags(v)]
    assert sum(f.category=='CNV' and f.status=='Failed' for f in flags)==4
    assert sum(f.category=='Expression imbalance' for f in flags)==5
    assert sum(f.category=='RNAExonVariant' for f in flags)==4
