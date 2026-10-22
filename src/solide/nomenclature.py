from __future__ import annotations
import math
import re
from urllib.parse import quote
import requests
from .public_http import public_api_session as system_trust_session
from ._vendor.archer.services.genomic_notation import format_mtbp_grch37
from .models import Variant
from .quality import MANE_TARGETS


# NCBI GRCh37.p13 assembly report, primary assembled molecules only:
# https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/001/405/GCF_000001405.25_GRCh37.p13/GCF_000001405.25_GRCh37.p13_assembly_report.txt
_GRCH37_REFERENCES = dict(zip(
    [str(n) for n in range(1, 23)] + ['X', 'Y', 'M'],
    ['NC_000001.10', 'NC_000002.11', 'NC_000003.11', 'NC_000004.11',
     'NC_000005.9', 'NC_000006.11', 'NC_000007.13', 'NC_000008.10',
     'NC_000009.11', 'NC_000010.10', 'NC_000011.9', 'NC_000012.11',
     'NC_000013.10', 'NC_000014.8', 'NC_000015.9', 'NC_000016.9',
     'NC_000017.10', 'NC_000018.9', 'NC_000019.9', 'NC_000020.10',
     'NC_000021.8', 'NC_000022.10', 'NC_000023.10', 'NC_000024.9', 'NC_012920.1']))
_CHROMOSOME = r'(?:[1-9]|1[0-9]|2[0-2]|X|Y|M)'
_FULL_HGVS = re.compile(
    r'(?:NM|NR|NC|NG)_\d+\.\d+(?:\((?:NM|NR)_\d+\.\d+\))?:'
    r'[cgnm]\.[0-9*()_+\-ACGTNacgtn;\[\]delinsupv>=?.]+')
_SPLICE_SCORES = ('DS_AG', 'DS_AL', 'DS_DG', 'DS_DL')
_SPLICE_POSITIONS = ('DP_AG', 'DP_AL', 'DP_DG', 'DP_DL')


def hgvs_query(v: Variant) -> str:
    if v.corrected_hgvs:
        return v.corrected_hgvs.strip()
    if ':' in v.coding and re.match(r'(NM_|NR_|NC_|NG_)', v.coding):
        return v.coding
    if re.fullmatch(r'(?:NM_|NR_|NC_|NG_)[\w.]+',v.transcript) and v.coding:
        return f'{v.transcript}:{v.coding}'
    raise ValueError('Missing or ambiguous transcript / reference. Enter full HGVS for review.')


def genomic_query(v: Variant) -> str:
    if v.assembly != 'GRCh37':
        raise ValueError('Genomic searches require confirmed GRCh37 / hg19.')
    if v.controlled_genomic:
        if not v.nomenclature_verified:
            raise ValueError('Approve the reviewed genomic variant before searching.')
        match=re.fullmatch(rf'(?:chr)?({_CHROMOSOME})-([1-9]\d*)-([ACGT]+)-([ACGT]+)',v.controlled_genomic,re.I)
        if not match:
            raise ValueError('Reviewed genomic variant must use chr-pos-REF-ALT.')
        if match[3].upper() == match[4].upper():
            raise ValueError('REF and ALT must describe a sequence change.')
        return f'chr{match[1].upper()}-{match[2]}-{match[3].upper()}-{match[4].upper()}'
    if v.corrected_hgvs:
        raise ValueError('Reviewed HGVS requires matching reviewed GRCh37 chr-pos-REF-ALT for genomic searches.')
    match = re.fullmatch(rf'(?:chr)?({_CHROMOSOME}):([1-9]\d*)', v.locus, re.I)
    if not match or not re.fullmatch('[ACGT]+', v.ref.upper()) or not re.fullmatch('[ACGT]+', v.alt.upper()):
        raise ValueError('Genomic searches require chromosome:position and explicit REF/ALT.')
    if v.ref.upper() == v.alt.upper():
        raise ValueError('REF and ALT must describe a sequence change.')
    return f'chr{match[1].upper()}-{match[2]}-{v.ref.upper()}-{v.alt.upper()}'


def _genomic_normalization_query(v: Variant) -> str:
    chrom, pos, ref, alt = genomic_query(v).removeprefix('chr').split('-')
    genomic_hgvs = format_mtbp_grch37(f'chr{chrom}:{pos}', ref, alt)
    if not genomic_hgvs:
        raise ValueError('Cannot construct HGVS from the supplied GRCh37 alleles.')
    return _GRCH37_REFERENCES[chrom] + ':' + genomic_hgvs.split(':', 1)[1]


def _normalization_query(v: Variant) -> tuple[str, str]:
    from .annotations import require_resolved_annotations
    require_resolved_annotations(v)
    try:
        description = hgvs_query(v)
    except ValueError:
        return _genomic_normalization_query(v), 'genomic_grch37'
    if len(description) > 500 or not _FULL_HGVS.fullmatch(description):
        raise ValueError('Enter one complete, versioned nucleotide HGVS description for review.')
    return description, 'full_hgvs'


