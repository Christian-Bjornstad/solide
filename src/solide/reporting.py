"""Versioned Excel reports produced from the app's reviewed session."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
from openpyxl import Workbook
from openpyxl.styles import Font,Alignment
from .models import Session
from .quality import qc_flags,review_reasons
from .evidence import evidence_is_current,assess_evidence,valid_capture
from .report_layout import safe_text,add_row,original_row,style_table,title,status_cell,internal_link,put_image,GREEN
from . import __version__

STATUS={'found':'Found','verified':'Verified','not_found':'Not found','not_applicable':'Not applicable',
    'needs_review':'Review required','error':'Error','timeout':'Timeout','identity_mismatch':'Identity mismatch',
    'partial_capture':'Partial capture','manual_required':'Manual search','login_required':'Sign-in required',
    'verification_required':'Review required','authentication_failed':'Sign-in failed','network_error':'Network error',
    'ambiguous_result':'Ambiguous match'}
SOURCE_ORDER=('MTBP','Franklin','ClinVar','OncoKB','COSMIC','BRCA Exchange','Mutalyzer','SpliceAI')


def source_classification(evidence):
    raw=evidence.get('raw',{})
    value=evidence.get('clinical_significance') or raw.get('expert_classification') or raw.get('classification') or ''
    if isinstance(value,dict):return value.get('expert','')
    return str(value)


def captured_time(value):
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError,AttributeError):return None


def ordered_evidence(variant):
    order={name:index for index,name in enumerate(SOURCE_ORDER)}
    return sorted(variant.evidence.items(),key=lambda pair:order.get(pair[0],99))


def original_value(v,*keys):
    return next((v.raw[key] for key in keys if v.raw.get(key) not in (None,'')),'')


def raw_values(v):
    columns=v.raw.get('_columns',[]);values=v.raw.get('_values',[])
    if not columns:return {key:value for key,value in v.raw.items() if not key.startswith('_')}
    result={};reserved={str(name).casefold() for name in columns if name}
    for index,name in enumerate(columns):
        label=str(name) if name else f'Unnamed column {index+1}'
        base=label;number=1
        while label.casefold() in {key.casefold() for key in result} or (not name and label.casefold() in reserved):
            number+=1;label=f'{base} ({number})'
        result[label]=values[index] if index<len(values) else None
    return result


def evidence_summary(v,session):
    assessments=[assess_evidence(v,e,session) for _,e in ordered_evidence(v)]
    if not assessments:return 'Not run'
    labels=[a.label for a in assessments]
    verified=labels.count('Verified match');matches=labels.count('Review match')
    if 'Identity mismatch' in labels:state='Identity mismatch'
    elif 'Outdated' in labels:state='Outdated'
    elif any(a.retryable for a in assessments):state='Retry / review needed'
    elif any(label=='Review required' for label in labels):state='Review required'
    elif verified:state='Verified match'
    elif matches:state='Review match'
    elif 'No match' in labels:state='No match'
    else:state='Not applicable'
    counts=[]
    if verified:counts.append(f'{verified} verified')
    if matches:counts.append(f'{matches} review match')
    return state+('\n'+', '.join(counts) if counts else '')


def detail_sheet(workbook,v,index):
    name=re.sub(r'[\\/*?:\[\]]','_',f'V{index:02}_{v.gene or "Variant"}')[:31]
    detail=workbook.create_sheet(name);title(detail,f'{v.gene}  {v.corrected_hgvs or v.coding or v.protein}',8)
    for column in 'ABCDEFGH':detail.column_dimensions[column].width=18
    add_row(detail,['Patient',v.patient,'Assembly',v.assembly])
    add_row(detail,['Classification',v.classification,'Decision',v.report_decision,'Reviewer',v.reviewer])
    add_row(detail,['Assessment',v.comment]);detail.merge_cells('B4:H4');detail.row_dimensions[4].height=max(60,min(240,18*(len(v.comment)//100+2)))
    detail.cell(4,1).alignment=Alignment(vertical='top')
    detail.cell(4,2).alignment=Alignment(wrap_text=True,vertical='top')
    internal_link(detail.cell(5,1),'Overview',label='Back to findings')
    detail.freeze_panes='A6';return detail,7


def export_patient(session:Session,patient:str,directory:Path)->Path:
    variants=[v for v in session.variants if v.patient==patient]
    if not variants:raise ValueError('No rows for this patient.')
    selected=[v for v in variants if v.selected]
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    stem=re.sub(r'[^\w.-]','_',patient).strip('.')[:70] or 'patient'
    generated=datetime.now().astimezone();report_id=uuid.uuid4().hex[:8]
    path=directory/f'{stem}_{hashlib.sha256(patient.encode()).hexdigest()[:6]}_Solide_{generated:%Y%m%d_%H%M%S}_{report_id}.xlsx'
    w=Workbook();overview=w.active;overview.title='Overview';title(overview,'SOLIDE',10)
    add_row(overview,['Patient / sample',patient,'MTBP tissue',session.tissue(patient),'Report ID',report_id])
    add_row(overview,['Generated (UTC)',generated.astimezone(timezone.utc).replace(tzinfo=None),'App version',__version__,'Report format',2])
    assemblies=', '.join(sorted({v.assembly for v in variants}))
    add_row(overview,['Assembly',assemblies,'Imported rows',len(variants),'Selected variants',len(selected),'Failed QC rows',
        sum(any(f.status=='Failed' for f in qc_flags(v)) for v in variants)])
    headers=['Gene','Variant','Protein','AF (%)','Coverage','Quality',
        'Classification','Report decision','Evidence','Reviewer']
    add_row(overview,headers)
    detail_names={v.id:re.sub(r'[\\/*?:\[\]]','_',f'V{i:02}_{v.gene or "Variant"}')[:31]
        for i,v in enumerate(selected,1)}
    for v in selected:
        flags=qc_flags(v)
        quality='; '.join(dict.fromkeys(flag.status for flag in flags)) or 'No row flags'
        add_row(overview,[v.gene,v.corrected_hgvs or v.coding or v.protein,v.protein,
            v.af_percent,v.coverage,quality,v.classification,v.report_decision,
            evidence_summary(v,session),v.reviewer])
        row=overview.max_row
        internal_link(overview.cell(row,2),detail_names[v.id],label=overview.cell(row,2).value or 'Open variant')
        status_cell(overview.cell(row,8),v.report_decision)
        status_cell(overview.cell(row,6),'Failed' if any(f.status=='Failed' for f in flags) else quality)
    style_table(overview,5,'SolideFindings')
    widths={'A':12,'B':28,'C':22,'D':10,'E':12,'F':14,'G':22,'H':17,'I':24,'J':20}
    for column,width in widths.items():overview.column_dimensions[column].width=width
    overview.freeze_panes='C6';overview.sheet_view.zoomScale=90
    overview.cell(3,2).number_format='yyyy-mm-dd hh:mm'
    for row in range(6,overview.max_row+1):
        overview.cell(row,4).number_format='0.00" %"';overview.cell(row,5).number_format='#,##0'
        lines=max(str(overview.cell(row,c).value or '').count('\n')+1 for c in (2,9))
        overview.row_dimensions[row].height=max(44,min(72,18*lines+12))
    overview.print_area=f'A1:J{overview.max_row}'

    qc=w.create_sheet('Quality')
    add_row(qc,['Gene','Category','Status','Reason','Coverage','Copy Number','Type','Call','Source row','Source file','Row ID'])
    for v in variants:
        for flag in qc_flags(v):
            add_row(qc,[v.gene,flag.category,flag.status,flag.message,v.coverage,v.copy_number,v.kind,v.call,v.source_row,Path(v.source_file).name,v.id])
    style_table(qc,name='SolideQuality');qc.column_dimensions['D'].width=65
    for row in range(2,qc.max_row+1):status_cell(qc.cell(row,3),qc.cell(row,3).value)

    searches=w.create_sheet('Searches')
    add_row(searches,['Gene','Variant','Source','Result','Match assessment','Classification from source','Accession',
        'Captured at (UTC)','Tissue','Source URL','Summary','Evidence','Row ID','JSON response'])
    for v in selected:
        for source,e in ordered_evidence(v):
            assessment=assess_evidence(v,e,session)
            add_row(searches,[v.gene,v.corrected_hgvs or v.coding or v.protein,source,STATUS.get(e.get('status'),e.get('status','Unknown')),
                assessment.label,source_classification(e),e.get('accession',''),captured_time(e.get('captured_at','')),
                e.get('tissue',''),e.get('url',''),e.get('summary',''),'Open evidence',v.id,
                json.dumps(e.get('raw',{}),ensure_ascii=False,default=str)])
            row=searches.max_row;searches.cell(row,8).number_format='yyyy-mm-dd hh:mm'
            url=e.get('url','')
            if isinstance(url,str) and url.startswith(('https://','http://')):searches.cell(row,10).hyperlink=url
            if v.id in detail_names:internal_link(searches.cell(row,12),detail_names[v.id])
    style_table(searches,name='SolideSearches')
    for letter,width in {'B':28,'E':24,'F':40,'J':55,'K':70,'L':20}.items():searches.column_dimensions[letter].width=width
    searches.column_dimensions['N'].hidden=True
    for row in range(2,searches.max_row+1):
        status_cell(searches.cell(row,5),searches.cell(row,5).value)
        searches.row_dimensions[row].height=max(48,min(180,18*(str(searches.cell(row,11).value or '').count('\n')+2)))

    raw=w.create_sheet('Raw data')
    # Preserve A–L and every subsequent exported column in source order.
    originals=[raw_values(v) for v in variants]
    keys=list(dict.fromkeys(key for original in originals for key in original))
    technical=['Solide Row ID','Selected','Source row','Source file','Source sheet','Source SHA256','Assembly']
    occupied={key.casefold() for key in keys}
    for index,name in enumerate(technical):
        while name.casefold() in occupied:name+=' (provenance)'
        technical[index]=name;occupied.add(name.casefold())
    add_row(raw,[*keys,*technical])
    for v,original in zip(variants,originals):original_row(raw,[*[original.get(k) for k in keys],v.id,v.selected,v.source_row,Path(v.source_file).name,v.raw.get('_sheet',''),v.source_hash,v.assembly])
    style_table(raw,name='SolideRawData');raw.freeze_panes='C2'

    full_reports={}
    for index,v in enumerate(selected,1):
        detail,cursor=detail_sheet(w,v,index)
        for source,e in ordered_evidence(v):
            assessment=assess_evidence(v,e,session);current=evidence_is_current(v,e,session.tissue(patient),session)
            detail.cell(cursor,1,safe_text(source)).font=Font(bold=True,size=15,color=GREEN)
            detail.cell(cursor,3,safe_text(assessment.label));status_cell(detail.cell(cursor,3),assessment.label);cursor+=1
            for label,value in [('Source classification',source_classification(e)),('Captured at (UTC)',captured_time(e.get('captured_at',''))),
                ('Source URL',e.get('url','')),('Summary',e.get('summary',''))]:
                label_cell=detail.cell(cursor,1,label);label_cell.alignment=Alignment(vertical='top',wrap_text=True)
                cell=detail.cell(cursor,2,safe_text(value));cell.alignment=Alignment(horizontal='left',wrap_text=True,vertical='top')
                detail.merge_cells(start_row=cursor,start_column=2,end_row=cursor,end_column=8)
                if label=='Source URL' and isinstance(value,str) and value.startswith(('https://','http://')):cell.hyperlink=value;cell.style='Hyperlink'
                if label=='Captured at (UTC)':cell.number_format='yyyy-mm-dd hh:mm'
                if label=='Summary':detail.row_dimensions[cursor].height=max(48,min(240,18*(str(value).count('\n')+len(str(value))//100+2)))
                cursor+=1
            data=e.get('raw',{});images=data.get('screenshots',[]) or ([{'path':data['screenshot'],'label':source}] if data.get('screenshot') else [])
            if not current:
                detail.cell(cursor,1,'Outdated evidence: rerun before reporting.');cursor+=2;continue
            for info in images:
                image_path=info.get('path','')
                if valid_capture(image_path):cursor=put_image(detail,image_path,cursor,info.get('label',source))
                else:detail.cell(cursor,1,'Screenshot missing or unreadable: capture again.');cursor+=2
            full=data.get('patient_report_screenshot')
            if full:
                if full not in full_reports:
                    full_reports[full]=f'MTBP attachment {len(full_reports)+1}'
                    attachment=w.create_sheet(full_reports[full]);title(attachment,'MTBP full report',8)
                    for column in 'ABCDEFGH':attachment.column_dimensions[column].width=18
                    add_row(attachment,['Patient',patient,'Captured at (UTC)',captured_time(e.get('captured_at',''))])
                    internal_link(attachment.cell(3,1),'Overview',label='Back to findings')
                    if valid_capture(full):put_image(attachment,full,5,'MTBP full report')
                    else:attachment.cell(5,1,'Full report screenshot missing or unreadable. Capture again.')
                internal_link(detail.cell(cursor,1),full_reports[full],label='Open full MTBP report');cursor+=2
            cursor+=2

    fd,tmp=tempfile.mkstemp(dir=directory,prefix='.solide-',suffix='.xlsx');os.close(fd)
    try:w.save(tmp);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
        w.close()
    return path
