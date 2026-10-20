import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt,QItemSelectionModel
from solide.gui import MainWindow
from solide.importing import load_file
from solide.models import Variant
from solide.table_model import VariantTableModel

def test_import_does_not_implicitly_choose_all_present_rows(tmp_path):
    app=QApplication.instance() or QApplication([]);view=MainWindow()
    p=tmp_path/'00OUM00001.tsv'
    p.write_text('Type\tGenes\tTranscript\tCoding\tGenotype\n'
                 'SNV\tEGFR\tNM_005228.5\tc.2573T>G\tPRESENT\n'
                 'SNV\tTP53\tNM_000546.6\tc.743G>A\tPRESENT\n')
    try:
        view.accept_import([(str(p),load_file(p),'')])
        assert not any(v.selected for v in view.session.variants)
        expected=view.variant_model.variants[view.proxy.mapToSource(view.proxy.index(1,0)).row()]
        view.variant_table.selectRow(1)
        view.select_highlighted()
        chosen=[v for v in view.session.variants if v.selected]
        assert len(chosen)==1
        assert chosen[0] is expected
        jobs=[];view.launch=jobs.append
        for source,c in view.source_checks.items():c.setChecked(source=='ClinVar')
        view.start_queue()
        assert len(jobs)==1
        assert {row for row,source in jobs[0].plan}=={chosen[0].id}
        view.run_timer.stop()
    finally:view.close()

def test_highlight_selection_replaces_prior_checked_rows_in_active_file(tmp_path):
    from solide.models import Session
    app=QApplication.instance() or QApplication([]);view=MainWindow()
    first=Variant(patient='00OUM00001',gene='EGFR',selected=True)
    second=Variant(patient='00OUM00001',gene='TP53')
    other=Variant(patient='00OUM00002',gene='BRCA1',selected=True)
    view.session=Session(variants=[first,second,other]);view.refresh()
    try:
        view.analysis_selector.setCurrentIndex(view.analysis_selector.findData(first.analysis_id))
        view.search.setText('TP53');view.variant_table.selectRow(0)
        view.select_highlighted()
        assert not first.selected and second.selected and other.selected
        view.variant_table.clearSelection();view.select_highlighted()
        assert second.selected,'No highlight must not silently clear checked rows'
    finally:view.close()

def test_clear_selection_also_clears_hidden_checked_rows():
    from solide.models import Session
    app=QApplication.instance() or QApplication([]);view=MainWindow()
    first=Variant(patient='00OUM00001',gene='EGFR',selected=True)
    second=Variant(patient='00OUM00001',gene='TP53',selected=True)
    other=Variant(patient='00OUM00002',gene='BRCA1',selected=True)
    view.session=Session(variants=[first,second,other]);view.refresh()
    try:
        view.analysis_selector.setCurrentIndex(view.analysis_selector.findData(first.analysis_id))
        view.search.setText('TP53');view.clear_selection()
        assert not first.selected and not second.selected and other.selected
    finally:view.close()

def test_overlapping_genes_are_purple_and_quality_failure_is_retained():
    v=Variant(gene='KLLN,PTEN',transcript='NM_001126049.2,NM_000314.8',coverage=400)
    model=VariantTableModel([v])
    assert model.data(model.index(0,2),Qt.ItemDataRole.BackgroundRole).name()=='#eadcf5'
    assert model.data(model.index(0,7),Qt.ItemDataRole.BackgroundRole).name()=='#fce5e3'
    assert 'Overlappende gener' in model.data(model.index(0,2),Qt.ItemDataRole.ToolTipRole)

def test_checked_transcript_change_does_not_mix_new_name_and_old_protein():
    v=Variant(gene='MET',transcript='NM_001127500.3',coding='c.3736G>A',protein='p.OldNumber',
              corrected_hgvs='NM_000245.4:c.3682G>A',nomenclature_verified=True)
    model=VariantTableModel([v])
    assert model.data(model.index(0,3))=='NM_000245.4'
    assert model.data(model.index(0,5))==''
    assert 'p.OldNumber' in model.data(model.index(0,5),Qt.ItemDataRole.ToolTipRole)
    assert v.transcript=='NM_001127500.3' and v.protein=='p.OldNumber'

