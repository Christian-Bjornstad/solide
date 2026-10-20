from copy import deepcopy
import json
from urllib.parse import unquote
from unittest.mock import Mock
import pytest
import requests

from solide.models import Variant
from solide.nomenclature import normalize_variant


G='NC_000007.13:g.55242465_55242479del'
VCF='NC_000007.13:g.55242464_55242479delAGGAATTAAGAGAAGCinsA'
TX='NM_005228.5:c.2235_2249del'
SHORT='NC_000007.13(NM_201284.2):c.*4228_*4242del'


def variant(**changes):
    fields=dict(gene='EGFR',locus='chr7:55242464',ref='AGGAATTAAGAGAAGC',alt='A',assembly='GRCh37')
    fields.update(changes)
    return Variant(**fields)


def normalized(original,canonical,gene=None,**changes):
    payload=dict(input_description=original,normalized_description=canonical,
        normalized_model={'reference':{'id':canonical.split(':')[0]},'variants':[{}]},
        equivalent_descriptions={'g':[{'description':G}], 'c':[{'description':SHORT},
            {'description':'NC_000007.13(NM_005228.5):c.2235_2249del'}]})
    if gene:payload['gene_id']=gene
    payload.update(changes)
    return payload


def delins(description,start=55242464,end=55242479,inserted='',reference='NC_000007.13'):
    return dict(input_description=description,delins_model={'reference':{'id':reference},'coordinate_system':'i',
        'variants':[{'type':'deletion_insertion','location':{'type':'range','start':{'position':start},
        'end':{'position':end}},'inserted':[{'sequence':inserted}] if inserted else []}]})


class Http:
    def __init__(self,payloads):self.payloads=payloads;self.calls=[]
    def get(self,url,**kwargs):
        key=unquote(url.split('/api/')[-1])
        if key=='map/':key='map/'+kwargs['params']['description']
        self.calls.append((key,kwargs))
        payload=deepcopy(self.payloads[key]);status=200
        if isinstance(payload,tuple):status,payload=payload
        response=Mock(status_code=status)
        if status>=400:response.raise_for_status.side_effect=requests.HTTPError(response=response)
        response.json.return_value=payload
        return response


def genomic_http(**changes):
    payloads={'normalize/'+G:normalized(G,G),'normalize/'+VCF:normalized(VCF,G),'delins_model/'+G:delins(G)}
    payloads.update(changes)
    return Http(payloads)


def test_genomic_deletion_never_chooses_first_short_transcript_equivalent():
    http=genomic_http()
    row=variant(coding='c.2235_2249delGGAATTAAGAGAAGC',patient='PRIVATE',source_file='secret.tsv')
    result=normalize_variant(row,http=http)
    assessment=result['nomenclature_assessment']
    assert assessment['status']=='Unchanged' and assessment['identity_confirmed'] is True
    assert assessment['suggested_hgvs']==G and assessment['genomic_hgvs']==G
    assert assessment['source_genomic_query']=='chr7-55242464-AGGAATTAAGAGAAGC-A'
    assert all(item['description']!=SHORT for item in assessment['candidates'])
    assert not row.corrected_hgvs and not row.nomenclature_verified
    assert all(secret not in str(http.calls) for secret in ['PRIVATE','secret.tsv'])


def test_explicit_source_transcript_is_selected_by_version_and_gene():
    http=genomic_http()
    http.payloads['normalize/'+TX]=normalized(TX,TX,'EGFR')
    http.payloads['map/'+TX]=dict(mapped_description='NC_000007.13(NM_005228.5):c.2235_2249del',
        genomic_description=G,ref_seq_differences=False)
    result=normalize_variant(variant(transcript='NM_005228.5',coding='c.2235_2249del'),http=http)
    assessment=result['nomenclature_assessment']
    assert assessment['status']=='Unchanged' and assessment['identity_confirmed'] is True
    assert assessment['suggested_hgvs']==TX
    assert {item['description'] for item in assessment['candidates']}=={TX,G}


