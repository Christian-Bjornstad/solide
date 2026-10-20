"""The everyday flow needs no saved review or permanent evidence folder."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton
from solide.gui import MainWindow
from solide.models import Session, Variant


def window():
    app = QApplication.instance() or QApplication([])
    return app, MainWindow()


def test_search_uses_temporary_storage_without_saving_review(monkeypatch):
    app, view = window()
    view.session = Session(variants=[Variant(patient='DEMO', gene='TP53',
        transcript='NM_000546.6', coding='c.1A>T', assembly='GRCh37', selected=True)])
    view.refresh()
    for name, check in view.source_checks.items():
        check.setChecked(name == 'ClinVar')
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (_ for _ in ()).throw(AssertionError('Save prompt')))
    launched = []
    monkeypatch.setattr(view, 'launch', launched.append)
    root = view.work_root()
    try:
        view.start_queue()
        assert len(launched) == 1
        assert launched[0].root == root / 'evidence'
        assert view.session_path is None
        assert not list(root.rglob('*.solide.json'))
    finally:
        view.run_timer.stop()
        view.close()
    assert not root.exists()


def test_editing_legacy_review_never_rewrites_its_file(tmp_path):
    app, view = window()
    view.session_path = tmp_path / 'old.solide.json'
    view.session_path.write_text('original review', encoding='utf8')
    view.session = Session(variants=[Variant(patient='DEMO', gene='TP53')])
    try:
        view.refresh()
        view.select_visible(True)
        view.tissue.setCurrentText('Lung');view.save_tissue()
        assert view.session_path.read_text(encoding='utf8') == 'original review'
    finally:
        view.close()


def test_close_discards_work_without_save_prompt(monkeypatch):
    app, view = window()
    view.dirty = True
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: (_ for _ in ()).throw(AssertionError('Save prompt')))
    assert view.close()


def test_export_asks_for_destination_and_only_writes_after_click(tmp_path, monkeypatch):
    app, view = window()
    view.session = Session(variants=[Variant(patient='DEMO', gene='TP53', selected=True)])
    view.refresh()
    view.session.analyses[0].profile = 'OPA'
    destinations = []
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(tmp_path))
    monkeypatch.setattr('solide.gui.export_analysis', lambda session, analysis, directory, **kwargs: destinations.append(Path(directory)))
    jobs = []
    monkeypatch.setattr(view, 'launch', jobs.append)
    try:
        assert not destinations
        view.export()
        jobs[0].fn()
        assert destinations == [tmp_path]
        assert not (tmp_path / 'reports').exists()
    finally:
        view.close()


def test_import_and_settings_do_not_offer_review_storage():
    app, view = window()
    view.show()
    app.processEvents()
    try:
        labels = [button.text() for button in view.pages.widget(0).findChildren(QPushButton) if button.isVisible()]
        assert 'Open review…' not in labels and 'Save' not in labels
        view.nav.setCurrentRow(3)
        app.processEvents()
        labels = [button.text() for button in view.pages.widget(3).findChildren(QPushButton)]
        assert 'Browse…' not in labels
        assert not view.analysis_context.isVisible()
    finally:
        view.close()


def test_variant_cells_copy_as_tab_separated_text():
    from PyQt6.QtCore import QItemSelection, QItemSelectionModel, Qt
    from PyQt6.QtTest import QTest
    app, view = window()
    view.session = Session(variants=[Variant(patient='DEMO', gene='TP53', transcript='NM_000546.6', af_percent=0, coverage=0)])
    view.refresh()
    try:
        selection = QItemSelection(view.proxy.index(0, 2), view.proxy.index(0, 3))
        view.variant_table.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        QTest.keyClick(view.variant_table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert app.clipboard().text() == 'TP53\tNM_000546.6'
        selection = QItemSelection(view.proxy.index(0, 6), view.proxy.index(0, 7))
        view.variant_table.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        QTest.keyClick(view.variant_table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert app.clipboard().text() == '0\t0'
    finally:
        view.close()


def test_clear_files_removes_temporary_captures_and_resets_sample_list():
    app, view = window()
    view.session = Session(variants=[Variant(patient='DEMO', gene='TP53')])
    view.refresh()
    root = view.work_root()
    (root / 'capture.png').write_bytes(b'synthetic')
    view.clear_files()
    try:
        assert view.session.variants == [] and view.sample_list.count() == 0
        assert not root.exists()
        assert view.work_root().is_dir()
    finally:
        view.close()


def test_unambiguous_tsv_opens_without_confirmation_dialog(tmp_path, monkeypatch):
    from solide.importing import load_file
    path = tmp_path / '26OUM12345.tsv'
    path.write_text('Type\tGenes\tTranscript\tCoding\nSNV\tTP53\tNM_000546.6\tc.1A>T\n', encoding='utf8')
    app, view = window()
    monkeypatch.setattr('solide.gui.SampleImportDialog', lambda *args: (_ for _ in ()).throw(AssertionError('Redundant confirmation')))
    try:
        view.accept_import([(str(path), load_file(path), '')])
        assert view.session.analyses[0].profile == 'Ion Torrent'
        assert view.session.variants[0].patient == '26OUM12345'
        assert view.nav.currentRow() == 1
    finally:
        view.close()


def test_excel_keeps_embedded_evidence_after_temporary_workspace_is_removed(tmp_path):
    from test_vpm_analysis_reports import make_session, capture, result, load_workbook
    from solide.reporting import export_analysis
    from zipfile import ZipFile
    app, view = window()
    view.session, rows = make_session(Variant(gene='EGFR', selected=True))
    root = view.work_root()
    image = capture(root)
    rows[0].evidence['Franklin'] = result(rows[0], image)
    report = export_analysis(view.session, 'analysis-a', tmp_path).report
    view.close()
    assert not root.exists()
    assert list(tmp_path.iterdir()) == [report]
    with load_workbook(report) as book:
        assert len(book['EGFR']._images) == 1
    with ZipFile(report) as archive:
        assert any(name.startswith('xl/media/') for name in archive.namelist())