def _map_normalization(http, result: dict, target: str) -> None:
    result['mane_target'] = target
    try:
        response = http.get('https://mutalyzer.nl/api/map/', params={
            'description': result['normalization']['normalized_description'],
            'reference_id': target, 'filter_out': 'true'}, timeout=45)
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            result['mapping_response'] = payload
        response.raise_for_status()
        mapped = payload.get('mapped_description') if isinstance(payload, dict) else None
        if not isinstance(mapped, str) or not mapped.startswith(target + ':'):
            raise ValueError('No unambiguous target description returned.')
        result['mapping'] = payload
    except (requests.RequestException, ValueError) as exc:
        # Mapping is optional. Preserve valid normalization when the remote
        # mapper rejects sequence differences or times out; never swap accessions.
        payload = result.get('mapping_response', {})
        custom = payload.get('custom')
        errors = payload.get('errors') or (custom.get('errors') if isinstance(custom, dict) else None)
        errors = errors if isinstance(errors, list) else []
        codes = [str(item.get('code')) for item in errors if isinstance(item, dict) and item.get('code')]
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        reason = f'HTTP {status}' if isinstance(status, int) else type(exc).__name__
        if codes:
            reason += '; ' + ', '.join(codes)
        result['mapping_issue'] = f'MANE mapping unavailable ({reason}). Review the target transcript manually.'
        result['mapping_retryable']=isinstance(exc,requests.RequestException)


def _normalize_description(http, description: str, basis: str) -> dict:
    # Current API schema: https://mutalyzer.nl/api/swagger.json
    response = http.get('https://mutalyzer.nl/api/normalize/' + quote(description, safe=''), timeout=45)
    if response.status_code != 422:
        response.raise_for_status()
    data = response.json()
    # Validation rejections use HTTP 422 and put the normalizer output in
    # custom. They are useful review evidence, not a lost network response.
    if response.status_code == 422:
        custom = data.get('custom') if isinstance(data, dict) else None
        if not isinstance(custom, dict) or not custom.get('errors'):
            response.raise_for_status()
        data = custom
    if not isinstance(data, dict) or not (data.get('normalized_description') or data.get('errors')):
        raise ValueError('Mutalyzer returned no normalization or error details.')
    if data.get('input_description') and data['input_description'] != description:
        raise ValueError('Mutalyzer did not confirm the requested HGVS description.')
    result = {'original': description, 'query_basis': basis, 'normalization': data}
    if response.status_code == 422:
        result['normalization_http_status'] = 422
    return result


def _intronic_genomic_candidate(v: Variant, http, result: dict) -> None:
    errors = result['normalization'].get('errors')
    if (not isinstance(errors, list) or not errors
            or any(not isinstance(error, dict) or error.get('code') not in {'EINTRONIC','EOUTOFBOUNDARY'} for error in errors)
            or v.corrected_hgvs or v.controlled_genomic):
        return
    try:
        description = _genomic_normalization_query(v)
    except ValueError:
        return
    reference, _ = description.split(':', 1)
    transcript, coding = result['original'].split(':', 1)
    # Mutalyzer's EINTRONIC response gives explicit assembly/transcript context.
    # Require that hg19 context to agree with the source chromosome; no accession
    # or assembly is inferred from gene names. Both requests retain their input.
    for error in errors:
        if error.get('code')=='EOUTOFBOUNDARY':continue
        assemblies = error.get('assemblies')
        grch37 = assemblies.get('GRCh37') if isinstance(assemblies, dict) else None
        context = grch37.get(transcript) if isinstance(grch37, dict) else None
        if not isinstance(context, dict) or context.get('chr_id') != reference:
            return
    try:
        candidate = _normalize_description(http, description, 'genomic_grch37')
        normalized = candidate['normalization']
        if (normalized.get('errors') or normalized.get('input_description') != description
                or not isinstance(normalized.get('normalized_description'), str)
                or not normalized['normalized_description'].startswith(reference + ':g.')):
            raise ValueError('Genomic response did not confirm the GRCh37 reference.')
        equivalents = normalized.get('equivalent_descriptions', {})
        descriptions = equivalents.get('c', []) if isinstance(equivalents, dict) else None
        if not isinstance(descriptions, list):
            raise ValueError('Genomic response returned malformed transcript equivalents.')
        prefix = f'{reference}({transcript}):'
        if any(isinstance(item, dict) and isinstance(item.get('description'), str)
               and item['description'].startswith(prefix) and item['description'] != prefix + coding
               for item in descriptions):
            raise ValueError('Genomic response conflicts with the original versioned transcript.')
        # Keep the original EINTRONIC error. This separate candidate remains a
        # suggestion for review and never marks nomenclature as accepted.
        result['genomic_normalization'] = candidate
    except (requests.RequestException, ValueError) as exc:
        result['genomic_normalization_issue'] = (
            f'GRCh37 genomic candidate unavailable ({type(exc).__name__}). '
            'Review the original transcript and genomic alleles.')
        result['genomic_normalization_retryable']=isinstance(exc,requests.RequestException)


