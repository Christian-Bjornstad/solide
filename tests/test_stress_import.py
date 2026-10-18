"""Regressions from malformed and quoted synthetic TSV stress cases."""
import csv,io
import pytest
from solide.importing import load_file

HEADER=['Type','Genes','Transcript','Coding','Comment']
ROW=['SNV','EGFR','NM_005228.5','c.2573T>G','Synthetic']

def write(path,rows):
    stream=io.StringIO(newline='');stream.write('##sampleNames=00OUM00001\n')
    writer=csv.writer(stream,delimiter='\t',lineterminator='\n');writer.writerow(HEADER);writer.writerows(rows)
    path.write_bytes(stream.getvalue().encode());return path

def test_multiline_cell_cannot_create_a_second_variant(tmp_path):
    value='First\nSNV\tTP53\tNM_000546.6\tc.743G>A\nLast'
    p=write(tmp_path/'quoted.tsv',[ROW[:-1]+[value],ROW])
    result=load_file(p)
    assert len(result.variants)==2
    assert result.variants[0].raw['Comment']==value
    assert result.variants[0].source_row==3
    assert result.variants[1].source_row==6

def test_unclosed_quote_rejected(tmp_path):
    p=write(tmp_path/'broken.tsv',[])
    with p.open('a') as f:f.write('SNV\tEGFR\tNM_1.1\tc.1A>T\t"unfinished\n')
    with pytest.raises(ValueError,match='TSV'):load_file(p)

def test_extra_nonempty_columns_cannot_be_discarded(tmp_path):
    p=write(tmp_path/'extra.tsv',[ROW+['Must be retained or rejected']])
    with pytest.raises(ValueError,match='kolonner'):load_file(p)

def test_concatenated_exports_with_new_sample_metadata_rejected(tmp_path):
    p=write(tmp_path/'two.tsv',[ROW])
    with p.open('a') as f:f.write('##sampleNames=00OUM00002\n'+'\t'.join(HEADER)+'\n'+'\t'.join(ROW)+'\n')
    with pytest.raises(ValueError,match='eksport'):load_file(p)

def test_corrupt_extreme_intron_offsets_cannot_crash_quality_view():
    from solide.quality import review_reasons
    from solide.models import Variant
    assert 'SpliceAI' not in review_reasons(Variant(coding='c.100+'+'9'*5000+'A>G'))
    assert 'SpliceAI' in review_reasons(Variant(coding='c.100+'+'0'*5000+'1A>G'))
