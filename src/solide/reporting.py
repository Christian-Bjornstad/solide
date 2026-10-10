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
from openpyxl.styles import Font,Alignment,PatternFill
from .models import Session
from .quality import qc_flags,review_reasons
from .evidence import evidence_is_current,assess_evidence,valid_capture
from .report_layout import safe_text,add_row,original_row,style_table,title,status_cell,internal_link,put_image,GREEN,INK,PALE
from . import __version__

STATUS={'found':'Found','verified':'Verified','not_found':'Not found','not_applicable':'Not applicable',
    'needs_review':'Review required','error':'Error','timeout':'Timeout','identity_mismatch':'Identity mismatch',
    'partial_capture':'Partial capture','manual_required':'Manual search','login_required':'Sign-in required',
    'verification_required':'Review required','authentication_failed':'Sign-in failed','network_error':'Network error',
    'ambiguous_result':'Ambiguous match','invalid_query':'Review query','unsupported_query':'Review query',
    'submission_unknown':'Submission uncertain','rate_limited':'Rate limited','quota_exhausted':'Quota reached',
    'deferred':'Deferred','unauthorized':'Access required','token_required':'Access required',
    'layout_changed':'Layout changed','ambiguous':'Ambiguous match'}
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


def variant_label(v):
    values=[v.corrected_hgvs or v.coding or v.protein]
    if v.protein and v.protein not in values:values.append(v.protein)
    if v.transcript:values.append(v.transcript)
    return '\n'.join(filter(None,values)) or 'Open variant'


def scope_note(variants):
    scopes={json.dumps(v.raw.get('_export_scope',{}),sort_keys=True) for v in variants
            if v.raw.get('_export_scope',{}).get('filtered_export')}
    notes=[]
    for scope in sorted(scopes):
        data=json.loads(scope);total=data.get('total_variant_count')
        exported=data.get('exported_variant_count')
        count=f'{exported:,} exported / {total:,} total' if total is not None else f'{exported:,} exported'
        notes.append(f'Filtered export: {count}. QC covers supplied rows only.')
    return '\n'.join(notes) or 'QC covers supplied rows only.'


def section_heading(sheet,row,label):
    sheet.merge_cells(start_row=row,start_column=1,end_row=row,end_column=8)
    cell=sheet.cell(row,1,safe_text(label));cell.font=Font(name='Calibri',size=13,bold=True,color='FFFFFF')
    for column in range(1,9):sheet.cell(row,column).fill=PatternFill('solid',fgColor=GREEN)
    cell.alignment=Alignment(vertical='center',wrap_text=True);sheet.row_dimensions[row].height=32
    return row+1


def readable_chunks(text):
    start=0;lines=1;column=0
    for index,char in enumerate(text):
        if char=='\n':lines+=1;column=0
        else:
            column+=1
            if column>100:lines+=1;column=1
        if lines>=20 or index-start>=899:
            yield text[start:index+1];start=index+1;lines=1;column=0
    if start<len(text):yield text[start:]


def service_fields(source,data):
    basis={'full_hgvs':'Full versioned HGVS','genomic_grch37':'GRCh37 genomic alleles',
           'gene_cdna':'Gene / cDNA','gene_protein_or_identifier':'Gene / protein or identifier'}.get(data.get('query_basis'))
    fields=[('Query basis',basis)]
    if source=='Mutalyzer':
        fields.extend([('Requested HGVS',data.get('original')),('Normalized HGVS',data.get('normalization',{}).get('normalized_description')),
            ('Target transcript',data.get('mane_target')),('Mapped HGVS',data.get('mapping',{}).get('mapped_description')),
            ('Mapping limitation',data.get('mapping_issue'))])
    elif source=='SpliceAI':
        fields.extend([('Requested allele',data.get('query')),('Scored allele',data.get('scored_variant')),
            ('Prediction settings',f"GRCh{data['hg']}; distance={data['distance']}; mask={data['mask']}"
                if all(key in data for key in ('hg','distance','mask')) else None)])
    elif source=='BRCA Exchange':
        release=data.get('release') or {}
        classification=data.get('classification');classification=classification if isinstance(classification,dict) else {}
        fields.extend([('Dataset release',json.dumps(release,ensure_ascii=False,default=str)),
            ('Expert evaluated',classification.get('expert_date'))])
    return [(label,value) for label,value in fields if value not in (None,'')]


