import pytest

from solide._vendor.archer.core.models import DatabaseEvidence
from solide._vendor.archer.services.evidence_audit import is_completed_evidence


@pytest.mark.parametrize("status", ["layout_changed", "ambiguous", "transient", "submission_unknown", "deferred", "unknown"])
def test_unfinished_provider_status_remains_retryable(status):
    assert not is_completed_evidence(DatabaseEvidence("Franklin", status))


@pytest.mark.parametrize("status", ["found", "not_found", "not_applicable", "manual_review", "invalid_query"])
def test_explicit_terminal_provider_status_is_complete(status):
    assert is_completed_evidence(DatabaseEvidence("Franklin", status))
