from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone

import pytest

from solide._vendor.archer.core.models import DatabaseEvidence, VariantRecord
from solide._vendor.archer.services.browser_review import BrowserReviewCancelled, BrowserReviewService


@pytest.mark.parametrize('age_minutes,body,url,expected',[
    (21,'Reports List other report','https://mtbp.org/patients/',True),
    (21,'Report List Currently, 0 Reports Report ID Entry Date Cancer Type Share Delete','https://mtbp.org/patients/',True),
    (21,'Currently, 0 Reports','https://mtbp.org/patients/',False),
    (1,'Reports List other report','https://mtbp.org/patients/',False),
    (21,'Reports List SOLIDE-retained Processing','https://mtbp.org/patients/',False),
    (21,'Reports List other report','https://mtbp.org/login/',False),
])
def test_lost_submission_requires_expired_deadline_and_two_confirmed_absence_checks(tmp_path,monkeypatch,age_minutes,body,url,expected):
    service=BrowserReviewService(profile_root=tmp_path);reloads=[]
    prior=DatabaseEvidence('MTBP','submission_unknown',raw={'analysis_id':'SOLIDE-retained',
        'submitted_at':(datetime.now(timezone.utc)-timedelta(minutes=age_minutes)).isoformat()})
    page=SimpleNamespace(url=url,locator=lambda selector:SimpleNamespace(count=lambda:1 if "Currently" in body else 3,inner_text=lambda:body))
    monkeypatch.setattr(service,'_goto_with_retries',lambda *args:reloads.append(True))
    assert service._mtbp_submission_confirmed_absent(page,prior) is expected
    assert bool(reloads) is expected


