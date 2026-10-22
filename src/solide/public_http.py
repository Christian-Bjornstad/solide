"""Public API reads using Windows-managed Edge when Python cannot connect.

No sign-in profile, credentials, TLS exceptions or persistent query cache.
The same service response validators apply to both transports.
"""
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
import json
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, parse_qs

import requests

from ._vendor.archer.services.system_trust import system_trust_session
from ._vendor.archer.services.edge_cdp import sync_edge_cdp

_current_session = ContextVar('solide_public_api_session', default=None)

def _allowed(url):
    address = urlsplit(url)
    if address.scheme != 'https' or address.username or address.password or address.port or address.fragment:
        return False
    if address.netloc == 'mutalyzer.nl':
        return (address.path.startswith(('/api/normalize/', '/api/delins_model/'))
                or address.path in {'/api/map/', '/api/reference_model/'}) and set(parse_qs(address.query)) <= {
                    'description', 'reference_id', 'selector_id', 'filter_out'}
    if address.netloc == 'brcaexchange.org':
        return address.path in {'/backend/data/','/backend/data/variant/'} and set(parse_qs(address.query)) <= {
            'format','include','page_size','page_num','filter','filterValue','search_term','variant_id'}
    return address.netloc == 'spliceai-37-xwkwwwxdwq-uc.a.run.app' and address.path == '/spliceai/' and set(
        parse_qs(address.query)) <= {'hg', 'variant', 'distance', 'mask'}


class PublicHttpSession:
    def __init__(self, http=None, *, browser_get=None):
        self.http = http
        self._browser_get = browser_get or self._edge_get
        self._browser_origins = set()
        self._stack = ExitStack()
        self._page = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        try:
            self._stack.close()
        finally:
            if self.http is not None:self.http.close()
            self._page = None
            self._browser_origins.clear()

    def get(self, url, **kwargs):
        prepared = requests.Request('GET', url, params=kwargs.get('params')).prepare().url
        # Never transfer custom credentials, headers, bodies or verification
        # overrides to a browser. Only the fixed public service contracts qualify.
        allowed = _allowed(prepared) and not set(kwargs) - {'params', 'timeout', 'allow_redirects'}
        origin = urlsplit(prepared).netloc
        if allowed and origin in self._browser_origins:
            return self._browser_get(prepared, timeout=kwargs.get('timeout', 45))
        try:
            if self.http is None:self.http = system_trust_session()
            direct_kwargs = dict(kwargs)
            if isinstance(kwargs.get('timeout'), (int, float)):
                direct_kwargs['timeout'] = (min(5, kwargs['timeout']), kwargs['timeout'])
            response = self.http.get(url, **direct_kwargs)
        except (requests.ConnectionError, requests.Timeout, OSError):
            if not allowed:
                raise
        else:
            html_block=response.status_code==200 and 'html' in str(response.headers.get('Content-Type','')).lower()
            if not allowed or response.status_code not in {403, 407} and not html_block:
                return response
        self._browser_origins.add(origin)
        return self._browser_get(prepared, timeout=kwargs.get('timeout', 45))

    def _edge_get(self, url, *, timeout):
        if not _allowed(url):
            raise requests.ConnectionError('Public API browser destination is not permitted.')
        milliseconds = int(min(120, max(1, timeout)) * 1000)
        try:
            if self._page is None:
                directory = self._stack.enter_context(TemporaryDirectory(prefix='solide-public-api-'))
                runtime = self._stack.enter_context(sync_edge_cdp())
                context = runtime.chromium.launch_persistent_context(directory, background=True)
                self._page = context.pages[0] if context.pages else context.new_page()
            origin = 'https://' + urlsplit(url).netloc
            if urlsplit(self._page.url).netloc != urlsplit(url).netloc:
                self._page.goto(origin + '/', timeout=milliseconds)
            if urlsplit(self._page.url).scheme != 'https' or urlsplit(self._page.url).netloc != urlsplit(url).netloc:
                raise ValueError('Public API origin redirected away from its approved host.')
            # Same-origin fetch retains the real HTTP status, including 422.
            # Redirects and sign-in cookies are deliberately excluded.
            result = self._page.evaluate('''async () => {
                const response = await fetch(''' + json.dumps(url) + ''', {
                    credentials: 'omit', redirect: 'error', referrerPolicy: 'no-referrer',
                    signal: AbortSignal.timeout(''' + str(milliseconds) + ''')});
                const text = await response.text();
                if (text.length > 4000000) throw new Error('Public API response is too large');
                return {status: response.status, url: response.url, text,
                    contentType: response.headers.get('content-type') || ''};
            }''', timeout_ms=milliseconds + 2000)
            if not isinstance(result, dict) or result.get('url') != url or type(result.get('status')) is not int:
                raise ValueError('Public API browser response did not confirm its destination.')
            if not isinstance(result.get('text'), str) or len(result['text']) > 4_000_000:
                raise ValueError('Public API browser response is incomplete or too large.')
            response = requests.Response()
            response.status_code = result['status']
            response.url = url
            response.encoding = 'utf-8'
            response._content = result['text'].encode('utf-8')
            response.headers['Content-Type'] = result.get('contentType', '')
            response.headers['X-Solide-Transport'] = 'Edge'
            return response
        except Exception as exc:
            raise requests.ConnectionError('Public API unavailable through Python and managed Edge ('
                                           + type(exc).__name__ + ').') from exc


def public_api_session():
    current = _current_session.get()
    return _BorrowedSession(current) if current is not None else PublicHttpSession()


class _BorrowedSession:
    def __init__(self, session):self.session = session
    def get(self, *args, **kwargs):return self.session.get(*args, **kwargs)
    def close(self):pass  # Owned and closed by the queue's scope.


@contextmanager
def public_api_run():
    """Keep network recovery per worker/run, never across patients on disk."""
    if _current_session.get() is not None:
        yield
        return
    with PublicHttpSession() as session:
        token = _current_session.set(session)
        try:yield
        finally:_current_session.reset(token)