def _intronic_context_normalization(v: Variant, http, result: dict) -> None:
    """Check the original transcript in its explicitly returned genomic context.

    An mRNA reference contains no intronic sequence. Mutalyzer supports an exact
    genomic reference with a transcript selector, as documented in its Normalizer
    examples: https://mutalyzer.readthedocs.io/en/latest/usage.html#the-normalizer
    Keep the mRNA rejection separately; this request does not make it valid.
    """
    errors = result['normalization'].get('errors')
    original = result['original']
    candidate = result.get('genomic_normalization', {})
    genomic = candidate.get('normalization', {})
    if (v.corrected_hgvs or v.controlled_genomic
            or not re.fullmatch(r'(?:NM|NR)_\d+\.\d+:[cn]\..+', original)
            or not isinstance(errors, list) or not errors
            or any(not isinstance(error, dict) or error.get('code') not in {'EINTRONIC','EOUTOFBOUNDARY'} for error in errors)
            or not isinstance(genomic.get('normalized_model'), dict)
            or genomic.get('errors') or genomic.get('input_description') != candidate.get('original')):
        return
    transcript, coding = original.split(':', 1)
    try:
        source = _genomic_normalization_query(v)
        reference = source.split(':', 1)[0]
        if candidate.get('original') != source:
            return
        for error in errors:
            if error.get('code')=='EOUTOFBOUNDARY':continue
            assemblies = error.get('assemblies')
            grch37 = assemblies.get('GRCh37') if isinstance(assemblies, dict) else None
            context = grch37.get(transcript) if isinstance(grch37, dict) else None
            if not isinstance(context, dict) or context.get('chr_id') != reference:
                return
        description = f'{reference}({transcript}):{coding}'
        result['contextual_normalization'] = _normalize_description(http, description, 'genomic_transcript_grch37')
    except (requests.RequestException, ValueError) as exc:
        result['contextual_normalization_issue'] = (
            f'Intronic genomic-context normalization unavailable ({type(exc).__name__}). '
            'Review the original transcript and genomic alleles.')
        result['contextual_normalization_retryable']=isinstance(exc,requests.RequestException)


class _IdentityConflict(ValueError):
    """A returned reference, gene or sequence event contradicts the source."""


def _transcript(description: str) -> str:
    match=re.fullmatch(r'NC_\d+\.\d+\(((?:NM|NR)_\d+\.\d+)\):[cn]\..+',description)
    if match:return match[1]
    reference=description.split(':',1)[0]
    return reference if re.fullmatch(r'(?:NM|NR)_\d+\.\d+',reference) else ''


def _source_allele_description(v: Variant) -> tuple[str,str]:
    query=genomic_query(v)
    chrom,pos,ref,alt=query.removeprefix('chr').split('-')
    position=int(pos);reference=_GRCH37_REFERENCES[chrom]
    if len(ref)==len(alt)==1:
        change=f'{pos}{ref}>{alt}'
    else:
        end=position+len(ref)-1
        location=pos if len(ref)==1 else f'{pos}_{end}'
        # Include unchanged padding too: removing the VCF anchor before reference
        # validation can hide an incorrect REF base. Mutalyzer trims it itself.
        change=f'{location}del{ref}ins{alt}'
    description=reference+':g.'+change
    if len(description)>5000:
        raise ValueError('The explicit genomic allele is too long for this lookup.')
    return query,description


def _delins_identity(http,description: str,reference: str,checks: dict) -> tuple:
    """Compare sequence events, not spelling: internal coordinates are [start,end).

    https://mutalyzer.nl/api/swagger.json documents zero-based half-open locations.
    https://github.com/mutalyzer/mutalyzer/blob/master/mutalyzer/normalizer.py
    documents construction of inserted sequences in the returned delins model.
    """
    response=http.get('https://mutalyzer.nl/api/delins_model/'+quote(description,safe=''),timeout=45)
    response.raise_for_status();payload=response.json()
    checks.setdefault('delins_responses',{})[description]=payload
    if not isinstance(payload,dict) or payload.get('errors') or payload.get('input_description')!=description:
        raise ValueError('Mutalyzer did not confirm the event model request.')
    model=payload.get('delins_model')
    if not isinstance(model,dict) or model.get('coordinate_system')!='i':
        raise ValueError('Mutalyzer returned no internal genomic event model.')
    if model.get('reference',{}).get('id')!=reference:
        raise _IdentityConflict('The returned genomic reference differs from the source assembly.')
    variants=model.get('variants')
    if not isinstance(variants,list) or len(variants)!=1 or not isinstance(variants[0],dict):
        raise ValueError('One fully specified genomic event is required.')
    variant=variants[0];location=variant.get('location',{})
    start=location.get('start',{}).get('position');end=location.get('end',{}).get('position')
    inserted=variant.get('inserted')
    if (type(start) is not int or type(end) is not int or not 0<=start<=end
            or not isinstance(inserted,list) or any(not isinstance(item,dict)
            or not isinstance(item.get('sequence'),str) or not re.fullmatch('[ACGT]*',item['sequence']) for item in inserted)):
        raise ValueError('The genomic event model lacks exact positions or inserted sequence.')
    return reference,start,end,''.join(item['sequence'] for item in inserted)


