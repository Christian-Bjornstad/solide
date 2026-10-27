from solide.models import Variant
from solide.report_identity import report_variant_text
import pytest


@pytest.mark.parametrize('protein,display',[
    ('p.(Arg1516Ter)','p.Arg1516Ter'),('p.(Lys1720AsnfsTer25)','p.Lys1720AsnfsTer25'),
    ('p.Arg172Met','p.Arg172Met'),('p.Gly17Val','p.Gly17Val'),
    ('p.[Arg1Gly;Gly2Val]','p.[Arg1Gly;Gly2Val]'),
])
def test_protein_prediction_parentheses_are_removed_only_for_presentation(protein,display):
    from solide.nomenclature import display_identity
    from solide.table_model import VariantTableModel
    v=Variant(gene='TEST',transcript='NM_000001.1',coding='c.1A>T',protein=protein)
    assert display_identity(v)[1]==display
    model=VariantTableModel([v])
    assert model.index(0,5).data()==display
    assert report_variant_text(v).endswith('; '+display)
    assert v.protein==protein


def test_copy_line_keeps_version_gene_cdna_protein_and_cosmic_id():
    v=Variant(gene='KRAS',transcript='NM_033360.4',coding='c.35G>A',protein='p.Gly12Asp',variant_id='COSM521')
    assert report_variant_text(v)=='NM_033360.4(KRAS): c.35G>A; p.Gly12Asp (COSM521)'


def test_copy_line_omits_missing_protein_and_identifier_without_empty_parentheses():
    v=Variant(gene='ATM',transcript='NM_000051.4',coding='c.1A>T',protein='p.?')
    assert report_variant_text(v)=='NM_000051.4(ATM): c.1A>T'


def test_genomic_only_identity_does_not_invent_a_transcript_or_protein():
    v=Variant(gene='ATM',coding='NC_000011.9:g.100A>T')
    assert report_variant_text(v)=='NC_000011.9(ATM): g.100A>T'


def test_excel_contains_copy_line_in_overview_and_variant_sheet(tmp_path):
    from contextlib import closing
    from openpyxl import load_workbook
    from test_vpm_analysis_reports import make_session
    from solide.reporting import export_analysis
    session,rows=make_session(Variant(gene='KRAS',transcript='NM_033360.4',coding='c.35G>A',
        protein='p.Gly12Asp',variant_id='COSM521',selected=True))
    with closing(load_workbook(export_analysis(session,'analysis-a',tmp_path).report)) as book:
        assert book['Oversikt']['E7'].value=='Rapporttekst'
        assert book['Oversikt']['E8'].value==book['KRAS']['B4'].value=='NM_033360.4(KRAS): c.35G>A; p.Gly12Asp (COSM521)'
