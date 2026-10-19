"""Synthetic Franklin assessment captures, independent of live credentials."""
from pathlib import Path

import pytest

from solide._vendor.archer.core.models import VariantRecord
from solide._vendor.archer.services.browser_review import BrowserReviewService
from solide._vendor.archer.services.capture_validation import CaptureValidation


def variant():
    return VariantRecord(source_file=Path('synthetic.tsv'),source_row=1,sample='SYNTHETIC',
        symbol='TP53',hgvsc='NM_000546.6:c.524G>A',genomic_location='chr17:7578406',
        ref_allele='G',alt_allele='A')


class AssessmentLocator:
    def __init__(self,page,label='',section=False):
        self.page=page
        self.label=label
        self.section=section

    def filter(self,*,has):
        return AssessmentLocator(self.page,has.label,section=True)

    def locator(self,selector):
        assert selector=='.frequency-details-toggle'
        return AssessmentLocator(self.page,'clinical-toggle')

    def count(self):
        if self.label=='clinical-toggle':
            return int(self.page.has_more)
        return self.page.counts.get(self.label,1)

    def wait_for(self,**kwargs):
        if self.count()!=1:
            raise TimeoutError(f'{self.label} was unavailable')

    def inner_text(self):
        if self.label=='clinical-toggle':
            return 'Minimize' if self.page.expanded else 'See all evidences'
        return self.page.body

    def click(self):
        assert self.label=='clinical-toggle'
        self.page.expanded=True

    def bounding_box(self):
        return dict(x=200,y=120,width=1000,height=300 if self.section else 40)

    def evaluate(self,script):
        if 'descendants' in script:
            return dict(width=1000,height=1800 if self.label=='Clinical evidence' else 400)
        return None


class AssessmentPage:
    url='https://franklin.genoox.com/clinical-db/variant/snpTumor/chr17-7578406-G-A'

    def __init__(self,*,counts=None,body='TP53 NM_000546.6:c.524G>A chr17-7578406 G>A',has_more=False):
        self.counts=counts or {}
        self.body=body
        self.captures=[]
        self.visited=[]
        self.has_more=has_more
        self.expanded=False

    def goto(self,url,**kwargs):
        self.url=url
        self.visited.append(url)

    def get_by_role(self,role,*,name,exact):
        assert role=='heading' and exact
        return AssessmentLocator(self,name)

    def locator(self,selector):
        assert selector in ('body','div.section')
        return AssessmentLocator(self)

    def evaluate(self,script):
        return None

    def screenshot(self,**kwargs):
        self.captures.append(kwargs)


def service(tmp_path,monkeypatch):
    review=BrowserReviewService(profile_root=tmp_path,
        capture_validator=lambda path:CaptureValidation(True,'ok',1000,600,12.0))
    monkeypatch.setattr(review,'_wait_for_franklin_section_stability',lambda *args:None)
    return review


def test_assessment_includes_complete_clinical_evidence_beside_population(tmp_path,monkeypatch):
    review=service(tmp_path,monkeypatch)
    page=AssessmentPage()
    captures=review._capture_franklin_assessment(page,variant(),tmp_path)
    assert [item['label'] for item in captures]==[
        'Predictions','Population frequencies','Clinical evidence']
    assert captures[-1]['path'].endswith('-clinical-evidence.png')
    assert all(item['url']==page.visited[0] for item in captures)
    assert len(page.visited)==1
    assert page.captures[-1]['clip']['height']>=1800


def test_no_clinical_evidence_is_captured_as_the_visible_source_message(tmp_path,monkeypatch):
    review=service(tmp_path,monkeypatch)
    page=AssessmentPage(body='TP53 NM_000546.6:c.524G>A chr17-7578406 G>A\nNo clinical evidence')
    captures=review._capture_franklin_assessment(page,variant(),tmp_path)
    assert any(item['label']=='Clinical evidence' for item in captures)


def test_clinical_evidence_expands_all_records_before_capture(tmp_path,monkeypatch):
    review=service(tmp_path,monkeypatch)
    page=AssessmentPage(has_more=True)
    review._capture_franklin_assessment(page,variant(),tmp_path)
    assert page.expanded


@pytest.mark.parametrize('count',[0,2])
def test_missing_or_ambiguous_clinical_panel_is_not_a_completed_capture(tmp_path,monkeypatch,count):
    review=service(tmp_path,monkeypatch)
    page=AssessmentPage(counts={'Clinical evidence':count})
    with pytest.raises((TimeoutError,ValueError),match='Clinical|clinical|ambiguous'):
        review._capture_franklin_assessment(page,variant(),tmp_path)
    assert not page.captures


def test_assessment_navigation_cannot_capture_another_variant(tmp_path,monkeypatch):
    review=service(tmp_path,monkeypatch)
    page=AssessmentPage(body='BRAF NM_004333.6:c.1799T>A chr7-140453136 A>T')
    with pytest.raises(ValueError,match='identity'):
        review._capture_franklin_assessment(page,variant(),tmp_path)
    assert not page.captures


def test_stability_rejects_a_panel_that_only_displays_a_loading_indicator(tmp_path):
    review=BrowserReviewService(profile_root=tmp_path,navigation_timeout_ms=1500)

    class Section:
        def evaluate(self,script):
            return dict(height=200,textLength=24,top=300,loading=True)

    class Page:
        def wait_for_timeout(self,ms):
            pass

    with pytest.raises(TimeoutError,match='assessment panel'):
        review._wait_for_franklin_section_stability(Page(),Section())


def test_stability_waits_until_content_above_the_panel_stops_moving(tmp_path):
    review=BrowserReviewService(profile_root=tmp_path,navigation_timeout_ms=5000)

    class Section:
        calls=0

        def evaluate(self,script):
            self.calls+=1
            return dict(height=200,textLength=24,top=300 if self.calls<3 else 500,loading=False)

    class Page:
        def wait_for_timeout(self,ms):
            pass

    section=Section()
    review._wait_for_franklin_section_stability(Page(),section)
    assert section.calls>=5