def evidence_field(sheet,row,label,value):
    """Split long notes into readable rows without discarding their text."""
    text=str(value or '')
    chunks=list(readable_chunks(text)) or ['']
    for index,chunk in enumerate(chunks):
        sheet.cell(row,1,label if index==0 else label+' (continued)').font=Font(name='Calibri',size=11,bold=True,color=INK)
        sheet.cell(row,1).alignment=Alignment(wrap_text=True,vertical='top')
        sheet.merge_cells(start_row=row,start_column=2,end_row=row,end_column=8)
        content=value if isinstance(value,datetime) else safe_text(chunk)
        cell=sheet.cell(row,2,content);cell.font=Font(name='Calibri',size=11,color=INK)
        cell.alignment=Alignment(wrap_text=True,vertical='top')
        lines=max(sum(max(1,(len(line)+99)//100) for line in chunk.split('\n')),
                  (len(str(sheet.cell(row,1).value))+17)//18)
        sheet.row_dimensions[row].height=max(30,min(390,16*lines+10))
        if isinstance(value,datetime):cell.number_format='yyyy-mm-dd hh:mm'
        if label=='Source URL' and text.startswith(('https://','http://')):
            cell.hyperlink=text;cell.style='Hyperlink';cell.alignment=Alignment(wrap_text=True,vertical='top')
        row+=1
    return row


def export_patient(session:Session,patient:str,directory:Path)->Path:
    variants=[v for v in session.variants if v.patient==patient]
    if not variants:raise ValueError('No rows for this patient.')
    selected=[v for v in variants if v.selected]
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    stem=re.sub(r'[^\w.-]','_',patient).strip('.')[:70] or 'patient'
    generated=datetime.now().astimezone();report_id=uuid.uuid4().hex[:8]
    path=directory/f'{stem}_{hashlib.sha256(patient.encode()).hexdigest()[:6]}_Solide_{generated:%Y%m%d_%H%M%S}_{report_id}.xlsx'
    w=Workbook();w.properties.identifier='solide:variant-review-report'
    overview=w.active;overview.title='Overview';title(overview,'SOLIDE',8)
    add_row(overview,['Patient / sample',patient,'MTBP tissue',session.tissue(patient),'Report ID',report_id,'Export scope',scope_note(variants)])
    add_row(overview,['Generated (UTC)',generated.astimezone(timezone.utc).replace(tzinfo=None),'App version',__version__,'Report format',3])
    assemblies=', '.join(sorted({v.assembly for v in variants}))
    add_row(overview,['Assembly',assemblies,'Imported rows',len(variants),'Selected variants',len(selected),'Failed QC rows',
        sum(any(f.status=='Failed' for f in qc_flags(v)) for v in variants)])
    headers=['Gene','Variant','AF (%)','Coverage','Quality','Classification','Report decision','Evidence']
    add_row(overview,headers)
    for v in selected:
        flags=qc_flags(v)
        quality='; '.join(dict.fromkeys(flag.status for flag in flags)) or 'No row flags'
        add_row(overview,[v.gene,variant_label(v),v.af_percent,v.coverage,quality,
            v.classification,v.report_decision,evidence_summary(v,session)])
    style_table(overview,5,'SolideFindings')
    widths={'A':12,'B':35,'C':9,'D':11,'E':14,'F':22,'G':17,'H':24}
    for column,width in widths.items():overview.column_dimensions[column].width=width
    overview.freeze_panes='C6';overview.sheet_view.zoomScale=90
    overview.cell(3,2).number_format='yyyy-mm-dd hh:mm'
    for row,v in enumerate(selected,6):
        overview.cell(row,3).number_format='0.00" %"';overview.cell(row,4).number_format='#,##0'
        lines=max(sum(max(1,(len(line)+int(widths[column])-1)//int(widths[column]))
                      for line in str(overview[f'{column}{row}'].value or '').split('\n')) for column in ('B','F','H'))
        overview.row_dimensions[row].height=max(54,min(120,16*lines+10))
        flags=qc_flags(v)
        status_cell(overview.cell(row,7),v.report_decision)
        status_cell(overview.cell(row,5),'Failed' if any(f.status=='Failed' for f in flags) else overview.cell(row,5).value)
        status_cell(overview.cell(row,8),str(overview.cell(row,8).value).split('\n')[0])
    for row in (2,3,4):
        overview.row_dimensions[row].height=60 if row==2 else 34
        for cell in overview[row]:cell.font=Font(name='Calibri',size=11,color=INK);cell.alignment=Alignment(wrap_text=True,vertical='center')
    overview.print_area=f'A1:H{overview.max_row}'

    qc=w.create_sheet('Quality')
    raw_rows={v.id:index for index,v in enumerate(variants,2)}
    add_row(qc,['Gene','Variant','Category','Status','Value','Reason','Source row','Source file','Row ID'])
    for v in variants:
        for flag in qc_flags(v):
            value=v.coverage if flag.category=='Coverage' else v.copy_number if flag.category.startswith('CNV') else v.call
            add_row(qc,[v.gene,v.corrected_hgvs or v.coding or v.protein,flag.category,flag.status,value,flag.message,v.source_row,Path(v.source_file).name,v.id])
            internal_link(qc.cell(qc.max_row,7),'Raw data',raw_rows[v.id],label=str(v.source_row))
    style_table(qc,name='SolideQuality')
    for letter,width in {'A':12,'B':32,'C':24,'D':14,'E':14,'F':48,'G':12}.items():qc.column_dimensions[letter].width=width
    for letter in ('H','I'):qc.column_dimensions[letter].hidden=True
    for row in range(2,qc.max_row+1):
        status_cell(qc.cell(row,4),qc.cell(row,4).value);qc.row_dimensions[row].height=54
    qc.print_area=f'A1:G{qc.max_row}'

    detail=w.create_sheet('Evidence');title(detail,'EVIDENCE',8)
    add_row(detail,['Patient / sample',patient,'Assembly',assemblies])
    detail.cell(3,1,'App assessments and source assertions are recorded separately.');detail.merge_cells('A3:H3')
    internal_link(detail.cell(4,1),'Overview',label='Back to findings')
    add_row(detail,['Gene','Variant','Classification','Report decision','Reviewer','Reviewed at (UTC)','Quality','Evidence'])
    for v in selected:add_row(detail,[v.gene,v.corrected_hgvs or v.coding or v.protein,v.classification,v.report_decision,
        v.reviewer,captured_time(v.reviewed_at),'; '.join(f.status for f in qc_flags(v)) or 'No row flags','Open evidence'])
    style_table(detail,5,'SolideEvidenceIndex')
    for column in 'ABCDEFGH':detail.column_dimensions[column].width=18
    detail.freeze_panes='A6';detail.sheet_view.zoomScale=90
    for row in range(6,detail.max_row+1):
        detail.row_dimensions[row].height=48;detail.cell(row,6).number_format='yyyy-mm-dd hh:mm'
    cursor=detail.max_row+3;anchors={};source_anchors={};full_reports={};full_links=[]
    for index,v in enumerate(selected,6):
        anchors[v.id]=cursor
        internal_link(overview.cell(index,2),'Evidence',cursor,label=variant_label(v))
        internal_link(overview.cell(index,8),'Evidence',cursor,label=evidence_summary(v,session))
        internal_link(detail.cell(index,2),'Evidence',cursor,label=v.corrected_hgvs or v.coding or v.protein or 'Open variant')
        internal_link(detail.cell(index,8),'Evidence',cursor)
        cursor=section_heading(detail,cursor,f'{v.gene}  {v.corrected_hgvs or v.coding or v.protein}')
        internal_link(detail.cell(cursor,1),'Overview',index,label='Back to finding')
        internal_link(detail.cell(cursor,3),'Evidence',5,label='Evidence index');cursor+=1
        fields=[('Original HGVS',':'.join(filter(None,[v.transcript,v.coding]))),('Protein',v.protein),
            ('Reviewed HGVS',v.corrected_hgvs),('Genomic identity',' | '.join(filter(None,[v.assembly,v.locus,v.ref,v.alt]))),
            ('Reviewed allele',v.controlled_genomic),('Identity review','Approved' if v.nomenclature_verified else 'Not approved'),
            ('Type / call',' / '.join(filter(None,[v.kind,v.call]))),('AF / coverage',f'{v.af_percent if v.af_percent is not None else "Unknown"}% / {v.coverage if v.coverage is not None else "Unknown"}'),
            ('Imported variant ID',v.variant_id or original_value(v,'Variant ID')),('Imported ClinVar',original_value(v,'ClinVar')),
            ('Classification',v.classification),('Report decision',v.report_decision),('Reviewer',v.reviewer),
            ('Reviewed at (UTC)',captured_time(v.reviewed_at)),('Assessment',v.comment),
            ('Required checks',', '.join(review_reasons(v))),('Quality', '\n'.join(f'{f.category}: {f.status} — {f.message}' for f in qc_flags(v)) or 'No row flags'),
            ('Source provenance',f'{Path(v.source_file).name} | sheet {v.raw.get("_sheet", "")} | row {v.source_row}'),
            ('Source SHA256',v.source_hash),('Row ID',v.id)]
        for label,value in fields:
            if value not in (None,''):cursor=evidence_field(detail,cursor,label,value)
        internal_link(detail.cell(cursor,1),'Raw data',raw_rows[v.id],label='Open original row');cursor+=2
        if not v.evidence:cursor=evidence_field(detail,cursor,'Search status','Not run')
        for source,e in ordered_evidence(v):
            source_anchors[v.id,source]=cursor
            assessment=assess_evidence(v,e,session);current=evidence_is_current(v,e,session.tissue(patient),session)
            cursor=section_heading(detail,cursor,source)
            cursor=evidence_field(detail,cursor,'Match assessment',assessment.label)
            status_cell(detail.cell(cursor-1,2),assessment.label)
            for label,value in [('Source result',STATUS.get(e.get('status'),e.get('status','Unknown'))),
                ('Source classification',source_classification(e)),('Accession',e.get('accession','')),
                ('Captured at (UTC)',captured_time(e.get('captured_at',''))),('Source URL',e.get('url','')),('Summary',e.get('summary',''))]:
                if value not in (None,''):cursor=evidence_field(detail,cursor,label,value)
            data=e.get('raw',{});images=data.get('screenshots',[]) or ([{'path':data['screenshot'],'label':source}] if data.get('screenshot') else [])
            for label,value in service_fields(source,data):cursor=evidence_field(detail,cursor,label,value)
            if not current:
                cursor=evidence_field(detail,cursor,'Freshness','Outdated evidence: rerun before reporting.');cursor+=2;continue
            for info in images:
                image_path=info.get('path','')
                if valid_capture(image_path):cursor=put_image(detail,image_path,cursor,info.get('label',source))
                else:cursor=evidence_field(detail,cursor,'Capture','Screenshot missing or unreadable: capture again.')
            full=data.get('patient_report_screenshot')
            if full:
                full_reports.setdefault(full,e);full_links.append((cursor,full))
                detail.cell(cursor,1,'Open full MTBP report');cursor+=2
            cursor+=2
        cursor+=2
    full_anchors={}
    for number,(full,e) in enumerate(full_reports.items(),1):
        full_anchors[full]=cursor;cursor=section_heading(detail,cursor,f'MTBP full report {number}')
        internal_link(detail.cell(cursor,1),'Evidence',5,label='Evidence index');cursor+=1
        cursor=evidence_field(detail,cursor,'Captured at (UTC)',captured_time(e.get('captured_at','')))
        if valid_capture(full):cursor=put_image(detail,full,cursor,'MTBP full report')
        else:cursor=evidence_field(detail,cursor,'Capture','Full report screenshot missing or unreadable. Capture again.')
        cursor+=2
    for row,full in full_links:internal_link(detail.cell(row,1),'Evidence',full_anchors[full],label='Open full MTBP report')
    detail.print_area=f'A1:H{max(detail.max_row,cursor-1)}'

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
            internal_link(searches.cell(row,12),'Evidence',source_anchors[v.id,source])
    style_table(searches,name='SolideSearches')
    for letter,width in {'B':28,'E':24,'F':40,'J':55,'K':70,'L':20}.items():searches.column_dimensions[letter].width=width
    searches.column_dimensions['N'].hidden=True;searches.sheet_state='hidden'
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

    fd,tmp=tempfile.mkstemp(dir=directory,prefix='.solide-',suffix='.xlsx');os.close(fd)
    try:w.save(tmp);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
        w.close()
    return path
