from copy import deepcopy
import pytest
from test_mutalyzer_identity import Http,variant,normalized,delins,G,VCF,TX,genomic_http
from solide.nomenclature import normalize_variant,normalization_unchanged

CONTEXT='NC_000007.13(NM_005228.5):c.2235_2249del'


def reference_difference_http():
    http=genomic_http()
    http.payloads.update({'normalize/'+TX:normalized(TX,TX,'EGFR'),
        'map/'+TX:{'mapped_description':CONTEXT,'genomic_description':G,
            'ref_seq_differences':True,'filtered_variants':True,
            'unfiltered_mapped_description':'NC_000007.13(NM_005228.5):c.[2235_2249del;2500A>G]',
            'reference_sequences_description':'NC_000007.13(NM_005228.5):c.2500A>G'},
        'normalize/'+CONTEXT:normalized(CONTEXT,CONTEXT,'EGFR')})
    return http


def test_unrelated_reference_difference_requires_independent_genomic_context_validation():
    http=reference_difference_http()
    result=normalize_variant(variant(transcript='NM_005228.5',coding='c.2235_2249del'),http=http)
    assert result['nomenclature_assessment']['identity_confirmed'] is True
    assert result['nomenclature_assessment']['status']=='Unchanged'
    assert ('normalize/'+CONTEXT) in [url for url,_ in http.calls]
    assert result['genomic_identity_check']['mapping_context_checks'][CONTEXT]['gene_id']=='EGFR'


@pytest.mark.parametrize('issue',['not_filtered','wrong_gene','wrong_version','unqualified_context','wrong_genome','missing_model','bad_context'])
def test_reference_difference_never_bypasses_event_or_reference_checks(issue):
    http=reference_difference_http();context=http.payloads['normalize/'+CONTEXT]
    if issue=='not_filtered':http.payloads['map/'+TX]['filtered_variants']=False
    if issue=='wrong_gene':context['gene_id']='OTHER'
    if issue=='wrong_version':context['normalized_description']=CONTEXT.replace('.5)', '.4)')
    if issue=='unqualified_context':context['normalized_description']=TX
    if issue=='wrong_genome':context['equivalent_descriptions']['g']=[{'description':G.replace('55242465','55242466')}]
    if issue=='missing_model':context.pop('normalized_model')
    if issue=='bad_context':context['errors']=[{'code':'ESEQUENCEMISMATCH'}]
    result=normalize_variant(variant(transcript='NM_005228.5',coding='c.2235_2249del'),http=http)
    assert result['nomenclature_assessment']['identity_confirmed'] is False
    assert not result['nomenclature_assessment']['suggested_hgvs']


def test_unchanged_genomic_input_without_a_transcript_is_complete():
    row=variant();result=normalize_variant(row,http=genomic_http())
    assert normalization_unchanged(row,result)
