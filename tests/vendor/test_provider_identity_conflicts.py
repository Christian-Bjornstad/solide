from dataclasses import replace
from pathlib import Path

import pytest

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import parse_franklin_page, parse_oncokb_page


def variant():
    return VariantRecord(Path("synthetic.tsv"), 1, "SYNTHETIC", "TP53",
                         "NM_000546.6:c.524G>A", "p.Arg175His",
                         genomic_location="chr17:7578406", ref_allele="G", alt_allele="A")


@pytest.mark.parametrize("heading", ["BRAF V600E Somatic", "TP53 R248Q Somatic", "Unidentified Somatic"])
def test_oncokb_request_genomic_url_cannot_override_returned_identity(heading):
    body = f"{heading}\nVariant Overview\nMutation Effect\nOncogenicity\nOncogenic\nBiological Effect\nGain-of-function\nHighest Level of Evidence"

    result = parse_oncokb_page(body, variant(), "https://www.oncokb.org/hgvsg/17:g.7578406G%3EA?refGenome=GRCh37")

    assert result.status == "identity_mismatch"
    assert result.clinical_significance == ""


def test_oncokb_other_variant_heading_overrides_requested_variant_reference_in_prose():
    body = "BRAF V600E Somatic\nVariant Overview\nA comparison with TP53 R175H.\nMutation Effect\nOncogenicity\nOncogenic\nHighest Level of Evidence"

    result = parse_oncokb_page(body, variant(), "https://www.oncokb.org/hgvsg/17:g.7578406G%3EA?refGenome=GRCh37")

    assert result.status == "identity_mismatch"


def test_oncokb_visible_gene_protein_match_does_not_certify_requested_genomic_url():
    body = "TP53 R175H Somatic\nVariant Overview\nMutation Effect\nOncogenicity\nOncogenic\nHighest Level of Evidence"

    result = parse_oncokb_page(body, variant(), "https://www.oncokb.org/hgvsg/17:g.7578406G%3EA?refGenome=GRCh37")

    assert result.status == "found"
    assert "assembly_verified" not in result.raw
    assert "identity_verification" not in result.raw


def test_franklin_old_transcript_version_without_genomic_proof_is_rejected():
    requested = replace(variant(), genomic_location="", ref_allele="", alt_allele="")
    body = "TP53\nNM_000546.3:c.524G>A\nSuggested classification\nPathogenic"

    result = parse_franklin_page(body, requested, "https://franklin.genoox.com/clinical-db/variant/example")

    assert result.status == "identity_mismatch"
    assert result.clinical_significance == ""
    assert result.raw["identity_verification"]["accepted"] is False


def test_franklin_exact_versioned_transcript_matches_without_genomic_fields():
    requested = replace(variant(), genomic_location="", ref_allele="", alt_allele="")
    body = "TP53\nNM_000546.6:c.524G>A\nSuggested classification\nPathogenic"

    result = parse_franklin_page(body, requested, "https://franklin.genoox.com/clinical-db/variant/example")

    assert result.status == "found"
    assert result.raw["identity_verification"]["basis"] == "exact_transcript"


def test_franklin_gene_cdna_only_match_is_not_called_exact_transcript():
    requested = replace(variant(), genomic_location="", ref_allele="", alt_allele="")
    body = "TP53:c.524G>A\nSuggested classification\nPathogenic"

    result = parse_franklin_page(body, requested, "https://franklin.genoox.com/clinical-db/variant/example")

    assert result.raw["identity_verification"]["basis"] != "exact_transcript"


def test_franklin_matching_genomic_alleles_can_verify_across_transcript_versions():
    body = "TP53\nNM_000546.3:c.524G>A\nchr17-7578406 G>A\nSuggested classification\nPathogenic"

    result = parse_franklin_page(body, variant(), "https://franklin.genoox.com/clinical-db/variant/example")

    identity = result.raw["identity_verification"]
    assert result.status == "found"
    assert identity["basis"] == "grch37_genomic"
    assert identity["requested"] == identity["returned"]


def test_franklin_unversioned_accession_is_not_called_exact_transcript():
    requested = replace(variant(), hgvsc="NM_000546:c.524G>A", genomic_location="", ref_allele="", alt_allele="")
    body = "TP53\nNM_000546:c.524G>A\nSuggested classification\nPathogenic"

    result = parse_franklin_page(body, requested, "https://franklin.genoox.com/clinical-db/variant/example")

    assert result.status == "found"
    assert result.raw["identity_verification"]["basis"] != "exact_transcript"
