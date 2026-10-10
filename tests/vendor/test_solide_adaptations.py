from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import BrowserReviewService


def test_solide_profile_and_cancer_defaults_are_retained(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    service = BrowserReviewService(mtbp_cancer_type=" ")

    assert service.profile_root == tmp_path / ".solide" / "browser_profiles"
    assert service.mtbp_cancer_type == "Other"


def test_mtbp_preflight_empties_all_report_types(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    names = ["manual-report", "ARCHER-old", "SOLIDE-old"]
    monkeypatch.setattr(service, "_goto_with_retries", lambda *args, **kwargs: None)
    class Buttons:
        def count(self): return len(names)
        def nth(self, i): return SimpleNamespace(get_attribute=lambda _: names[i])
    page = SimpleNamespace(url="https://mtbp.org/patients/", locator=lambda _: Buttons())
    def delete(current, name):
        assert current is page
        names.remove(name)
        return {"status": "deleted"}
    monkeypatch.setattr(service, "_delete_mtbp_report", delete)
    outcome = service._cleanup_stale_mtbp_reports(page, progress=None)
    assert outcome["deleted_reports"] == ["manual-report", "ARCHER-old", "SOLIDE-old"]
    assert outcome["remaining_reports"] == 0


def test_failed_mtbp_deletion_blocks_new_submission(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    monkeypatch.setattr(service, "_goto_with_retries", lambda *args, **kwargs: None)
    buttons = SimpleNamespace(count=lambda: 1, nth=lambda _: SimpleNamespace(get_attribute=lambda _: "old"))
    page = SimpleNamespace(url="https://mtbp.org/patients/", locator=lambda _: buttons)
    monkeypatch.setattr(service, "_delete_mtbp_report", lambda *args: {"status": "failed", "message": "still listed"})
    with pytest.raises(RuntimeError, match="no new analysis"):
        service._cleanup_stale_mtbp_reports(page, progress=None)


def test_genomic_alleles_keep_missing_hgvs_keys_and_captures_distinct(tmp_path):
    first = VariantRecord(Path("synthetic.tsv"), 1, "SYNTHETIC", "TP53", "",
                          genomic_location="chr17:7578406", ref_allele="G", alt_allele="A")
    second = replace(first, alt_allele="T")
    service = BrowserReviewService(profile_root=tmp_path)

    assert service.variant_key(first) != service.variant_key(second)
    assert service._screenshot_path(tmp_path, "ClinVar", first) != service._screenshot_path(tmp_path, "ClinVar", second)


def test_cosmic_capture_keeps_sample_rows_from_all_tissues(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    record = VariantRecord(Path("synthetic.tsv"), 1, "SYNTHETIC", "TP53", "", cosmic_id="COSM1")
    filters = []
    all_rows = ["breast specimen", "lymphoid specimen"]
    search = SimpleNamespace(count=lambda: 1, fill=filters.append)
    rows = SimpleNamespace(all_inner_texts=lambda: all_rows if filters[-1] == "" else ["lymphoid specimen"])
    section = SimpleNamespace(locator=lambda selector: search if selector.startswith("input") else rows,
                              screenshot=lambda **kwargs: None)
    page = SimpleNamespace(url="https://cancer.sanger.ac.uk/cosmic/mutation/overview?id=1&genome=37",
                           locator=lambda selector: SimpleNamespace(inner_text=lambda **kwargs: "COSM1"),
                           wait_for_timeout=lambda milliseconds: None)
    monkeypatch.setattr(service, "_cosmic_section", lambda *args: section)

    evidence = service._capture_cosmic_result(record, page, tmp_path / "captures")

    assert evidence.raw["sample_filter"] == ""
    assert evidence.raw["visible_sample_rows"] == all_rows
