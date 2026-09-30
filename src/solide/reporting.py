from __future__ import annotations
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.drawing.image import Image
from openpyxl.utils import get_column_letter
from .models import Session
from .quality import qc_flags, review_reasons
from .evidence import evidence_is_current, assess_evidence
from . import __version__

STATUS = {'found':'Found', 'verified':'Verified', 'not_found':'Not found',
          'not_applicable':'Not applicable', 'needs_review':'Review required',
          'error':'Error', 'timeout':'Timeout', 'identity_mismatch':'Identity mismatch',
          'partial_capture':'Partial capture', 'manual_required':'Manual search',
          'login_required':'Sign-in required','verification_required':'Review required',
          'authentication_failed':'Sign-in failed','network_error':'Network error','ambiguous_result':'Ambiguous match'}


def safe_text(value):
    if isinstance(value, str):
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
        if value.startswith(('=', '+', '-', '@')):
            value = "'" + value
        return value[:32767]
    return value


def add_row(sheet, values):
    sheet.append([safe_text(v) for v in values])


def style_table(sheet, header_row=1):
    sheet.freeze_panes=f'A{header_row+1}'
    sheet.auto_filter.ref=f'A{header_row}:{get_column_letter(sheet.max_column)}{sheet.max_row}'
    for cell in sheet[header_row]:
        cell.fill=PatternFill('solid',fgColor='425B3D')
        cell.font=Font(name='Calibri',color='FFFFFF',bold=True,size=11)
        cell.alignment=Alignment(wrap_text=True,vertical='center')
    sheet.row_dimensions[header_row].height=30
    for row in sheet.iter_rows(min_row=header_row+1):
        for cell in row:
            cell.font=Font(name='Calibri',size=11,color='1F2A22')
            cell.alignment=Alignment(vertical='top',wrap_text=True)
            if cell.row % 2 == 0:
                cell.fill=PatternFill('solid',fgColor='F4F6F2')
    for column in range(1,sheet.max_column+1):
        width=max((len(str(sheet.cell(row,column).value or '')) for row in range(header_row,min(sheet.max_row,header_row+30)+1)), default=15)
        sheet.column_dimensions[get_column_letter(column)].width=min(60,max(16,width+2))
    sheet.sheet_view.showGridLines=False
    sheet.print_options.horizontalCentered=True
    sheet.sheet_properties.pageSetUpPr.fitToPage=True
    sheet.page_setup.orientation='landscape'
    sheet.page_setup.paperSize=sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth=1
    sheet.page_setup.fitToHeight=0
    sheet.print_title_rows=f'{header_row}:{header_row}'


