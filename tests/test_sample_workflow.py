import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from copy import deepcopy
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication
from solide.importing import load_file
from solide.models import Analysis,Session,Variant
from solide.gui import MainWindow


SAMPLE_A='26'+'OUM12345'
SAMPLE_B='26'+'OUM54321'

ION='Type\tGenes\tTranscript\tCoding\tGenotype\nSNV\tTP53\tNM_000546.6\tc.1A>T\tA/T\n'
OPA='Type\tGene\tNucleotide Change\tGene Isoform\tAllele Frequency\tCall\nSNV\tEGFR\tc.1A>T\tNM_005228.5\t0.2\tPRESENT\n'


def source(tmp_path,content,name='source.tsv'):
    path=tmp_path/name;path.write_text(content,encoding='utf8');return path


def test_ion_detection_and_oum_core_from_original_metadata(tmp_path):
    result=load_file(source(tmp_path,'##sampleNames='+SAMPLE_A.lower()+'_v1\n##workflowName=Oncomine Childhood Cancer Research\n'+ION))
    assert (result.profile,result.assay,result.sample_hint)==('Ion Torrent','Childhood',SAMPLE_A)
    assert result.detection_reason


def test_opa_schema_without_sample_id_is_detected_without_inventing_identity(tmp_path):
    result=load_file(source(tmp_path,OPA))
    assert result.profile=='OPA' and not result.sample_hint
    assert result.assay=='Oncomine Precision Assay'
    assert result.assembly=='Unknown'


def test_oum_filename_fallback_and_conflicting_ids_require_input(tmp_path):
    path=source(tmp_path,OPA,SAMPLE_B.lower()+'_variants.tsv')
    assert load_file(path).sample_hint==SAMPLE_B
    path.write_text('##sampleNames='+SAMPLE_A+'\n'+OPA,encoding='utf8')
    result=load_file(path)
    assert result.sample_hint=='' and len(result.sample_candidates)==2
    assert any('conflict' in value.lower() for value in result.warnings)


def test_explicit_precision_assay_takes_precedence_over_reporter_column_layout(tmp_path):
    result=load_file(source(tmp_path,'##workflowName=Oncomine Precision Assay\n'+ION))
    assert result.profile=='OPA' and result.variants[0].platform=='Ion Reporter'


def test_generic_table_does_not_establish_an_assay_and_multisample_metadata_is_rejected(tmp_path):
    assert load_file(source(tmp_path,'Type\tGene\nSNV\tTP53\n')).profile=='Unassigned'
    with pytest.raises(ValueError,match='Multiple samples'):
        load_file(source(tmp_path,'##sampleNames='+SAMPLE_A+','+SAMPLE_B+'\n'+ION))


def test_import_dialog_detects_type_and_requires_missing_sample_id(tmp_path):
    from solide.import_dialog import SampleImportDialog
    app=QApplication.instance() or QApplication([])
    path=source(tmp_path,OPA);result=load_file(path)
    dialog=SampleImportDialog(result,path)
    try:
        assert dialog.profile.currentText()=='OPA'
        assert not dialog.add_button.isEnabled()
        assert not dialog.details.isVisible()
        dialog.patient.setText(SAMPLE_A);app.processEvents()
        assert dialog.add_button.isEnabled()
        assert 'OPA' in dialog.detected.text()
    finally:dialog.close()


def test_sample_list_switches_only_active_file_and_candidate_view_preserves_raw_rows(tmp_path):
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    a=Analysis(id='a',patient=SAMPLE_A,profile='OPA')
    b=Analysis(id='b',patient=SAMPLE_B,profile='Ion Torrent')
    rows=[Variant(analysis_id='a',patient=a.patient,gene='EGFR',kind='SNV',call='PRESENT',selected=True),
          Variant(analysis_id='a',patient=a.patient,gene='TP53',kind='SNV',call='ABSENT',platform='Genexus'),
          Variant(analysis_id='a',patient=a.patient,gene='MET',kind='CNV'),
          Variant(analysis_id='b',patient=b.patient,gene='BRCA1',kind='SNV',call='A/T',platform='Ion Reporter')]
    window.session=Session(analyses=[a,b],variants=rows);window.refresh()
    try:
        assert window.sample_list.count()==2 and window.proxy.rowCount()==1
        window.show_all_rows.setChecked(True);assert window.proxy.rowCount()==3
        window.show_all_rows.setChecked(False)
        window.sample_list.setCurrentRow(1);app.processEvents()
        assert window.active_analysis_id=='b' and window.proxy.rowCount()==1
        window.select_visible(True)
        assert rows[0].selected and rows[3].selected and not rows[1].selected
        assert len(window.session.variants)==4
    finally:window.dirty=False;window.close()


def test_rename_missing_identity_keeps_analysis_evidence_and_other_sources():
    from solide.analyses import rename_analysis_sample
    a=Analysis(id='a',patient='Temporary',profile='OPA');b=Analysis(id='b',patient='Temporary',profile='Ion Torrent')
    v=Variant(analysis_id='a',patient='Temporary',raw={'Gene':'TP53'},evidence={'ClinVar':{'raw':{'result':'original'}}})
    other=Variant(analysis_id='b',patient='Temporary')
    session=Session(analyses=[a,b],variants=[v,other],tissues={'Temporary':'Lung'})
    before=deepcopy(v.evidence);rename_analysis_sample(session,'a',SAMPLE_A)
    assert a.patient==v.patient==SAMPLE_A and other.patient==b.patient=='Temporary'
    assert v.evidence==before and v.raw=={'Gene':'TP53'} and v.analysis_id=='a'
    assert session.tissue_for(v)==session.tissue_for(other)=='Lung'


def test_import_has_its_own_page_and_export_stays_with_database_results():
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    try:
        assert [window.nav.item(i).text() for i in range(window.nav.count())]==['Import','Variants','Searches','Settings']
        assert window.pages.count()==4
        window.nav.setCurrentRow(2);window.show();app.processEvents()
        assert window.report_btn.isVisible() and window.include_evidence.isVisible()
    finally:window.dirty=False;window.close()


def test_new_file_does_not_inherit_previous_samples_gene_filter(tmp_path,monkeypatch):
    from solide.import_dialog import SampleImportDialog
    from PyQt6.QtWidgets import QDialog
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    path=source(tmp_path,OPA,SAMPLE_B+'.tsv')
    window.session=Session(variants=[Variant(patient=SAMPLE_A,gene='PTEN')]);window.refresh()
    window.search.setText('PTEN')
    monkeypatch.setattr(SampleImportDialog,'exec',lambda self:QDialog.DialogCode.Accepted)
    try:
        window.accept_import([(str(path),load_file(path),'')])
        assert window.search.text()=='' and window.proxy.rowCount()==1
        assert window.variant_model.variants[0].patient==SAMPLE_B
        assert window.nav.currentRow()==1
    finally:window.dirty=False;window.close()
