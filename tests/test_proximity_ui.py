import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication,QMessageBox
from solide.models import Variant,Session
from solide.gui import MainWindow
from solide.table_model import VariantTableModel


def rows():
    return [Variant(patient='SOURCE',gene='ATM',assembly='GRCh37',locus=f'chr11:{n}',
        ref='A',alt='G',coding=f'c.{n}A>G',selected=True) for n in (100,200)]


def test_model_has_igv_warning_color_and_updates_when_selection_changes():
    app=QApplication.instance() or QApplication([])
    variants=rows();model=VariantTableModel(variants)
    assert 'IGV' in model.data(model.index(0,11))
    assert model.data(model.index(0,2),Qt.ItemDataRole.BackgroundRole).name()=='#ffe1ad'
    assert '100 bp' in model.data(model.index(0,2),Qt.ItemDataRole.ToolTipRole)
    model.setData(model.index(1,0),Qt.CheckState.Unchecked,Qt.ItemDataRole.CheckStateRole)
    assert 'IGV' not in model.data(model.index(0,11))


def test_declining_igv_prompt_starts_no_worker_or_source_search(monkeypatch):
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    window.session=Session(variants=rows());window.refresh();called=[]
    for source,check in window.source_checks.items():check.setChecked(source=='ClinVar')
    monkeypatch.setattr(QMessageBox,'question',lambda *args,**kwargs:QMessageBox.StandardButton.No)
    monkeypatch.setattr(window,'work_root',lambda:called.append('work'))
    try:
        window.start_queue('all')
        assert not called and window.active is None
    finally:window.dirty=False;window.close()


def test_acknowledgement_is_session_only_and_new_neighbour_requires_a_new_prompt(monkeypatch):
    app=QApplication.instance() or QApplication([]);window=MainWindow();prompts=[]
    variants=rows();window.session=Session(variants=variants);window.refresh()
    for source,check in window.source_checks.items():check.setChecked(source=='ClinVar')
    def answer(*args,**kwargs):prompts.append(args[2]);return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox,'question',answer)
    monkeypatch.setattr(window,'work_root',lambda:None)
    try:
        window.start_queue('all');window.start_queue('all')
        assert len(prompts)==1 and 'cis/på samme allel' in prompts[0]
        variants[1].locus='chr11:190'
        window.start_queue('all');assert len(prompts)==2
        assert window.config.get('igv_acknowledged') is None
    finally:window.dirty=False;window.close()