@pytest.mark.parametrize("button_ready, acknowledgement_lost, expected", [(True, False, "submission_unknown"), (False, False, "error"), (True, True, "submission_unknown")])
def test_mtbp_uncertain_acceptance_preserves_exact_recovery_id(tmp_path, monkeypatch, button_ready, acknowledgement_lost, expected):
    record = VariantRecord(Path("synthetic.tsv"), 1, "SYNTHETIC", "TP53",
                           "NM_000546.6:c.524G>A", "p.Arg175His")
    clicks = []
    submitted_ids = []
    def dispatch_click():
        clicks.append("clicked")
        if acknowledgement_lost:
            raise TimeoutError("synthetic click dispatched but CDP acknowledgement was lost")

    button = SimpleNamespace(is_visible=lambda: True, is_enabled=lambda: button_ready,
                             click=dispatch_click)
    page = SimpleNamespace(url="https://mtbp.org/analyse/", locator=lambda selector: button)
    context = SimpleNamespace(pages=[page], close=lambda: None)

    class Runtime:
        chromium = SimpleNamespace(launch_persistent_context=lambda *args, **kwargs: context)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    service = BrowserReviewService(profile_root=tmp_path)
    checkpoints = []
    monkeypatch.setattr(service, "_browser_api", lambda: (Runtime, Exception, TimeoutError))
    monkeypatch.setattr(service, "_goto_with_retries", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_session_authenticated", lambda *args: True)
    monkeypatch.setattr(service, "_cleanup_stale_mtbp_reports", lambda *args, **kwargs: {})
    monkeypatch.setattr(service, "_fill_mtbp_form", lambda page, analysis_id, queries: submitted_ids.append(analysis_id))
    monkeypatch.setattr(service, "_wait_for_mtbp_acceptance", lambda page: (_ for _ in ()).throw(TimeoutError("synthetic stalled acceptance")))
    monkeypatch.setattr(service, "_recover_mtbp_timeouts", lambda *args, **kwargs: {})

    evidence = service.search_variants(
        [record], ["MTBP"], tmp_path / "captures", checkpoint=checkpoints.append
    )[service.variant_key(record)][0]

    assert evidence.status == expected
    assert evidence.raw["analysis_id"] == submitted_ids[0]
    assert evidence.raw["analysis_id"].startswith("SOLIDE-")
    assert evidence.raw["failure_stage"] == "submission_acceptance"
    assert clicks == (["clicked"] if button_ready else [])
    if button_ready:
        assert evidence.raw["remote_report_recovery"]["status"] == "pending"
        assert checkpoints[0][service.variant_key(record)][0].raw["provisional_status"] == "submission_unknown"
    assert "provisional_status" not in evidence.raw
    assert "provisional_status" not in checkpoints[-1][service.variant_key(record)][0].raw


def test_unknown_submission_is_recovered_before_any_new_batch(tmp_path, monkeypatch):
    record = VariantRecord(Path("synthetic.tsv"), 1, "SYNTHETIC", "TP53", "NM_000546.6:c.524G>A")
    previous = DatabaseEvidence("MTBP", "submission_unknown", raw={"analysis_id": "SOLIDE-retained"})
    service = BrowserReviewService(profile_root=tmp_path)
    recovered = DatabaseEvidence("MTBP", "found", "retained exact report", raw={"analysis_id": "SOLIDE-retained"})
    monkeypatch.setattr(service, "_recover_mtbp_timeouts", lambda *args, **kwargs: {service.variant_key(record): recovered})
    monkeypatch.setattr(service, "_search_mtbp_batch", lambda *args, **kwargs: pytest.fail("Unknown submission must be reconciled before a new batch"))

    results = service._search_mtbp([record], tmp_path / "captures", progress=None,
                                   prior_evidence={service.variant_key(record): [previous]})

    assert results[service.variant_key(record)] is recovered


@pytest.mark.parametrize("recovery_returns_prior", [False, True])
def test_returned_retained_submission_is_final_without_mutating_checkpoint(tmp_path, monkeypatch, recovery_returns_prior):
    record = VariantRecord(Path("synthetic.tsv"), 1, "SYNTHETIC", "TP53", "NM_000546.6:c.524G>A")
    previous = DatabaseEvidence("MTBP", "submission_unknown", raw={
        "analysis_id": "SOLIDE-retained", "provisional_status": "submission_unknown",
    })
    service = BrowserReviewService(profile_root=tmp_path)
    checkpoints = []
    key = service.variant_key(record)
    monkeypatch.setattr(service, "_recover_mtbp_timeouts", lambda *args, **kwargs: {key: previous} if recovery_returns_prior else {})
    monkeypatch.setattr(service, "_search_mtbp_batch", lambda *args, **kwargs: pytest.fail("Retained submission must not be resubmitted"))

    results = service.search_variants([record], ["MTBP"], tmp_path / "captures",
                                      checkpoint=checkpoints.append, prior_evidence={key: [previous]})

    assert results[key][0].status == "submission_unknown"
    assert results[key][0].raw["analysis_id"] == "SOLIDE-retained"
    assert "provisional_status" not in results[key][0].raw
    assert "provisional_status" not in checkpoints[-1][key][0].raw
    assert previous.raw["provisional_status"] == "submission_unknown"


def test_accepted_submission_is_checkpointed_before_cancellable_report_wait(tmp_path, monkeypatch):
    import json

    record = VariantRecord(Path("synthetic.tsv"), 1, "SYNTHETIC", "TP53", "NM_000546.6:c.524G>A")
    closed = []
    checkpoints = []
    button = SimpleNamespace(is_visible=lambda: True, is_enabled=lambda: True, click=lambda: None)
    page = SimpleNamespace(url="https://mtbp.org/queue/synthetic", locator=lambda selector: button)
    context = SimpleNamespace(pages=[page], close=lambda: closed.append(True))

    class Runtime:
        chromium = SimpleNamespace(launch_persistent_context=lambda *args, **kwargs: context)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    service = BrowserReviewService(profile_root=tmp_path)
    monkeypatch.setattr(service, "_browser_api", lambda: (Runtime, Exception, TimeoutError))
    monkeypatch.setattr(service, "_goto_with_retries", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_session_authenticated", lambda *args: True)
    monkeypatch.setattr(service, "_cleanup_stale_mtbp_reports", lambda *args, **kwargs: {})
    monkeypatch.setattr(service, "_fill_mtbp_form", lambda *args: None)
    monkeypatch.setattr(service, "_wait_for_mtbp_acceptance", lambda page: "")

    def cancel_wait(*args, **kwargs):
        assert checkpoints, "Report ID must be stored before a cancellable wait"
        raise BrowserReviewCancelled()

    monkeypatch.setattr(service, "_wait_for_mtbp_report", cancel_wait)

    with pytest.raises(BrowserReviewCancelled):
        service.search_variants([record], ["MTBP"], tmp_path / "captures", checkpoint=checkpoints.append)

    pending = checkpoints[0][service.variant_key(record)][0]
    assert pending.status == "submission_unknown"
    assert pending.raw["provisional_status"] == "submission_unknown"
    assert pending.raw["analysis_id"].startswith("SOLIDE-")
    audits = list((tmp_path / "captures" / "mtbp").glob("*.audit.json"))
    assert len(audits) == 1
    audit_raw = json.loads(audits[0].read_text(encoding="utf-8"))["raw"]
    assert audit_raw["analysis_id"] == pending.raw["analysis_id"]
    assert audit_raw["provisional_status"] == "submission_unknown"
    assert closed
