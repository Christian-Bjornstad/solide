"""Opt-in managed Edge regression: unrelated resources must not block a result."""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

import pytest

from solide._vendor.archer.services.edge_cdp import sync_edge_cdp
from solide._vendor.archer.services.source_panel_capture import (
    CLINVAR_PANEL_JS, ONCOKB_PANEL_JS, capture_source_panel,
)

pytestmark = pytest.mark.skipif(os.environ.get('SOLIDE_EDGE_CAPTURE_TESTS') != '1',
    reason='Opt-in isolated, background managed Edge test')

HTML = b'''<!doctype html><html><head><style>
@font-face {font-family:Pending;src:url(/stall-font);font-display:swap}
body {font:16px Arial;margin:32px} .alterationTiles {width:800px;padding:20px;border:1px solid #ddd}
</style></head><body><main><div class="functions-container"><h1>TP53 R175H</h1></div>
<nav aria-label="breadcrumb">TP53 R175H Somatic</nav><section class="col-md-11">
<h3>Variant Overview</h3><p>The TP53 R175H variant.</p>
<div class="alterationTiles"><div><h3>Mutation Effect</h3><p>Oncogenicity</p>
<p>Unknown Oncogenic Effect</p></div></div></section>
<section id="germline-somatic-info">Germline classification: Benign</section>
<p style="font-family:Pending">Unrelated footer font</p><img src="/stall-image"></main></body></html>'''


@pytest.mark.parametrize('script,expected', [(ONCOKB_PANEL_JS, 'Unknown Oncogenic Effect'),
                                           (CLINVAR_PANEL_JS, 'Benign')])
def test_native_panels_capture_while_unrelated_image_and_font_are_pending(tmp_path, script, expected):
    release = Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html' if self.path == '/' else 'application/octet-stream')
            self.end_headers()
            if self.path == '/':
                self.wfile.write(HTML)
            else:
                release.wait(20)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_edge_cdp() as runtime:
            context = runtime.chromium.launch_persistent_context(str(tmp_path/'profile'), background=True)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='domcontentloaded')
            state = page.evaluate(script)
            assert state['document_state'] == 'interactive'
            assert state['font_state'] == 'loading'
            assert state['ready']
            image = tmp_path/'panel.png'
            capture_source_panel(page, image, script, timeout_ms=3000, required_text=[expected])
            assert image.stat().st_size > 1000
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