def _genomic_projection(http,data: dict,reference: str,checks: dict) -> str:
    description=data['normalized_description']
    if description.startswith(reference+':g.'):
        return description
    transcript=_transcript(description)
    if description.startswith(reference+'('):
        equivalents=data.get('equivalent_descriptions',{})
        rows=equivalents.get('g',[]) if isinstance(equivalents,dict) else []
        choices={row.get('description') for row in rows if isinstance(row,dict)
            and isinstance(row.get('description'),str) and row['description'].startswith(reference+':g.')}
        if len(choices)==1:return choices.pop()
        raise ValueError('No unique GRCh37 genomic equivalent was returned.')
    if not transcript:
        raise _IdentityConflict('The normalized reference differs from the source GRCh37 reference.')
    # Official Mapper examples use a named assembly and an exact selector; never
    # replace an NM accession while retaining a cDNA position from another one.
    # https://mutalyzer.readthedocs.io/en/latest/usage.html#the-mapper
    response=http.get('https://mutalyzer.nl/api/map/',params={'description':description,
        'reference_id':'GRCh37','selector_id':transcript,'filter_out':'true'},timeout=45)
    response.raise_for_status();mapping=response.json()
    checks.setdefault('genomic_mappings',{})[description]=mapping
    if not isinstance(mapping,dict) or type(mapping.get('ref_seq_differences')) is not bool:
        raise ValueError('Genomic mapping did not describe reference-sequence differences.')
    mapped=mapping.get('mapped_description');genomic=mapping.get('genomic_description')
    if (not isinstance(mapped,str) or not mapped.startswith(f'{reference}({transcript}):')
            or not isinstance(genomic,str) or not genomic.startswith(reference+':g.')):
        raise _IdentityConflict('The mapped transcript or genomic assembly differs from the source.')
    if mapping['ref_seq_differences']:
        # RefSeq and assembly sequences can differ outside the tested event.
        # The documented mapper filters those differences; independently check
        # that filtered description on the exact genomic transcript before the
        # caller compares its sequence event to the explicit source REF/ALT.
        if mapping.get('filtered_variants') is not True:
            raise ValueError('Genomic mapping did not filter reference-sequence differences.')
        contextual=_normalize_description(http,mapped,'genomic_transcript_grch37')['normalization']
        checks.setdefault('mapping_context_checks',{})[mapped]=contextual
        contextual_name=contextual.get('normalized_description','')
        if (contextual.get('errors') or not isinstance(contextual.get('normalized_model'),dict)
                or contextual.get('input_description')!=mapped
                or not isinstance(contextual_name,str) or not contextual_name.startswith(f'{reference}({transcript}):')
                or _transcript(contextual_name)!=transcript
                or contextual.get('gene_id')!=data.get('gene_id') or not data.get('gene_id')):
            raise _IdentityConflict('The filtered mapping could not be validated on the exact genomic transcript.')
        if _genomic_projection(http,contextual,reference,checks)!=genomic:
            raise _IdentityConflict('The independently checked mapping describes a different genomic event.')
    return genomic


