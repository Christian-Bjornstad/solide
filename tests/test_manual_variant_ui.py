import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication,QDialogButtonBox
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from solide.models import Analysis,Session,Variant
from solide.gui import MainWindow


def make_window(tmp_path):
    app=QApplication.instance() or QApplication([])
    with patch('solide.gui.Path.home',return_value=tmp_path):window=MainWindow()
    window.session=Session(analyses=[Analysis(id='a',patient='SAMPLE',profile='Ion Torrent',assembly='GRCh37'),
        Analysis(id='b',patient='OTHER',profile='OPA')],variants=[
            Variant(id='a1',analysis_id='a',patient='SAMPLE',gene='PTEN',transcript='NM_000314.8',coding='c.19G>A'),
            Variant(id='a2',analysis_id='a',patient='SAMPLE',gene='TP53'),
            Variant(id='b1',analysis_id='b',patient='OTHER',gene='PTEN')])
    window.active_analysis_id='a';window.refresh();window.nav.setCurrentRow(1)
    return app,window


def test_select_all_header_selects_only_visible_rows_and_handles_partial_state(tmp_path):
    app,w=make_window(tmp_path)
    try:
        check=w.selection_header.checkbox
        QTest.mouseClick(check,Qt.MouseButton.LeftButton)
        assert [v.selected for v in w.session.variants]==[True,True,False]
        w.search.setText('PTEN')
        assert check.checkState()==Qt.CheckState.Checked
        QTest.mouseClick(check,Qt.MouseButton.LeftButton)
        assert [v.selected for v in w.session.variants]==[False,True,False]
        w.search.clear()
        assert check.checkState()==Qt.CheckState.PartiallyChecked
        QTest.mouseClick(check,Qt.MouseButton.LeftButton)
        assert [v.selected for v in w.session.variants]==[True,True,False]
        w.search.setText('no matches');assert not check.isEnabled()
    finally:w.close()


def test_manual_dialog_validation_and_optional_locus():
    from solide.manual_variant_dialog import ManualVariantDialog
    app=QApplication.instance() or QApplication([])
    dialog=ManualVariantDialog()
    save=dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
    QTest.mouseClick(save,Qt.MouseButton.LeftButton)
    assert dialog.result()==0 and dialog.error.text()
    dialog.transcript.setText('NM_000314.8');dialog.coding.setText('c.19G>A')
    dialog.protein.setText('p.Glu7Lys')
    QTest.mouseClick(save,Qt.MouseButton.LeftButton)
    assert dialog.result()==dialog.DialogCode.Accepted
    assert dialog.values()['locus']==''


def test_select_all_is_reenabled_after_worker_updates_and_finishes(tmp_path):
    from PyQt6.QtCore import QObject
    app,w=make_window(tmp_path)
    worker=QObject()
    try:
        w.active=worker;w.workers.append(worker);w.busy(True);w.refresh_counts()
        assert not w.selection_header.checkbox.isEnabled()
        w.finished(worker)
        assert w.selection_header.checkbox.isEnabled()
        QTest.mouseClick(w.selection_header.checkbox,Qt.MouseButton.LeftButton)
        assert [v.selected for v in w.session.variants]==[True,True,False]
    finally:w.active=None;w.close()


def test_add_from_selected_row_preserves_original_and_shows_new_row(tmp_path):
    app,w=make_window(tmp_path)
    from solide.manual_variant_dialog import ManualVariantDialog
    try:
        w.variant_table.setCurrentIndex(w.proxy.index(0,2))
        w.search.setText('PTEN')
        def enter(dialog):
            assert dialog.transcript.text()=='NM_000314.8'
            assert dialog.locus.text()==''
            dialog.coding.setText('c.19_20delinsAT');dialog.protein.setText('p.Glu7Ile')
            return dialog.DialogCode.Accepted
        with patch.object(ManualVariantDialog,'exec',enter):w.add_manual_row(from_selected=True)
        assert len(w.session.variants)==4
        added=w.session.variants[-1]
        assert added.raw['_manual_variant']['parent_ids']==['a1']
        assert added.coding=='c.19_20delinsAT' and added.selected
        assert w.current_variant is added
        assert w.session.variants[0].coding=='c.19G>A'
    finally:w.close()


def test_gui_accepts_manual_derived_alleles_only_with_current_unchanged_inputs(tmp_path):
    from copy import deepcopy
    from solide.manual_variants import add_manual_variant
    from solide.manual_resolution import resolve_manual_variant
    from test_manual_resolution import PublicHttp,Resolver
    from solide.annotations import annotation_resolution_current
    app,w=make_window(tmp_path)
    try:
        original=add_manual_variant(w.session,'a',transcript='NM_000314.8',coding='c.1A>T')
        w.refresh();worker=deepcopy(original)
        assert resolve_manual_variant(worker,Resolver(),http=PublicHttp())
        payload={'variant':worker,'analysis_id':'a','input_fingerprint':original.fingerprint('')}
        w.accept_identity_resolution(original.id,payload)
        assert (original.gene,original.locus,original.ref,original.alt)==('PTEN','chr10:100','A','T')
        assert annotation_resolution_current(original)
        forged=deepcopy(original);forged.raw['_manual_variant']['coding']='c.2G>T'
        forged.gene='WRONG'
        w.accept_identity_resolution(original.id,{'variant':forged,'analysis_id':'a','input_fingerprint':original.fingerprint('')})
        assert original.gene=='PTEN'
    finally:w.close()
