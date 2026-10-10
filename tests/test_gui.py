import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication
from solide.gui import MainWindow
from solide.models import Variant, Session

def test_variant_selection_filter_and_session(tmp_path):
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    window.session=Session(variants=[Variant(patient='DEMO',gene='EGFR',selected=True,coverage=400),
                                     Variant(patient='DEMO',gene='MET',selected=False,coverage=500)])
    window.refresh()
    assert window.variant_model.rowCount()==2
    assert window.qc_model.rowCount()==1
    window.search.setText('MET')
    assert window.proxy.rowCount()==1
    window.select_visible(True)
    assert all(v.selected for v in window.session.variants)
    window.save_to(tmp_path/'demo.solide.json')
    assert (tmp_path/'demo.solide.json').exists()
    window.close()


def test_english_navigation_and_identity_review_tab():
    from PyQt6.QtWidgets import QTabWidget
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    assert [window.nav.item(i).text() for i in range(window.nav.count())]==[
        'Workspace','Searches','Reports','Settings']
    window.session=Session(variants=[Variant(patient='DEMO',gene='EGFR',coverage=499,source_row=8)])
    window.refresh();window.nav.setCurrentRow(0);window.show();app.processEvents()
    window.variant_table.selectRow(0);app.processEvents()
    assert 'Source:' in window.detail.toPlainText()
    assert window.qc_model.item(0,3).text()=='Failed'
    assert 'on row 8' in window.qc_model.item(0,4).text()
    tabs=window.findChild(QTabWidget)
    assert tabs.tabText(1)=='Identity review'
    tabs.setCurrentIndex(1);app.processEvents()
    assert window.hgvs_edit.isVisible()
    window.close()


def test_search_rows_status_filter_and_rerun_target():
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    a=Variant(patient='DEMO',gene='EGFR',selected=True)
    a.evidence['ClinVar']={'database':'ClinVar','status':'timeout','fingerprint':a.fingerprint('Other')}
    window.session=Session(variants=[a]);window.refresh()
    window.result_filter.setCurrentText('Needs attention')
    assert window.evidence_model.rowCount()==1
    assert window.evidence_model.item(0,3).text()=='Timeout'
    window.evidence_table.selectRow(0)
    assert window.selected_result_keys()=={(a.id,'ClinVar')}
    window.refresh_evidence()
    assert window.selected_result_keys()=={(a.id,'ClinVar')}
    called=[];window.start_queue=lambda *args:called.append(args)
    window.rerun_selected()
    assert called==[('chosen',{(a.id,'ClinVar')})]
    window.close()


def test_run_progress_keeps_partial_capture_and_history(tmp_path):
    app=QApplication.instance() or QApplication([])
    window=MainWindow();v=Variant(patient='DEMO',gene='EGFR',selected=True)
    old={'database':'ClinVar','status':'not_found','fingerprint':v.fingerprint('Other')}
    v.evidence['ClinVar']=old;window.session=Session(variants=[v]);window.session_path=tmp_path/'session.solide.json'
    window.run_id='synthetic-run';window.run_plan={(v.id,'ClinVar')}
    window.accept_evidence(v.id,'ClinVar',{'status':'partial_capture','raw':{'provisional_status':'found'}})
    assert not window.run_done
    window.accept_evidence(v.id,'ClinVar',{'database':'ClinVar','status':'error','fingerprint':v.fingerprint('Other')})
    assert len(window.run_done)==1 and '1 failed' in window.live_status.text()
    archived=[e for e in window.session.history if e.get('event')=='evidence_replaced']
    assert len(archived)==1 and archived[0]['evidence']['status']=='not_found'
    window.close()


def test_retry_worker_counts_only_targeted_failures(monkeypatch,tmp_path):
    import time
    import solide.evidence as evidence
    import solide.gui as gui
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    class Service:
        def __init__(self,**kwargs):pass
        variant_key=staticmethod(BrowserReviewService.variant_key)
        def search_variants(self,records,sources,root,progress,checkpoint):
            progress('Synthetic ClinVar lookup')
            checkpoint({self.variant_key(r):[DatabaseEvidence(sources[0],'not_found','Fresh')] for r in records})
    monkeypatch.setattr(evidence,'BrowserReviewService',Service)
    monkeypatch.setattr(gui,'browser_credentials',lambda accounts:{})
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    a,b=[Variant(patient='DEMO',gene=gene,transcript='NM_1.1',coding='c.1A>T',assembly='GRCh37',selected=True) for gene in ('EGFR','TP53')]
    for v,status in ((a,'error'),(b,'not_found')):
        v.evidence['ClinVar']={'database':'ClinVar','status':status,'fingerprint':v.fingerprint('Other'),'summary':'Original'}
    window.session=Session(variants=[a,b]);window.session_path=tmp_path/'session.solide.json'
    window.output_dir.setText(str(tmp_path));window.refresh()
    for source,check in window.source_checks.items():check.setChecked(source=='ClinVar')
    window.start_queue('failed')
    deadline=time.monotonic()+5
    while window.active and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
    assert window.active is None
    assert window.run_done=={(a.id,'ClinVar')} and window.run_state=='Completed'
    assert b.evidence['ClinVar']['summary']=='Original'
    assert '1/1' in window.live_status.text()
    assert any(e.get('event')=='run_end' for e in window.session.history)
    window.close()