def _assess_normalization(v: Variant,http,result: dict,*,reference_identity=None) -> None:
    assessment=dict(status='Review required',reason='Independent genomic identity has not been confirmed.',
        suggested_hgvs='',genomic_hgvs='',source_genomic_query='',identity_confirmed=False,candidates=[])
    result['nomenclature_assessment']=assessment
    assessment['retryable']=any(result.get(key) is True for key in (
        'mapping_retryable','genomic_normalization_retryable','contextual_normalization_retryable'))
    primary=result['normalization'];original=result['original'];errors=primary.get('errors') or []
    validated_input=original;contextual=False
    if errors:
        context=result.get('contextual_normalization')
        if isinstance(context,dict):
            primary=context['normalization'];validated_input=context['original'];contextual=True
            errors=primary.get('errors') or []
        if errors:
            codes={item.get('code') for item in errors if isinstance(item,dict)}
            assessment['status']='Conflict' if 'ESEQUENCEMISMATCH' in codes else 'Review required'
            assessment['reason']='The input description failed reference or HGVS validation; review the retained source errors.'
            return
    if (not isinstance(primary.get('normalized_model'),dict)
            or primary.get('input_description')!=validated_input):
        assessment['reason']='Mutalyzer returned insufficient structured data for independent identity validation.'
        return
    if not v.gene or ',' in v.gene or ',' in v.transcript:
        assessment['reason']='Resolve the source gene and transcript before selecting a nomenclature candidate.'
        return
    primary_name=primary.get('normalized_description')
    if not isinstance(primary_name,str) or not _FULL_HGVS.fullmatch(primary_name):
        assessment['reason']='The normalized description is incomplete or unsupported.'
        return
    if contextual and primary_name.split(':',1)[0]!=validated_input.split(':',1)[0]:
        assessment.update(status='Conflict',reason='The normalized intronic genomic reference or transcript version differs from the input context.')
        return
    requested_transcript=_transcript(original)
    returned_transcript=_transcript(primary_name)
    if requested_transcript and requested_transcript!=returned_transcript:
        assessment.update(status='Conflict',reason='The normalized transcript accession or version differs from the input.')
        return
    if (not v.corrected_hgvs and requested_transcript and v.transcript
            and re.fullmatch(r'(?:NM|NR)_\d+\.\d+',v.transcript) and v.transcript!=requested_transcript):
        assessment.update(status='Conflict',reason='The complete input HGVS and source transcript identify different references.')
        return
    returned_gene=primary.get('gene_id')
    if isinstance(returned_gene,str) and returned_gene and returned_gene!=v.gene:
        assessment.update(status='Conflict',reason='The normalized transcript belongs to a different gene than the source.')
        return
    if (not returned_gene and isinstance(reference_identity,dict)
            and reference_identity.get('status')=='resolved' and reference_identity.get('source') in {'NCBI RefSeq','Mutalyzer RefSeq'}
            and reference_identity.get('transcript')==returned_transcript==requested_transcript==v.transcript
            and reference_identity.get('gene')==v.gene):
        returned_gene=reference_identity['gene']
        result['reference_identity']=dict(reference_identity)
    checks={};result['genomic_identity_check']=checks
    try:
        query,source_description=_source_allele_description(v)
        assessment['source_genomic_query']=query
        source=({key:value for key,value in result.items() if key in {'original','query_basis','normalization'}}
            if original==source_description else result.get('genomic_normalization'))
        if not isinstance(source,dict) or source.get('original')!=source_description:
            source=_normalize_description(http,source_description,'genomic_grch37')
        checks['source_allele_normalization']=source
        genomic=source['normalization']
        if genomic.get('errors'):
            raise _IdentityConflict('The explicit source REF/ALT failed genomic reference validation.')
        if genomic.get('input_description')!=source_description:
            raise ValueError('The source genomic allele request was not confirmed.')
        reference=source_description.split(':',1)[0]
        canonical=genomic.get('normalized_description')
        if not isinstance(canonical,str) or not canonical.startswith(reference+':g.'):
            raise _IdentityConflict('The source alleles did not normalize on the requested GRCh37 reference.')
        assessment['genomic_hgvs']=canonical
        model_cache={}
        def identity(description):
            if description not in model_cache:
                model_cache[description]=_delins_identity(http,description,reference,checks)
            return model_cache[description]
        expected=identity(canonical)
        projection=_genomic_projection(http,primary,reference,checks)
        projected=source if projection==source_description else (
            {'normalization':genomic} if projection==canonical else _normalize_description(http,projection,'genomic_grch37'))
        checks['query_genomic_normalization']=projected
        if projected['normalization'].get('errors'):
            raise _IdentityConflict('The normalized input could not be confirmed on the source genome.')
        projected_name=projected['normalization'].get('normalized_description')
        if not isinstance(projected_name,str) or identity(projected_name)!=expected:
            raise _IdentityConflict('The normalized input describes a different genomic sequence event than the source alleles.')
        transcript=_transcript(primary_name)
        if transcript and returned_gene!=v.gene:
            raise ValueError('The source transcript gene could not be confirmed.')
        candidates=[dict(description=canonical,label='GRCh37 genomic',transcript='')]
        suggested=canonical
        if transcript:
            candidates.insert(0,dict(description=primary_name,label='Source transcript',transcript=transcript))
            suggested=primary_name
        target=MANE_TARGETS.get(v.gene)
        if target and target[0]==transcript:
            mapped=result.get('mapping',{}).get('mapped_description')
            if not isinstance(mapped,str):
                raise ValueError('The required MANE transcript mapping is not confirmed.')
            mapped_data=_normalize_description(http,mapped,'full_hgvs')['normalization']
            checks['mane_normalization']=mapped_data
            if mapped_data.get('errors') or mapped_data.get('gene_id')!=v.gene or _transcript(mapped_data.get('normalized_description',''))!=target[1]:
                raise _IdentityConflict('The MANE candidate gene or transcript version differs from the target.')
            mane_g=_genomic_projection(http,mapped_data,reference,checks)
            mane_normalized=_normalize_description(http,mane_g,'genomic_grch37')['normalization']
            if mane_normalized.get('errors') or identity(mane_normalized.get('normalized_description',''))!=expected:
                raise _IdentityConflict('The MANE candidate describes a different genomic sequence event.')
            suggested=mapped_data['normalized_description']
            candidates.insert(0,dict(description=suggested,label='MANE transcript',transcript=target[1]))
        assessment.update(status='Unchanged' if suggested==original else 'Normalized',
            reason='The normalized sequence event matches the explicit GRCh37 source alleles. Review before applying.',
            identity_confirmed=True,suggested_hgvs=suggested,candidates=candidates)
        if not transcript:
            assessment['reason']+=' No transcript was inferred from the equivalent-description list.'
        if contextual:
            assessment['reason']='The original transcript reference cannot validate this intronic or out-of-boundary position. The exact transcript in GRCh37 genomic context matches the explicit source alleles. Review before applying.'
        checks['matched_event']=dict(reference=expected[0],start=expected[1],end=expected[2],inserted=expected[3])
    except _IdentityConflict as exc:
        assessment.update(status='Conflict',reason=str(exc))
    except (requests.RequestException,ValueError,KeyError,TypeError,AttributeError) as exc:
        assessment['reason']=f'Independent identity validation requires review ({type(exc).__name__}).'
        if isinstance(exc,requests.RequestException):assessment['retryable']=True