def export_patient(session: Session, patient: str, directory: Path) -> Path:
    variants=[v for v in session.variants if v.patient==patient]
    if not variants:
        raise ValueError('No rows for this patient.')
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    stem=re.sub(r'[^\w.-]', '_', patient).strip('.')[:80] or 'patient'
    # Hash prevents distinct patient labels collapsing to the same sanitized filename.
    path=directory/f'{stem}_{hashlib.sha256(patient.encode()).hexdigest()[:6]}_Solide.xlsx'
    w=Workbook()
    overview=w.active; overview.title='Overview'
    add_row(overview,['SOLIDE – variant review',patient,'Tissue',session.tissue(patient)])
    add_row(overview,['Generated',datetime.now().astimezone().isoformat(),'App version',__version__])
    assemblies=sorted({v.assembly for v in variants})
    add_row(overview,['Coverage applies to exported rows. Assembly: '+', '.join(assemblies)+
                      ('. Review: mixed or unknown assembly.' if len(assemblies)>1 or 'Unknown' in assemblies else '')])
    add_row(overview,['Gene','Transcript','Original HGVS','Reviewed HGVS','Protein','AF (%)','Coverage','Type','Call','Locus','Review status','Comment','Source findings','Assembly','Reviewed genomic variant'])
    for v in variants:
        if not v.selected:
            continue
        summaries=[]
        for source,e in v.evidence.items():
            current=evidence_is_current(v,e,session.tissue(patient),session)
            label=assess_evidence(v,e,session).label
            summaries.append(f'{source}: {label} – {e.get("summary", "")}')
        add_row(overview,[v.gene,v.transcript,v.coding,v.corrected_hgvs,v.protein,v.af_percent,
            v.coverage,v.kind,v.call,v.locus,
            'HGVS reviewed' if v.nomenclature_verified else ', '.join(review_reasons(v)),
            v.comment,'\n'.join(summaries) or 'No database searches run',v.assembly,v.controlled_genomic])
    style_table(overview,4)
    overview.column_dimensions['M'].width=75
    overview.column_dimensions['L'].width=50
    for row in range(5,overview.max_row+1):
        overview.cell(row,6).number_format='0.00" %"'
        overview.row_dimensions[row].height=max(45,min(150,18*(str(overview.cell(row,13).value).count('\n')+2)))
    qc=w.create_sheet('Quality')
    add_row(qc,['Gene','Category','Status','Reason','Coverage','Copy Number','Type','Call','Source row','Source file'])
    for v in variants:
        for f in qc_flags(v):
            add_row(qc,[v.gene,f.category,f.status,f.message,v.coverage,v.copy_number,v.kind,v.call,v.source_row,Path(v.source_file).name])
    style_table(qc)
    qc.column_dimensions['D'].width=65
    raw=w.create_sheet('Raw data')
    keys=sorted({k for v in variants for k in v.raw})
    add_row(raw,['Row ID','Selected','Source row','Source file','Assembly',*keys])
    for v in variants:
        add_row(raw,[v.id,v.selected,v.source_row,Path(v.source_file).name,v.assembly,*[v.raw.get(k) for k in keys]])
    style_table(raw)
    audit=w.create_sheet('Searches')
    add_row(audit,['Row ID','Gene','Source','Status','Captured at','Tissue','URL','Summary','JSON result','Match assessment'])
    used_names=set(w.sheetnames)
    full_reports=set()
    for v in variants:
        if not v.selected:
            continue
        name=re.sub(r'[\\/*?:\[\]]','_',v.gene or 'Variant')[:25]
        suffix=1; candidate=name
        while candidate in used_names:
            suffix+=1;candidate=f'{name}_{suffix}'
        used_names.add(candidate)
        detail=w.create_sheet(candidate)
        add_row(detail,[v.gene,v.corrected_hgvs or v.coding,v.protein])
        add_row(detail,['Comment',v.comment])
        detail.column_dimensions['A'].width=28
        detail.column_dimensions['B'].width=90
        cursor=4
        for source,e in v.evidence.items():
            current=evidence_is_current(v,e,session.tissue(patient),session)
            state=e.get('status','Unknown') if current else 'Outdated'
            assessment=assess_evidence(v,e,session)
            add_row(audit,[v.id,v.gene,source,state,e.get('captured_at'),e.get('tissue'),e.get('url'),e.get('summary'),json.dumps(e.get('raw',{}),ensure_ascii=False,default=str),assessment.label])
            detail.cell(cursor,1,safe_text(source));detail.cell(cursor,2,safe_text(state));cursor+=1
            detail.cell(cursor,1,'Match assessment');detail.cell(cursor,2,safe_text(assessment.label));cursor+=1
            detail.cell(cursor,2,safe_text(e.get('summary',''))).alignment=Alignment(wrap_text=True)
            detail.row_dimensions[cursor].height=60;cursor+=1
            url=e.get('url','')
            if url.startswith(('https://','http://')):
                cell=detail.cell(cursor,2,url);cell.hyperlink=url;cell.style='Hyperlink';cursor+=1
            data=e.get('raw',{})
            images=data.get('screenshots',[])
            if data.get('screenshot') and not images:
                images=[{'path':data['screenshot'],'label':source}]
            for image_info in images:
                image_path=Path(image_info.get('path',''))
                if not current:
                    continue
                if not image_path.is_file():
                    detail.cell(cursor,2,'Screenshot missing: capture again');cursor+=1
                    continue
                try:
                    image=Image(str(image_path))
                    scale=min(1,1000/image.width)
                    image.width*=scale;image.height*=scale
                    detail.cell(cursor,1,safe_text(image_info.get('label',source)));cursor+=1
                    detail.add_image(image,f'A{cursor}')
                    cursor+=int(image.height/20)+2
                except (OSError,ValueError):
                    detail.cell(cursor,2,'Screenshot could not be read.');cursor+=1
            full=data.get('patient_report_screenshot')
            if full and current and full not in full_reports:
                full_reports.add(full)
                attachment=w.create_sheet(f'MTBP attachment {len(full_reports)}')
                attachment.cell(1,1,'MTBP – full report')
                attachment.cell(2,1,safe_text(e.get('captured_at','')))
                if Path(full).is_file():
                    try:
                        image=Image(full);scale=min(1,1000/image.width)
                        image.width*=scale;image.height*=scale;attachment.add_image(image,'A4')
                    except (OSError,ValueError):attachment.cell(4,1,'Full report could not be read.')
                else:attachment.cell(4,1,'Full report missing. Capture again.')
        detail.sheet_view.showGridLines=False
        detail.freeze_panes='B4'
    style_table(audit)
    fd,tmp=tempfile.mkstemp(dir=directory,prefix='.solide-',suffix='.xlsx')
    os.close(fd)
    try:
        w.save(tmp)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
        w.close()
    return path
