"""Synthetic regressions selected from Archer c12a1b8 (15 October provider parity)."""


from dataclasses import replace
from pathlib import Path

import pytest

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import (
    BrowserReviewService,
    _mtbp_screenshot_row_matches,
    parse_mtbp_report,
)
from solide._vendor.archer.services.database_search import DatabaseSearchService


def mtbp_variant(**changes):
    base = VariantRecord(
        source_file=Path("synthetic.tsv"), source_row=1, sample="SYNTHETIC",
        symbol="TESTGENE", hgvsc="NM_999999.1:c.100del", hgvsp="p.Arg100Ser",
        genomic_location="chr17:1000", ref_allele="AC", alt_allele="A",
    )
    return replace(base, **changes)


def mtbp_row(identity, *, alteration=None):
    return {
        "gene": "TESTGENE", "identity_text": identity,
        "alteration": identity if alteration is None else alteration,
        "section": "Reported variants", "functional_evidence": "Evidence B",
        "biomarkers": "", "source_links": [],
    }


def mtbp_lookup(rows, variants, **kwargs):
    return parse_mtbp_report("", rows, variants, "synthetic", cancer_type="Blood", **kwargs)


@pytest.mark.parametrize("identity,basis", [
    ("NM_999999.2:c.100del", "cdna"),
    ("chr17:g.1001del (GRCh37)", "genomic_grch37"),
])
def test_report_without_protein_uses_verified_dna_for_parser_and_capture(identity, basis):
    requested = mtbp_variant()
    evidence = mtbp_lookup([mtbp_row(identity)], [requested])[BrowserReviewService.variant_key(requested)]
    assert evidence.status == "found"
    assert evidence.raw["match_basis"] == basis
    assert _mtbp_screenshot_row_matches("TESTGENE " + identity, requested)


def test_cdna_in_alteration_is_available_to_parser_and_capture():
    requested = mtbp_variant(hgvsp="")
    report = mtbp_row("", alteration="NM_999999.1:c.100del")
    evidence = mtbp_lookup([report], [requested])[BrowserReviewService.variant_key(requested)]
    assert evidence.status == "found"
    assert _mtbp_screenshot_row_matches("TESTGENE " + report["alteration"], requested)


def test_known_protein_fallback_requires_qualified_cdna_without_exact_genomic_identity():
    requested = mtbp_variant()
    evidence = mtbp_lookup([mtbp_row("c.100del")], [requested])[BrowserReviewService.variant_key(requested)]
    assert evidence.status == "not_found"
    assert not _mtbp_screenshot_row_matches("TESTGENE c.100del", requested)


def test_capture_target_uses_identity_from_alteration_field(tmp_path, monkeypatch):
    requested = mtbp_variant(hgvsp="")
    report = {**mtbp_row("", alteration="NM_999999.1:c.100del"), "row_index": 0}
    service = BrowserReviewService(profile_root=tmp_path)
    monkeypatch.setattr(service, "_extract_mtbp_rows", lambda page: [report])

    class Target:
        def is_visible(self):
            return True

        def locator(self, selector):
            return self

        def count(self):
            return 0

        def wait_for(self, **kwargs):
            pass

    target = Target()

    class Rows:
        def nth(self, index):
            assert index == 0
            return target

    class Page:
        def locator(self, selector):
            assert selector == "table tr"
            return Rows()

    assert service._locate_mtbp_screenshot_target(Page(), requested) == (target, target)


@pytest.mark.parametrize("identity,alteration", [
    ("p.Arg100Ser", "p.Arg100Ser chr17:g.2001del (GRCh37)"),
    ("p.Arg100Gly", "NM_999999.1:c.100del chr17:g.1001del (GRCh37)"),
    ("NM_888888.1:c.100del", "NM_888888.1:c.100del"),
])
def test_explicit_conflicts_are_not_overridden_by_other_identity_fields(identity, alteration):
    requested = mtbp_variant()
    evidence = mtbp_lookup([mtbp_row(identity, alteration=alteration)], [requested])[
        BrowserReviewService.variant_key(requested)
    ]
    assert evidence.status == "not_found"
    assert not _mtbp_screenshot_row_matches("TESTGENE " + identity + " " + alteration, requested)


