"""Prove selected annotation candidates against public references and source DNA."""
from __future__ import annotations
from copy import deepcopy
import re
import requests

from .annotations import (annotation_group,annotation_tokens,annotation_fingerprint,
                          annotation_resolution_current)
from .nomenclature import (normalize_variant,hgvs_query,genomic_query,_transcript,_FULL_HGVS,
                           _GRCH37_REFERENCES,apply_confirmed_normalization)
from .source_failures import source_failure

_MAX_NAMES=64


def _probe(variant,gene,coding):
    candidate=deepcopy(variant)
    for key in ('_annotation_group','_annotation_issue','_annotation_resolution'):
        candidate.raw.pop(key,None)
    candidate.gene=gene;candidate.coding=coding;candidate.protein=''
    candidate.evidence={}
    return candidate


def _names(variant):
    if variant.corrected_hgvs:
        return [variant.corrected_hgvs]
    group=annotation_group(variant)
    names=group.get('coding_candidates',annotation_tokens(variant.coding))
    result=[]
    for name in names:
        if not isinstance(name,str) or not name:continue
        if ':' in name:
            if _transcript(name)!=variant.transcript:continue
        else:
            if not name.startswith('n.' if variant.transcript.startswith('NR_') else 'c.'):continue
        if name not in result:result.append(name)
    return result


def _checked(probe,result):
    if not isinstance(result,dict):return False
    assessment=result.get('nomenclature_assessment',{})
    data=result.get('contextual_normalization',{}).get('normalization') or result.get('normalization',{})
    try:original=hgvs_query(probe);genomic=genomic_query(probe)
    except ValueError:return False
    description=data.get('normalized_description','')
    gene=data.get('gene_id')
    reference=result.get('reference_identity',{})
    if (not gene and isinstance(reference,dict) and reference.get('status')=='resolved'
            and reference.get('source') in {'NCBI RefSeq','Mutalyzer RefSeq'} and reference.get('transcript')==probe.transcript):
        gene=reference.get('gene')
    contextual=result.get('contextual_normalization',{})
    expected_input=contextual.get('original') if contextual.get('normalization') else result.get('original')
    return (assessment.get('identity_confirmed') is True and assessment.get('status') in {'Unchanged','Normalized'}
        and assessment.get('source_genomic_query')==genomic and result.get('original')==original
        and isinstance(description,str) and _FULL_HGVS.fullmatch(description) is not None
        and _transcript(description)==probe.transcript and gene==probe.gene
        and not data.get('errors') and data.get('input_description')==expected_input
        and isinstance(result.get('genomic_identity_check',{}).get('matched_event'),dict)
        and bool(result['genomic_identity_check']['matched_event']))


def _protein(result,reference):
    data=result.get('contextual_normalization',{}).get('normalization') or result.get('normalization',{})
    name=data.get('protein',{}).get('description','')
    protein=reference.get('protein','');transcript=reference.get('transcript','')
    match=re.fullmatch(r'(?:NC_\d+\.\d+\()?'+re.escape(transcript)+r'\('+re.escape(protein)+r'\)\)?:((?:p\.).+)',name) if protein else None
    return match[1] if match else ''


