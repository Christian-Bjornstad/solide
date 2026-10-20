import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PyQt6.QtWidgets import QApplication,QDialog
from solide.import_dialog import SampleImportDialog
from solide.importing import load_file

OPA='Type\tGene\tNucleotide Change\tGene Isoform\tCall\nSNV\tEGFR\tc.1A>T\tNM_1.1\tPRESENT\n'


def test_missing_oum_requires_valid_number_and_converts_lowercase(tmp_path):
    app=QApplication.instance() or QApplication([])
    p=tmp_path/'variants.tsv';p.write_text(OPA)
    dialog=SampleImportDialog(load_file(p),p)
    try:
        assert not dialog.add_button.isEnabled()
        dialog.patient.setText('en prøve')
        assert not dialog.add_button.isEnabled()
        dialog.patient.setText('26oum12345')
        assert dialog.patient.text()=='26OUM12345'
        assert dialog.add_button.isEnabled()
        assert dialog.add_button.text()=='Importer'
    finally:dialog.close()


def test_missing_oum_popup_binds_only_the_imported_file(tmp_path,monkeypatch):
    from solide.gui import MainWindow
    app=QApplication.instance() or QApplication([]);view=MainWindow()
    p=tmp_path/'variants.tsv';p.write_text(OPA)
    dialogs=[]
    def confirm(dialog):
        dialogs.append(dialog)
        assert not dialog.patient.text()
        dialog.patient.setText('26oum54321')
        assert dialog.add_button.isEnabled()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(SampleImportDialog,'exec',confirm)
    try:
        view.accept_import([(str(p),load_file(p),'')])
        assert len(dialogs)==1
        assert view.session.analyses[0].patient=='26OUM54321'
        assert view.session.variants[0].patient=='26OUM54321'
        assert p.read_text()==OPA
    finally:view.close()


def test_row_sample_column_cannot_merge_two_samples(tmp_path):
    p=tmp_path/'two.tsv'
    p.write_text('Type\tGene\tNucleotide Change\tSample Name\n'
                 'SNV\tEGFR\tc.1A>T\t26OUM11111\n'
                 'SNV\tTP53\tc.2A>G\t26OUM22222\n')
    with pytest.raises(ValueError,match='Flere prøver'):
        load_file(p)


def test_row_sample_column_can_supply_the_oum_number(tmp_path):
    p=tmp_path/'one.tsv'
    p.write_text('Type\tGene\tNucleotide Change\tSample ID\n'
                 'SNV\tEGFR\tc.1A>T\t26oum11111\n'
                 'SNV\tTP53\tc.2A>G\t26oum11111\n')
    assert load_file(p).sample_hint=='26OUM11111'
