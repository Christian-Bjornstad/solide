"""Render native UI with synthetic data only; no external providers."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from solide.models import Variant,Session
from solide.gui import MainWindow

app=QApplication([])
window=MainWindow()
window.session=Session(variants=[
    Variant(patient='DEMO-001',gene='EGFR',transcript='NM_005228.5',coding='c.2573T>G',protein='p.L858R',
            af_percent=21.1,coverage=7050,kind='SNV',call='PRESENT',assembly='GRCh37',selected=True,
            comment='Syntetisk demonstrasjon; ingen pasientdata.',platform='Genexus',source_row=2),
    Variant(patient='DEMO-001',gene='TP53',transcript='NM_000546.6',coding='c.743G>A',protein='p.R248Q',
            af_percent=25.8,coverage=6355,kind='SNV',call='PRESENT',assembly='GRCh37',selected=True),
    Variant(patient='DEMO-001',gene='MET',transcript='NM_001174067.1',coding='c.3029C>T',protein='p.T1010I',
            af_percent=8.2,coverage=420,kind='SNV',call='PRESENT',assembly='GRCh37',selected=False),
    Variant(patient='DEMO-001',gene='BRCA1',transcript='NM_007294.4',coding='c.5346+5C>A',
            af_percent=12.4,coverage=2200,kind='SNV',call='PRESENT',assembly='GRCh37',selected=True),
    Variant(patient='DEMO-002',gene='ERBB2',kind='CNV',copy_number=0.8,call='ABSENT'),
    Variant(patient='DEMO-002',gene='ALK',kind='RNAExonTiles',call='NO CALL')])
window.refresh();window.nav.setCurrentRow(2);window.show();app.processEvents()
window.variant_table.selectRow(0);app.processEvents()
out=Path('artifacts/solide-preview.png').resolve();out.parent.mkdir(exist_ok=True)
window.grab().save(str(out));print(out)
window.dirty=False;window.close()
