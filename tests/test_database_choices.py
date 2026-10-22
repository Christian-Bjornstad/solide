import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtWidgets import QApplication
import solide.gui as gui
from solide.evidence import SOURCES
from solide.models import Session, Variant


@pytest.fixture
def view(monkeypatch, tmp_path):
    monkeypatch.setattr(gui, 'read_ui_settings', lambda path: {})
    app = QApplication.instance() or QApplication([])
    window = gui.MainWindow()
    window.config_path = tmp_path/'settings.json'
    window.session = Session(variants=[Variant(patient='SYNTHETIC', gene='TP53',
        transcript='NM_000546.6', coding='c.1A>T', assembly='GRCh37', selected=True)])
    window.refresh(); window.nav.setCurrentRow(2); window.show(); app.processEvents()
    yield window
    window.run_timer.stop(); window.close()


def test_all_database_choices_are_visible_without_opening_an_extra_panel(view):
    view.resize(1050,700)
    QApplication.instance().processEvents()
    assert set(view.source_checks) == set(SOURCES)
    assert all(check.isVisible() for check in view.source_checks.values())
    for check in view.source_checks.values():
        assert check.height() >= check.sizeHint().height()
        assert view.source_options.rect().contains(check.geometry())
    group_bottom=view.source_options.mapTo(view,view.source_options.rect().bottomRight()).y()
    run_top=view.run_btn.mapTo(view,view.run_btn.rect().topLeft()).y()
    assert group_bottom < run_top


def test_select_all_and_clear_databases_prevent_an_empty_search(view, monkeypatch):
    jobs = []
    monkeypatch.setattr(view, 'launch', jobs.append)
    view.select_all_sources_btn.click()
    assert all(check.isChecked() for check in view.source_checks.values())
    view.clear_sources_btn.click()
    assert not any(check.isChecked() for check in view.source_checks.values())
    view.start_queue()
    assert jobs == [] and 'database' in view.banner.text().lower()


@pytest.mark.parametrize('mode', ['pending', 'all'])
def test_search_worker_receives_only_checked_databases(view, monkeypatch, mode):
    jobs = []
    monkeypatch.setattr(view, 'launch', jobs.append)
    for source, check in view.source_checks.items():
        check.setChecked(source == 'ClinVar')
    view.start_queue(mode)
    assert len(jobs) == 1 and jobs[0].sources == ['ClinVar']
    assert {source for _, source in jobs[0].plan} == {'ClinVar'}
