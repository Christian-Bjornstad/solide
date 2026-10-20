from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from openpyxl import load_workbook
from solide.reporting import captured_time, export_analysis
from solide.models import Analysis, Session, Variant


@pytest.mark.parametrize('stamp, expected', [
    ('2026-01-18T09:30:00Z', datetime(2026, 1, 18, 10, 30)),
    ('2026-07-18T09:30:00+00:00', datetime(2026, 7, 18, 11, 30)),
    ('2026-10-18T23:30:00Z', datetime(2026, 10, 19, 1, 30)),
    ('2026-10-25T00:30:00Z', datetime(2026, 10, 25, 2, 30)),
    ('2026-10-25T01:30:00Z', datetime(2026, 10, 25, 2, 30, fold=1)),
])
def test_excel_source_times_use_oslo_including_dst(stamp, expected):
    assert captured_time(stamp) == expected


def test_report_filename_and_header_use_same_oslo_clock(tmp_path, monkeypatch):
    import solide.reporting as reporting
    moment = datetime(2026, 10, 19, 1, 30, tzinfo=ZoneInfo('Europe/Oslo'))
    monkeypatch.setattr(reporting, 'oslo_now', lambda: moment, raising=False)
    a = Analysis(id='a', patient='DEMO', profile='OPA')
    v = Variant(analysis_id='a', patient='DEMO', gene='EGFR', selected=True)
    path = export_analysis(Session(analyses=[a], variants=[v]), 'a', tmp_path).report
    assert '_20261019_013000_' in path.name
    book = load_workbook(path)
    try:
        assert book['Oversikt']['A4'].value == 'Opprettet (Oslo)'
        assert book['Oversikt']['C4'].value == moment.replace(tzinfo=None)
        assert book['Oversikt']['C4'].number_format == 'dd.mm.yyyy hh:mm:ss'
        assert 'Hentet (Oslo)' in [cell.value for cell in book['Kilder'][5]]
    finally:
        book.close()


def test_gui_displays_utc_evidence_as_oslo():
    from PyQt6.QtWidgets import QApplication
    from solide.gui import MainWindow
    app = QApplication.instance() or QApplication([])
    view = MainWindow()
    v = Variant(patient='DEMO', gene='EGFR', selected=True)
    v.evidence['ClinVar'] = {'database': 'ClinVar', 'status': 'not_found',
        'captured_at': '2026-10-18T09:30:00Z', 'fingerprint': v.fingerprint('Other')}
    view.session = Session(variants=[v]);view.refresh()
    try:
        row = next(r for r in range(view.evidence_model.rowCount()) if view.evidence_model.item(r, 2).text() == 'ClinVar')
        assert view.evidence_model.item(row, 4).text() == '18.10.2026 11:30:00 CEST'
    finally:
        view.close()
