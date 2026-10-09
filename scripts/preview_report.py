"""Exercise the production exporter with synthetic data only."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PIL import Image,ImageDraw,ImageFont
from solide.models import Session,Variant
from solide.evidence import batch_fingerprint
from solide.reporting import export_patient


def main():
    root=Path(__file__).resolve().parents[1]/'artifacts'/'report-preview';root.mkdir(parents=True,exist_ok=True)
    capture=root/'synthetic-source.png'
    image=Image.new('RGB',(1200,650),'white');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22)
    draw.rectangle((0,0,1200,90),fill='#425B3D')
    draw.text((30,35),'SYNTHETIC SOURCE PANEL — DEMONSTRATION ONLY',fill='white',font=font)
    draw.text((30,140),'No patient data or real provider lookup. Variant and evidence labels are examples.',fill='#243128',font=font)
    draw.rectangle((30,210,1160,540),outline='#425B3D',width=3)
    draw.text((60,260),'App assessment stays separate from database source assertions.',fill='#243128',font=font);image.save(capture)
    v=Variant(patient='DEMO-SYNTHETIC',gene='BRCA1',transcript='NM_007294.4',coding='c.68_69del',
        protein='p.Glu23ValfsTer17',kind='DEL',call='PRESENT',af_percent=21.1,coverage=2200,assembly='GRCh37',
        selected=True,classification='Demonstration only',report_decision='Include',reviewer='Demo reviewer',
        reviewed_at='2026-10-09T12:00:00+00:00',comment='Synthetic assessment. This workbook demonstrates the report layout.',
        raw={'Transcript':'NM_007294.4','Genes':'BRCA1','Coding':'c.68_69del','Amino Acid Change':'p.Glu23ValfsTer17',
             'Variant ID':'DEMO','ClinVar':'Imported annotation example','Allele Frequency %':21.1,'Coverage':2200,'Type':'DEL'},
        source_file='synthetic.tsv',source_row=2)
    s=Session(variants=[v,Variant(patient=v.patient,gene='MET',kind='CNV',copy_number=0.8,coverage=420,
        call='ABSENT',source_file='synthetic.tsv',source_row=3),
        Variant(patient=v.patient,gene='ALK',kind='RNA Exon Tiles',call='NO CALL',source_file='synthetic.tsv',source_row=4)])
    identity={'gene':v.gene,'assembly':'GRCh37','hgvs':v.transcript+':'+v.coding}
    common={'fingerprint':v.fingerprint('Other'),'captured_at':'2026-10-09T12:00:00+00:00','tissue':'Other'}
    v.evidence['BRCA Exchange']={**common,'database':'BRCA Exchange','status':'found','clinical_significance':'Synthetic source assertion',
        'accession':'DEMO','url':'https://brcaexchange.org/variants','summary':'Synthetic result: no live database query.',
        'raw':{'query_basis':'full_hgvs','identity_verification':{'requested':identity,'returned':identity,'accepted':True,'method':'full_hgvs'}}}
    v.evidence['MTBP']={**common,'database':'MTBP','status':'found','mtbp_batch':batch_fingerprint(s,v.patient),
        'summary':'Synthetic source panel. Confirm source identity before interpretation.',
        'raw':{'screenshots':[{'path':str(capture),'label':'Synthetic panel'}],'patient_report_screenshot':str(capture)}}
    path=export_patient(s,v.patient,root)
    (root/'latest-report.txt').write_text(str(path),encoding='utf8');print(path)


if __name__=='__main__':main()
