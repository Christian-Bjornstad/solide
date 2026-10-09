from pathlib import Path

import pytest
from PIL import Image

from solide._vendor.archer.core.models import DatabaseEvidence, VariantRecord
from solide._vendor.archer.services import browser_review
from solide._vendor.archer.services.browser_review import BrowserReviewService, parse_oncokb_page, FRANKLIN_HOME_URL
from solide._vendor.archer.services.capture_validation import CaptureValidation, IncompleteCaptureError
from solide._vendor.archer.services.provider_failures import ProviderFailureKind, ProviderLookupError

VALID_CAPTURE = lambda _: CaptureValidation(True, "ok", 800, 500, 10.0)


def synthetic_variant():
    return VariantRecord(source_file=Path("synthetic.tsv"), source_row=1, sample="SYNTHETIC",
                         symbol="TP53", hgvsc="NM_000546.6:c.524G>A", hgvsp="p.Arg175His",
                         genomic_location="chr17:7578406", ref_allele="G", alt_allele="A",
                         cosmic_id="COSM10648")


def _oncokb_query_urls(record):
    return browser_review._oncokb_query_urls(record)


def test_mtbp_variant_capture_uses_direct_fallback_when_report_crop_fails(tmp_path, monkeypatch):
    variant = synthetic_variant()
    service = BrowserReviewService(profile_root=tmp_path)
    full_report = tmp_path / "patient-report.png"
    direct_image = tmp_path / "variant.png"
    attempts = []

    def failed_crop(*args):
        attempts.append("crop")
        raise IncompleteCaptureError(CaptureValidation(False, "missing row", 0, 0, 0.0))

    def direct_capture(*args):
        attempts.append("direct")
        return direct_image

    monkeypatch.setattr(service, "_crop_mtbp_variant_from_report", failed_crop)
    monkeypatch.setattr(service, "_capture_mtbp_variant_screenshot", direct_capture)

    assert service._capture_mtbp_variant_with_fallback(
        object(), variant, tmp_path, full_report
    ) == direct_image
    assert attempts == ["crop", "direct"]


def test_cosmic_cache_returns_independent_evidence_objects(tmp_path, monkeypatch):
    from dataclasses import replace

    first = synthetic_variant()
    first.cosmic_id = "COSM10648"
    second = replace(first, sample="second-patient-sample")
    service = BrowserReviewService(profile_root=tmp_path)
    calls = []

    def lookup(page, candidate, query_url, artifact_directory, *, progress):
        calls.append(candidate.cosmic_id)
        return DatabaseEvidence(
            "COSMIC",
            "found",
            "matched",
            accession=candidate.cosmic_id,
            raw={"screenshots": [{"path": "shared.png"}]},
        )

    monkeypatch.setattr(service, "_lookup_cosmic_with_retry", lookup)

    first_result = service._lookup_cosmic_variant(
        object(), first, tmp_path, progress=None
    )
    second_result = service._lookup_cosmic_variant(
        object(), second, tmp_path, progress=None
    )
    second_result.raw["query_attempts"].append("mutated")

    assert calls == ["COSM10648"]
    assert first_result is not second_result
    assert first_result.raw["query_attempts"] == ["COSM10648"]


def test_oncokb_visible_page_parser_rejects_different_variant_content():
    variant = synthetic_variant()
    body = """
    BRAF V600E Somatic
    Variant Overview
    The BRAF V600E mutation is known to be oncogenic.
    Mutation Effect
    Oncogenicity
    Oncogenic
    Biological Effect
    Gain-of-function
    Highest Level of Evidence
    """

    evidence = parse_oncokb_page(body, variant, "https://www.oncokb.org/example")

    assert evidence.status == "identity_mismatch"


def test_oncokb_visible_page_parser_extracts_core_evidence_for_requested_synthetic_variant():
    variant = synthetic_variant()
    body = """
    TP53 R175H Somatic
    Variant Overview
    The TP53 R175H mutation is known to be oncogenic.
    Mutation Effect
    Oncogenicity
    Oncogenic
    Biological Effect
    Gain-of-function
    Highest Level of Evidence
    """

    evidence = parse_oncokb_page(
        body, variant, "https://www.oncokb.org/gene/TP53/somatic/R175H"
    )

    assert evidence.status == "found"
    assert evidence.clinical_significance == "Oncogenic"
    assert "mutation_effect=Gain-of-function" in evidence.summary


