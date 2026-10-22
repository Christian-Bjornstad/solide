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
<section id="new-variant-details"><h3>Variant Details
<a><i class="new-icon-down" onclick="document.querySelector('#variant-details-table').style.display='block'"></i></a>
</h3><div id="variant-details-table">
<dl><dt>Identifiers</dt><dd>Variation ID: 1 Accession: VCV000000001.1</dd>
<dt>Type and length</dt><dd>single nucleotide variant, 1 bp</dd>
<dt>Location</dt><dd>17:7578406 (GRCh37)</dd>
<dt>Timeline in ClinVar</dt><dd>First in ClinVar; Last submission; Last evaluated</dd>
<dt>HGVS</dt><dd><table><tr><th>Nucleotide</th><th>Protein</th></tr>
<tr><td>NM_000546.6:c.524G&gt;A</td><td>p.Arg175His</td></tr></table></dd>
<dt>Protein change</dt><dd>R175H</dd></dl></div></section>
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


def test_clinvar_crop_includes_expanded_variant_details_and_rejects_incomplete_panels(tmp_path,monkeypatch):
    from urllib.parse import quote
    from pathlib import Path
    from solide._vendor.archer.core.models import DatabaseEvidence,VariantRecord
    from solide._vendor.archer.services.browser_review import BrowserReviewService
    with sync_edge_cdp() as runtime:
        context=runtime.chromium.launch_persistent_context(str(tmp_path/'profile'),background=True)
        page=context.pages[0] if context.pages else context.new_page()
        # Keep this geometry test self-contained; the pending-resource test
        # above separately exercises the same native section structure.
        html=HTML.decode().replace('/stall-font','data:font/woff2;base64,AA==').replace('/stall-image','')
        page.goto('data:text/html,'+quote(html))
        state=page.evaluate(CLINVAR_PANEL_JS)
        bottom=page.evaluate('() => document.querySelector("#new-variant-details").getBoundingClientRect().bottom')
        assert state['clip']['y']+state['clip']['height']>=bottom
        assert 'Variation ID: 1' in state['details_text']
        assert 'Last evaluated' in state['details_text'] and 'NM_000546.6:c.524G>A' in state['details_text']
        page.evaluate('document.querySelector("#variant-details-table").style.display="none"')
        assert not page.evaluate(CLINVAR_PANEL_JS)['ready']
        service=BrowserReviewService(profile_root=tmp_path)
        def readiness(_):assert page.locator('#variant-details-table').is_visible()
        monkeypatch.setattr(service,'_wait_for_clinvar_result',readiness)
        evidence=service._capture_clinvar_result(
            VariantRecord(Path('synthetic.tsv'),1,'SOURCE','TP53','NM_000546.6:c.524G>A'),
            DatabaseEvidence('ClinVar','found',clinical_significance='Benign',
                             raw={'classifications':{'germline':'Benign'}}),page,tmp_path)
        assert 'NM_000546.6:c.524G>A' in evidence.raw['variant_details']
        page.evaluate("[...document.querySelectorAll('#variant-details-table dt')].find(el=>el.innerText==='HGVS').remove()")
        assert not page.evaluate(CLINVAR_PANEL_JS)['ready']
        page.evaluate('document.querySelector("#new-variant-details").remove()')
        assert page.evaluate(CLINVAR_PANEL_JS)['clip'] is None
