import pytest
from pathlib import Path

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import BrowserReviewService
from solide._vendor.archer.services.provider_failures import ProviderFailureKind, ProviderLookupError


class SearchPage:
    url = 'https://cancer.sanger.ac.uk/cosmic/search?q=COSM937333'

    def __init__(self, text):
        self.text = text

    def locator(self, selector):
        return self

    def evaluate_all(self, script):
        return []

    def inner_text(self):
        return self.text

    def wait_for_timeout(self, milliseconds):
        pass


TEXT = ('COSMIC search results\nYour search term "COSM937333" returned results in 1 section of the database.\n'
        'Genes (0 hits)\nLegacy Mutations (0)\nMutations (15)\n'
        'Gene\tSyntax\nOTHERGENE\tc.100A>G\nShowing 1 to 10 of 15 entries')


@pytest.mark.parametrize('text,kind', [
    (TEXT, ProviderFailureKind.NOT_FOUND),
    (TEXT.replace('Legacy Mutations (0)', 'Legacy Mutations (1)'), ProviderFailureKind.TRANSIENT),
    (TEXT.replace('Showing 1 to 10 of 15 entries', 'Loading...'), ProviderFailureKind.TRANSIENT),
    (TEXT.replace('"COSM937333"', '"COSM9373330"'), ProviderFailureKind.TRANSIENT),
])
def test_completed_fuzzy_results_do_not_become_exact_legacy_matches(tmp_path, text, kind):
    service = BrowserReviewService(profile_root=tmp_path, navigation_timeout_ms=500)
    variant = VariantRecord(Path('synthetic.tsv'), 1, 'SYNTHETIC', 'TESTGENE',
                            'NM_999999.1:c.100A>G', cosmic_id='COSM937333')
    with pytest.raises(ProviderLookupError) as error:
        service._resolve_cosmic_mutation_page(SearchPage(text), variant)
    assert error.value.kind == kind
