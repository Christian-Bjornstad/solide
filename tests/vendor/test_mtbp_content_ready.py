from types import SimpleNamespace

import pytest

from solide._vendor.archer.services.browser_review import BrowserReviewService


def test_report_recovery_navigates_target_blank_link_in_controlled_tab(tmp_path,monkeypatch):
    service=BrowserReviewService(profile_root=tmp_path);destinations=[]
    link=SimpleNamespace(get_attribute=lambda _: '/patients/source/report/123/',
                         click=lambda:pytest.fail('Opening a new tab loses the controlled report'))
    page=object()
    monkeypatch.setattr(service,'_goto_with_retries',lambda current,url:destinations.append((current,url)))
    service._open_mtbp_report_link(page,link)
    assert destinations==[(page,'https://mtbp.org/patients/source/report/123/')]


def test_report_recovery_rejects_external_report_link(tmp_path):
    service=BrowserReviewService(profile_root=tmp_path)
    link=SimpleNamespace(get_attribute=lambda _: 'https://example.org/patients/source/report/123/')
    with pytest.raises(ValueError,match='unsupported report link'):
        service._open_mtbp_report_link(object(),link)


def test_report_navigation_waits_for_stable_loaded_alterations(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    state = {"index": 0}
    rows = [[], [{"gene": "TP53", "identity_text": "p.Arg175His"}]]
    page = SimpleNamespace(
        url="https://mtbp.org/patients/source/report/123/",
        locator=lambda _: SimpleNamespace(inner_text=lambda **kwargs: "Analysis run date: today Pipeline version: 7.7"),
        wait_for_timeout=lambda _: state.update(index=state["index"] + 1),
        evaluate=lambda _: False,
    )
    monkeypatch.setattr(service, "_extract_mtbp_rows", lambda _: rows[min(state["index"], 1)])
    service._wait_for_mtbp_content(page)
    assert state["index"] == 2


def test_populated_report_still_waits_for_loading_overlay(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    state = {"index": 0}
    page = SimpleNamespace(
        url="https://mtbp.org/patients/source/report/123/",
        locator=lambda _: SimpleNamespace(inner_text=lambda **kwargs: "Analysis run date: today Pipeline version: 7.7"),
        evaluate=lambda _: state["index"] < 2,
        wait_for_timeout=lambda _: state.update(index=state["index"] + 1),
    )
    monkeypatch.setattr(service, "_extract_mtbp_rows", lambda _: [{"gene": "TP53", "identity_text": "p.Arg175His"}])
    service._wait_for_mtbp_content(page)
    assert state["index"] == 3


@pytest.mark.parametrize("url, body", [
    ("https://mtbp.org/patients/source/report/123/", "Loading"),
    ("https://mtbp.org/login/", "Analysis run date: today Pipeline version: 7.7"),
    ("https://mtbp.org/patients/source/report/123/", "Analysis run date: today Pipeline version: 7.7"),
])
def test_incomplete_report_cannot_be_interpreted_as_no_match(tmp_path, monkeypatch, url, body):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=1)
    page = SimpleNamespace(url=url, locator=lambda _: SimpleNamespace(inner_text=lambda **kwargs: body),
                           wait_for_timeout=lambda _: None, evaluate=lambda _: False)
    monkeypatch.setattr(service, "_extract_mtbp_rows", lambda _: [])
    with pytest.raises(TimeoutError, match="no absence of matches was inferred"):
        service._wait_for_mtbp_content(page)
