import pytest
from openpyxl import Workbook,load_workbook
from solide.importing import load_file
from solide.models import Session
from solide.reporting import export_patient


def test_preamble_empty_column_and_repeated_header_preserved(tmp_path):
    source=tmp_path/'source.tsv'
    source.write_text('##reference=hg19\nMetadata\nType\tGene\t\tCoverage\nSNV\tEGFR\tOriginal value\t400\nType\tGene\t\tCoverage\n',encoding='utf8')
    data=load_file(source);assert len(data.variants)==1
    v=data.variants[0];v.patient='DEMO'
    assert v.source_row==4 and v.raw['_columns']==['Type','Gene','','Coverage']
    report=load_workbook(export_patient(Session(variants=[v]),'DEMO',tmp_path))
    rows=list(report['Raw data'].values)
    assert rows[0][:4]==('Type','Gene','Unnamed column 3','Coverage')
    assert rows[1][:4]==('SNV','EGFR','Original value','400')


def test_ambiguous_reviewed_sheets_rejected(tmp_path):
    w=Workbook()
    for sheet in [w.active,w.create_sheet('Presentation copy')]:
        sheet.append(['Type','Gene']);sheet.append(['SNV','EGFR'])
    path=tmp_path/'duplicate.xlsx';w.save(path)
    with pytest.raises(ValueError,match='Multiple variant tables'):load_file(path)


def test_duplicate_headers_rejected_instead_of_overwritten(tmp_path):
    path=tmp_path/'duplicate.tsv';path.write_text('Type\tGene\tCoding\tCoding\nSNV\tEGFR\tc.1A>T\tc.2A>G')
    with pytest.raises(ValueError,match='Duplicate column names'):load_file(path)


def test_placeholder_and_provenance_header_names_do_not_overwrite_source(tmp_path):
    source=tmp_path/'columns.tsv'
    source.write_text('Type\tGene\t\tUnnamed column 3\tSource row\nSNV\tEGFR\tBlank-header value\tNamed-header value\tOriginal row value')
    v=load_file(source).variants[0];v.patient='DEMO'
    w=load_workbook(export_patient(Session(variants=[v]),'DEMO',tmp_path))
    rows=list(w['Raw data'].values)
    assert rows[0][:5]==('Type','Gene','Unnamed column 3 (2)','Unnamed column 3','Source row')
    assert rows[1][:5]==('SNV','EGFR','Blank-header value','Named-header value','Original row value')
    assert len(rows[0])==len(set(str(value).casefold() for value in rows[0]))