def test_genomic_only_input_requires_exact_identity():
    requested = mtbp_variant(hgvsc="", hgvsp="")
    found = mtbp_lookup([mtbp_row("chr17:g.1001del (GRCh37)")], [requested])[
        BrowserReviewService.variant_key(requested)
    ]
    rejected = mtbp_lookup([mtbp_row("p.Arg999Gly")], [requested])[
        BrowserReviewService.variant_key(requested)
    ]
    assert found.status == "found"
    assert found.raw["match_basis"] == "genomic_grch37"
    assert rejected.status == "not_found"


def test_input_without_any_variant_identity_cannot_import_gene_evidence():
    requested = mtbp_variant(hgvsc="", hgvsp="", genomic_location="", ref_allele="", alt_allele="")
    evidence = mtbp_lookup([mtbp_row("p.Arg999Gly")], [requested])[BrowserReviewService.variant_key(requested)]
    assert evidence.status == "invalid_query"
    assert evidence.clinical_significance == ""


def test_identity_free_row_cannot_verify_two_distinct_submitted_variants_in_same_gene():
    first = mtbp_variant(hgvsp="")
    second = replace(first, source_row=2, hgvsc="NM_999999.1:c.200del", genomic_location="chr17:2000")
    results = mtbp_lookup([mtbp_row("Mutation upstream gene -")], [first, second])
    for requested in (first, second):
        evidence = results[BrowserReviewService.variant_key(requested)]
        assert evidence.status == "manual_review"
        assert evidence.clinical_significance == ""
        assert evidence.raw["submitted_gene_variant_count"] == 2


def test_identity_free_row_retains_legacy_single_input_match():
    requested = mtbp_variant(hgvsp="")
    duplicate = replace(requested, source_row=2)
    evidence = mtbp_lookup([mtbp_row("Mutation upstream gene -")], [requested, duplicate])[
        BrowserReviewService.variant_key(requested)
    ]
    assert evidence.status == "found"
    assert evidence.raw["match_basis"] == "unique_gene_without_reported_identity"
    assert evidence.raw["submitted_gene_variant_count"] == 1


def test_retained_report_without_complete_submission_cannot_use_gene_only_fallback():
    requested = mtbp_variant(hgvsp="")
    evidence = mtbp_lookup([mtbp_row("Mutation upstream gene -")], [requested], complete_submission=False)[
        BrowserReviewService.variant_key(requested)
    ]
    assert evidence.status == "manual_review"
    assert evidence.clinical_significance == ""


def test_reported_row_without_identity_is_unresolved_when_input_has_known_protein():
    requested = mtbp_variant()
    evidence = mtbp_lookup([mtbp_row("Mutation splice region more")], [requested])[
        BrowserReviewService.variant_key(requested)
    ]
    assert evidence.status == "manual_review"
    assert evidence.raw["gene_candidate_count"] == 1


def test_multiple_exact_matching_rows_are_terminal_manual_review():
    requested = mtbp_variant()
    evidence = mtbp_lookup([mtbp_row("p.Arg100Ser"), mtbp_row("p.Arg100Ser")], [requested])[
        BrowserReviewService.variant_key(requested)
    ]
    assert evidence.status == "manual_review"
    assert evidence.raw["candidate_count"] == 2


def test_mtbp_audit_records_matching_algorithm_revision():
    requested = mtbp_variant()
    evidence = mtbp_lookup([mtbp_row("p.Arg100Ser")], [requested])[BrowserReviewService.variant_key(requested)]
    assert evidence.raw["identity_matching_version"] == 3


from pathlib import Path

import pytest

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import BrowserReviewService


def requested_variant():
    return VariantRecord(
        source_file=Path("synthetic.tsv"), source_row=1, sample="SYNTHETIC",
        symbol="TESTGENE", hgvsc="NM_999999.1:c.100G>A", hgvsp="p.Arg100Ser",
        cosmic_id="COSM123", genomic_location="chr17:1000", ref_allele="G", alt_allele="A",
    )


class CapturePage:
    url = "https://cancer.sanger.ac.uk/cosmic/mutation/overview?genome=37&id=999"

    def __init__(self, text):
        self.text = text
        self.captures = []

    def locator(self, selector):
        page = self

        class Locator:
            def inner_text(self, **kwargs):
                return page.text

            def count(self):
                return 1

            def fill(self, value):
                pass

            def all_inner_texts(self):
                return []

            def locator(self, selector):
                return self

            def screenshot(self, *, path):
                page.captures.append(path)

        return Locator()

    def wait_for_timeout(self, milliseconds):
        pass


