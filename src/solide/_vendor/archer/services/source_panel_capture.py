"""Capture native result panels after their font/layout geometry has settled."""
import time


CLINVAR_PANEL_JS = '''() => {
    window.scrollTo(0,0);
    const title=document.querySelector('main div.functions-container');
    const summary=document.querySelector('#germline-somatic-info');
    const boxes=[title,summary].map(el=>el?.getBoundingClientRect());
    return {ready:document.readyState==='complete' && (!document.fonts || document.fonts.status==='loaded'),
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
    return {ready:document.readyState==='complete' && (!document.fonts || document.fonts.status==='loaded'),
        clip:boxes.every(b=>b?.width>0 && b?.height>0)?{
            x:Math.min(...boxes.map(b=>b.left)),y:Math.min(...boxes.map(b=>b.top)),
            width:Math.max(scope?.right||0,...boxes.map(b=>b.right))+16-Math.min(...boxes.map(b=>b.left)),
            height:Math.max(...boxes.map(b=>b.bottom))-Math.min(...boxes.map(b=>b.top))}:null};
}'''


def capture_source_panel(page,path,script,*,timeout_ms,checkpoint=lambda:None,required_text=()):
    deadline=time.monotonic()+timeout_ms/1000
    previous=None;stable=0
    while time.monotonic()<deadline:
        checkpoint()
        state=page.evaluate(script);clip=state.get('clip')
        if (state.get('ready') and clip and clip.get('width',0)>0 and clip.get('height',0)>0
                and clip.get('x',-1)>=0 and clip.get('y',-1)>=0
                and all(text in state.get('text','') for text in required_text)):
            stable=stable+1 if clip==previous else 0
            if stable>=2:
                page.screenshot(path=str(path),clip=clip)
                checkpoint()
                # Late CSS/notices can move a panel while a full-document CDP
                # screenshot is taken. Never publish a crop using old bounds.
                after=page.evaluate(script)
                if (after.get('ready') and after.get('clip')==clip
                        and all(text in after.get('text','') for text in required_text)):return after
                previous=None;stable=0
                continue
            previous=clip
        else:
            previous=None;stable=0
        page.wait_for_timeout(250)
    raise TimeoutError('Source result panels did not reach a stable, complete layout.')