def test_oncokb_queries_add_documented_grch37_hgvsg_fallback():
    variant = synthetic_variant()

    assert _oncokb_query_urls(variant) == [
        "https://www.oncokb.org/gene/TP53/somatic/R175H",
        "https://www.oncokb.org/hgvsg/17:g.7578406G%3EA?refGenome=GRCh37",
    ]


def test_oncokb_fallback_runs_only_after_identity_failure(tmp_path, monkeypatch):
    variant = synthetic_variant()
    service = BrowserReviewService(profile_root=tmp_path)
    attempted = []

    def lookup(page, candidate, url, artifact_directory):
        attempted.append(url)
        if "/gene/" in url:
            return DatabaseEvidence(
                "OncoKB",
                "not_found",
                "canonical transcript mismatch",
                raw={"failure_kind": ProviderFailureKind.IDENTITY_MISMATCH.value},
            )
        return DatabaseEvidence("OncoKB", "found", "verified genomic result")

    monkeypatch.setattr(service, "_lookup_oncokb_url", lookup)

    evidence = service._lookup_oncokb_variant(object(), variant, tmp_path)

    assert evidence.status == "found"
    assert attempted == _oncokb_query_urls(variant)
    assert evidence.raw["query_attempts"] == attempted


def test_oncokb_transient_error_does_not_switch_query_identity(tmp_path, monkeypatch):
    variant = synthetic_variant()
    service = BrowserReviewService(profile_root=tmp_path)
    attempted = []

    def lookup(page, candidate, url, artifact_directory):
        attempted.append(url)
        return DatabaseEvidence("OncoKB", "error", "provider unavailable")

    monkeypatch.setattr(service, "_lookup_oncokb_url", lookup)

    evidence = service._lookup_oncokb_variant(object(), variant, tmp_path)

    assert evidence.status == "error"
    assert attempted == [_oncokb_query_urls(variant)[0]]


def test_oncokb_unresolved_transcript_mismatch_requires_manual_review(
    tmp_path, monkeypatch
):
    variant = synthetic_variant()
    service = BrowserReviewService(profile_root=tmp_path)

    def lookup(page, candidate, url, artifact_directory):
        if "/gene/" in url:
            return DatabaseEvidence(
                "OncoKB",
                "not_found",
                "canonical transcript mismatch",
                raw={"failure_kind": ProviderFailureKind.IDENTITY_MISMATCH.value},
            )
        return DatabaseEvidence("OncoKB", "not_found", "no genomic result")

    monkeypatch.setattr(service, "_lookup_oncokb_url", lookup)

    evidence = service._lookup_oncokb_variant(object(), variant, tmp_path)

    assert evidence.status == "manual_review"
    assert "transcript" in evidence.summary.casefold()
    assert len(evidence.raw["query_attempts"]) == 2


@pytest.mark.parametrize(
    "terminal_text",
    [
        "We do not have any information for this gene",
        (
            "NF1\nY2285Tfs*5\nInvalid\nSomatic\n"
            "The reference amino acid at position 2285 is N instead of Y "
            "on the OncoKB canonical transcript."
        ),
    ],
)
def test_oncokb_wait_recognizes_terminal_no_result_pages(tmp_path, terminal_text):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=45_000)

    class Body:
        def inner_text(self):
            return terminal_text

    class Page:
        url = "https://www.oncokb.org/gene/NF1/somatic/Y2285Tfs*5"
        waits = []

        def locator(self, selector):
            assert selector == "body"
            return Body()

        def wait_for_timeout(self, milliseconds):
            self.waits.append(milliseconds)

    page = Page()
    service._wait_for_oncokb_result(page)

    assert page.waits == []


def test_oncokb_parser_explains_canonical_transcript_mismatch():
    variant = VariantRecord(
        source_file=Path("synthetic.tsv"),
        source_row=1,
        sample="SYNTHETIC",
        symbol="NF1",
        hgvsc="NM_001042492.2:c.6852_6855del",
        hgvsp="p.Tyr2285ThrfsTer5",
    )
    body = (
        "NF1\nY2285Tfs*5\nInvalid\nSomatic\n"
        "NF1 Y2285Tfs*5: The reference amino acid at position 2285 is N "
        "instead of Y on the OncoKB canonical transcript."
    )

    evidence = parse_oncokb_page(
        body, variant, "https://www.oncokb.org/gene/NF1/somatic/Y2285Tfs*5"
    )

    assert evidence.status == "not_found"
    assert "canonical transcript" in evidence.summary
    assert evidence.raw["failure_kind"] == ProviderFailureKind.IDENTITY_MISMATCH


