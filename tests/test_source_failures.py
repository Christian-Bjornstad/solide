import requests
import pytest
from solide.evidence import run_queue,QueueControl
from solide.models import Variant,Session

@pytest.mark.parametrize('error,status,words',[
    (requests.Timeout('SYNTHETIC stalled API'),'timeout','tids'),
    (requests.exceptions.ProxyError('SYNTHETIC proxy'),'network_error','proxy'),
    (requests.exceptions.SSLError('SYNTHETIC certificate'),'network_error','sertifikat'),
    (requests.ConnectionError('SYNTHETIC disconnected'),'network_error','nettverk'),
    (requests.HTTPError(response=type('Response',(),{'status_code':429})()),'rate_limited','mange'),
])
def test_public_source_failure_reports_actionable_cause(monkeypatch,tmp_path,error,status,words):
    import solide.evidence as module
    def fail(v):raise error
    monkeypatch.setattr(module,'normalize_variant',fail)
    v=Variant(patient='00OUM00001',gene='EGFR',assembly='GRCh37',selected=True)
    run_queue(Session(variants=[v]),['Mutalyzer'],tmp_path,QueueControl(),lambda *a:None,lambda *a:None)
    evidence=v.evidence['Mutalyzer']
    assert evidence['status']==status
    assert words in evidence['summary'].lower()
    assert evidence['raw']['failure']['source']=='Mutalyzer'

def test_managed_browser_policy_is_recognized_through_startup_wrapper():
    from solide.source_failures import source_failure
    from solide._vendor.archer.services.edge_cdp import EdgeCdpPolicyError
    from solide._vendor.archer.services.browser_review import BrowserAutomationUnavailable
    wrapped=BrowserAutomationUnavailable('Unable to start Edge')
    wrapped.__cause__=EdgeCdpPolicyError('Managed policy')
    result=source_failure('COSMIC',wrapped)
    assert result['status']=='network_error'
    assert 'policy' in result['summary']

def test_typed_proxy_error_keeps_its_cause_when_it_wraps_a_transport_error():
    from solide.source_failures import source_failure
    error=requests.exceptions.ProxyError('Proxy rejected connection')
    error.__cause__=RuntimeError('Underlying socket failure')
    result=source_failure('SpliceAI',error)
    assert result['status']=='network_error' and 'Proxy' in result['summary']