def test_normalized_name_is_distinct_from_unchanged_and_does_not_approve():
    original='NM_005228.5:c.2235_2249delGGAATTAAGAGAAGC'
    http=genomic_http()
    http.payloads['normalize/'+original]=normalized(original,TX,'EGFR')
    http.payloads['map/'+TX]=dict(mapped_description='NC_000007.13(NM_005228.5):c.2235_2249del',
        genomic_description=G,ref_seq_differences=False)
    row=variant(transcript='NM_005228.5',coding=original.split(':')[1])
    result=normalize_variant(row,http=http)
    assert result['nomenclature_assessment']['status']=='Normalized'
    assert result['nomenclature_assessment']['suggested_hgvs']==TX
    assert row.coding.endswith('delGGAATTAAGAGAAGC') and not row.nomenclature_verified


def test_different_normalized_genomic_event_is_a_conflict():
    other='NC_000007.13:g.55242466_55242479del'
    http=genomic_http()
    http.payloads.update({'normalize/'+TX:normalized(TX,TX,'EGFR'),
        'map/'+TX:dict(mapped_description='NC_000007.13(NM_005228.5):c.2235_2249del',
            genomic_description=other,ref_seq_differences=False),
        'normalize/'+other:normalized(other,other),'delins_model/'+other:delins(other,start=55242465)})
    assessment=normalize_variant(variant(transcript='NM_005228.5',coding='c.2235_2249del'),http=http)['nomenclature_assessment']
    assert assessment['status']=='Conflict' and assessment['identity_confirmed'] is False
    assert not assessment['suggested_hgvs'] and not assessment['candidates']


def test_wrong_source_gene_is_a_conflict_before_choosing_any_transcript():
    http=Http({'normalize/'+TX:normalized(TX,TX,'MET')})
    assessment=normalize_variant(variant(transcript='NM_005228.5',coding='c.2235_2249del'),http=http)['nomenclature_assessment']
    assert assessment['status']=='Conflict' and not assessment['suggested_hgvs']
    assert len(http.calls)==1


def test_missing_source_alleles_keeps_normalization_but_does_not_claim_identity():
    http=Http({'normalize/'+TX:normalized(TX,TX,'EGFR')})
    result=normalize_variant(variant(transcript='NM_005228.5',coding='c.2235_2249del',ref='',alt=''),http=http)
    assert result['normalization']['normalized_description']==TX
    assert result['nomenclature_assessment']['status']=='Review required'
    assert result['nomenclature_assessment']['identity_confirmed'] is False
    assert not result['nomenclature_assessment']['candidates']


def test_unreviewed_corrected_hgvs_cannot_reuse_original_genomic_alleles():
    http=Http({'normalize/'+TX:normalized(TX,TX,'EGFR')})
    assessment=normalize_variant(variant(corrected_hgvs=TX),http=http)['nomenclature_assessment']
    assert assessment['status']=='Review required' and not assessment['identity_confirmed']
    assert len(http.calls)==1


def test_minimal_legacy_response_does_not_force_additional_network_calls():
    http=Http({'normalize/'+G:dict(normalized_description=G)})
    result=normalize_variant(variant(),http=http)
    assert result['nomenclature_assessment']['status']=='Review required'
    assert len(http.calls)==1


def test_model_missing_inserted_sequence_cannot_confirm_identity():
    http=genomic_http()
    bad=delins(G);bad['delins_model']['variants'][0]['inserted']=[{'source':'reference'}]
    http.payloads['delins_model/'+G]=bad
    assessment=normalize_variant(variant(),http=http)['nomenclature_assessment']
    assert assessment['status']=='Review required' and not assessment['identity_confirmed']


def test_normalizer_cannot_silently_change_the_versioned_source_transcript():
    other='NM_005228.4:c.2235_2249del'
    http=Http({'normalize/'+TX:normalized(TX,other,'EGFR')})
    assessment=normalize_variant(variant(transcript='NM_005228.5',coding='c.2235_2249del'),http=http)['nomenclature_assessment']
    assert assessment['status']=='Conflict' and not assessment['candidates']
    assert len(http.calls)==1


def test_full_coding_description_must_agree_with_explicit_source_transcript():
    http=Http({'normalize/'+TX:normalized(TX,TX,'EGFR')})
    assessment=normalize_variant(variant(transcript='NM_005228.4',coding=TX),http=http)['nomenclature_assessment']
    assert assessment['status']=='Conflict' and not assessment['candidates']
    assert len(http.calls)==1


