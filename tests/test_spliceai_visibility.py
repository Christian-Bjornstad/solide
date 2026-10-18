import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from solide.models import Analysis,Session,Variant
from solide.reporting import export_analysis
from openpyxl import load_workbook


def test_excel_explains_spliceai_not_indicated_instead_of_empty_cell(tmp_path):
    a=Analysis(id='a',patient='DEMO',profile='OPA')
    v=Variant(analysis_id='a',patient='DEMO',gene='EGFR',coding='c.2573T>G',selected=True)
    v.evidence['SpliceAI']={'database':'SpliceAI','status':'not_applicable',
        'fingerprint':v.fingerprint('Other'),'summary':'Outside the ±100 bp intronic rule.'}
    book=load_workbook(export_analysis(Session(analyses=[a],variants=[v]),'a',tmp_path).report)
    try:
        assert book['Oversikt']['M8'].value=='Ikke kjørt'
    finally:book.close()


def test_search_page_shows_intronic_spliceai_candidate_count():
    from PyQt6.QtWidgets import QApplication
    from solide.gui import MainWindow
    app=QApplication.instance() or QApplication([]);view=MainWindow()
    view.session=Session(variants=[Variant(patient='DEMO',gene='PTEN',coding='c.254-1G>A',selected=True),
                                   Variant(patient='DEMO',gene='EGFR',coding='c.2573T>G',selected=True)])
    view.refresh()
    try:
        assert 'SpliceAI: 1 candidate' in view.sources_summary.text()
        assert '±100 bp' in view.source_checks['SpliceAI'].toolTip()
    finally:view.close()