class _CheckpointHttp:
    def __init__(self,http,checkpoint):self.http=http;self.checkpoint=checkpoint
    def get(self,*args,**kwargs):
        self.checkpoint()
        result=self.http.get(*args,**kwargs)
        self.checkpoint()
        return result
    def close(self):self.http.close()


def normalize_variant(v: Variant, http=None, *, checkpoint=None,reference_identity=None) -> dict:
    description, basis = _normalization_query(v)
    owned_session = http is None
    if owned_session:
        http = system_trust_session()
    if checkpoint is not None:http=_CheckpointHttp(http,checkpoint)
    try:
        result = _normalize_description(http, description, basis)
        data = result['normalization']
        _intronic_genomic_candidate(v, http, result)
        _intronic_context_normalization(v, http, result)
        target = MANE_TARGETS.get(v.gene)
        if target and target[0] in v.transcript and not data.get('errors'):
            _map_normalization(http, result, target[1])
        _assess_normalization(v,http,result,reference_identity=reference_identity)
        return result
    finally:
        if owned_session:
            http.close()


def apply_confirmed_normalization(v: Variant, result: dict) -> bool:
    """Use an independently checked new name; retain every imported field.

    Only the candidate validated against the explicit source sequence event may
    be applied. The API's equivalent-description list alone is insufficient.
    """
    assessment=result.get('nomenclature_assessment',{})
    adopt_genomic=(isinstance(assessment,dict) and assessment.get('status')=='Unchanged'
        and result.get('query_basis')=='genomic_grch37' and not v.transcript and not v.corrected_hgvs
        and ('delins' in v.coding.lower() or v.kind.replace(' ','').lower()=='complex'))
    if (not isinstance(assessment,dict) or (assessment.get('status')!='Normalized' and not adopt_genomic)
            or assessment.get('identity_confirmed') is not True
            or not v.gene or ',' in v.gene or ',' in v.transcript):
        return False
    suggested=assessment.get('suggested_hgvs')
    if not isinstance(suggested,str) or not _FULL_HGVS.fullmatch(suggested):
        return False
    try:
        original,_=_normalization_query(v)
        genomic=genomic_query(v)
    except ValueError:
        return False
    if (result.get('original')!=original or (suggested==original and not adopt_genomic)
            or assessment.get('source_genomic_query')!=genomic):
        return False
    checks=result.get('genomic_identity_check')
    if not isinstance(checks,dict):return False
    event=checks.get('matched_event',{})
    chrom=genomic.removeprefix('chr').split('-',1)[0]
    if (not isinstance(event,dict) or event.get('reference')!=_GRCH37_REFERENCES.get(chrom)
            or not isinstance(event.get('start'),int) or not isinstance(event.get('end'),int)
            or not 0<=event['start']<=event['end'] or not isinstance(event.get('inserted'),str)):
        return False
    candidates=assessment.get('candidates',[])
    if not isinstance(candidates,list):return False
    candidate=next((item for item in candidates if isinstance(item,dict) and item.get('description')==suggested),None)
    if not candidate:return False
    requested_transcript=_transcript(original);target_transcript=_transcript(suggested)
    if target_transcript and target_transcript!=requested_transcript:
        target=MANE_TARGETS.get(v.gene)
        if (not target or target!=(requested_transcript,target_transcript)
                or candidate.get('label')!='MANE transcript'):
            return False
    from .annotations import refresh_annotation_proof
    v.corrected_hgvs=suggested;v.controlled_genomic=genomic;v.nomenclature_verified=True
    refresh_annotation_proof(v)
    result['nomenclature_application']={'applied':True,'from_hgvs':original,
        'to_hgvs':suggested,'source_genomic_query':genomic}
    if adopt_genomic:result['nomenclature_application']['adopted_genomic']=True
    return True