def test_verified_worker_normalization_is_applied_to_live_variant():
    from test_automatic_nomenclature import variant,checked_result
    from solide.models import Session
    from solide.nomenclature import apply_confirmed_normalization
    from copy import deepcopy
    app=QApplication.instance() or QApplication([]);view=MainWindow();v=variant()
    view.session=Session(variants=[v]);view.refresh()
    worker_copy=deepcopy(v);raw=checked_result()
    assert apply_confirmed_normalization(worker_copy,raw)
    evidence={'database':'Mutalyzer','status':'needs_review','raw':raw,
              'fingerprint':worker_copy.fingerprint('Other'),'tissue':'Other'}
    try:
        view.accept_evidence(v.id,'Mutalyzer',evidence)
        assert v.corrected_hgvs=='NM_005228.5:c.2235_2249del'
        assert v.nomenclature_verified
        assert v.fingerprint('Other')==v.evidence['Mutalyzer']['fingerprint']
        assert v.raw['Coding']=='c.2235_2250delinsA'
        assert view.variant_model.data(view.variant_model.index(0,4))=='NM_005228.5:c.2235_2249del'
    finally:view.close()

def test_variant_details_separate_checked_identity_from_original_source():
    from solide.models import Session
    app=QApplication.instance() or QApplication([]);view=MainWindow()
    v=Variant(patient='00OUM00001',gene='MET',transcript='NM_001127500.3',coding='c.3736G>A',protein='p.OldNumber',
              corrected_hgvs='NM_000245.4:c.3682G>A',nomenclature_verified=True)
    view.session=Session(variants=[v]);view.refresh()
    try:
        view.variant_table.selectRow(0);app.processEvents()
        detail=view.detail.toPlainText()
        assert 'DNA: NM_000245.4:c.3682G>A' in detail
        assert 'Transcript: NM_000245.4' in detail
        assert 'Opprinnelig: NM_001127500.3:c.3736G>A p.OldNumber' in detail
    finally:view.close()

def test_normalization_updates_gui_plan_and_reruns_now_outdated_source(monkeypatch,tmp_path):
    import time
    import solide.evidence as evidence
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    from solide.models import Session
    from test_automatic_nomenclature import variant,checked_result
    app=QApplication.instance() or QApplication([]);view=MainWindow();v=variant()
    view.session=Session(variants=[v]);view.refresh()
    v.evidence['ClinVar']={'database':'ClinVar','status':'not_found','fingerprint':v.fingerprint('Other')}
    monkeypatch.setattr(evidence,'normalize_variant',lambda v:checked_result())
    monkeypatch.setattr(evidence,'capture_mutalyzer',lambda *a,**k:{'screenshots':[]})
    monkeypatch.setattr('solide.gui.browser_credentials',lambda *a:{})
    class Browser:
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def __init__(self,**kwargs):pass
        def search_variants(self,records,sources,root,progress,checkpoint):
            checkpoint({self.variant_key(r):[DatabaseEvidence('ClinVar','not_found','Synthetic recheck')] for r in records})
    monkeypatch.setattr(evidence,'BrowserReviewService',Browser)
    try:
        for source,c in view.source_checks.items():c.setChecked(source in {'Mutalyzer','ClinVar'})
        view.start_queue()
        end=time.monotonic()+5
        while view.active and time.monotonic()<end:app.processEvents();time.sleep(.005)
        assert view.active is None
        assert view.run_plan=={(v.id,'Mutalyzer'),(v.id,'ClinVar')}
        assert view.progress.maximum()==2 and view.progress.value()==2
        assert v.evidence['ClinVar']['fingerprint']==v.fingerprint('Other')
    finally:view.close()
