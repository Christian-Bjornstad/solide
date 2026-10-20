import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time

from PyQt6.QtWidgets import QApplication

import solide.gui as gui


def window_for_test(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(gui, 'read_password', lambda *a: '')
    window = gui.MainWindow()
    window.config = {}; window.config_path = tmp_path/'settings.json'
    window.account_username.setText('dummy@example.org')
    window.account_password.setText('wrong-test-password')
    return app, window


def finish(app, window):
    deadline = time.monotonic()+5
    while window.active and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.005)
    assert window.active is None


def test_password_saved_only_after_verified_credential_login(monkeypatch, tmp_path):
    saved = []
    monkeypatch.setattr(gui, 'write_password', lambda *a: saved.append(a))
    class Browser:
        login_confirmed = True
        login_credentials_verified = True
        def __init__(self, **kwargs):pass
        def open_login(self, *a, **k):return 'Confirmed'
    monkeypatch.setattr(gui, 'BrowserReviewService', Browser)
    app, window = window_for_test(monkeypatch, tmp_path)
    try:
        window.login(); finish(app, window)
        assert saved == [('Franklin', 'dummy@example.org', 'wrong-test-password')]
        assert 'Innlogget' in window.account_status.text()
        assert 'wrong-test-password' not in window.config_path.read_text()
        assert 'wrong-test-password' not in window.queue_log.toPlainText()
    finally:window.close()


def test_wrong_password_cancel_then_retry_recovers(monkeypatch, tmp_path):
    saved = []
    monkeypatch.setattr(gui, 'write_password', lambda *a: saved.append(a))
    class Browser:
        login_confirmed = False
        login_credentials_verified = False
        def __init__(self, **kwargs):self.stop = kwargs['stop_requested']
        def open_login(self, *a, **k):
            while not self.stop():time.sleep(.005)
            raise gui.BrowserReviewCancelled()
    monkeypatch.setattr(gui, 'BrowserReviewService', Browser)
    app, window = window_for_test(monkeypatch, tmp_path)
    try:
        window.login(); app.processEvents()
        assert window.login_cancel_btn.isEnabled()
        window.cancel_login(); finish(app, window)
        assert not saved
        assert window.login_btn.isEnabled()
        assert 'Innlogget' not in window.account_status.text()
        window.login(); window.cancel_login(); finish(app, window)
    finally:window.close()


def test_existing_session_never_replaces_saved_account_with_unverified_input(monkeypatch,tmp_path):
    saved=[]
    monkeypatch.setattr(gui,'write_password',lambda *args:saved.append(args))
    class Browser:
        login_confirmed=True
        login_credentials_verified=False
        def __init__(self,**kwargs):pass
        def open_login(self,*a,**k):return 'Innlogget med eksisterende økt.'
    monkeypatch.setattr(gui,'BrowserReviewService',Browser)
    app,window=window_for_test(monkeypatch,tmp_path)
    try:
        window.config['accounts']={'Franklin':'verified-account@example.org'}
        window.account_username.setText('wrong-account@example.org')
        window.login();finish(app,window)
        assert window.config['accounts']['Franklin']=='verified-account@example.org'
        assert not saved
        assert window.account_username.text()=='verified-account@example.org'
    finally:window.close()


def test_manual_login_without_observed_identity_does_not_guess_account(monkeypatch,tmp_path):
    class Browser:
        login_confirmed=True
        login_credentials_verified=False
        def __init__(self,**kwargs):pass
        def open_login(self,*a,**k):return 'Innlogget.'
    monkeypatch.setattr(gui,'BrowserReviewService',Browser)
    app,window=window_for_test(monkeypatch,tmp_path)
    try:
        window.login();finish(app,window)
        assert not window.config.get('accounts',{}).get('Franklin')
        assert 'Franklin' in window.login_verified
    finally:window.close()


def test_saved_confirmation_is_not_presented_as_current_login(monkeypatch, tmp_path):
    app, window = window_for_test(monkeypatch, tmp_path)
    try:
        window.config['login_checks'] = {'Franklin': {'state': 'Last sign-in confirmed', 'time': '2026-10-18T10:00:00+02:00'}}
        window.show_account()
        assert 'Sist bekreftet' in window.account_status.text()
        assert 'Ikke kontrollert' in window.account_status.text()
        assert 'Innlogget' not in window.account_status.text()
    finally:window.close()


def test_expired_search_clears_current_login_and_all_summary(monkeypatch, tmp_path):
    app, window = window_for_test(monkeypatch, tmp_path)
    try:
        for source in gui.ACCOUNT_PROVIDERS:window.set_login_state(source, True)
        assert 'alle' in window.login_summary.text().casefold()
        window.set_login_state('MTBP', False)
        assert 'alle' not in window.login_summary.text().casefold()
        assert 'Logg inn' in window.source_checks['MTBP'].text()
    finally:window.close()


def test_close_during_login_waits_for_worker_cleanup(monkeypatch,tmp_path):
    released=[]
    class Browser:
        def __init__(self,**kwargs):self.stop=kwargs['stop_requested']
        def open_login(self,*a,**k):
            try:
                while not self.stop():time.sleep(.005)
                raise gui.BrowserReviewCancelled()
            finally:released.append(True)
    monkeypatch.setattr(gui,'BrowserReviewService',Browser)
    app,window=window_for_test(monkeypatch,tmp_path)
    window.show();app.processEvents()
    root=window.work_root()
    window.login();window.close();finish(app,window);app.processEvents()
    assert released
    assert not window.isVisible()
    assert not root.exists()


def test_only_fresh_provider_auth_marker_updates_login_state(monkeypatch,tmp_path):
    from solide.models import Variant
    app,window=window_for_test(monkeypatch,tmp_path)
    try:
        variant=Variant(patient='26OUM12345',gene='EGFR',selected=True)
        window.session.variants=[variant];window.refresh()
        window.accept_evidence(variant.id,'MTBP',{'status':'found','raw':{}})
        assert 'MTBP' not in window.login_verified
        window.accept_evidence(variant.id,'MTBP',{'status':'found','raw':{'auth_verified':True}})
        assert 'MTBP' in window.login_verified
        window.accept_evidence(variant.id,'MTBP',{'status':'error','raw':{'auth_verified':True,'failure_kind':'login_required'}})
        assert 'MTBP' not in window.login_verified
    finally:window.close()
