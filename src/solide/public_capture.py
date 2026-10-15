"""Real source screenshots bound to the validated public-service response."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode,quote

from .nomenclature import validate_spliceai_response
from ._vendor.archer.services.edge_cdp import sync_edge_cdp
from ._vendor.archer.services.capture_validation import validate_capture

_SCORES=('DS_AG','DS_AL','DS_DG','DS_DL','DP_AG','DP_AL','DP_DG','DP_DL')


def spliceai_url(data:dict)->str:
    validate_spliceai_response(data['response'],data['query'])
    return 'https://spliceailookup.broadinstitute.org/#'+urlencode({
        'variant':data['query'],'hg':37,'bc':'basic','distance':500,'mask':1,'ra':1})


def validate_spliceai_capture(data:dict,browser:dict)->None:
    """A screenshot must show the same allele, settings, transcripts and scores."""
    validate_spliceai_response(data['response'],data['query'])
    # The website removes the optional chr prefix before its own API request.
    # Accept that presentation change only after allele-equivalent spelling is
    # checked, then validate the returned scored coordinates against our query.
    equivalent={data['query'].removeprefix('chr'),data.get('scored_variant','').removeprefix('chr')}
    if browser.get('variant','').removeprefix('chr') not in equivalent:
        raise ValueError('SpliceAI page requested a different allele.')
    validate_spliceai_response({**browser,'variant':data['query']},data['query'])
    if browser.get('bc','basic')!='basic':raise ValueError('SpliceAI capture uses different transcript annotations.')
    def signature(response):
        return sorted((str(row.get('g_name') or row.get('gene_name') or row.get('symbol') or ''),
                       str(row.get('t_id') or row.get('transcript_id') or ''),
                       tuple(sorted(row.get('t_refseq_ids') or [])),
                       tuple(float(row[key]) for key in _SCORES)) for row in response['scores'])
    if not browser['scores'] or signature(browser)!=signature(data['response']):
        raise ValueError('SpliceAI page scores or transcripts differ from the validated response. Capture again.')


def validate_spliceai_dom(data:dict,state:dict)->None:
    if (state.get('input')!=data['query'] or state.get('hg')!='37' or state.get('bc')!='basic'
            or state.get('distance')!='500' or state.get('mask') is not True or state.get('ref_alt') is not True
            or not state.get('table_visible') or state.get('visible_rows')!=4*len(data['response']['scores'])):
        raise ValueError('SpliceAI rendered settings or complete transcript rows are unavailable. Capture again.')


def capture_spliceai(data:dict,directory:Path,*,background=True,checkpoint=lambda:None,progress=lambda text:None)->dict:
    """Capture the live form/settings and all transcript scores, excluding other tools."""
    url=spliceai_url(data);directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    stem=hashlib.sha256(data['query'].encode()).hexdigest()[:16]
    progress('SpliceAI: capturing validated transcript scores')
    with sync_edge_cdp() as runtime:
        context=runtime.chromium.launch_persistent_context(str(Path.home()/'.solide'/'browser_profiles'/'SpliceAI'),
            background=background,viewport={'width':1600,'height':1000})
        page=context.pages[0] if context.pages else context.new_page();checkpoint();page.goto(url)
        deadline=time.monotonic()+180;state={}
        while time.monotonic()<deadline:
            checkpoint()
            state=page.evaluate("""() => ({input:document.querySelector('#search-box')?.value,
                response:typeof lastSpliceaiResponseJson==='undefined'?null:lastSpliceaiResponseJson,
                rows:document.querySelectorAll('#spliceai-table .spliceai-result-row').length,
                visible:!!document.querySelector('#spliceai-table')?.getBoundingClientRect().height})""")
            if state.get('response') and state.get('rows') and state.get('visible'):break
            time.sleep(.25)
        if state.get('input')!=data['query'] or not state.get('response'):
            raise ValueError('SpliceAI page did not finish the requested variant; screenshot unavailable.')
        validate_spliceai_capture(data,state['response'])
        # All basic-annotation transcripts remain visible; do not silently choose
        # the first gene or discard a non-MANE transcript from the evidence.
        page.evaluate("""() => document.querySelector('#all-transcript-button')?.click()""")
        visible=page.evaluate("""() => ({input:document.querySelector('#search-box')?.value,
            hg:document.querySelector('input[name="hg"]:checked')?.value,
            bc:document.querySelector('input[name="gencode-gene-set"]:checked')?.value,
            distance:document.querySelector('#max-distance-input')?.value,
            mask:document.querySelector('input[name="mask"]')?.checked,
            ref_alt:document.querySelector('input[name="show-ref-alt"]')?.checked,
            table_visible:!!document.querySelector('#spliceai-table')?.getBoundingClientRect().height,
            visible_rows:[...document.querySelectorAll('#spliceai-table .spliceai-result-row')]
                .filter(el=>el.getBoundingClientRect().height>0).length})""")
        validate_spliceai_dom(data,visible)
        specs=[]
        form=page.locator('#search-box').evaluate("el => el.closest('.ui.form')?.getBoundingClientRect().toJSON()")
        if not form or form.get('width',0)<=0 or form.get('height',0)<=0:
            raise ValueError('SpliceAI query/settings panel is unavailable. Capture again.')
        path=directory/f'{stem}-spliceai-query.png';page.screenshot(path=str(path),clip=form)
        specs.append({'path':str(path),'label':'SpliceAI query · hg19 · ±500 bp · masked · REF/ALT'})
        path=directory/f'{stem}-spliceai-scores.png';page.locator('#spliceai-table').screenshot(path=str(path))
        specs.append({'path':str(path),'label':'SpliceAI transcript scores · all basic transcripts'})
        for record in specs:
            if not validate_capture(Path(record['path'])).valid:
                raise ValueError('SpliceAI screenshot is unreadable; capture again.')
        metadata={'url':url,'captured_at':datetime.now(timezone.utc).isoformat(),
                  'query':data['query'],'settings':{'hg':37,'distance':500,'mask':1,'bc':'basic','ref_alt':True},
                  'score_identity_confirmed':True,'dom_identity_confirmed':True,'transcripts':len(state['response']['scores']),
                  'screenshots':specs}
        (directory/f'{stem}-spliceai.capture.json').write_text(json.dumps(metadata,indent=2),encoding='utf8')
        return metadata


def validate_mutalyzer_capture(data:dict,state:dict)->None:
    normalization=data.get('normalization',{})
    name=normalization.get('normalized_description')
    if (normalization.get('errors') or not name or state.get('input')!=data.get('original')
            or state.get('normalized')!=name):
        raise ValueError('Mutalyzer page does not match the requested normalization response.')


def capture_mutalyzer(data:dict,directory:Path,*,background=True,checkpoint=lambda:None,progress=lambda text:None)->dict:
    """Capture the original query and actual normalized-name panel together."""
    if data.get('normalization',{}).get('errors') and data.get('nomenclature_assessment',{}).get('identity_confirmed'):
        data=data.get('contextual_normalization') or data
    if data['normalization'].get('errors') or not data['normalization'].get('normalized_description'):
        return {}
    url='https://mutalyzer.nl/normalizer/'+quote(data['original'],safe='')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    stem=hashlib.sha256(data['original'].encode()).hexdigest()[:16]
    progress('Mutalyzer: capturing the original and normalized names')
    with sync_edge_cdp() as runtime:
        context=runtime.chromium.launch_persistent_context(str(Path.home()/'.solide'/'browser_profiles'/'Mutalyzer'),
            background=background,viewport={'width':1600,'height':1000})
        page=context.pages[0] if context.pages else context.new_page();checkpoint();page.goto(url)
        deadline=time.monotonic()+90;state={}
        while time.monotonic()<deadline:
            checkpoint()
            state=page.evaluate("""() => ({input:document.querySelector('input')?.value,
                normalized:document.querySelector('.v-alert.green,.v-alert.blue')?.innerText?.trim()})""")
            if state.get('normalized'):break
            time.sleep(.25)
        validate_mutalyzer_capture(data,state)
        box=page.evaluate("""() => {const input=document.querySelector('input').getBoundingClientRect();
            const alert=document.querySelector('.v-alert.green,.v-alert.blue').getBoundingClientRect();
            const x=Math.max(0,Math.min(input.left,alert.left)-20),y=Math.max(0,input.top-55);
            return {x,y,width:Math.max(input.right,alert.right)-x+15,height:alert.bottom-y+15};}""")
        path=directory/f'{stem}-mutalyzer-normalization.png';page.screenshot(path=str(path),clip=box)
        if not validate_capture(path).valid:raise ValueError('Mutalyzer screenshot is unreadable; capture again.')
        metadata={'url':url,'captured_at':datetime.now(timezone.utc).isoformat(),'query':data['original'],
            'normalized':state['normalized'],'screenshots':[{'path':str(path),'label':'Mutalyzer · input and normalized name'}]}
        (directory/f'{stem}-mutalyzer.capture.json').write_text(json.dumps(metadata,indent=2),encoding='utf8')
        return metadata