def test_equivalent_shifted_genomic_spelling_is_normalized_before_event_comparison():
    shifted='NC_000007.13:g.55242464_55242478del'
    http=genomic_http()
    http.payloads.update({'normalize/'+TX:normalized(TX,TX,'EGFR'),
        'map/'+TX:dict(mapped_description='NC_000007.13(NM_005228.5):c.2235_2249del',
            genomic_description=shifted,ref_seq_differences=False),
        'normalize/'+shifted:normalized(shifted,G)})
    assessment=normalize_variant(variant(transcript='NM_005228.5',coding='c.2235_2249del'),http=http)['nomenclature_assessment']
    assert assessment['identity_confirmed'] is True and assessment['genomic_hgvs']==G
    assert assessment['status']=='Unchanged'


def test_wrong_full_ref_including_padding_is_a_conflict():
    http=genomic_http()
    http.payloads['normalize/'+VCF]=dict(input_description=VCF,errors=[dict(code='ESEQUENCEMISMATCH')])
    result=normalize_variant(variant(),http=http)
    assert result['nomenclature_assessment']['status']=='Conflict'
    assert not result['nomenclature_assessment']['candidates']
    assert result['genomic_identity_check']['source_allele_normalization']['normalization']['errors']


def test_refseq_version_in_mapping_must_match_the_explicit_source():
    http=genomic_http()
    http.payloads.update({'normalize/'+TX:normalized(TX,TX,'EGFR'),
        'map/'+TX:dict(mapped_description='NC_000007.13(NM_005228.4):c.2235_2249del',
            genomic_description=G,ref_seq_differences=False)})
    assessment=normalize_variant(variant(transcript='NM_005228.5',coding='c.2235_2249del'),http=http)['nomenclature_assessment']
    assert assessment['status']=='Conflict' and not assessment['identity_confirmed']


def test_single_base_genomic_result_is_serializable_without_self_references():
    g='NC_000007.13:g.55249071C>T'
    http=Http({'normalize/'+g:normalized(g,g), 'delins_model/'+g:delins(g,start=55249070,end=55249071,inserted='T')})
    result=normalize_variant(variant(locus='chr7:55249071',ref='C',alt='T'),http=http)
    assert result['nomenclature_assessment']['identity_confirmed'] is True
    assert json.loads(json.dumps(result))['nomenclature_assessment']['suggested_hgvs']==g


def test_configured_mane_candidate_must_have_matching_gene_version_and_sequence_event():
    source='NM_001127500.3:c.3736G>A';mane='NM_000245.4:c.3682G>A'
    g='NC_000007.13:g.116423407G>A'
    http=Http({'normalize/'+source:normalized(source,source,'MET'),
        'map/'+source:dict(mapped_description=mane),
        'normalize/'+g:normalized(g,g),
        'delins_model/'+g:delins(g,start=116423406,end=116423407,inserted='A'),
        'normalize/'+mane:normalized(mane,mane,'MET'),
        'map/'+mane:dict(mapped_description='NC_000007.13(NM_000245.4):c.3682G>A',
            genomic_description=g,ref_seq_differences=False)})
    original_get=http.get
    def request(url,**kwargs):
        if url.endswith('/map/') and kwargs['params'].get('reference_id')=='GRCh37' and kwargs['params']['description']==source:
            reply=Mock(status_code=200);reply.json.return_value=dict(mapped_description='NC_000007.13(NM_001127500.3):c.3736G>A',
                genomic_description=g,ref_seq_differences=False)
            return reply
        return original_get(url,**kwargs)
    http.get=request
    row=variant(gene='MET',transcript='NM_001127500.3',coding='c.3736G>A',locus='chr7:116423407',ref='G',alt='A')
    result=normalize_variant(row,http=http)
    assessment=result['nomenclature_assessment']
    assert assessment['status']=='Normalized' and assessment['identity_confirmed'] is True
    assert assessment['suggested_hgvs']==mane
    assert assessment['candidates'][0]['transcript']=='NM_000245.4'
    assert row.transcript=='NM_001127500.3' and not row.nomenclature_verified


INTRON='NM_000314.8:c.254-1G>A'
CONTEXT='NC_000010.10(NM_000314.8):c.254-1G>A'
PTEN_G='NC_000010.10:g.89692769G>A'