@pytest.fixture
def service(tmp_path, monkeypatch):
    value = BrowserReviewService(profile_root=tmp_path)
    monkeypatch.setattr(value, "_cosmic_section", lambda page, heading: page.locator(heading))
    monkeypatch.setattr(value, "_write_audit", lambda *args: None)
    return value


@pytest.mark.parametrize("body", [
    "COSM1234\nOTHERGENE c.900A>T p.H300L",
    "PRECOSM123\nOTHERGENE c.900A>T p.H300L",
    "TESTGENE2 c.100G>A p.R100S",
    "TESTGENE-2 c.100G>A p.R100S",
    "TESTGENE c.100G>AA",
    "TESTGENE p.R100Sfs*3",
    "TESTGENE p.R100Ser",
])
def test_cosmic_rejects_identifier_gene_or_change_prefixes(service, tmp_path, body):
    page = CapturePage(body)

    evidence = service._capture_cosmic_result(requested_variant(), page, tmp_path)

    assert evidence.status == "identity_mismatch"
    assert not page.captures


@pytest.mark.parametrize("change", ["c.100G>A", "p.R100S"])
def test_cosmic_canonical_alias_accepts_exact_gene_and_change(service, tmp_path, change):
    page = CapturePage(f"Canonical COSMIC ID: COSM999\nTESTGENE {change}")

    evidence = service._capture_cosmic_result(requested_variant(), page, tmp_path)

    assert evidence.status == "found"
    assert len(page.captures) == 3


def test_cosmic_exact_identifier_still_supports_resolved_record(service, tmp_path):
    page = CapturePage("Mutation ID: COSM123\nOverview\nTissue distribution\nSamples")

    evidence = service._capture_cosmic_result(requested_variant(), page, tmp_path)

    assert evidence.status == "found"
    assert len(page.captures) == 3


@pytest.mark.parametrize("protein", ["p.?", "-", ".", "="])
def test_cosmic_unknown_protein_is_not_identity_proof(service, tmp_path, protein):
    item = requested_variant()
    item.hgvsp = protein
    page = CapturePage("TESTGENE\nProtein: ?\nAnnotation - pending. Classification = unknown")

    evidence = service._capture_cosmic_result(item, page, tmp_path)

    assert evidence.status == "identity_mismatch"
    assert not page.captures


from dataclasses import replace
from pathlib import Path

import pytest

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import BrowserReviewService, parse_mtbp_report
from solide._vendor.archer.services.browser_review import parse_oncokb_page
from solide._vendor.archer.services.browser_review import _mtbp_screenshot_row_matches
from solide._vendor.archer.services import browser_popups
from solide._vendor.archer.services.provider_failures import ProviderLookupError, ProviderFailureKind


def workstation_variant(protein=""):
    return VariantRecord(
        source_file=Path("synthetic.tsv"), source_row=1, sample="SYNTHETIC",
        symbol="TESTGENE", hgvsc="NM_999999.1:c.100del", hgvsp=protein,
        genomic_location="chr17:1000", ref_allele="AC", alt_allele="A",
    )


class SearchPage:
    url = "https://www.ncbi.nlm.nih.gov/clinvar/search/?q=synthetic"

    def __init__(self, text):
        self.text = text
        self.waits = []
        self.visited = []

    def locator(self, selector):
        page = self
        class Locator:
            def inner_text(self, **kwargs):
                return page.text

            def evaluate_all(self, script):
                return []
        return Locator()

    def goto(self, url, **kwargs):
        self.visited.append(url)

    def wait_for_timeout(self, ms):
        self.waits.append(ms)






def workstation_row(identity):
    return {"gene": "TESTGENE", "identity_text": identity, "alteration": identity,
        "section": "Reported variants", "functional_evidence": "", "biomarkers": "", "source_links": []}