def test_oncokb_parser_keeps_explicit_provider_error_retryable():
    variant = synthetic_variant()

    evidence = parse_oncokb_page(
        "An error has occurred\nPlease try again later.",
        variant,
        "https://www.oncokb.org/gene/TP53/somatic/R175H",
    )

    assert evidence.status == "error"
    assert "provider error" in evidence.summary.casefold()
    assert evidence.raw["failure_kind"] == ProviderFailureKind.TRANSIENT


def test_franklin_timeout_records_the_exact_failure_stage(tmp_path, monkeypatch):
    variant = VariantRecord(
        source_file=Path("synthetic.tsv"),
        source_row=1,
        sample="PATIENT_A",
        symbol="LUC7L2",
        hgvsc="NM_016019.4:c.784dup",
    )
    service = BrowserReviewService(profile_root=tmp_path)

    class Search:
        def wait_for(self, **kwargs):
            raise TimeoutError("search input stayed hidden")

    class Page:
        url = FRANKLIN_HOME_URL

        def goto(self, url, **kwargs):
            pass

        def locator(self, selector):
            return Search()

    monkeypatch.setattr(
        service, "_browser_api", lambda: (object, Exception, TimeoutError)
    )
    monkeypatch.setattr(
        "solide._vendor.archer.services.browser_review.dismiss_known_overlays",
        lambda page: None,
    )

    evidence = service._search_franklin_query(
        Page(), variant, "LUC7L2:c.784dup", tmp_path, progress=None
    )

    assert evidence.status == "timeout"
    assert evidence.raw["failure_stage"] == "waiting for the Franklin search input"
    assert "search input" in evidence.summary


def test_franklin_subtab_switch_uses_fixed_render_buffer_for_narrow_valid_panel(
    tmp_path,
):
    service = BrowserReviewService(profile_root=tmp_path)

    class TabLocator:
        def count(self):
            return 1

        def evaluate(self, script):
            return True

    class PanelLocator:
        def wait_for(self, **kwargs):
            pass

        def evaluate(self, script):
            raise AssertionError(
                "A valid Franklin panel must not be rejected by a width/text heuristic"
            )

    class Page:
        def __init__(self):
            self.waits = []
            self.panel = PanelLocator()

        def get_by_text(self, label, exact):
            return TabLocator()

        def locator(self, selector):
            assert selector == "gnx-oncogenic-classification-app"
            return self.panel

        def evaluate(self, script):
            pass

        def wait_for_timeout(self, milliseconds):
            self.waits.append(milliseconds)

    page = Page()
    service._activate_franklin_classification_subtab(
        page, "Oncogenic Classification"
    )

    assert page.waits == [1_000]


def test_franklin_overview_uses_only_active_panel_layout(
    tmp_path, monkeypatch
):
    service = BrowserReviewService(
        profile_root=tmp_path, capture_validator=VALID_CAPTURE
    )
    captures = []
    expanded_selectors = []

    class ActivePanelLayout:
        def __init__(self, selector):
            self.selector = selector

        def __enter__(self):
            expanded_selectors.append(self.selector)

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        "solide._vendor.archer.services.browser_review.expanded_capture_layout",
        lambda page, selector: ActivePanelLayout(selector),
    )

    class Element:
        def __init__(self, box):
            self.box = box

        def bounding_box(self):
            return self.box

    class Matches:
        def count(self):
            return 1

        def nth(self, index):
            assert index == 0
            return Element({"x": 70, "y": 90, "width": 180, "height": 42})

    class Page:
        def evaluate(self, script):
            pass

        def wait_for_timeout(self, milliseconds):
            assert milliseconds == 200

        def get_by_text(self, text, *, exact):
            assert text == "TP53"
            assert exact is True
            return Matches()

        def screenshot(self, **kwargs):
            captures.append(kwargs)

    class Panel(Element):
        def evaluate(self, script):
            pass

    page = Page()
    service._capture_franklin_classification_overview(
        page,
        Panel({"x": 100, "y": 150, "width": 900, "height": 600}),
        Element({"x": 100, "y": 360, "width": 900, "height": 100}),
        tmp_path / "overview.png",
        panel_selector="gnx-oncogenic-classification-app",
        gene_symbol="TP53",
    )

    assert expanded_selectors == ["gnx-oncogenic-classification-app"]
    assert captures[0]["clip"] == {
        "x": 38,
        "y": 66,
        "width": 994,
        "height": 294,
    }


