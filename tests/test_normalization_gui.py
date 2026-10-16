import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication
from solide.models import Session,Variant
from solide.gui import MainWindow


def test_verified_normalization_suggestion_populates_review_without_approval(tmp_path):
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    v=Variant(patient='SOURCE',gene='EGFR',transcript='NM_005228.5',coding='c.2235_2249del',
        locus='chr7:55242464',ref='AGGAATTAAGAGAAGC',alt='A',assembly='GRCh37')
    suggested='NM_005228.5:c.2235_2249del'
    v.evidence['Mutalyzer']={'database':'Mutalyzer','fingerprint':v.fingerprint('Other'),
        'raw':{'nomenclature_assessment':{'status':'Unchanged','identity_confirmed':True,
            'reason':'Same genomic event','suggested_hgvs':suggested,'source_genomic_query':'chr7-55242464-AGGAATTAAGAGAAGC-A',
            'candidates':[{'description':suggested,'label':'Source transcript','transcript':v.transcript}]}}}
    window.session=Session(variants=[v]);window.session_path=tmp_path/'review.solide.json'
    try:
        window.refresh();window.variant_table.selectRow(0);app.processEvents()
        assert 'Unchanged' in window.normalization_status.text()
        assert window.use_normalization_btn.isEnabled()
        window.use_normalization()
        assert window.hgvs_edit.text()==suggested
        assert window.genomic_edit.text()=='chr7-55242464-AGGAATTAAGAGAAGC-A'
        assert not window.verified_check.isChecked()
        assert not v.corrected_hgvs and not v.nomenclature_verified
        window.verified_check.setChecked(True);window.save_identity()
        assert v.corrected_hgvs==suggested and v.nomenclature_verified
    finally:
        window.dirty=False;window.close()


def test_conflicting_or_stale_normalization_cannot_be_selected(tmp_path):
    app=QApplication.instance() or QApplication([]);window=MainWindow()
    v=Variant(patient='SOURCE',gene='EGFR',coding='c.1A>T')
    v.evidence['Mutalyzer']={'database':'Mutalyzer','fingerprint':v.fingerprint('Other'),
        'raw':{'nomenclature_assessment':{'status':'Conflict','identity_confirmed':False,'reason':'Different event',
        'suggested_hgvs':'NM_1.1:c.1A>T','candidates':[{'description':'NM_1.1:c.1A>T'}]}}}
    try:
        window.session=Session(variants=[v]);window.refresh();window.variant_table.selectRow(0);app.processEvents()
        assert not window.use_normalization_btn.isEnabled()
        v.evidence['Mutalyzer']['raw']['nomenclature_assessment'].update(status='Normalized',identity_confirmed=True)
        v.coding='c.2A>T';window.show_variant(window.variant_table.currentIndex())
        assert 'Outdated' in window.normalization_status.text()
        assert not window.use_normalization_btn.isEnabled()
    finally:
        window.dirty=False;window.close()
