"""Render native UI with synthetic data only; no external providers."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PyQt6.QtWidgets import QApplication
from solide.models import Variant,Session
from solide.gui import MainWindow
from PIL import Image,ImageDraw

app=QApplication([])
with patch('solide.gui.Path.home',return_value=Path('artifacts/preview-home').resolve()), \
     patch('solide.gui.ActivityLog',return_value=None), \
     patch('solide.gui.read_password',return_value=''):
    window=MainWindow()
window.output_dir.setText('C:/Solide/workspace')
window.session=Session(variants=[
    Variant(patient='DEMO-001',gene='EGFR',transcript='NM_005228.5',coding='c.2573T>G',protein='p.L858R',
            af_percent=21.1,coverage=7050,kind='SNV',call='PRESENT',assembly='GRCh37',selected=True,
            comment='Synthetic demonstration',classification='Demonstration only',report_decision='Include',
            reviewer='Demo reviewer',platform='Genexus',source_row=2),
    Variant(patient='DEMO-001',gene='TP53',transcript='NM_000546.6',coding='c.743G>A',protein='p.R248Q',
            af_percent=25.8,coverage=6355,kind='SNV',call='PRESENT',assembly='GRCh37',selected=True),
    Variant(patient='DEMO-001',gene='MET',transcript='NM_001127500.3',coding='c.3029C>T',protein='p.T1010I',
            af_percent=8.2,coverage=420,kind='SNV',call='PRESENT',assembly='GRCh37',selected=False),
    Variant(patient='DEMO-001',gene='BRCA1',transcript='NM_007294.4',coding='c.5346+5C>A',
            af_percent=12.4,coverage=2200,kind='SNV',call='PRESENT',assembly='GRCh37',selected=True),
    Variant(patient='DEMO-002',gene='ERBB2',kind='CNV',copy_number=0.8,call='ABSENT'),
    Variant(patient='DEMO-002',gene='ALK',kind='RNAExonTiles',call='NO CALL')])
synthetic=Path('artifacts/synthetic-evidence.png').resolve();synthetic.parent.mkdir(exist_ok=True)
image=Image.new('RGB',(800,250),'white');draw=ImageDraw.Draw(image)
draw.rectangle((0,0,800,55),fill='#425B3D');draw.text((20,20),'SYNTHETIC EVIDENCE — UI DEMONSTRATION ONLY',fill='white')
draw.text((20,95),'No provider lookup or patient data. Review the source identity before reporting.',fill='#243128')
image.save(synthetic)
first,second=window.session.variants[:2]
first.evidence['ClinVar']={'database':'ClinVar','status':'found','summary':'Synthetic result — identity review required',
    'captured_at':'2026-09-30T18:00:00+00:00','fingerprint':first.fingerprint('Other'),
    'raw':{'screenshots':[{'path':str(synthetic),'label':'Synthetic example'}]}}
second.evidence['Franklin']={'database':'Franklin','status':'timeout','summary':'Synthetic example — request timed out',
    'captured_at':'2026-09-30T18:00:00+00:00','fingerprint':second.fingerprint('Other')}
window.refresh();window.nav.setCurrentRow(0);window.show();app.processEvents()
window.variant_table.selectRow(0);app.processEvents()
out=Path('artifacts/solide-preview.png').resolve();out.parent.mkdir(exist_ok=True)
window.grab().save(str(out));print(out)
for index in range(window.nav.count()):
    window.nav.setCurrentRow(index);app.processEvents()
    window.grab().save(str(out.parent/f'page-{index}.png'))
window.resize(1050,700)
for index in (0,1,3):
    window.nav.setCurrentRow(index);app.processEvents()
    window.grab().save(str(out.parent/f'compact-{index}.png'))
window.dirty=False;window.close()
