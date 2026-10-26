"""Capture native result panels after their font/layout geometry has settled."""
import time
import math

PREPARE_CAPTURE_JS = '''() => {
    if(document.getElementById('solide-static-source-capture')) return;
    const style=document.createElement('style');style.id='solide-static-source-capture';
    style.textContent='html {scroll-behavior:auto!important;overflow-y:scroll!important;scrollbar-gutter:stable!important} *, *::before, *::after {animation:none!important;transition:none!important}';
    document.head.appendChild(style);
}'''
RESTORE_CAPTURE_JS = "() => document.getElementById('solide-static-source-capture')?.remove()"


CLINVAR_PANEL_JS = '''() => {
    window.scrollTo(0,0);
    const title=document.querySelector('main div.functions-container');
    const summary=document.querySelector('#germline-somatic-info');
    const details=document.querySelector('#new-variant-details');
    const table=document.querySelector('#variant-details-table');
    const detailsVisible=table?.getBoundingClientRect().height>0;
    const detailsText=detailsVisible?table.innerText:'';
    const boxes=[title,summary,details,table].map(el=>el?.getBoundingClientRect());
    return {ready:document.readyState!=='loading' && detailsVisible &&
            ['Variation ID:', 'Location', 'Timeline in ClinVar', 'HGVS'].every(label=>detailsText.includes(label)),
        document_state:document.readyState,font_state:document.fonts?.status,
        details_text:detailsText,
        text:summary?.innerText||'',clip:boxes.every(b=>b?.width>0 && b?.height>0)?{
            x:Math.min(...boxes.map(b=>b.left)),y:Math.min(...boxes.map(b=>b.top)),
            width:Math.max(...boxes.map(b=>b.right))-Math.min(...boxes.map(b=>b.left)),
            height:Math.max(...boxes.map(b=>b.bottom))-Math.min(...boxes.map(b=>b.top))}:null};
}'''

ONCOKB_PANEL_JS = '''() => {
    window.scrollTo(0,0);
    const title=document.querySelector('nav[aria-label="breadcrumb"]') || document.querySelector('h1');
    const heading=[...document.querySelectorAll('h3')].find(el=>el.innerText.trim()==='Mutation Effect');
    const tiles=heading?.closest('[class*="alterationTiles"]');
    const boxes=[title,tiles].map(el=>el?.getBoundingClientRect());
    const scope=tiles?.closest('.col-md-11')?.getBoundingClientRect();
    // A stalled tracker/image or unused font must not block a rendered result.
    // Stable panel geometry is checked before AND after the screenshot.
    return {ready:document.readyState!=='loading' && (tiles?.innerText||'').includes('Oncogenicity'),
        document_state:document.readyState,font_state:document.fonts?.status,
        text:[title,tiles].map(el=>el?.innerText||'').join(String.fromCharCode(10)),
        clip:boxes.every(b=>b?.width>0 && b?.height>0)?{
            x:Math.min(...boxes.map(b=>b.left)),y:Math.min(...boxes.map(b=>b.top)),
            width:Math.max(scope?.right||0,...boxes.map(b=>b.right))+16-Math.min(...boxes.map(b=>b.left)),
            height:Math.max(...boxes.map(b=>b.bottom))-Math.min(...boxes.map(b=>b.top))}:null};
}'''


class SourcePanelCaptureTimeout(TimeoutError):
    """Retain layout/readiness diagnostics without logging full page contents."""

    def __init__(self, state, required_text):
        super().__init__('Source result panels did not reach a stable, complete layout.')
        self.diagnostics = {'last_state': {key: state.get(key)
            for key in ('ready', 'clip', 'document_state', 'font_state')},
            'required_text_present': [text in state.get('text', '') for text in required_text]}


def capture_source_panel(page,path,script,*,timeout_ms,checkpoint=lambda:None,required_text=()):
    native=script in (CLINVAR_PANEL_JS,ONCOKB_PANEL_JS)
    if native:page.evaluate(PREPARE_CAPTURE_JS)
    try:
        return _capture_stable_panel(page,path,script,timeout_ms=timeout_ms,
                                     checkpoint=checkpoint,required_text=required_text)
    finally:
        if native:
            try:page.evaluate(RESTORE_CAPTURE_JS)
            except Exception:pass  # Closing/cancellation must keep its original outcome.


def _same_bounds(first,second):
    if not first or not second:return False
    edges=lambda c:(c['x'],c['y'],c['x']+c['width'],c['y']+c['height'])
    return all(abs(a-b)<=0.5 for a,b in zip(edges(first),edges(second)))


def _capture_stable_panel(page,path,script,*,timeout_ms,checkpoint,required_text):
    deadline=time.monotonic()+timeout_ms/1000
    previous=None;stable=0;state={}
    while time.monotonic()<deadline:
        checkpoint()
        state=page.evaluate(script);clip=state.get('clip')
        if (state.get('ready') and clip and clip.get('width',0)>0 and clip.get('height',0)>0
                and clip.get('x',-1)>=0 and clip.get('y',-1)>=0
                and all(text in state.get('text','') for text in required_text)):
            stable=stable+1 if _same_bounds(clip,previous) else 0
            if stable>=2:
                left=max(0,math.floor(clip['x'])-2);top=max(0,math.floor(clip['y'])-2)
                capture_clip={'x':left,'y':top,'width':math.ceil(clip['x']+clip['width'])+2-left,
                              'height':math.ceil(clip['y']+clip['height'])+2-top}
                page.screenshot(path=str(path),clip=capture_clip)
                checkpoint()
                # Late CSS/notices can move a panel while a full-document CDP
                # screenshot is taken. Never publish a crop using old bounds.
                after=page.evaluate(script)
                if (after.get('ready') and _same_bounds(after.get('clip'),clip)
                        and all(text in after.get('text','') for text in required_text)):return after
                state=after;previous=None;stable=0
                continue
            previous=clip
        else:
            previous=None;stable=0
        page.wait_for_timeout(250)
    raise SourcePanelCaptureTimeout(state, required_text)
