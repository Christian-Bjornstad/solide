from copy import deepcopy

import pytest

from solide.models import Variant, Session
from solide.nomenclature import display_identity
from solide.evidence import query_record
from solide.reporting import export_analysis
from solide.analyses import add_analysis
from solide.models import ImportResult
from openpyxl import load_workbook


def checked():
    v=Variant(gene='KIT',transcript='NM_000222.3',coding='c.1674_1676delGGTinsTGG',
        protein='p.[Lys558Asn;Val559Gly]',locus='chr4:55593608',ref='GGT',alt='TGG',assembly='GRCh37',
        selected=True,corrected_hgvs='NM_000222.3:c.1674_1676delinsTGG',
        controlled_genomic='chr4-55593608-GGT-TGG',nomenclature_verified=True)
    v.evidence['Mutalyzer']={'database':'Mutalyzer','status':'verified','tissue':'Other',
        'fingerprint':v.fingerprint('Other'),'raw':{
            'nomenclature_assessment':{'identity_confirmed':True,'status':'Normalized',
                'source_genomic_query':v.controlled_genomic,'suggested_hgvs':v.corrected_hgvs},
            'nomenclature_application':{'applied':True,'to_hgvs':v.corrected_hgvs},
            'normalization':{'normalized_description':v.corrected_hgvs,'gene_id':'KIT',
                'protein':{'description':'NM_000222.3(NP_000213.1):p.(Lys558_Val559delinsAsnGly)'}}}}
    return v


def test_verified_mutalyzer_protein_is_used_without_replacing_imported_protein(tmp_path):
    v=checked();s=Session();a=add_analysis(s,ImportResult([v]),'00OUM00001','GRCh37','Ion Torrent','Childhood')
    v=s.variants[0];v.selected=True
    assert display_identity(v)==(v.corrected_hgvs,'p.Lys558_Val559delinsAsnGly','NM_000222.3')
    assert query_record(v,'ClinVar').hgvsp=='p.(Lys558_Val559delinsAsnGly)'
    assert v.protein=='p.[Lys558Asn;Val559Gly]'
    book=load_workbook(export_analysis(s,a.id,tmp_path).report)
    try:assert book['Oversikt']['C8'].value=='p.Lys558_Val559delinsAsnGly'
    finally:book.close()


@pytest.mark.parametrize('issue',['stale','transcript','gene','wrong_name','unconfirmed'])
def test_inconsistent_protein_is_never_presented_as_the_normalized_result(issue):
    v=checked();item=v.evidence['Mutalyzer'];data=item['raw']
    if issue=='stale':item['fingerprint']='old'
    if issue=='transcript':data['normalization']['protein']['description']='NM_000222.4(NP_000213.1):p.(Lys558Asn)'
    if issue=='gene':data['normalization']['gene_id']='OTHER'
    if issue=='wrong_name':data['normalization']['normalized_description']='NM_000222.3:c.1A>T'
    if issue=='unconfirmed':data['nomenclature_assessment']['identity_confirmed']=False
    assert display_identity(v)[1]==''
