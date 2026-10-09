"""Formatting and image placement for the generated Excel report."""
from __future__ import annotations
from io import BytesIO
from math import ceil
from pathlib import Path
import re
from PIL import Image as PillowImage
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment,Font,PatternFill
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.utils import get_column_letter

GREEN='425B3D'
INK='243128'
PALE='F2F5EF'
WARN='FFF2D5'
FAIL='FCE5E3'


def safe_text(value):
    if isinstance(value,str):
        value=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',value)
        if value.startswith(('=','+','-','@')):value="'"+value
        return value[:32767]
    return value


def add_row(sheet,values):
    sheet.append([safe_text(value) for value in values])


def original_row(sheet,values):
    """Retain source text without allowing Excel to interpret formulas."""
    row=sheet.max_row+1
    for index,value in enumerate(values,1):
        if isinstance(value,str):
            value=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',value)[:32767]
        cell=sheet.cell(row,index,value)
        if isinstance(value,str):
            cell.data_type='s'
            cell.quotePrefix=value.startswith(('=','+','-','@'))


def title(sheet,text,width=8):
    sheet.sheet_view.showGridLines=False
    sheet.sheet_view.zoomScale=90
    sheet.sheet_properties.tabColor=GREEN
    sheet.merge_cells(start_row=1,start_column=1,end_row=1,end_column=width)
    cell=sheet.cell(1,1,safe_text(text));cell.font=Font(name='Calibri',size=22,bold=True,color='FFFFFF')
    cell.fill=PatternFill('solid',fgColor=GREEN);cell.alignment=Alignment(vertical='center')
    sheet.row_dimensions[1].height=40


def style_table(sheet,header_row=1,name=None):
    sheet.freeze_panes=f'C{header_row+1}'
    sheet.sheet_view.showGridLines=False
    sheet.sheet_properties.tabColor=GREEN
    last=get_column_letter(sheet.max_column)
    sheet.auto_filter.ref=f'A{header_row}:{last}{sheet.max_row}'
    for cell in sheet[header_row]:
        cell.fill=PatternFill('solid',fgColor=GREEN)
        cell.font=Font(name='Calibri',size=11,color='FFFFFF',bold=True)
        cell.alignment=Alignment(wrap_text=True,vertical='center')
    sheet.row_dimensions[header_row].height=34
    for row in sheet.iter_rows(min_row=header_row+1):
        sheet.row_dimensions[row[0].row].height=36
        for cell in row:
            cell.font=Font(name='Calibri',size=11,color=INK)
            cell.alignment=Alignment(vertical='top',wrap_text=True)
            if cell.row%2==0:cell.fill=PatternFill('solid',fgColor=PALE)
    for column in range(1,sheet.max_column+1):
        width=max((len(str(sheet.cell(row,column).value or '')) for row in range(header_row,min(sheet.max_row,header_row+25)+1)),default=16)
        sheet.column_dimensions[get_column_letter(column)].width=min(48,max(16,width+2))
    if name and sheet.max_row>header_row:
        table=Table(displayName=name,ref=f'A{header_row}:{last}{sheet.max_row}')
        table.tableStyleInfo=TableStyleInfo(name='TableStyleMedium4',showRowStripes=True)
        sheet.add_table(table)
    sheet.print_title_rows=f'{header_row}:{header_row}'
    sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0
    sheet.sheet_properties.pageSetUpPr.fitToPage=True


def status_cell(cell,status):
    if status in {'Failed','Error','Timeout','Identity mismatch','Missing capture','Sign-in required','Ambiguous match'}:
        cell.fill=PatternFill('solid',fgColor=FAIL)
    elif status in {'Unknown','Review','Review required','Review match','Outdated','Pending'}:
        cell.fill=PatternFill('solid',fgColor=WARN)


def internal_link(cell,sheet,row=1,label='Open evidence'):
    cell.value=safe_text(label)
    cell.hyperlink=f"#'{sheet.replace(chr(39),chr(39)*2)}'!A{row}"
    cell.style='Hyperlink'


def put_image(sheet,path,row,label='',crop_top=0):
    """Embed a copy in full-width segments; keep the original capture unchanged."""
    path=Path(path)
    try:
        with PillowImage.open(path) as original:
            original.load();width,height=original.size
            crop_top=max(0,min(int(crop_top or 0),height-1))
            max_width=1050;scale=min(1,max_width/width)
            segment_height=max(1,int(900/scale))
            for number,top in enumerate(range(crop_top,height,segment_height),1):
                bottom=min(height,top+segment_height)
                segment=original.crop((0,top,width,bottom))
                buffer=BytesIO();segment.save(buffer,format='PNG');buffer.seek(0)
                image=Image(buffer);image.width*=scale;image.height*=scale
                if label:
                    sheet.cell(row,1,safe_text(f'{label} — part {number}' if height-crop_top>segment_height else label))
                    sheet.cell(row,1).font=Font(bold=True,color=GREEN,size=11);row+=1
                occupied=ceil(image.height/24)
                for index in range(row,row+occupied+1):sheet.row_dimensions[index].height=18
                sheet.add_image(image,f'A{row}');row+=occupied+2
            return row
    except (OSError,ValueError,PillowImage.DecompressionBombError):
        sheet.cell(row,1,'Screenshot could not be read.');return row+2