def test_settings_store_password_in_vault_only(monkeypatch,tmp_path):
    import solide.gui as gui
    stored=[]
    monkeypatch.setattr(gui,'write_password',lambda *args:stored.append(args))
    monkeypatch.setattr(gui,'read_password',lambda *args:'synthetic-password-test' if stored else '')
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    window.config={};window.config_path=tmp_path/'ui_config.json'
    window.account_username.setText('demo@example.org');window.account_password.setText('synthetic-password-test')
    window.save_account()
    assert stored and window.account_password.text()==''
    assert 'synthetic-password-test' not in window.config_path.read_text()
    window.save_settings()
    assert window.config['accounts']['Franklin']=='demo@example.org'
    assert 'synthetic-password-test' not in window.queue_log.toPlainText()
    window.close()


def test_edge_sign_in_still_works_when_vault_unavailable(monkeypatch,tmp_path):
    import time
    import solide.gui as gui
    calls=[]
    def unavailable(accounts):raise RuntimeError('Vault unavailable')
    class Browser:
        def __init__(self,**kwargs):calls.append(kwargs)
        def open_login(self,source,maximum_minutes):return f'{source} sign-in confirmed; browser profile released.'
    monkeypatch.setattr(gui,'browser_credentials',unavailable)
    monkeypatch.setattr(gui,'BrowserReviewService',Browser)
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    window.config_path=tmp_path/'ui_config.json';window.account_username.setText('demo@example.org')
    window.login();deadline=time.monotonic()+5
    while window.active and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
    assert calls and not any(k.endswith('_password') for k in calls[0])
    assert window.config['login_checks']['Franklin']['state']=='Last sign-in confirmed'
    assert window.live_status.text()=='Idle'
    window.close()


def test_compact_workspace_keeps_variant_rows_visible_and_brca_gene_scoped():
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    window.session=Session(variants=[Variant(patient='DEMO',gene='EGFR',selected=True),Variant(patient='DEMO',gene='BRCA1',selected=True)])
    window.refresh();window.resize(1050,700);window.show();app.processEvents()
    assert window.variant_table.viewport().height()>=100
    for source,check in window.source_checks.items():check.setChecked(source=='BRCA Exchange')
    assert window.evidence_model.rowCount()==1 and 'BRCA1' in window.evidence_model.item(0,1).text()
    window.close()


def test_assessment_dialog_saves_into_app_session(monkeypatch,tmp_path):
    import solide.gui as gui
    from PyQt6.QtWidgets import QDialog
    class Dialog:
        def __init__(self,v,parent):assert v.gene=='EGFR'
        def exec(self):return QDialog.DialogCode.Accepted
        def values(self):return dict(classification='VUS',decision='Include',reviewer='DEMO reviewer',comment='Manual assessment')
    monkeypatch.setattr(gui,'AssessmentDialog',Dialog)
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    window.session=Session(variants=[Variant(patient='DEMO',gene='EGFR')]);window.session_path=tmp_path/'demo.solide.json'
    window.refresh();window.variant_table.selectRow(0);app.processEvents();window.assess_variant()
    assert window.session.variants[0].classification=='VUS'
    assert 'Manual assessment' in window.detail.toPlainText()
    from solide.session import load_session
    assert load_session(window.session_path).variants[0].report_decision=='Include'
    assert window.session.history[-1]['event']=='assessment'
    window.close()


def test_open_session_path_uses_persisted_data_without_demo_rows(tmp_path):
    from solide.session import save_session
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    path=tmp_path/'existing.solide.json';save_session(Session(variants=[Variant(patient='SOURCE',gene='MET')]),path)
    window.load_session_path(path)
    assert window.variant_model.rowCount()==1 and window.session.variants[0].patient=='SOURCE'
    assert window.session_path==path and not window.dirty
    window.close()


def test_failed_import_is_visible_and_does_not_claim_success():
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    window.accept_import([('unsupported.xlsx',None,'No variant table found.')])
    assert 'failed' in window.banner.text().lower()
    assert 'Import failed: No variant table found.' in window.queue_log.toPlainText()
    assert not window.dirty and not window.session.variants
    window.close()


def test_identity_edit_preserves_selected_variant_when_sort_order_changes(tmp_path):
    from PyQt6.QtCore import Qt
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    window.config_path=tmp_path/'config.json'
    first=Variant(patient='SOURCE',gene='EGFR')
    window.session=Session(variants=[first,Variant(patient='SOURCE',gene='BRCA1')])
    window.refresh();window.proxy.sort(2,Qt.SortOrder.AscendingOrder)
    window.variant_table.selectRow(1);app.processEvents()
    assert window.current_variant is first
    window.gene_edit.setText('AKT1');window.save_identity();app.processEvents()
    index=window.variant_table.currentIndex()
    assert index.isValid()
    assert window.session.variants[window.proxy.mapToSource(index).row()] is first
    assert window.proxy.data(window.proxy.index(index.row(),2))=='AKT1'
    window.dirty=False;window.close()