def resolve_annotation(variant,resolver,*,normalize=None,checkpoint=lambda:None):
    """Commit a unique checked mapping; incomplete or conflicting data stay visible."""
    if annotation_resolution_current(variant):return True
    checkpoint()
    if normalize is None:
        normalize=lambda probe:normalize_variant(probe,checkpoint=checkpoint,reference_identity=reference)
    def unresolved(reason,**details):
        checkpoint()
        variant.raw['_annotation_resolution']={'status':'unresolved','reason':reason,**details}
        return False
    if not re.fullmatch(r'(?:NM|NR)_\d+\.\d+',variant.transcript):
        return unresolved('Velg ett versjonert NM-/NR-transkript i variantdetaljer.')
    # Allele and transcript alternatives are separate axes. Never infer allele
    # choice or copy one AF across a multiallelic source row.
    if ',' in variant.ref or ',' in variant.alt:
        return unresolved('Flere ALT-/REF-alleler i kilderaden. Importer én allel per rad.')
    try:
        genomic_query(variant)
        names=_names(variant)
    except ValueError:
        return unresolved('Genomisk kontroll krever GRCh37/hg19-lokus og én eksplisitt REF/ALT-allel.')
    if len(names)>_MAX_NAMES:return unresolved('For mange mulige variantnavn. Oppgi full HGVS i variantdetaljer.')
    reference=resolver.resolve([variant.transcript]).get(variant.transcript,{})
    checkpoint()
    if reference.get('status')!='resolved' or reference.get('transcript')!=variant.transcript or not reference.get('gene'):
        return unresolved('Transkriptets gen kunne ikke bekreftes. Prøv igjen eller kontroller referansen.',reference=reference,
            retryable=reference.get('reason') in {'network_error','timeout','rate_limited','http_error','invalid_xml','oversized_response'})
    gene=reference['gene'];winners={};attempts=[]
    try:
        # Missing names can be recovered from exact transcript equivalents of
        # the source allele, then independently validated like imported names.
        if not names or len(names)>16:
            source_names=names
            genomic=_probe(variant,gene,'');genomic.corrected_hgvs='';genomic.nomenclature_verified=False
            result=normalize(genomic)
            if result.get('nomenclature_assessment',{}).get('retryable') is True:
                return unresolved('Mutalyzer-kontrollen ble avbrutt av en tjenestefeil. Prøv igjen.',retryable=True)
            equivalents=result.get('normalization',{}).get('equivalent_descriptions',{})
            if isinstance(equivalents,dict):
                projected=list(dict.fromkeys(row['description'] for rows in equivalents.values() if isinstance(rows,list)
                    for row in rows if isinstance(row,dict) and isinstance(row.get('description'),str)
                    and _transcript(row['description'])==variant.transcript))
                names=projected or source_names
        if len(names)>_MAX_NAMES:return unresolved('Flere mulige navn for transkriptet. Kontroller full HGVS.')
        for name in names:
            candidates=[name]
            coordinate=name.split(':',1)[-1]
            if not name.startswith('NC_') and coordinate.startswith(('c.','n.')):
                chrom=genomic_query(variant).removeprefix('chr').split('-',1)[0]
                candidates.append(f'{_GRCH37_REFERENCES[chrom]}({variant.transcript}):{coordinate}')
            for candidate in candidates:
                checkpoint();probe=_probe(variant,gene,candidate)
                if probe.corrected_hgvs!=candidate:probe.corrected_hgvs='';probe.nomenclature_verified=False
                result=normalize(probe)
                checked=_checked(probe,result)
                assessment=result.get('nomenclature_assessment',{})
                attempts.append({'query':hgvs_query(probe),'matched':bool(checked),
                    'assessment':deepcopy(assessment),'errors':result.get('normalization',{}).get('errors',[])})
                if assessment.get('retryable') is True:
                    return unresolved('Mutalyzer-kontrollen ble avbrutt av en tjenestefeil. Prøv igjen.',attempts=attempts,retryable=True)
                if checked:
                    data=result.get('contextual_normalization',{}).get('normalization') or result['normalization']
                    key=variant.transcript+':'+data['normalized_description'].split(':',1)[1]
                    winners.setdefault(key,(probe,result))
                    # A valid mRNA description already proves this candidate.
                    break
    except requests.RequestException as exc:
        failure=source_failure('Mutalyzer',exc)
        return unresolved(failure['summary'],attempts=attempts,retryable=True,
            failure=failure['raw']['failure'])
    except (ValueError,KeyError,TypeError,AttributeError):
        return unresolved('Ufullstendig svar ved kontroll av annotasjonen.',attempts=attempts)
    if len(winners)!=1:
        return unresolved('Ingen entydig kobling mellom transkript og genomisk endring. Kontroller full HGVS.',attempts=attempts)
    probe,result=next(iter(winners.values()))
    probe.protein=_protein(result,reference)
    apply_confirmed_normalization(probe,result)
    checkpoint()
    # Source cells, parent annotation and independent checkbox/evidence remain.
    for field in ('gene','transcript','coding','protein','corrected_hgvs','controlled_genomic','nomenclature_verified'):
        setattr(variant,field,getattr(probe,field))
    variant.raw['_annotation_resolution']={'status':'verified','reason':'Gen, transkript og genomisk endring bekreftet.',
        'reference':deepcopy(reference),'attempts':attempts,'normalization':result,
        'source_genomic_query':genomic_query(variant),'fingerprint':annotation_fingerprint(variant)}
    return True
