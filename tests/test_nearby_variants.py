from dataclasses import replace
from solide.models import Variant
from solide.proximity import nearby_variants


def variant(position=100,**kw):
    return Variant(patient='SOURCE',analysis_id='a',gene='ATM',assembly='GRCh37',
        locus=f'chr11:{position}',ref='A',alt='G',selected=True,**kw)


def test_proximity_uses_selected_distinct_events_same_analysis_gene_and_chromosome():
    first=variant();near=variant(200);far=variant(301)
    other_sample=replace(near,id='other',analysis_id='b')
    duplicate=replace(first,id='duplicate',transcript='NM_000001.1')
    unselected=replace(near,id='unselected',selected=False)
    other_gene=replace(near,id='gene',gene='BARD1')
    other_chrom=replace(near,id='chrom',locus='chr2:200')
    result=nearby_variants([first,near,far,duplicate,other_sample,unselected,other_gene,other_chrom])
    assert {x.id for x,_ in result[first.id]}=={near.id}
    assert result[first.id][0][1]==100
    assert far.id not in result and other_sample.id not in result
    assert unselected.id not in result and other_gene.id not in result and other_chrom.id not in result
    assert {x.id for x,_ in result[duplicate.id]}=={near.id}


def test_three_nearby_events_and_same_coordinate_different_alleles_are_retained():
    rows=[variant(100),variant(110),variant(120),replace(variant(100),alt='T')]
    result=nearby_variants(rows)
    assert all(len(result[v.id])==3 for v in rows)


def test_unknown_coordinates_cnv_and_different_assemblies_do_not_get_a_phasing_warning():
    first=variant();rows=[first,replace(variant(),locus='bad'),replace(variant(101),kind='CNV'),
                         replace(variant(101),assembly='GRCh38')]
    assert nearby_variants(rows)=={}
