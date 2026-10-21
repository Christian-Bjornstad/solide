from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from solide._vendor.archer.services.browser_review import BrowserReviewCancelled, BrowserReviewService
from solide._vendor.archer.services.edge_cdp import EdgeCdpError, EdgeCdpTimeout


class LoginPage:
    url = 'about:blank'

    def __init__(self, *, failure=None, delayed=False):
        self.failure = failure
        self.delayed = delayed
        self.calls = []
        self.waits = 0
        self.form = False

    def goto(self, url, **kwargs):
        self.calls.append(kwargs['timeout'])
        self.url = 'https://mtbp.org/keycloak/realms/MTBP/protocol/openid-connect/auth'
        if not self.delayed:
            self.form = True
        if self.failure:
            raise self.failure

    def bring_to_front(self):
        pass

    def wait_for_timeout(self, milliseconds):
        self.waits += 1
        if self.delayed and self.waits >= 2:
            self.form = True

    def evaluate(self, *args, **kwargs):
        return {}

    def locator(self, selector):
        return SimpleNamespace(count=lambda: int(self.form), is_visible=lambda: self.form)


def runtime(monkeypatch, service, page):
    context = SimpleNamespace(pages=[page], closed=False)
    context.close = lambda: setattr(context, 'closed', True)
    @contextmanager
    def browser():
        yield object()
    monkeypatch.setattr(service, '_browser_api', lambda: (browser, EdgeCdpError, EdgeCdpTimeout))
    monkeypatch.setattr(service, '_launch_browser_context', lambda *args, **kwargs: context)
    return context


def test_mtbp_login_uses_full_configured_navigation_timeout(monkeypatch, tmp_path):
    service = BrowserReviewService(profile_root=tmp_path)
    page = LoginPage()
    def navigate(url, **kwargs):
        page.calls.append(kwargs['timeout'])
        if kwargs['timeout'] < 20_000:
            raise EdgeCdpTimeout('Microsoft Edge timed out during Page.navigate.')
        page.url = 'https://mtbp.org/keycloak/realms/MTBP/auth'
        page.form = True
    page.goto = navigate
    context = runtime(monkeypatch, service, page)
    monkeypatch.setattr(service, '_try_saved_login', lambda *args: True)
    assert service.open_login('MTBP') == 'MTBP: Innlogget.'
    assert page.calls == [45_000] and context.closed


@pytest.mark.parametrize('delayed', [False, True])
def test_timeout_does_not_discard_a_ready_or_finishing_login_form(monkeypatch, tmp_path, delayed):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=1_000)
    page = LoginPage(failure=EdgeCdpTimeout('Microsoft Edge timed out during Page.navigate.'), delayed=delayed)
    context = runtime(monkeypatch, service, page)
    submissions = []
    def authenticate(*args):
        assert page.form
        submissions.append(True)
        return True
    monkeypatch.setattr(service, '_try_saved_login', authenticate)
    assert service.open_login('MTBP') == 'MTBP: Innlogget.'
    assert len(page.calls) == 1 and submissions == [True] and context.closed


def test_navigation_waits_for_form_before_attempting_credentials(monkeypatch, tmp_path):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=1_000)
    page = LoginPage(delayed=True)
    runtime(monkeypatch, service, page)
    def authenticate(*args):
        assert page.form, 'Credentials must wait for the actual MTBP login form'
        return True
    monkeypatch.setattr(service, '_try_saved_login', authenticate)
    assert service.open_login('MTBP') == 'MTBP: Innlogget.'


@pytest.mark.parametrize('failure', [
    EdgeCdpTimeout('Microsoft Edge timed out during Page.navigate.'),
    EdgeCdpError('Edge navigation failed: net::ERR_CONNECTION_TIMED_OUT'),
])
def test_unreachable_mtbp_retries_once_then_returns_clear_unconfirmed_result(monkeypatch, tmp_path, failure):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=250)
    page = LoginPage(failure=failure)
    def navigate(url, **kwargs):
        page.calls.append(kwargs['timeout'])
        raise failure
    page.goto = navigate
    context = runtime(monkeypatch, service, page)
    monkeypatch.setattr(service, '_try_saved_login', lambda *args: pytest.fail('No form loaded; do not send credentials'))
    message = service.open_login('MTBP')
    assert not service.login_confirmed and not service.login_credentials_verified
    assert len(page.calls) == 2 and context.closed
    assert 'MTBP' in message and 'forbindelse' in message.lower()


@pytest.mark.parametrize('address', [
    'https://other.example/keycloak/auth', 'http://mtbp.org/keycloak/auth',
    'https://mtbp.org.evil.example/keycloak/auth', 'https://mtbp.org:8443/keycloak/auth',
])
def test_foreign_or_insecure_page_cannot_receive_saved_mtbp_credentials(monkeypatch, tmp_path, address):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=250)
    page = LoginPage()
    def navigate(url, **kwargs):
        page.calls.append(kwargs['timeout'])
        page.url = address
        page.form = True
    page.goto = navigate
    context = runtime(monkeypatch, service, page)
    monkeypatch.setattr(service, '_try_saved_login', lambda *args: pytest.fail('Foreign login form'))
    service.open_login('MTBP')
    assert not service.login_confirmed and context.closed


def test_cancel_during_delayed_login_releases_profile_before_credentials(monkeypatch, tmp_path):
    stop = [False]
    service = BrowserReviewService(profile_root=tmp_path, stop_requested=lambda: stop[0])
    page = LoginPage(delayed=True)
    page.wait_for_timeout = lambda milliseconds: stop.__setitem__(0, True)
    context = runtime(monkeypatch, service, page)
    monkeypatch.setattr(service, '_try_saved_login', lambda *args: pytest.fail('Cancelled'))
    with pytest.raises(BrowserReviewCancelled):
        service.open_login('MTBP')
    assert context.closed


def test_one_transient_connection_failure_recovers_before_credentials(monkeypatch, tmp_path):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=250)
    page = LoginPage()
    original = page.goto
    def navigate(url, **kwargs):
        if not page.calls:
            page.calls.append(kwargs['timeout'])
            raise EdgeCdpError('Edge navigation failed: net::ERR_CONNECTION_TIMED_OUT')
        original(url, **kwargs)
    page.goto = navigate
    context = runtime(monkeypatch, service, page)
    submitted = []
    monkeypatch.setattr(service, '_try_saved_login', lambda *args: submitted.append(True) or True)
    assert service.open_login('MTBP') == 'MTBP: Innlogget.'
    assert len(page.calls) == 2 and submitted == [True] and context.closed


def test_mtbp_waits_beyond_fifteen_seconds_after_one_credential_submission(monkeypatch):
    service = BrowserReviewService(mtbp_email='synthetic@example.org', mtbp_password='synthetic')
    clock = [0.0]
    submitted = []
    page = LoginPage()
    page.url = 'https://mtbp.org/keycloak/auth'
    page.locator = lambda selector: SimpleNamespace(fill=lambda value: None, click=lambda: submitted.append(True))
    page.wait_for_timeout = lambda milliseconds: clock.__setitem__(0, clock[0] + milliseconds / 1000)
    monkeypatch.setattr('solide._vendor.archer.services.browser_review.time.monotonic', lambda: clock[0])
    monkeypatch.setattr(service, '_session_authenticated', lambda *args: clock[0] >= 20)
    monkeypatch.setattr(service, '_login_rejected', lambda *args: False)
    assert service._try_saved_login('MTBP', page)
    assert service.login_credentials_verified and submitted == [True]
