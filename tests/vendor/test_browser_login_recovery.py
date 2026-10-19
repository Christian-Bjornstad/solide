from contextlib import contextmanager
from types import SimpleNamespace
from pathlib import Path

import pytest

from solide._vendor.archer.services.browser_review import BrowserReviewService, BrowserReviewCancelled


def login_runtime(service, monkeypatch, page):
    context = SimpleNamespace(pages=[page], closed=False)
    def close():context.closed = True
    context.close = close
    @contextmanager
    def runtime():yield SimpleNamespace()
    monkeypatch.setattr(service, '_browser_api', lambda: (runtime, RuntimeError, TimeoutError))
    monkeypatch.setattr(service, '_launch_browser_context', lambda *a, **k: context)
    return context


def test_login_navigation_failure_always_releases_profile(monkeypatch, tmp_path):
    service = BrowserReviewService(profile_root=tmp_path)
    def fail(*a, **k):raise ValueError('Navigation interrupted')
    page = SimpleNamespace(goto=fail)
    context = login_runtime(service, monkeypatch, page)
    with pytest.raises(ValueError):service.open_login('MTBP')
    assert context.closed
    assert not service.login_confirmed


def test_login_cancel_after_launch_releases_profile(monkeypatch, tmp_path):
    stop = [False]
    service = BrowserReviewService(profile_root=tmp_path, stop_requested=lambda: stop[0])
    def goto(*a, **k):stop[0] = True
    page = SimpleNamespace(goto=goto, bring_to_front=lambda: None)
    context = login_runtime(service, monkeypatch, page)
    monkeypatch.setattr(service, '_try_saved_login', lambda *a: pytest.fail('Cancelled login must not submit credentials'))
    with pytest.raises(BrowserReviewCancelled):service.open_login('MTBP')
    assert context.closed


@pytest.mark.parametrize('database,url', [
    ('Franklin', 'about:blank'),
    ('Franklin', 'https://franklin.genoox.com/'),
    ('OncoKB', 'about:blank'),
    ('OncoKB', 'https://www.oncokb.org/'),
    ('MTBP', 'https://other.example/analyse/'),
    ('COSMIC', 'https://other.example/cosmic/'),
])
def test_back_or_public_page_never_confirms_login(database, url):
    page = SimpleNamespace(url=url, evaluate=lambda *a, **k: {},
        locator=lambda *a: SimpleNamespace(count=lambda: 0),
        get_by_role=lambda *a, **k: SimpleNamespace(count=lambda: 0))
    assert not BrowserReviewService()._session_authenticated(database, page)


def test_saved_login_wait_is_cancellable_and_does_not_block_for_url(monkeypatch):
    stop = [False]
    service = BrowserReviewService(mtbp_email='dummy@example.org', mtbp_password='wrong',
        stop_requested=lambda: stop[0])
    control = SimpleNamespace(fill=lambda value: None, click=lambda: None)
    page = SimpleNamespace(url='https://auth.mtbp.org/auth/login', locator=lambda *a: control,
        wait_for_url=lambda *a, **k: pytest.fail('A single long URL wait cannot be cancelled'),
        wait_for_timeout=lambda ms: stop.__setitem__(0, True))
    monkeypatch.setattr(service, '_session_authenticated', lambda *a: False)
    monkeypatch.setattr(service, '_login_rejected', lambda *a: False)
    with pytest.raises(BrowserReviewCancelled):service._try_saved_login('MTBP', page)


@pytest.mark.parametrize('database,url,snapshot', [
    ('Franklin','https://franklin.genoox.com/clinical-db/home',{'franklinSearch':True}),
    ('Franklin','https://franklin.genoox.com/clinical-db/variant/snp/test',{'franklinUser':True}),
    ('OncoKB','https://www.oncokb.org/',{'oncokbAccount':True}),
    ('COSMIC','https://cancer.sanger.ac.uk/cosmic/',{'logout':True}),
    ('MTBP','https://mtbp.org/analyse/',{'mtbpInput':True}),
])
def test_provider_specific_positive_login_controls(database,url,snapshot):
    service=BrowserReviewService()
    page=SimpleNamespace(url=url,evaluate=lambda *a,**k:snapshot)
    assert service._session_authenticated(database,page)
    assert database in service.authenticated_sources
    page.url='about:blank'
    assert not service._session_authenticated(database,page)
    assert database not in service.authenticated_sources


def test_existing_session_does_not_verify_newly_entered_password(monkeypatch):
    service=BrowserReviewService(mtbp_email='dummy@example.org',mtbp_password='untested')
    monkeypatch.setattr(service,'_session_authenticated',lambda *a:True)
    assert service._try_saved_login('MTBP',None)
    assert not service.login_credentials_verified


def test_detached_login_form_does_not_verify_unsubmitted_credentials(monkeypatch):
    service=BrowserReviewService(mtbp_email='unverified@example.org',mtbp_password='never-submitted')
    checks=iter((False,True))
    monkeypatch.setattr(service,'_session_authenticated',lambda *a:next(checks))
    def detached(value):raise RuntimeError('Login form detached before submission')
    page=SimpleNamespace(locator=lambda *args:SimpleNamespace(fill=detached))
    assert service._try_saved_login('MTBP',page)
    assert not service.login_credentials_verified


@pytest.mark.parametrize('verified,status,expected', [(True,'found',True),(False,'found',False),(True,'login_required',False)])
def test_persisted_auth_marker_requires_fresh_check(monkeypatch,tmp_path,verified,status,expected):
    from solide._vendor.archer.core.models import DatabaseEvidence,VariantRecord
    service=BrowserReviewService(profile_root=tmp_path)
    variant=VariantRecord(Path('dummy.tsv'),1,'26OUM00000','EGFR','NM_005228.5:c.2573T>G')
    evidence=DatabaseEvidence('OncoKB',status,raw={'auth_verified':True,'auth_verified_at':'old'})
    def search(*a,**k):
        if verified:service.authenticated_sources.add('OncoKB')
        return {service.variant_key(variant):evidence}
    monkeypatch.setattr(service,'_search_database',search)
    service.search_variants([variant],['OncoKB'],tmp_path/'evidence')
    assert evidence.raw.get('auth_verified',False) is expected
    assert evidence.raw.get('auth_verified_at') != 'old'
