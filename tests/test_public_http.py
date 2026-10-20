from unittest.mock import Mock

import pytest
import requests

from solide.public_http import PublicHttpSession


URL = 'https://mutalyzer.nl/api/normalize/NM_000314.8%3Ac.242T%3EG'


def response(status=200, text='{"normalized_description":"NM_000314.8:c.242T>G"}'):
    item = requests.Response()
    item.status_code = status
    item._content = text.encode()
    item.headers['Content-Type'] = 'application/json'
    item.url = URL
    return item


def test_direct_connection_failure_uses_managed_edge_and_reuses_it_for_origin():
    direct = Mock()
    direct.get.side_effect = requests.exceptions.SSLError('Synthetic managed certificate')
    browser = Mock(return_value=response())
    with PublicHttpSession(direct, browser_get=browser) as session:
        assert session.get(URL, timeout=45).json()['normalized_description'].startswith('NM_000314.8:')
        session.get(URL, timeout=45)
    assert direct.get.call_count == 1
    assert browser.call_count == 2
    direct.close.assert_called_once()


@pytest.mark.parametrize('status', [200, 422, 429, 500])
def test_service_responses_are_not_retried_through_browser(status):
    direct = Mock()
    direct.get.return_value = response(status)
    browser = Mock()
    with PublicHttpSession(direct, browser_get=browser) as session:
        assert session.get(URL).status_code == status
    browser.assert_not_called()


def test_proxy_access_denial_can_use_the_browser_network_configuration():
    direct = Mock()
    direct.get.return_value = response(407)
    browser = Mock(return_value=response())
    with PublicHttpSession(direct, browser_get=browser) as session:
        assert session.get(URL).status_code == 200


def test_proxy_html_block_page_does_not_masquerade_as_a_variant_validation_error():
    direct=Mock();blocked=response(200,'<html>Organization proxy access page</html>')
    blocked.headers['Content-Type']='text/html; charset=utf-8'
    direct.get.return_value=blocked;browser=Mock(return_value=response())
    with PublicHttpSession(direct,browser_get=browser) as session:
        assert session.get(URL).json()['normalized_description']=='NM_000314.8:c.242T>G'
    browser.assert_called_once()


@pytest.mark.parametrize('url', ['https://example.org/api/', 'http://mutalyzer.nl/api/normalize/x',
    'https://user:secret@mutalyzer.nl/api/normalize/x', 'https://mutalyzer.nl.evil.org/api/'])
def test_browser_fallback_never_visits_unapproved_origins(url):
    direct = Mock()
    direct.get.side_effect = requests.ConnectionError('Synthetic unavailable')
    browser = Mock()
    with PublicHttpSession(direct, browser_get=browser) as session:
        with pytest.raises(requests.ConnectionError):
            session.get(url)
    browser.assert_not_called()


def test_public_query_parameters_are_preserved_without_patient_or_login_fields():
    direct = Mock()
    direct.get.side_effect = requests.ConnectionError('Synthetic unavailable')
    browser = Mock(return_value=response())
    with PublicHttpSession(direct, browser_get=browser) as session:
        session.get('https://mutalyzer.nl/api/map/', params={'description': 'NM_000314.8:c.242T>G',
            'reference_id': 'GRCh37'}, timeout=45)
    assert 'description=NM_000314.8%3Ac.242T%3EG' in browser.call_args.args[0]
    assert 'reference_id=GRCh37' in browser.call_args.args[0]


def test_one_queue_reuses_the_fallback_session_without_early_close(monkeypatch):
    import solide.public_http as module
    direct = Mock(); direct.get.side_effect = requests.ConnectionError('Synthetic offline')
    browser = Mock(return_value=response())
    session = PublicHttpSession(direct, browser_get=browser)
    monkeypatch.setattr(module, 'PublicHttpSession', lambda: session)
    with module.public_api_run():
        first = module.public_api_session(); first.get(URL); first.close()
        second = module.public_api_session(); second.get(URL); second.close()
        direct.close.assert_not_called()
    direct.close.assert_called_once()
    assert direct.get.call_count == 1 and browser.call_count == 2


def test_unused_queue_does_not_initialize_python_tls_or_launch_a_browser(monkeypatch):
    import solide.public_http as module
    direct = Mock(side_effect=OSError('Synthetic unavailable certificate store'))
    monkeypatch.setattr(module, 'system_trust_session', direct)
    browser = Mock(return_value=response())
    with module.PublicHttpSession(browser_get=browser):pass
    direct.assert_not_called();browser.assert_not_called()
    with module.PublicHttpSession(browser_get=browser) as session:
        assert session.get(URL).status_code == 200
    assert browser.call_count == 1
