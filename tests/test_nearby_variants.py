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
    result=nearby_variants([first,near,far,duplicate,other_sample,unselected,other_gene,other_chrom],distance=100)
    assert {x.id for x,_ in result[first.id]}=={near.id}
    assert result[first.id][0][1]==100
    assert far.id not in result and other_sample.id not in result
    assert unselected.id not in result and other_gene.id not in result and other_chrom.id not in result
    assert {x.id for x,_ in result[duplicate.id]}=={near.id}


def test_three_nearby_events_and_same_coordinate_different_alleles_are_retained():
    rows=[variant(100),variant(110),variant(120),replace(variant(100),alt='T')]
    result=nearby_variants(rows,distance=100)
    assert all(len(result[v.id])==3 for v in rows)


def test_unknown_coordinates_cnv_and_different_assemblies_do_not_get_a_phasing_warning():
    first=variant();rows=[first,replace(variant(),locus='bad'),replace(variant(101),kind='CNV'),
                         replace(variant(101),assembly='GRCh38')]
    assert nearby_variants(rows)=={}


def test_default_distance_includes_10_bp_but_excludes_11_bp():
    first=variant(100);boundary=variant(110);outside=variant(111)
    assert nearby_variants([first,boundary])[first.id][0][1]==10
    assert nearby_variants([first,outside])=={}


def test_settings_distance_updates_highlighting_and_survives_restart(tmp_path):
    import os,json
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from unittest.mock import patch
    from PyQt6.QtWidgets import QApplication
    from solide.gui import MainWindow
    from solide.models import Session,Analysis
    app=QApplication.instance() or QApplication([])
    with patch('solide.gui.Path.home',return_value=tmp_path):
        window=MainWindow()
        try:
            assert window.igv_distance.value()==10
            window.session=Session(variants=[variant(100),variant(150)],
                analyses=[Analysis(id='a',patient='SOURCE',profile='Ion Torrent',assembly='GRCh37')])
            window.refresh()
            assert not window.variant_model.nearby
            window.igv_distance.setValue(50)
            assert len(window.variant_model.nearby)==2
            assert '≤50 bp' in window.selection_summary.text()
            assert '≤50 bp' in window.variant_model.index(0,11).data()
            window.save_settings()
            assert json.loads(window.config_path.read_text())['igv_distance_bp']==50
        finally:window.close()
        restored=MainWindow()
        try:assert restored.igv_distance.value()==50
        finally:restored.close()
