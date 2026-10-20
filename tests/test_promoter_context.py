import pytest
from solide.models import Variant
from solide.nomenclature import normalize_variant
from test_mutalyzer_identity import Http,normalized,delins

TX='NM_198253.3:c.-146C>T'
CONTEXT='NC_000005.9(NM_198253.3):c.-146C>T'
G='NC_000005.9:g.1295250G>A'


def promoter_http():
    return Http({'normalize/'+TX:(422,{'custom':{'input_description':TX,'gene_id':'TERT',
        'errors':[{'code':'EOUTOFBOUNDARY','details':'67 bases before mRNA sequence'}]}}),
        'normalize/'+G:normalized(G,G),
        'normalize/'+CONTEXT:normalized(CONTEXT,CONTEXT,'TERT',equivalent_descriptions={'g':[{'description':G}]}),
        'delins_model/'+G:delins(G,start=1295249,end=1295250,inserted='A',reference='NC_000005.9')})


def promoter(**changes):
    fields=dict(gene='TERT',transcript='NM_198253.3',coding='c.-146C>T',
        locus='chr5:1295250',ref='G',alt='A',assembly='GRCh37')
    fields.update(changes);return Variant(**fields)


def test_promoter_outside_mrna_is_checked_in_exact_genomic_transcript_context():
    result=normalize_variant(promoter(),http=promoter_http())
    assert result['normalization']['errors'][0]['code']=='EOUTOFBOUNDARY'
    assert result['nomenclature_assessment']['identity_confirmed'] is True
    assert result['nomenclature_assessment']['suggested_hgvs']==CONTEXT
    assert result['nomenclature_assessment']['source_genomic_query']=='chr5-1295250-G-A'


@pytest.mark.parametrize('issue',['wrong_gene','wrong_version','wrong_genomic_event','reference_error','unknown_assembly'])
def test_promoter_context_never_overrides_a_conflict_or_missing_source_identity(issue):
    http=promoter_http();row=promoter();context=http.payloads['normalize/'+CONTEXT]
    if issue=='wrong_gene':context['gene_id']='OTHER'
    if issue=='wrong_version':context['normalized_description']=CONTEXT.replace('.3)', '.2)')
    if issue=='wrong_genomic_event':context['equivalent_descriptions']['g']=[{'description':'NC_000005.9:g.1295251G>A'}]
    if issue=='reference_error':context['errors']=[{'code':'ESEQUENCEMISMATCH'}]
    if issue=='unknown_assembly':row.assembly='Unknown'
    result=normalize_variant(row,http=http)
    assert result['nomenclature_assessment']['identity_confirmed'] is False
    assert not result['nomenclature_assessment']['suggested_hgvs']