def retain_confirmed_normalization(v: Variant, result: dict, tissue: str) -> bool:
    """Retain an applied name only after a fresh, independently checked recheck."""
    previous=v.evidence.get('Mutalyzer',{})
    if (previous.get('status')!='verified' or previous.get('fingerprint')!=v.fingerprint(tissue)
            or not v.nomenclature_verified or not v.corrected_hgvs):return False
    old_raw=previous.get('raw',{});application=old_raw.get('nomenclature_application',{})
    checked=result.get('nomenclature_assessment',{});normalization=result.get('normalization',{})
    if not all(isinstance(value,dict) for value in (application,checked,normalization)):return False
    if (application.get('applied') is not True or application.get('to_hgvs')!=v.corrected_hgvs
            or checked.get('status')!='Unchanged' or checked.get('identity_confirmed') is not True
            or result.get('original')!=v.corrected_hgvs
            or checked.get('suggested_hgvs')!=v.corrected_hgvs
            or normalization.get('normalized_description')!=v.corrected_hgvs
            or normalization.get('errors')):return False
    try:genomic=genomic_query(v)
    except ValueError:return False
    if checked.get('source_genomic_query')!=genomic or application.get('source_genomic_query')!=genomic:return False
    old_checks=old_raw.get('genomic_identity_check');new_checks=result.get('genomic_identity_check')
    if not isinstance(old_checks,dict) or not isinstance(new_checks,dict):return False
    event=old_checks.get('matched_event')
    if not isinstance(event,dict) or not event or new_checks.get('matched_event')!=event:return False
    result['nomenclature_application']=dict(application)
    return True


def normalization_unchanged(v: Variant, result: dict) -> bool:
    assessment=result.get('nomenclature_assessment',{})
    try:original,_=_normalization_query(v);genomic=genomic_query(v)
    except ValueError:return False
    data=result.get('normalization',{})
    return (assessment.get('status')=='Unchanged' and assessment.get('identity_confirmed') is True
        and assessment.get('suggested_hgvs')==result.get('original')==original
        and assessment.get('source_genomic_query')==genomic
        and data.get('normalized_description')==original and not data.get('errors')
        and bool(result.get('genomic_identity_check',{}).get('matched_event')))


def confirmed_protein(v: Variant) -> str:
    """Use only a current, same-event normalizer prediction on this transcript."""
    if not v.nomenclature_verified or not v.corrected_hgvs:return ''
    item=v.evidence.get('Mutalyzer',{})
    raw=item.get('raw',{}) if item.get('fingerprint')==v.fingerprint(item.get('tissue','Other')) else {}
    if not raw:
        from .annotations import annotation_resolution_current
        if annotation_resolution_current(v):raw=v.raw['_annotation_resolution'].get('normalization',{})
    assessment=raw.get('nomenclature_assessment',{})
    data=raw.get('contextual_normalization',{}).get('normalization') or raw.get('normalization',{})
    if (assessment.get('identity_confirmed') is not True or assessment.get('status') not in {'Normalized','Unchanged'}
            or assessment.get('suggested_hgvs')!=v.corrected_hgvs
            or data.get('normalized_description')!=v.corrected_hgvs or data.get('gene_id')!=v.gene
            or data.get('errors')):return ''
    try:
        if assessment.get('source_genomic_query')!=genomic_query(v):return ''
    except ValueError:return ''
    transcript=_transcript(v.corrected_hgvs)
    name=data.get('protein',{}).get('description','')
    if not isinstance(name,str) or not transcript:return ''
    match=re.fullmatch(r'(?:NC_\d+\.\d+\()?'+re.escape(transcript)
        +r'\(NP_\d+\.\d+\)\)?:('r'p\.[A-Za-z0-9_*?()=;\[\].]+)',name)
    return match[1] if match else ''


def display_identity(v: Variant) -> tuple[str,str,str]:
    """Present a checked nucleotide identity without inferring a protein name."""
    if v.nomenclature_verified and v.corrected_hgvs:
        return v.corrected_hgvs,confirmed_protein(v),_transcript(v.corrected_hgvs)
    return v.coding,v.protein,v.transcript


