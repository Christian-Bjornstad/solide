from pathlib import Path

import pytest

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import (
    BrowserReviewService, _mtbp_normalized_protein, parse_mtbp_report,
)


@pytest.mark.parametrize("long,short", [
    ("p.Glu746_Ala750del", "p.E746_A750del"),
    ("p.Arg248Trp", "p.R248W"),
    ("p.Glu746_Ala750delinsGly", "p.E746_A750delinsG"),
    ("p.Arg175GlyfsTer8", "p.R175Gfs*8"),
])
def test_equivalent_residue_notation_preserves_operation(long, short):
    assert _mtbp_normalized_protein(long) == _mtbp_normalized_protein(short)


def test_deletion_match_is_exact_and_does_not_accept_delins():
    v=VariantRecord(Path("synthetic.tsv"),1,"SOURCE","EGFR","",hgvsp="p.E746_A750del")
    rows=[{"gene":"EGFR","identity_text":"p.Glu746_Ala750del","alteration":"p.Glu746_Ala750del"},
          {"gene":"EGFR","identity_text":"p.Glu746_Ala750delinsGly","alteration":"p.Glu746_Ala750delinsGly"}]
    result=parse_mtbp_report("",rows,[v],"https://mtbp.org/patients/source/report/1/",cancer_type="Other")[BrowserReviewService.variant_key(v)]
    assert result.status=="found"
    assert result.raw["match_basis"]=="protein"
    assert result.raw["alteration"]=="p.Glu746_Ala750del"
    result=parse_mtbp_report("",rows[1:],[v],"https://mtbp.org/patients/source/report/1/",cancer_type="Other")[BrowserReviewService.variant_key(v)]
    assert result.status=="not_found"
