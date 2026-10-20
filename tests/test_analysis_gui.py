import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from solide.gui import MainWindow
from solide.models import Analysis, Session, Variant


def setup_window(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    opa = Analysis(id='opa', patient='SAMPLE', profile='OPA', assay='Precision')
    ion = Analysis(id='ion', patient='SAMPLE', profile='Ion Torrent', assay='Childhood')
    first = Variant(id='opa-row', analysis_id='opa', patient='SAMPLE', gene='EGFR', selected=True, coverage=400)
    second = Variant(id='ion-row', analysis_id='ion', patient='SAMPLE', gene='BRCA1', selected=True, coverage=800)
    window.session = Session(analyses=[opa, ion], variants=[first, second])
    window.config_path = tmp_path / 'config.json'
    window.session_path = tmp_path / 'review.solide.json'
    window.refresh();window.nav.setCurrentRow(1)
    return app, window, first, second


def test_switch_analysis_scopes_rows_quality_sources_and_selection(tmp_path):
    app, window, opa, ion = setup_window(tmp_path)
    try:
        assert window.variant_model.variants == [opa]
        assert window.qc_model.rowCount() == 1
        window.variant_table.selectRow(0); app.processEvents()
        assert window.current_variant is opa
        window.analysis_selector.setCurrentIndex(1); app.processEvents()
        assert window.current_variant is None
        assert window.variant_model.variants == [ion]
        assert window.qc_model.rowCount() == 0
        window.select_visible(False)
        assert opa.selected and not ion.selected
        window.variant_table.selectRow(0); app.processEvents()
        assert window.current_variant is ion
        window.gene_edit.setText('BRCA2'); window.save_identity()
        assert ion.gene == 'BRCA2' and opa.gene == 'EGFR'
        assert 'Ion Torrent' in window.report_analysis_label.text()
        assert all(window.evidence_model.item(r, 0).data(Qt.ItemDataRole.UserRole + 1)[0] == ion.id
                   for r in range(window.evidence_model.rowCount()))
    finally:
        window.dirty = False; window.close()


def test_tissue_and_busy_controls_belong_to_active_analysis(tmp_path):
    app, window, opa, ion = setup_window(tmp_path)
    try:
        window.tissue.setCurrentText('Lung'); window.save_tissue()
        assert window.session.tissue_for(opa) == 'Lung'
        assert window.session.tissue_for(ion) == 'Other'
        window.analysis_selector.setCurrentIndex(1); app.processEvents()
        assert window.tissue.currentText() == 'Other'
        window.busy(True)
        assert not window.analysis_selector.isEnabled()
        assert not window.analysis_edit_btn.isEnabled()
        assert not window.include_evidence.isEnabled()
        window.busy(False)
    finally:
        window.dirty = False; window.close()


def test_queue_worker_receives_active_projection_before_copy(monkeypatch, tmp_path):
    import solide.gui as gui
    app, window, opa, ion = setup_window(tmp_path)
    launched = []
    monkeypatch.setattr(gui, 'browser_credentials', lambda accounts: {})
    monkeypatch.setattr(window, 'launch', lambda worker: launched.append(worker))
    try:
        window.analysis_selector.setCurrentIndex(1)
        for source, check in window.source_checks.items(): check.setChecked(source == 'MTBP')
        window.start_queue('all')
        assert len(launched) == 1
        worker = launched[0]
        assert [v.id for v in worker.session.variants] == [ion.id]
        assert worker.plan == {(ion.id, 'MTBP')}
        assert worker.session.variants[0] is not ion
        assert window.session.history[-1]['analysis_id'] == 'ion'
    finally:
        window.run_timer.stop(); window.dirty = False; window.close()


def test_export_active_analysis_and_optional_attachment(monkeypatch, tmp_path):
    import solide.gui as gui
    app, window, opa, ion = setup_window(tmp_path)
    calls = []; launched = []
    monkeypatch.setattr(window, 'launch', lambda worker: launched.append(worker))
    monkeypatch.setattr(gui, 'export_analysis', lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *args: str(tmp_path))
    try:
        window.analysis_selector.setCurrentIndex(1); window.include_evidence.setChecked(False)
        window.export(); launched[0].fn()
        assert calls[0][0][1] == 'ion'
        assert calls[0][1] == {'include_evidence': False}
        assert calls[0][0][0] is not window.session
    finally:
        window.dirty = False; window.close()


def test_identical_labels_still_distinguish_separate_source_imports(tmp_path):
    app, window, opa, ion = setup_window(tmp_path)
    try:
        a,b=window.session.analyses
        b.profile=a.profile; b.assay=a.assay
        a.source_file='first.tsv'; b.source_file='second.tsv'
        window.refresh()
        labels=[window.analysis_selector.itemText(i) for i in range(2)]
        assert labels[0]!=labels[1]
        assert 'first.tsv' in labels[0] and 'second.tsv' in labels[1]
    finally:
        window.dirty=False; window.close()


def test_export_completion_replaces_running_message(tmp_path):
    app,window,opa,ion=setup_window(tmp_path)
    try:
        window.banner.setText('Exporting Excel…')
        window.export_finished((tmp_path/'report.xlsx',tmp_path/'attachment.xlsx'))
        assert window.banner.text()=='Excel export complete'
        assert 'attachment.xlsx' in window.report_log.toPlainText()
        window.session.analyses[0].assay='OPA'
        assert window.analysis_label(window.session.analyses[0])=='OPA · SAMPLE'
    finally:
        window.dirty=False;window.close()


def test_compact_large_text_keeps_detail_actions_below_variant_table(tmp_path):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QTabWidget
    app,window,opa,ion=setup_window(tmp_path)
    try:
        window.text_size.setCurrentIndex(window.text_size.findData(18))
        window.resize(1050,700);window.show();QTest.qWait(50)
        window.details_toggle.setChecked(True);app.processEvents()
        tabs=window.findChild(QTabWidget)
        table_bottom=window.variant_table.mapTo(window,QPoint(0,window.variant_table.height())).y()
        tabs_top=tabs.mapTo(window,QPoint(0,0)).y()
        assert tabs_top>=table_bottom
        assert window.variant_table.viewport().height()>=100
        button=window.assessment_btn
        assert button.isVisible() and button.mapTo(window,QPoint(0,0)).y()>=table_bottom
        window.search.setText('missing-gene')
        assert '0 shown' in window.summary.text()
    finally:
        window.dirty=False;window.close()