def test_oncokb_render_timeout_keeps_diagnostic_capture(tmp_path, monkeypatch):
    variant = synthetic_variant()
    service = BrowserReviewService(profile_root=tmp_path)

    class Body:
        def inner_text(self, **kwargs):
            return "OncoKB page shell without variant evidence"

    class Page:
        url = "https://www.oncokb.org/gene/TP53/R175H"

        def __init__(self):
            self.captures = []

        def goto(self, url, **kwargs):
            self.url = url

        def locator(self, selector):
            assert selector == "body"
            return Body()

        def screenshot(self, **kwargs):
            self.captures.append(kwargs)

    page = Page()
    monkeypatch.setattr(
        service,
        "_wait_for_oncokb_result",
        lambda candidate_page: (_ for _ in ()).throw(TimeoutError("slow render")),
    )

    evidence = service._lookup_oncokb_url(
        page,
        variant,
        "https://www.oncokb.org/gene/TP53/R175H",
        tmp_path / "oncokb",
    )

    assert evidence.status == "error"
    assert evidence.raw["failure_stage"] == "result_rendering"
    assert evidence.raw["failure_kind"] == "transient"
    assert "page shell" in evidence.raw["visible_text_preview"]
    assert evidence.raw["diagnostic_screenshot"].endswith(".png")
    assert len(page.captures) == 1



def test_cosmic_explicitly_selects_global_grch37_menu_option(tmp_path):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=500)

    class Links:
        def __init__(self, page):
            self.page = page

        def evaluate_all(self, script):
            selected = "genome=37" in self.page.url
            return [{
                "href": "https://cancer.sanger.ac.uk/cosmic/login?genome=37",
                "text": "GRCh37 ✔" if selected else "GRCh37",
            }]

    class Page:
        url = "https://cancer.sanger.ac.uk/cosmic/login"

        def __init__(self):
            self.visited = []

        def locator(self, selector):
            assert selector == "a[href*='genome=37']"
            return Links(self)

        def goto(self, url, **kwargs):
            self.url = url
            self.visited.append(url)

        def wait_for_timeout(self, milliseconds):
            pass

    page = Page()
    service._ensure_cosmic_grch37(page)

    assert page.visited == [
        "https://cancer.sanger.ac.uk/cosmic/login?genome=37"
    ]
    service._verify_cosmic_grch37(page)


def test_cosmic_accepts_selected_grch37_after_canonical_redirect(tmp_path):
    service = BrowserReviewService(profile_root=tmp_path)

    class Links:
        def evaluate_all(self, script):
            return [{"href": "?genome=37", "text": "GRCh37 ✔"}]

    class Page:
        url = (
            "https://cancer.sanger.ac.uk/cosmic/mutation/overview"
            "?cosm=COSM476&id=25001834&trans=BRAF"
        )

        def locator(self, selector):
            return Links()

    service._verify_cosmic_grch37(Page())


def test_cosmic_rejects_explicit_grch38_even_when_grch37_menu_is_selected(tmp_path):
    service = BrowserReviewService(profile_root=tmp_path)

    class Links:
        def evaluate_all(self, script):
            return [{"href": "?genome=37", "text": "GRCh37 ✔"}]

    class Page:
        url = "https://cancer.sanger.ac.uk/cosmic/mutation/overview?genome=38"

        def locator(self, selector):
            return Links()

    with pytest.raises(RuntimeError, match="GRCh37"):
        service._verify_cosmic_grch37(Page())


def test_cosmic_rejects_result_when_grch37_is_not_selected(tmp_path):
    service = BrowserReviewService(profile_root=tmp_path)

    class Links:
        def evaluate_all(self, script):
            return [{"href": "?genome=37", "text": "GRCh37"}]

    class Page:
        url = "https://cancer.sanger.ac.uk/cosmic/mutation/overview?genome=38"

        def locator(self, selector):
            return Links()

    with pytest.raises(RuntimeError, match="GRCh37"):
        service._verify_cosmic_grch37(Page())


def test_cosmic_ready_check_stops_immediately_when_mutation_is_not_found(tmp_path):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=45_000)

    class Body:
        def inner_text(self):
            return (
                "Mutation not found\n"
                "The mutation with ID 211028 was not found in our database."
            )

    class Page:
        waits = []

        def locator(self, selector):
            assert selector == "body"
            return Body()

        def wait_for_timeout(self, milliseconds):
            self.waits.append(milliseconds)

    page = Page()
    with pytest.raises(ProviderLookupError) as raised:
        service._wait_for_cosmic_result(page)

    assert getattr(raised.value, "kind", None) == ProviderFailureKind.NOT_FOUND
    assert "211028" in str(raised.value)
    assert page.waits == []

