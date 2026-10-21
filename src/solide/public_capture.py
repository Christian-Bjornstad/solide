"""Real source screenshots bound to the validated public-service response."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import re
import math
from collections import Counter
from urllib.parse import urlencode,quote,urlsplit

from .nomenclature import validate_spliceai_response
from ._vendor.archer.services.edge_cdp import sync_edge_cdp
from ._vendor.archer.services.capture_validation import validate_capture

_SCORES=('DS_AG','DS_AL','DS_DG','DS_DL','DP_AG','DP_AL','DP_DG','DP_DL')


def validate_brca_exchange_capture(evidence:dict,state:dict)->None:
    """Bind the visible current record to the independently verified API result."""
    raw=evidence.get('raw',{});identity=raw.get('identity_verification',{})
    if (evidence.get('status')!='found' or identity.get('accepted') is not True
            or not identity.get('requested') or identity.get('requested')!=identity.get('returned')):
        raise ValueError('BRCA Exchange API identity is not confirmed.')
    row=raw.get('variant',{});variant_id=row.get('id')
    if type(variant_id) is not int or variant_id<=0 or str(variant_id)!=evidence.get('accession'):
        raise ValueError('BRCA Exchange source record ID is not confirmed.')
    url=urlsplit(state.get('url',''))
    if (url.scheme!='https' or url.netloc!='brcaexchange.org'
            or not re.fullmatch(r'/variant/(?:[1-9]\d*|CA\d+)/?',url.path)
            or url.query or url.fragment):
        raise ValueError('BRCA Exchange screenshot is not on a variant record.')
    hgvs=row.get('HGVS_cDNA','')
    if hgvs.startswith('c.'):hgvs=row.get('Reference_Sequence','')+':'+hgvs
    match=re.fullmatch(r'((?:NM|NR)_\d+\.\d+):(c\.\S+)',hgvs)
    if not match or not row.get('Genomic_HGVS_37'):
        raise ValueError('BRCA Exchange record lacks a complete screenshot identity.')
    expected={'gene':row.get('Gene_Symbol'),'transcript':match[1],'coding':match[2],
              'genomic_grch37':row['Genomic_HGVS_37'],'classification':evidence.get('clinical_significance','')}
    if expected['classification']!=row.get('Pathogenicity_expert',''):
        raise ValueError('BRCA Exchange source classification differs from the API record.')
    if any(state.get(field)!=value for field,value in expected.items()):
        raise ValueError('BRCA Exchange visible gene, versioned HGVS, genome or classification differs from the API result.')
    evaluated=row.get('Date_last_evaluated_ENIGMA')
    if evaluated and evaluated!='-':
        api_date=datetime.fromisoformat(evaluated.replace('Z','+00:00')).date()
        page_date=datetime.strptime(state.get('evaluated',''),'%d %B %Y').date()
        if api_date!=page_date:
            raise ValueError('BRCA Exchange visible evaluation date differs from the API result.')
    if not state.get('names_visible') or not state.get('classification_visible'):
        raise ValueError('BRCA Exchange current variant and ENIGMA panels are not visible.')


def capture_brca_exchange(evidence:dict,directory:Path,*,background=True,checkpoint=lambda:None,progress=lambda text:None)->dict:
    """Capture current names and ENIGMA evidence, excluding historical versions."""
    variant_id=evidence.get('raw',{}).get('variant',{}).get('id')
    if type(variant_id) is not int or variant_id<=0:
        raise ValueError('BRCA Exchange source record ID is missing.')
    url=f'https://brcaexchange.org/variant/{variant_id}'
    if evidence.get('url')!=url:
        raise ValueError('BRCA Exchange result URL does not match its verified source ID.')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    progress('BRCA Exchange: capturing the verified variant and ENIGMA classification')
    with sync_edge_cdp() as runtime:
        context=runtime.chromium.launch_persistent_context(str(Path.home()/'.solide'/'browser_profiles'/'BRCAExchange'),
            background=background,viewport={'width':1600,'height':1000})
        page=context.pages[0] if context.pages else context.new_page();checkpoint();page.goto(url)
        deadline=time.monotonic()+60;state={}
        while time.monotonic()<deadline:
            checkpoint()
            state=page.evaluate("""() => {
                document.querySelectorAll('.variant-detail-group .row-value-truncated').forEach(el=>{
                    el.style.whiteSpace='normal';el.style.overflow='visible';el.style.textOverflow='clip';
                    el.style.maxWidth='none';el.style.wordBreak='break-word';
                });
                const groups=[...document.querySelectorAll('.variant-detail-group')];
                const group=title=>groups.find(g=>g.querySelector('.card-header .title')?.innerText.trim()===title);
                const names=group('Variant Names'),clinical=group('Clinical Significance (ENIGMA)');
                const value=(g,label)=>{const row=[...(g?.querySelectorAll('tr')||[])].find(r=>r.querySelector('.help-target')?.innerText.trim()===label);
                    return row?.querySelector('.row-value,.row-value-truncated')?.innerText.trim()||'';};
                const visible=g=>!!g && g.getBoundingClientRect().height>0 && !!g.querySelector('.collapse.show');
                const container=names?.closest('.container'),box=container?.getBoundingClientRect();
                const bottom=Math.max(names?.getBoundingClientRect().bottom||0,clinical?.getBoundingClientRect().bottom||0);
                return {url:location.href,gene:value(names,'Gene'),transcript:value(names,'Transcript Identifier'),
                    coding:value(names,'HGVS Nucleotide'),genomic_grch37:value(names,'Genomic Nomenclature (GRCh37)'),
                    classification:value(clinical,'Clinical Significance'),evaluated:value(clinical,'Date Last Evaluated'),
                    names_visible:visible(names),classification_visible:visible(clinical),
                    clip:box?{x:Math.max(0,box.x),y:Math.max(0,box.y),width:box.width,height:bottom-box.y+8}:null};
            }""")
            if state.get('gene') and state.get('transcript') and state.get('names_visible') and state.get('classification_visible'):break
            page.wait_for_timeout(250)
        validate_brca_exchange_capture(evidence,state)
        clip=state.get('clip')
        if not clip or clip['width']<=0 or clip['height']<=0:
            raise ValueError('BRCA Exchange screenshot panel geometry is unavailable.')
        path=directory/f'{variant_id}-brca-exchange.png';page.screenshot(path=str(path),clip=clip)
        if not validate_capture(path).valid:
            raise ValueError('BRCA Exchange screenshot is unreadable; capture again.')
        metadata={'url':state['url'],'requested_url':url,'captured_at':datetime.now(timezone.utc).isoformat(),
                  'variant_id':variant_id,'identity_confirmed':True,'classification_confirmed':True,
                  'visible_record':{key:value for key,value in state.items() if key!='clip'},
                  'screenshots':[{'path':str(path),'label':'BRCA Exchange · variant identity and ENIGMA classification'}]}
        (directory/f'{variant_id}-brca-exchange.capture.json').write_text(json.dumps(metadata,indent=2),encoding='utf8')
        return metadata


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
                       str(row.get('t_priority') or ''),
                       tuple(sorted(row.get('t_refseq_ids') or [])),
                       tuple(float(row[key]) for key in _SCORES)) for row in response['scores'])
    if not browser['scores'] or signature(browser)!=signature(data['response']):
        raise ValueError('SpliceAI page scores or transcripts differ from the validated response. Capture again.')


def _mane_ids(response:dict)->list[str]:
    ids=[row['t_id'] for row in response.get('scores',[]) if row.get('t_priority')=='MS' and row.get('t_id')]
    if not ids:raise ValueError('MANE Select transcript is unavailable; capture requires source review.')
    return sorted(set(ids))


def validate_pangolin_capture(data:dict,response:dict)->None:
    """Pangolin is a separate model: check its allele and settings, not SpliceAI scores."""
    reference=data['response']
    variants={data['query'].removeprefix('chr'),
              validate_spliceai_response(reference,data['query']).removeprefix('chr')}
    if (not isinstance(response,dict) or response.get('error') or response.get('errors')
            or response.get('variant','').removeprefix('chr') not in variants
            or any(str(response.get(key))!='37' for key in ('hg','genomeVersion'))
            or response.get('bc')!='basic' or response.get('distance')!=500
            or str(response.get('mask')).lower() not in {'1','true'}
            or any(response.get(key)!=reference.get(key) for key in ('chrom','pos','ref','alt'))):
        raise ValueError('Pangolin did not confirm the requested allele and hg19 settings.')
    _mane_ids(response)
    for row in response['scores']:
        try:
            scores=[float(row[key]) for key in ('DS_SL','DS_SG')]
            positions=[float(row[key]) for key in ('DP_SL','DP_SG')]
        except (KeyError,TypeError,ValueError):
            raise ValueError('Pangolin prediction scores are incomplete.') from None
        if (any(not math.isfinite(v) or abs(v)>1 for v in scores)
                or any(not math.isfinite(v) or not v.is_integer() for v in positions)):
            raise ValueError('Pangolin prediction scores are invalid.')


def validate_spliceai_dom(data:dict,state:dict)->None:
    if (state.get('input')!=data['query'] or state.get('hg')!='37' or state.get('bc')!='basic'
            or state.get('distance')!='500' or state.get('mask') is not True or state.get('ref_alt') is not True):
        raise ValueError('SpliceAI rendered query/settings are unavailable. Capture again.')
    for key,response,rows in [('spliceai',data['response'],4),('pangolin',data['pangolin_response'],2)]:
        panel=state.get('panels',{}).get(key,{})
        expected=Counter({transcript:rows for transcript in _mane_ids(response)})
        if not panel.get('visible') or Counter(panel.get('transcripts',[]))!=expected:
            raise ValueError(f'{key}: complete MANE Select scores are unavailable. Capture again.')
    prediction=data['response'].get('sai10kPredictions') or {}
    panel=state.get('panels',{}).get('consequences',{})
    transcript=prediction.get('transcript_id')
    output=panel.get('output','').strip()
    if (data['response'].get('sai10kPredictionsError') or not isinstance(prediction.get('aberrations'),list)
            or transcript not in _mane_ids(data['response']) or not panel.get('visible')
            or panel.get('transcripts')!=[transcript] or panel.get('method')!='SAI-10k-calc'
            or not output or output.lower().startswith(('loading','error'))
            or (not prediction['aberrations'] and output!='No prediction')
            or (prediction['aberrations'] and output=='No prediction')):
        raise ValueError('MANE Select predicted splicing consequences are unavailable. Capture again.')


# The site's "main" button also admits MANE Plus Clinical/canonical fallbacks.
# Restrict native rows to explicit MS annotations without changing source scores.
# Continuation rows inherit the transcript of their rowspan cell.
_SPLICEAI_MANE_PANELS_JS="""() => {
    document.querySelector('#main-transcript-button')?.click();
    // A minimized managed window can ignore --window-size. Give the native
    // panels enough layout width to keep transcript names and outputs readable.
    const results=document.querySelector('#response-box');
    if(results)results.style.minWidth='2600px';
    const panel=(id,response,rowClass)=>{
        const table=document.getElementById(id),transcripts=[];
        const ids=new Set((response?.scores||[]).filter(s=>s.t_priority==='MS').map(s=>s.t_id));
        let transcript=null;
        for(const row of table?.querySelectorAll(rowClass)||[]){
            const link=row.querySelector('a[href*="/Transcript/Summary?"]');
            if(link)transcript=link.textContent.trim();
            row.style.display=ids.has(transcript)?'':'none';
            if(row.getBoundingClientRect().height>0)transcripts.push(transcript);
        }
        return {visible:!!table?.getBoundingClientRect().height,transcripts};
    };
    const spliceai=panel('spliceai-table',lastSpliceaiResponseJson,'.spliceai-result-row');
    const pangolin=panel('pangolin-table',lastPangolinResponseJson,'.pangolin-result-row');
    const table=document.getElementById('sai10k-table');
    const rows=[...(table?.querySelectorAll('tr')||[])].filter(r=>r.querySelector('td') && r.getBoundingClientRect().height>0);
    const consequences={visible:!!table?.getBoundingClientRect().height,
        transcripts:rows.map(r=>r.querySelector('a[href*="/Transcript/Summary?"]')?.textContent.trim()),
        method:rows[0]?.cells[1]?.innerText.trim().split(/\\s+/)[0]||'',output:rows[0]?.cells[2]?.innerText.trim()||''};
    const boxes=['spliceai-table','pangolin-table','sai10k-table'].map(id=>document.getElementById(id)?.getBoundingClientRect());
    const clip=boxes.every(b=>b?.width>0 && b?.height>0)?{
        x:Math.min(...boxes.map(b=>b.left)),y:boxes[0].top,
        width:Math.max(...boxes.map(b=>b.right))-Math.min(...boxes.map(b=>b.left)),
        height:boxes[2].bottom-boxes[0].top}:null;
    return {input:document.querySelector('#search-box')?.value,
        hg:document.querySelector('input[name="hg"]:checked')?.value,
        bc:document.querySelector('input[name="gencode-gene-set"]:checked')?.value,
        distance:document.querySelector('#max-distance-input')?.value,
        mask:document.querySelector('input[name="mask"]')?.checked,
        ref_alt:document.querySelector('input[name="show-ref-alt"]')?.checked,
        panels:{spliceai,pangolin,consequences},clip};
}"""


def capture_spliceai(data:dict,directory:Path,*,background=True,checkpoint=lambda:None,progress=lambda text:None)->dict:
    """Capture native MANE Select SpliceAI, Pangolin and splicing consequences."""
    url=spliceai_url(data);directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    stem=hashlib.sha256(data['query'].encode()).hexdigest()[:16]
    progress('SpliceAI: capturing MANE Select, Pangolin and splicing consequences')
    with sync_edge_cdp() as runtime:
        context=runtime.chromium.launch_persistent_context(str(Path.home()/'.solide'/'browser_profiles'/'SpliceAI'),
            background=background,viewport={'width':1600,'height':1000})
        page=context.pages[0] if context.pages else context.new_page();checkpoint();page.goto(url)
        deadline=time.monotonic()+180;state={}
        while time.monotonic()<deadline:
            checkpoint()
            state=page.evaluate("""() => ({input:document.querySelector('#search-box')?.value,
                response:typeof lastSpliceaiResponseJson==='undefined'?null:lastSpliceaiResponseJson,
                pangolin:typeof lastPangolinResponseJson==='undefined'?null:lastPangolinResponseJson,
                rows:document.querySelectorAll('#spliceai-table .spliceai-result-row').length,
                visible:!!document.querySelector('#spliceai-table')?.getBoundingClientRect().height})""")
            if state.get('response') and state.get('rows') and state.get('visible'):break
            time.sleep(.25)
        if state.get('input')!=data['query'] or not state.get('response'):
            raise ValueError('SpliceAI page did not finish the requested variant; screenshot unavailable.')
        validate_spliceai_capture(data,state['response'])
        validate_pangolin_capture(data,state.get('pangolin'))
        captured_data={**data,'response':state['response'],'pangolin_response':state['pangolin']}
        visible=page.evaluate(_SPLICEAI_MANE_PANELS_JS)
        validate_spliceai_dom(captured_data,visible)
        specs=[]
        form=page.locator('#search-box').evaluate("""el => {
            const form=el.closest('.ui.form');if(!form)return null;
            const box=form.getBoundingClientRect();
            const right=Math.max(box.right,...[...form.querySelectorAll('label,input,button,.ui.checkbox')]
                .map(child=>child.getBoundingClientRect().right));
            return {x:box.x,y:box.y,width:right-box.x+8,height:box.height};
        }""")
        if not form or form.get('width',0)<=0 or form.get('height',0)<=0:
            raise ValueError('SpliceAI query/settings panel is unavailable. Capture again.')
        path=directory/f'{stem}-spliceai-query.png';page.screenshot(path=str(path),clip=form)
        specs.append({'path':str(path),'label':'SpliceAI query · hg19 · ±500 bp · masked · REF/ALT'})
        clip=visible.get('clip')
        if not clip or clip['width']<=0 or clip['height']<=0:
            raise ValueError('SpliceAI/Pangolin/consequences screenshot geometry is unavailable.')
        path=directory/f'{stem}-spliceai-scores.png';page.screenshot(path=str(path),clip=clip)
        specs.append({'path':str(path),'label':'SpliceAI, Pangolin and predicted splicing consequences · MANE Select'})
        for record in specs:
            if not validate_capture(Path(record['path'])).valid:
                raise ValueError('SpliceAI screenshot is unreadable; capture again.')
        metadata={'url':url,'captured_at':datetime.now(timezone.utc).isoformat(),
                  'query':data['query'],'settings':{'hg':37,'distance':500,'mask':1,'bc':'basic','ref_alt':True},
                  'score_identity_confirmed':True,'dom_identity_confirmed':True,'transcripts':len(state['response']['scores']),
                  'capture_version':2,'mane_transcripts':_mane_ids(state['response']),
                  'panels':visible['panels'],'pangolin_response':state['pangolin'],
                  'splicing_predictions':state['response']['sai10kPredictions'],
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