def _trim_spliceai_alleles(pos: int, ref: str, alt: str) -> tuple[int, str, str]:
    # Follow Broad's documented spelling exactly; preserve the VCF anchor.
    # https://github.com/broadinstitute/SpliceAI-lookup/blob/master/google_cloud_run_services/server.py
    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
        pos, ref, alt = pos + 1, ref[1:], alt[1:]
    return pos, ref, alt


def minimal_genomic_query(v: Variant) -> str:
    """Trim shared VCF padding while retaining indel anchors and source identity.

    This does not left-align repeats or overwrite the imported/reviewed allele.
    """
    chrom, pos, ref, alt = genomic_query(v).split('-')
    pos, ref, alt = _trim_spliceai_alleles(int(pos), ref, alt)
    return f'{chrom}-{pos}-{ref}-{alt}'


def validate_spliceai_response(data: dict, variant: str) -> str:
    """Confirm requested hg19 settings, allele identity and usable prediction rows.

    Return the actual scored chr-pos-REF-ALT spelling. Broad may trim shared
    bases while preserving the VCF anchor; delta positions refer to that spelling.
    An empty score list is valid but is not evidence of a prediction match.
    """
    if not isinstance(data, dict):
        raise ValueError('SpliceAI returned an unexpected response format.')
    if data.get('error') or data.get('errors'):
        raise ValueError(str(data.get('error') or data.get('errors')))
    if data.get('variant') != variant:
        raise ValueError('SpliceAI did not confirm the requested variant.')
    if any(str(data.get(key)) != '37' for key in ('hg', 'genomeVersion')):
        raise ValueError('SpliceAI did not confirm GRCh37 / hg19.')
    if data.get('distance') != 500 or data.get('mask') != 1:
        raise ValueError('SpliceAI did not confirm distance=500 and mask=1.')
    chrom, pos, ref, alt = variant.removeprefix('chr').split('-')
    returned = (str(data.get('chrom')).removeprefix('chr'), data.get('pos'), data.get('ref'), data.get('alt'))
    original = (chrom, int(pos), ref, alt)
    trimmed = (chrom, *_trim_spliceai_alleles(int(pos), ref, alt))
    if returned not in (original, trimmed):
        raise ValueError('SpliceAI scored alleles differ from the requested variant.')
    rows = data.get('scores')
    if not isinstance(rows, list):
        raise ValueError('SpliceAI returned an unexpected score format.')
    for row in rows:
        if not isinstance(row, dict) or not all(key in row for key in _SPLICE_SCORES + _SPLICE_POSITIONS):
            raise ValueError('SpliceAI returned incomplete prediction scores.')
        try:
            scores = [float(row[key]) for key in _SPLICE_SCORES]
            positions = [float(row[key]) for key in _SPLICE_POSITIONS]
        except (TypeError, ValueError):
            raise ValueError('SpliceAI returned invalid prediction values.') from None
        if any(not math.isfinite(score) or not 0 <= score <= 1 for score in scores) or any(
                not math.isfinite(pos) or not pos.is_integer() for pos in positions):
            raise ValueError('SpliceAI returned invalid prediction values.')
    return f'chr{returned[0]}-{returned[1]}-{returned[2]}-{returned[3]}'


def spliceai_variant(v: Variant, http=None) -> dict:
    variant = genomic_query(v)
    owned_session = http is None
    if owned_session:
        http = system_trust_session()
    try:
        response = http.get('https://spliceai-37-xwkwwwxdwq-uc.a.run.app/spliceai/', params={
            'hg': 37, 'variant': variant, 'distance': 500, 'mask': 1}, timeout=120)
        response.raise_for_status()
        data = response.json()
        scored = validate_spliceai_response(data, variant)
        return {'query': variant, 'hg': 37, 'distance': 500, 'mask': 1,
                'scored_variant': scored, 'response': data}
    finally:
        if owned_session:
            http.close()


def spliceai_summary(data: dict) -> str:
    rows=data.get('response',{}).get('scores',[])
    parts=[]
    for row in rows:
        values=[f'{key}={row[key]}' for key in _SPLICE_SCORES + _SPLICE_POSITIONS if key in row]
        gene = row.get('g_name') or row.get('gene_name') or row.get('symbol') or 'Unlabelled gene'
        transcript = row.get('t_id') or row.get('transcript_id') or ''
        refseq = row.get('t_refseq_ids') or []
        label = str(gene) + (f' / {transcript}' if transcript else '')
        if isinstance(refseq, list) and refseq:
            label += ' (' + ', '.join(str(item) for item in refseq) + ')'
        if values:parts.append(label+': '+', '.join(values))
    return '\n'.join(parts) or 'No scores returned; manual review required.'
