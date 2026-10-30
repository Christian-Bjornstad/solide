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


@pytest.mark.parametrize('issue',['stale','transcript','gene','wrong_name','unconfirmed','unverified'])
def test_inconsistent_protein_is_never_presented_as_the_normalized_result(issue):
    v=checked();item=v.evidence['Mutalyzer'];data=item['raw']
    if issue=='stale':item['fingerprint']='old'
    if issue=='transcript':data['normalization']['protein']['description']='NM_000222.4(NP_000213.1):p.(Lys558Asn)'
    if issue=='gene':data['normalization']['gene_id']='OTHER'
    if issue=='wrong_name':data['normalization']['normalized_description']='NM_000222.3:c.1A>T'
    if issue=='unconfirmed':data['nomenclature_assessment']['identity_confirmed']=False
    if issue=='unverified':item['status']='needs_review'
    assert display_identity(v)[1]==''


@pytest.mark.parametrize('protein_reference,expected',[
    ('NC_000004.11(NP_000213.1)','p.Lys558_Val559delinsAsnGly'),
    ('NC_000004.12(NP_000213.1)',''),
    ('NC_000007.13(NP_000213.1)',''),
    ('NM_000222.3(NP_000213.1)','p.Lys558_Val559delinsAsnGly'),
    ('NC_000004.11(NM_000222.3(NP_000213.1))','p.Lys558_Val559delinsAsnGly'),
    ('NC_000004.12(NM_000222.3(NP_000213.1))',''),
    ('NC_000004.11(NM_000222.4(NP_000213.1))',''),
    ('NP_000213.1',''),
])
def test_genomic_context_protein_requires_the_exact_confirmed_reference(protein_reference,expected):
    v=checked()
    v.corrected_hgvs='NC_000004.11(NM_000222.3):c.1674_1676delinsTGG'
    item=v.evidence['Mutalyzer'];item['fingerprint']=v.fingerprint('Other')
    raw=item['raw']
    raw['nomenclature_assessment']['suggested_hgvs']=v.corrected_hgvs
    data=raw['normalization']
    data['normalized_description']=v.corrected_hgvs
    data['protein']['description']=protein_reference+':p.(Lys558_Val559delinsAsnGly)'
    # Intronic/context normalization keeps the original mRNA error separately.
    raw['contextual_normalization']={'normalization':data}
    raw['normalization']={'errors':[{'code':'EINTRONIC'}]}
    assert display_identity(v)==(v.corrected_hgvs,expected,'NM_000222.3')


@pytest.mark.parametrize('source',['normalization','annotation_reference'])
@pytest.mark.parametrize('accession,expected',[('NP_000305.3','p.(Met1Leu)'),('NP_000305.4','')])
def test_manual_normalized_protein_respects_the_exact_resolved_np(source,accession,expected):
    from test_manual_resolution import manual,PublicHttp,Resolver,REFERENCE,TRANSCRIPT
    from solide.manual_resolution import resolve_manual_variant
    from solide.nomenclature import confirmed_protein
    from solide.report_identity import report_variant_text
    v=manual(coding=REFERENCE+'('+TRANSCRIPT+'):c.1A>T')
    http=PublicHttp()
    http.normalize_changes={'protein':{'description':REFERENCE+'('+accession+'):p.(Met1Leu)'}}
    assert resolve_manual_variant(v,Resolver(),http=http)
    assert v.protein==expected
    if source=='annotation_reference':
        del v.raw['_annotation_resolution']['normalization']['reference_identity']
    assert confirmed_protein(v)==expected
    assert display_identity(v)[1]==expected.replace('p.(','p.').rstrip(')')
    assert ('; p.Met1Leu' in report_variant_text(v))==bool(expected)
    assert query_record(v,'ClinVar').hgvsp==expected


@pytest.mark.parametrize('reference_transcript,reference_protein,expected',[
    ('NM_000222.3','NP_000213.1','p.(Lys558_Val559delinsAsnGly)'),
    ('NM_000222.3','NP_000213.2',''),
    ('NM_000222.2','NP_000213.2','p.(Lys558_Val559delinsAsnGly)'),
])
def test_current_normalization_reference_np_applies_only_to_its_exact_transcript(
        reference_transcript,reference_protein,expected):
    from solide.nomenclature import confirmed_protein
    v=checked()
    v.evidence['Mutalyzer']['raw']['reference_identity']={
        'status':'resolved','source':'NCBI RefSeq','gene':'KIT',
        'transcript':reference_transcript,'protein':reference_protein}
    assert confirmed_protein(v)==expected