@pytest.mark.parametrize("requested,reported", [
    ("p.Arg100SerfsTer5", "p.R100Sfs*5"),
    ("p.His100_Pro101dup", "p.H100_P101dup"),
    ("p.Asn100=", "p.N100="),
])
def test_mtbp_equivalent_long_and_short_protein_notation_matches(requested, reported):
    v = workstation_variant(requested)
    result = parse_mtbp_report("", [workstation_row(reported)], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "found"


def test_mtbp_different_frameshift_stop_is_rejected():
    v = workstation_variant("p.Arg100SerfsTer5")
    result = parse_mtbp_report("", [workstation_row("p.R100Sfs*6")], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "not_found"


def test_mtbp_missing_row_logs_report_and_gene_counts(tmp_path):
    v = workstation_variant()
    result = parse_mtbp_report("", [workstation_row("c.200del")], [v], "synthetic", cancer_type="Blood")
    evidence = result[BrowserReviewService.variant_key(v)]
    assert evidence.raw["report_row_count"] == 1
    messages = []
    BrowserReviewService(profile_root=tmp_path)._report_provider_results(
        "MTBP", [v], {BrowserReviewService.variant_key(v): evidence},
        duration_seconds=1, progress=messages.append,
    )
    message = next(m for m in messages if m.startswith("RESULT |"))
    assert "report_rows=1" in message and "gene_rows=1" in message
    assert "match_basis=cdna" in message


class OnboardingPage:
    def __init__(self, text, labels):
        self.text = text
        self.labels = labels
        self.clicked = []

    def locator(self, selector):
        page = self
        class Locator:
            def count(self): return len(page.labels) if selector == "button" else 1
            def nth(self, index): self.index = index; return self
            def is_visible(self): return True
            def inner_text(self, **kwargs): return page.text
            def all_inner_texts(self): return page.labels
            def locator(self, child): return page.locator(child)
            def click(self): page.clicked.append(page.labels[self.index])
        return Locator()

    def wait_for_timeout(self, ms): pass


def test_franklin_skips_optional_material_dialog_without_choosing_material():
    page = OnboardingPage("Choose sample material and tissue for your first analysis", ["Blood", "Tumor", "Skip"])
    assert browser_popups.dismiss_franklin_onboarding(page) == ["Skip"]
    assert page.clicked == ["Skip"]


def test_franklin_does_not_skip_unrelated_confirmation_dialog():
    page = OnboardingPage("Delete this report?", ["Skip", "Delete"])
    assert browser_popups.dismiss_franklin_onboarding(page) == []
    assert not page.clicked


def test_oncokb_login_prompt_on_variant_route_is_not_render_timeout(tmp_path):
    page = SearchPage("Please log in to view this variant")
    page.url = "https://www.oncokb.org/gene/TESTGENE/somatic/R100S"
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=500)
    with pytest.raises(ProviderLookupError) as error:
        service._wait_for_oncokb_result(page)
    assert error.value.kind == ProviderFailureKind.LOGIN_REQUIRED
    assert not page.waits


def test_oncokb_explicit_missing_variant_is_a_completed_result(tmp_path):
    page = SearchPage("GRCh37\n17:g.1001del\nWe do not have any information for this variant")
    page.url = "https://www.oncokb.org/hgvsg/17:g.1001del?refGenome=GRCh37"
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=500)
    service._wait_for_oncokb_result(page)
    result = parse_oncokb_page(page.text, workstation_variant(), page.url)
    assert result.status == "not_found"
    assert result.raw["failure_kind"] == "not_found"
    assert not page.waits


def test_mtbp_exact_genomic_identity_recovers_missing_cdna():
    v = workstation_variant()
    result = parse_mtbp_report("", [workstation_row("chr17:g.1001del (GRCh37)")], [v], "synthetic", cancer_type="Blood")
    evidence = result[BrowserReviewService.variant_key(v)]
    assert evidence.status == "found"
    assert evidence.raw["match_basis"] == "genomic_grch37"