def intronic_http():
    error=dict(input_description=INTRON,gene_id='PTEN',errors=[dict(code='EINTRONIC',
        assemblies={'GRCh37':{'NM_000314.8':{'chr_id':'NC_000010.10'}}})])
    equivalents={'g':[{'description':PTEN_G}],'c':[{'description':CONTEXT}]}
    return Http({'normalize/'+INTRON:(422,dict(custom=error)),
        'normalize/'+PTEN_G:normalized(PTEN_G,PTEN_G,equivalent_descriptions=equivalents),
        'normalize/'+CONTEXT:normalized(CONTEXT,CONTEXT,'PTEN',equivalent_descriptions=equivalents),
        'delins_model/'+PTEN_G:delins(PTEN_G,start=89692768,end=89692769,inserted='A',reference='NC_000010.10')})


def intronic_variant():
    return Variant(gene='PTEN',transcript='NM_000314.8',coding='c.254-1G>A',
        locus='chr10:89692769',ref='G',alt='A',assembly='GRCh37')


def test_intronic_mrna_rejection_can_offer_only_independently_checked_genomic_context():
    http=intronic_http();row=intronic_variant()
    result=normalize_variant(row,http=http);assessment=result['nomenclature_assessment']
    assert result['normalization']['errors'][0]['code']=='EINTRONIC'
    assert result['normalization_http_status']==422
    assert result['contextual_normalization']['original']==CONTEXT
    assert assessment['status']=='Normalized' and assessment['identity_confirmed'] is True
    assert assessment['suggested_hgvs']==CONTEXT
    assert {choice['description'] for choice in assessment['candidates']}=={CONTEXT,PTEN_G}
    assert 'intronic' in assessment['reason'].lower()
    assert row.transcript=='NM_000314.8' and not row.corrected_hgvs and not row.nomenclature_verified
    assert json.loads(json.dumps(result))['nomenclature_assessment']['identity_confirmed'] is True


@pytest.mark.parametrize('change',[{'gene_id':'OTHER'},
    {'normalized_description':'NC_000010.10(NM_000314.7):c.254-1G>A'},
    {'normalized_description':'NC_000010.11(NM_000314.8):c.254-1G>A'}])
def test_intronic_context_gene_or_transcript_conflict_never_yields_actionable_names(change):
    http=intronic_http();http.payloads['normalize/'+CONTEXT].update(change)
    result=normalize_variant(intronic_variant(),http=http);assessment=result['nomenclature_assessment']
    assert assessment['status']=='Conflict' and not assessment['identity_confirmed']
    assert not assessment['candidates'] and not assessment['suggested_hgvs']
    assert result['normalization']['errors'][0]['code']=='EINTRONIC'


def test_intronic_context_genomic_event_must_match_explicit_source_alleles():
    other='NC_000010.10:g.89692770G>A'
    http=intronic_http()
    http.payloads['normalize/'+CONTEXT]['equivalent_descriptions']['g']=[{'description':other}]
    http.payloads['normalize/'+other]=normalized(other,other)
    http.payloads['delins_model/'+other]=delins(other,start=89692769,end=89692770,inserted='A',reference='NC_000010.10')
    assessment=normalize_variant(intronic_variant(),http=http)['nomenclature_assessment']
    assert assessment['status']=='Conflict' and not assessment['identity_confirmed']
    assert not assessment['candidates']


def test_intronic_context_without_confirmed_gene_requires_review():
    http=intronic_http();http.payloads['normalize/'+CONTEXT].pop('gene_id')
    assessment=normalize_variant(intronic_variant(),http=http)['nomenclature_assessment']
    assert assessment['status']=='Review required' and not assessment['identity_confirmed']
    assert not assessment['candidates'] and not assessment['suggested_hgvs']


def test_intronic_context_is_not_inferred_from_another_assembly_or_transcript():
    http=intronic_http()
    error=http.payloads['normalize/'+INTRON][1]['custom']['errors'][0]
    error['assemblies']={'GRCh38':{'NM_000314.8':{'chr_id':'NC_000010.11'}},
        'GRCh37':{'NM_000314.7':{'chr_id':'NC_000010.10'}}}
    result=normalize_variant(intronic_variant(),http=http)
    assert result['nomenclature_assessment']['status']=='Review required'
    assert not result.get('contextual_normalization') and len(http.calls)==1


def test_minimal_intronic_genomic_candidate_does_not_start_context_or_identity_requests():
    http=intronic_http();http.payloads['normalize/'+PTEN_G].pop('normalized_model')
    result=normalize_variant(intronic_variant(),http=http)
    assert result['nomenclature_assessment']['status']=='Review required'
    assert 'contextual_normalization' not in result and len(http.calls)==2
