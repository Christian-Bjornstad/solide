from pathlib import Path
from types import SimpleNamespace

import pytest

from solide._vendor.archer.core.models import DatabaseEvidence
from solide._vendor.archer.services.browser_review import BrowserReviewService


@pytest.mark.parametrize("identifier", ["SOLIDE-old", "ARCHER-old", "manual report"])
def test_delete_verifies_server_after_settling(tmp_path, monkeypatch, identifier):
    service = BrowserReviewService(profile_root=tmp_path)
    state = {"checks": 0, "clicked": 0, "waits": []}
    button = SimpleNamespace(count=lambda: 1, get_attribute=lambda _: identifier,
                             click=lambda: state.update(clicked=state["clicked"] + 1))
    row = SimpleNamespace(locator=lambda _: button)
    link = SimpleNamespace(count=lambda: int(state["checks"] < 2), locator=lambda _: row)
    page = SimpleNamespace(url="https://mtbp.org/patients/", get_by_role=lambda *a, **k: link,
                           once=lambda *a: None, wait_for_timeout=state["waits"].append)
    monkeypatch.setattr(service, "_goto_with_retries", lambda *a, **k: state.update(checks=state["checks"] + 1))
    assert service._delete_mtbp_report(page, identifier)["status"] == "deleted"
    assert state["clicked"] == 1
    assert state["waits"] == [5000, 5000]


def test_delete_control_identity_mismatch_does_not_click(tmp_path):
    service = BrowserReviewService(profile_root=tmp_path)
    button = SimpleNamespace(count=lambda: 1, get_attribute=lambda _: "different",
                             click=lambda: pytest.fail("Wrong report must not be deleted"))
    link = SimpleNamespace(count=lambda: 1, locator=lambda _: SimpleNamespace(locator=lambda _: button))
    page = SimpleNamespace(url="https://mtbp.org/patients/", get_by_role=lambda *a, **k: link)
    assert service._delete_mtbp_report(page, "requested")["status"] == "failed"


def test_no_match_report_is_deleted_after_local_audit(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    events = []
    evidence = DatabaseEvidence("MTBP", "not_found", "No match")
    monkeypatch.setattr(service, "_write_audit", lambda *a: events.append("audit"))
    monkeypatch.setattr(service, "_delete_mtbp_report", lambda *a: events.append("delete") or {"status": "deleted"})
    service._finalize_mtbp_report(object(), "SOLIDE-test", [(tmp_path / "audit.json", evidence)])
    assert events == ["audit", "delete", "audit"]
    assert evidence.raw["remote_report_cleanup"]["status"] == "deleted"


def test_delete_navigates_from_patient_report_to_list(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    destinations = []
    page = SimpleNamespace(url="https://mtbp.org/patients/123/sample/123/report/456/",
                           get_by_role=lambda *a, **k: SimpleNamespace(count=lambda: 0))
    monkeypatch.setattr(service, "_goto_with_retries", lambda current, url: (destinations.append(url), setattr(current, "url", url)))
    assert service._delete_mtbp_report(page, "SOLIDE-test")["status"] == "already_absent"
    assert destinations == ["https://mtbp.org/patients/"]


def test_login_redirect_cannot_confirm_report_absence(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    page = SimpleNamespace(url="https://mtbp.org/login/",
                           get_by_role=lambda *a, **k: pytest.fail("Login page is not a report list"))
    monkeypatch.setattr(service, "_goto_with_retries", lambda *a: None)
    assert service._delete_mtbp_report(page, "SOLIDE-test")["status"] == "failed"


def test_cleanup_failure_is_visible_and_retryable(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    evidence = DatabaseEvidence("MTBP", "found", "Captured")
    monkeypatch.setattr(service, "_write_audit", lambda *a: None)
    monkeypatch.setattr(service, "_delete_mtbp_report", lambda *a: {"status": "failed"})
    service._finalize_mtbp_report(object(), "SOLIDE-test", [(tmp_path / "audit.json", evidence)])
    assert evidence.status == "partial_capture"
    assert "cleanup failed" in evidence.summary