@pytest.mark.parametrize("reported", [
    "chr17:g.1002del (GRCh37)", "chr17:g.1001del (GRCh38)",
    "chr17:g.1001del", "chr17:g.1001delinsT (GRCh37)",
])
def test_mtbp_genomic_recovery_rejects_unverified_or_different_identity(reported):
    v = workstation_variant()
    result = parse_mtbp_report("", [workstation_row(reported)], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "not_found"


def test_franklin_retries_assessment_panel_timeout_once_without_new_search(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    page = SearchPage("")
    page.url = "https://franklin.genoox.com/clinical-db/variant/snpTumor/synthetic"
    calls = []
    def capture(*args):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("Edge element did not reach state 'visible'.")
        return [{"label": "Predictions", "path": "synthetic.png"}]
    monkeypatch.setattr(service, "_capture_franklin_assessment", capture)
    result = service._capture_franklin_assessment_with_retry(page, workstation_variant(), tmp_path)
    assert len(calls) == 2 and result[0]["label"] == "Predictions"
    assert not page.visited


def test_franklin_does_not_retry_ambiguous_assessment_panels(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    calls = []
    def capture(*args):
        calls.append(1)
        raise ValueError("Franklin prediction/population evidence panels were ambiguous.")
    monkeypatch.setattr(service, "_capture_franklin_assessment", capture)
    with pytest.raises(ValueError):
        service._capture_franklin_assessment_with_retry(SearchPage(""), workstation_variant(), tmp_path)
    assert calls == [1]




def test_cosmic_final_link_timeout_saves_diagnostic_page_not_success_evidence(tmp_path, monkeypatch):
    from PIL import Image
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=500)
    class DiagnosticPage(SearchPage):
        def screenshot(self, *, path, full_page):
            Image.new("RGB", (80, 60), "white").save(path)
    page = DiagnosticPage("Synthetic canonical link did not load")
    def resolve(*args):
        raise ProviderLookupError(ProviderFailureKind.TRANSIENT, "No canonical link")
    monkeypatch.setattr(service, "_resolve_cosmic_mutation_page", resolve)
    result = service._lookup_cosmic_with_retry(page, workstation_variant(), "https://cancer.sanger.ac.uk/cosmic/search?q=COSM999999", tmp_path, progress=None)
    assert result.status == "transient"
    assert Path(result.raw["diagnostic_screenshot"]).exists()
    assert result.raw["visible_text_preview"] == page.text
    assert "screenshots" not in result.raw


def test_mtbp_declared_nonempty_report_with_no_extracted_rows_is_layout_error():
    v = workstation_variant()
    result = parse_mtbp_report("Putative functionally relevant variants: 2", [], [v], "synthetic", cancer_type="Blood")
    evidence = result[BrowserReviewService.variant_key(v)]
    assert evidence.status == "layout_changed"
    assert evidence.raw["failure_stage"] == "report_row_extraction"


def test_mtbp_capture_rejects_a_gene_with_matching_name_prefix():
    assert not _mtbp_screenshot_row_matches("TESTGENE2 c.100del", workstation_variant())


def test_hidden_cdna_from_different_refseq_transcript_does_not_verify_variant():
    v = workstation_variant()
    report_identity = "NM_888888.1:c.100del"
    result = parse_mtbp_report("", [workstation_row(report_identity)], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "not_found"
    assert not _mtbp_screenshot_row_matches("TESTGENE " + report_identity, v)


def test_hidden_cdna_exact_refseq_transcript_with_new_version_is_accepted():
    v = workstation_variant()
    result = parse_mtbp_report("", [workstation_row("NM_999999.2:c.100del")], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "found"


def test_known_protein_conflict_is_not_overridden_by_hidden_matching_cdna():
    v = workstation_variant("p.Arg100Ser")
    result = parse_mtbp_report("", [workstation_row("p.Arg100Gly NM_999999.1:c.100del")], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "not_found"


@pytest.mark.parametrize("protein", ["", "p.Arg100Ser"])
def test_reported_genomic_conflict_overrides_matching_cdna_or_protein(protein):
    v = workstation_variant(protein)
    report_identity = "NM_999999.1:c.100del p.Arg100Ser chr17:g.2001del (GRCh37)"
    result = parse_mtbp_report("", [workstation_row(report_identity)], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "not_found"
    assert not _mtbp_screenshot_row_matches("TESTGENE " + report_identity, v)


def test_shared_gene_cell_capture_is_marked_as_gene_context(tmp_path):
    import json
    from PIL import Image
    from solide._vendor.archer.services.capture_validation import CaptureValidation
    report = tmp_path / "synthetic-report.png"
    Image.new("RGB", (200, 100), "white").save(report)
    report.with_suffix(".geometry.json").write_text(json.dumps({
        "width": 200, "height": 100, "rows": [{
            "gene": "TESTGENE", "identity": "NM_999999.1:c.100del",
            "row": {"x": 0, "y": 20, "width": 200, "height": 60},
            "shared_gene_context": True,
        }],
    }))
    service = BrowserReviewService(profile_root=tmp_path, capture_validator=lambda p: CaptureValidation(True, "ok", 200, 60, 1))
    output = service._crop_mtbp_variant_from_report(None, workstation_variant(), tmp_path, report)
    with Image.open(output) as image:
        assert image.info["match_scope"] == "gene_context"


def test_separate_transcript_field_is_used_for_hidden_cdna_verification():
    v = replace(workstation_variant(), hgvsc="c.100del", transcript="NM_999999.1")
    report_identity = "NM_888888.1:c.100del"
    result = parse_mtbp_report("", [workstation_row(report_identity)], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "not_found"
    assert not _mtbp_screenshot_row_matches("TESTGENE " + report_identity, v)


@pytest.mark.parametrize("accession,other", [
    ("XM_999999.1", "XM_888888.1"), ("XR_999999.1", "XR_888888.1"),
    ("ENST999999.1", "ENST888888.1"),
])
def test_other_supported_transcript_families_require_matching_accession(accession, other):
    v = replace(workstation_variant(), hgvsc=f"{accession}:c.100del")
    result = parse_mtbp_report("", [workstation_row(f"{other}:c.100del")], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "not_found"


def test_unknown_input_transcript_does_not_accept_qualified_hidden_cdna():
    v = replace(workstation_variant(), hgvsc="c.100del", transcript="")
    result = parse_mtbp_report("", [workstation_row("NM_888888.1:c.100del")], [v], "synthetic", cancer_type="Blood")
    assert result[BrowserReviewService.variant_key(v)].status == "not_found"


def test_clinvar_indel_queries_start_with_exact_grch37_alleles():
    queries = DatabaseSearchService()._clinvar_queries(mtbp_variant())
    assert queries[0] == "17:1000:AC:A(GRCh37)"
    assert "NM_999999.1:c.100del[VARNAME]" in queries


def test_clinvar_cache_does_not_reuse_another_allele_at_the_same_position(monkeypatch):
    from types import SimpleNamespace
    from solide._vendor.archer.core.models import DatabaseEvidence

    requested = mtbp_variant(hgvsc="", hgvsp="", ref_allele="G", alt_allele="A")
    service = DatabaseSearchService()

    def request(url, params):
        content = (b'<Result><IdList><Id>1</Id></IdList></Result>' if "esearch" in url else
                   b'<Result><SequenceLocation Assembly="GRCh37" Chr="17" positionVCF="1000" '
                   b'referenceAlleleVCF="G" alternateAlleleVCF="A"/></Result>')
        return SimpleNamespace(content=content, raise_for_status=lambda: None)

    monkeypatch.setattr(service, "_eutils_get", request)
    monkeypatch.setattr(service, "_parse_clinvar", lambda *args: DatabaseEvidence("ClinVar", "found"))
    assert service._search_clinvar(requested).status == "found"
    assert service._search_clinvar(replace(requested, alt_allele="T")).status == "not_found"


def test_clinvar_current_zero_results_completes_without_waiting(tmp_path):
    page = SearchPage("Search results: 0 variants for synthetic\nNo data available in table")
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=500)
    assert service._wait_for_clinvar_result(page)[1] == []
    assert not page.waits


def test_clinvar_empty_loading_table_is_not_proof_of_absence(tmp_path):
    page = SearchPage("Loading... No data available in table")
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=500)
    with pytest.raises(TimeoutError):
        service._wait_for_clinvar_result(page)


@pytest.mark.parametrize("revision,expected", [(None, "verification_required"), (1, "verification_required"), (2, "verification_required"), (3, "not_found")])
def test_previous_mtbp_gene_nohit_is_rechecked_with_current_matching(tmp_path, revision, expected):
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.evidence_audit import migrate_loaded_evidence

    raw = {"gene_candidate_count": 1}
    if revision is not None:
        raw["identity_matching_version"] = revision
    result = migrate_loaded_evidence(DatabaseEvidence("MTBP", "not_found", raw=raw), tmp_path)
    assert result.status == expected


@pytest.mark.parametrize("status,raw,recheck", [
    ("not_found", {"gene_candidate_count": 1}, True),
    ("not_found", {"gene_candidate_count": 1, "identity_matching_version": 2}, True),
    ("not_found", {"gene_candidate_count": 1, "identity_matching_version": 3}, False),
    ("found", {"match_basis": "unique_gene_without_reported_identity"}, True),
    ("found", {"match_basis": "unique_gene_without_reported_identity", "identity_matching_version": 3,
               "submitted_gene_variant_count": 1}, False),
    ("found", {"match_basis": "protein"}, False),
])
def test_legacy_matching_issue_does_not_mutate_saved_evidence(status, raw, recheck):
    from copy import deepcopy
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.evidence_audit import mtbp_legacy_matching_issue

    evidence = DatabaseEvidence("MTBP", status, "Original summary", raw=raw)
    before = deepcopy(evidence)
    assert bool(mtbp_legacy_matching_issue(evidence)) == recheck
    assert evidence == before


def test_recovered_mtbp_canonical_audit_is_current_before_remote_deletion(tmp_path, monkeypatch):
    import json
    from solide._vendor.archer.core.models import DatabaseEvidence
    from solide._vendor.archer.services.evidence_audit import audit_digest, write_evidence_audit

    requested = mtbp_variant()
    service = BrowserReviewService(profile_root=tmp_path)
    path = write_evidence_audit(tmp_path, "MTBP", requested, DatabaseEvidence("MTBP", "not_found"))
    recovered = DatabaseEvidence("MTBP", "found", raw={"identity_matching_version": 2})

    def remove_report(*args):
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["status"] == "found"
        assert saved["raw"]["identity_matching_version"] == 2
        assert saved["schema_version"] == 2
        return {"status": "deleted"}

    monkeypatch.setattr(service, "_delete_mtbp_report", remove_report)
    service._finalize_mtbp_report(None, "SOLIDE-synthetic", [(path, requested, recovered)])
    assert path.name == audit_digest("MTBP", requested) + ".audit.json"
    assert json.loads(path.read_text(encoding="utf-8"))["raw"]["remote_report_cleanup"]["status"] == "deleted"


def test_cosmic_cache_requires_the_same_requested_variant(tmp_path, monkeypatch):
    from solide._vendor.archer.core.models import DatabaseEvidence

    first = requested_variant()
    second = replace(first, alt_allele="T", hgvsc="NM_999999.1:c.100G>T", hgvsp="p.Arg100Leu")
    service = BrowserReviewService(profile_root=tmp_path)
    calls = []

    def lookup(page, requested, *args, **kwargs):
        calls.append(requested.alt_allele)
        return DatabaseEvidence("COSMIC", "found" if requested.alt_allele == "A" else "not_found")

    monkeypatch.setattr(service, "_lookup_cosmic_with_retry", lookup)
    assert service._lookup_cosmic_variant(None, first, tmp_path, progress=None).status == "found"
    assert service._lookup_cosmic_variant(None, second, tmp_path, progress=None).status == "not_found"
    assert calls == ["A", "T"]


def test_cosmic_without_identifier_does_not_open_a_browser(tmp_path, monkeypatch):
    service = BrowserReviewService(profile_root=tmp_path)
    monkeypatch.setattr(service, "_browser_api", lambda: pytest.fail("No identifier is available for this provider"))
    requested = mtbp_variant()
    results = service._search_cosmic([requested], tmp_path, progress=None)
    assert results[service.variant_key(requested)].status == "not_applicable"


def test_interleaved_retained_reports_restore_the_correct_page_before_capture(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from solide._vendor.archer.core.models import DatabaseEvidence

    service = BrowserReviewService(profile_root=tmp_path)
    first = mtbp_variant(hgvsp="")
    second = replace(first, hgvsc="NM_999999.1:c.200del", genomic_location="chr17:2000")
    third = replace(first, hgvsc="NM_999999.1:c.300del", genomic_location="chr17:3000")
    report_url = lambda name: f"https://mtbp.org/patients/{name}/report/123/"
    page = SimpleNamespace(url="https://mtbp.org/analyse/", wait_for_url=lambda *a, **k: None)
    page.locator = lambda selector: SimpleNamespace(count=lambda: 0, inner_text=lambda **k: "Complete report")
    page.get_by_role = lambda role, name, **k: SimpleNamespace(count=lambda: 1, href=report_url(name))
    context = SimpleNamespace(pages=[page], close=lambda: None)

    @contextmanager
    def runtime():
        yield SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=lambda *a, **k: context))

    monkeypatch.setattr(service, "_browser_api", lambda: (runtime, Exception, TimeoutError))
    monkeypatch.setattr(service, "_session_authenticated", lambda *a: True)
    monkeypatch.setattr(service, "_goto_with_retries", lambda p, url, **k: setattr(p, "url", url))
    monkeypatch.setattr(service, "_open_mtbp_report_link", lambda p, link: setattr(p, "url", link.href))
    monkeypatch.setattr(service, "_wait_for_mtbp_content", lambda p: None)
    reports = {report_url("SOLIDE-A"): [mtbp_row(first.hgvsc), mtbp_row(third.hgvsc)],
               report_url("SOLIDE-B"): [mtbp_row(second.hgvsc)]}
    monkeypatch.setattr(service, "_extract_mtbp_rows", lambda p: reports[p.url])
    monkeypatch.setattr(service, "_capture_mtbp_full_report", lambda p, directory, name: directory / f"{name}.png")
    captures = []
    monkeypatch.setattr(service, "_capture_mtbp_variant_with_fallback", lambda p, v, *a: captures.append((v.hgvsc, p.url)))
    monkeypatch.setattr(service, "_finalize_mtbp_report", lambda *a: {})
    pending = [(v, DatabaseEvidence("MTBP", "partial_capture", raw={"analysis_id": name}))
               for v, name in [(first, "SOLIDE-A"), (second, "SOLIDE-B"), (third, "SOLIDE-A")]]

    results = service._recover_mtbp_timeouts(pending, tmp_path, progress=None)

    assert len(results) == 3
    assert captures == [(first.hgvsc, report_url("SOLIDE-A")), (second.hgvsc, report_url("SOLIDE-B")),
                        (third.hgvsc, report_url("SOLIDE-A"))]


from solide._vendor.archer.services.edge_cdp import EdgeCdpContext, EdgeCdpError, EdgeCdpTimeout


@pytest.mark.parametrize(
    "exit_code, endpoint_ready_at, expected_error",
    [
        pytest.param(0, 5.0, None, id="clean-handoff-ready-after-three-seconds"),
        pytest.param(0, 19.0, None, id="clean-handoff-ready-before-deadline"),
        pytest.param(0, None, EdgeCdpTimeout, id="clean-handoff-never-ready"),
        pytest.param(7, None, EdgeCdpError, id="nonzero-exit-fails-early"),
    ],
)
def test_launch_waits_for_clean_broker_handoff_but_bounds_failure(
    tmp_path, monkeypatch, exit_code, endpoint_ready_at, expected_error,
):
    from types import SimpleNamespace
    from solide._vendor.archer.services import edge_cdp

    clock = {"now": 0.0}
    cleanup = []
    process = SimpleNamespace(returncode=exit_code, poll=lambda: exit_code)
    monkeypatch.setattr(edge_cdp.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(
        edge_cdp.time, "sleep",
        lambda delay: clock.__setitem__("now", clock["now"] + delay),
    )
    monkeypatch.setattr(edge_cdp.subprocess, "Popen", lambda *a, **k: process)
    monkeypatch.setattr(
        edge_cdp, "_close_failed_browser",
        lambda owned_process, version: cleanup.append((owned_process, version)),
    )

    def read_port(port_file):
        if endpoint_ready_at is None or clock["now"] < endpoint_ready_at:
            raise FileNotFoundError("Broker has not announced DevTools yet")
        return 25687

    def http_json(url, **kwargs):
        if url.endswith("/json/version"):
            return {"webSocketDebuggerUrl": "ws://127.0.0.1:25687/devtools/browser/owned"}
        assert url.endswith("/json/list")
        return [{"id": "page-1", "type": "page", "webSocketDebuggerUrl":
                 "ws://127.0.0.1:25687/devtools/page/page-1"}]

    class Connection:
        def __init__(self, url):
            pass

        def call(self, *args, **kwargs):
            return {}

    monkeypatch.setattr(edge_cdp, "_read_devtools_active_port", read_port)
    monkeypatch.setattr(edge_cdp, "_http_json", http_json)
    monkeypatch.setattr(edge_cdp, "_CdpConnection", Connection)

    def launch():
        return EdgeCdpContext._launch_owned(
            tmp_path, Path("msedge.exe"), viewport={"width": 1024, "height": 640},
            accept_downloads=False, background=False,
        )

    if expected_error is None:
        context = launch()
        assert context.endpoint == "http://127.0.0.1:25687"
        assert endpoint_ready_at <= clock["now"] < 20
        assert cleanup == []
    else:
        with pytest.raises(expected_error) as caught:
            launch()
        assert type(caught.value) is expected_error
        assert cleanup == [(process, {})]
        if exit_code == 0:
            assert 20 <= clock["now"] < 20.3
        else:
            assert 3 <= clock["now"] < 3.3
            assert "code 7" in str(caught.value)

