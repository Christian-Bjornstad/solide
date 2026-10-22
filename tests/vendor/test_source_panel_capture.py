import pytest

from solide._vendor.archer.services.source_panel_capture import capture_source_panel, SourcePanelCaptureTimeout


def test_capture_retries_when_late_layout_changes_between_measurement_and_screenshot(tmp_path):
    class Page:
        calls=[];reads=0
        def evaluate(self,script):
            self.reads+=1
            y=100 if self.reads<=3 else 300
            return {'ready':True,'clip':{'x':10,'y':y,'width':900,'height':500}}
        def screenshot(self,**kwargs):self.calls.append(kwargs)
        def wait_for_timeout(self,ms):pass
    page=Page();path=tmp_path/'capture.png'
    result=capture_source_panel(page,path,'test',timeout_ms=1000)
    assert [call['clip']['y'] for call in page.calls]==[100,300]
    assert result['clip']['y']==300


def test_capture_waits_for_all_expected_classification_sections(tmp_path):
    class Page:
        reads=0;captured_at=0
        def evaluate(self,script):
            self.reads+=1
            return {'ready':True,'clip':{'x':0,'y':0,'width':900,'height':500},
                'text':'Germline' if self.reads<4 else 'Germline Clinical impact Oncogenicity'}
        def screenshot(self,**kwargs):self.captured_at=self.reads
        def wait_for_timeout(self,ms):pass
    page=Page()
    capture_source_panel(page,tmp_path/'capture.png','test',timeout_ms=1000,
        required_text=['Germline','Clinical impact','Oncogenicity'])
    assert page.captured_at>=6


def test_capture_timeout_keeps_layout_diagnostics_without_source_text(tmp_path):
    class Page:
        def evaluate(self, script):
            return {'ready': True, 'clip': None, 'document_state': 'interactive',
                    'font_state': 'loading', 'text': 'private source details'}
        def wait_for_timeout(self, ms):
            pass
    with pytest.raises(SourcePanelCaptureTimeout) as failure:
        capture_source_panel(Page(), tmp_path/'capture.png', 'test', timeout_ms=5,
                             required_text=['Oncogenic'])
    assert failure.value.diagnostics['last_state']['clip'] is None
    assert failure.value.diagnostics['required_text_present'] == [False]
    assert 'private source details' not in str(failure.value.diagnostics)
