"""Selectable transcript interpretations of one immutable genomic source row."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re

from .models import Variant

_MAX_ALTERNATIVES = 64


def annotation_tokens(value: str, *, references=False) -> list[str]:
    """Separate top-level entries, preserving HGVS allele/uncertainty syntax."""
    if not isinstance(value,str):raise ValueError('Annotasjonen må være tekst.')
    if len(value)>32767:raise ValueError('Annotasjonen er for lang til automatisk kobling.')
    stack=[];parts=[];start=0
    for index,char in enumerate(value):
        if char in '[(':stack.append(char)
        elif char in '])':
            if not stack or stack.pop()!=({']':'[',')':'('}[char]):
                raise ValueError('Ubalanserte parenteser i annotasjonen.')
        elif not stack and (char==',' or references and char in ';|'):
            parts.append(value[start:index].strip());start=index+1
    if stack:raise ValueError('Ubalanserte parenteser i annotasjonen.')
    parts.append(value[start:].strip())
    if len(parts)>_MAX_ALTERNATIVES:raise ValueError('For mange annotasjoner i én kilderad.')
    return parts


def _parts(value: str) -> list[str]:
    return annotation_tokens(value)


def _aligned_names(value: str, transcripts: list[str], *, protein=False) -> tuple[list[str], str]:
    """Keep positional lists; assign a singleton only to one compatible reference."""
    count = len(transcripts)
    if not value.strip():
        return [''] * count, ''
    parts = _parts(value)
    if len(parts) == count:
        return parts, ''
    if len(parts) != 1:
        return ['']*count, 'Variantnavn avklares mot transkript og genomisk endring ved søk.'
    # Ion Reporter omits the noncoding entry in some NM/NR overlaps. A c./p.
    # name cannot belong to NR; never broadcast it over multiple NM references.
    prefix = 'p.' if protein else 'c.'
    coding = [i for i, transcript in enumerate(transcripts) if transcript.startswith('NM_')]
    noncoding = all(transcript.startswith(('NM_', 'NR_')) for transcript in transcripts)
    if parts[0].startswith(prefix) and len(coding) == 1 and noncoding:
        names = [''] * count
        names[coding[0]] = parts[0]
        return names, 'Enkelt c./p.-navn knyttet til eneste kodende NM-transkript; NR står uten c./p.-navn.'
    # These remain candidate names; selected-run resolution must prove each
    # reference/gene/event association, including equal-length positional lists.
    return ['']*count, 'Variantnavn avklares mot transkript og genomisk endring ved søk.'


def split_annotations(variant: Variant) -> list[Variant]:
    """Expand aligned annotations, never a Cartesian product or a second allele."""
    if variant.raw.get('_annotation_issue'):return [variant]
    if variant.kind.replace(' ','').lower() in {'cnv','fusion','rnaexonvariant','rnaexontiles'}:
        return [variant]
    try:
        genes=annotation_tokens(variant.gene,references=True)
        source_transcripts=annotation_tokens(variant.transcript,references=True)
        names=annotation_tokens(variant.coding)
        proteins=annotation_tokens(variant.protein)
        if max(map(len,(genes,source_transcripts,names,proteins)))==1:return [variant]
        transcripts=list(dict.fromkeys(source_transcripts))
        count = len(transcripts)
        if not 1 <= count <= _MAX_ALTERNATIVES:
            raise ValueError('Flere annotasjoner krever en avgrenset liste med transkripter.')
        if len(genes) == 1 and genes[0]:
            genes *= count
        if len(genes)!=count or not all(genes):genes=['']*count
        if not all(re.fullmatch(r'(?:NM_|NR_)\d+\.\d+', transcript) for transcript in transcripts):
            raise ValueError('Hver annotasjon må ha ett versjonert transkript.')
        if ',' in variant.ref or ',' in variant.alt:
            raise ValueError('Flere alleler må avklares før annotasjonene kan deles.')
        coding, coding_note = _aligned_names(variant.coding, transcripts)
        protein, protein_note = _aligned_names(variant.protein, transcripts, protein=True)
        for index,transcript in enumerate(transcripts):
            qualified=[name for name in names if name.startswith(transcript+':')]
            if qualified:coding[index]=qualified[0] if len(set(qualified))==1 else ''
            elif ':' in coding[index]:coding[index]=''
            if transcript.startswith('NR_'):
                if coding[index].removeprefix(transcript+':').startswith('c.'):coding[index]=''
                protein[index]=''
    except ValueError as exc:
        variant.raw['_annotation_issue'] = str(exc)
        return [variant]

    children = []
    for index, (gene, transcript, name, amino) in enumerate(zip(genes, transcripts, coding, protein)):
        child = deepcopy(variant)
        child.id = hashlib.sha256(f'{variant.id}:annotation:{index}'.encode()).hexdigest()[:24]
        child.gene, child.transcript, child.coding, child.protein = gene, transcript, name, amino
        child.selected = False
        child.raw['_annotation_group'] = {
            'parent_id': variant.id, 'index': index, 'count': count,
            'gene': variant.gene, 'transcript': variant.transcript,
            'coding': variant.coding, 'protein': variant.protein,
            'pairing': 'candidates', 'note': coding_note or protein_note,
            'coding_candidates':names,'protein_candidates':proteins,
        }
        children.append(child)
    return children


def annotation_group(variant: Variant) -> dict:
    value = variant.raw.get('_annotation_group')
    return value if isinstance(value, dict) and value.get('parent_id') else {}


def require_resolved_annotations(variant: Variant) -> None:
    if needs_annotation_resolution(variant) and not annotation_resolution_current(variant):
        reason=variant.raw.get('_annotation_resolution',{}).get('reason') or variant.raw.get('_annotation_issue')
        raise ValueError(reason or 'Annotasjoner må kontrolleres mot gen, transkript og genomisk endring før søk.')


def needs_annotation_resolution(variant: Variant) -> bool:
    return bool(annotation_group(variant) or variant.raw.get('_annotation_issue'))


def annotation_fingerprint(variant: Variant) -> str:
    source=[variant.id,variant.analysis_id,variant.source_hash,variant.source_file,
            variant.source_row,variant.raw.get('_sheet',''),variant.raw.get('_source_row_id',''),
            annotation_group(variant),variant.raw.get('_annotation_column_repair'),
            variant.raw.get('_columns'),variant.raw.get('_values'),variant.nomenclature_verified,
            variant.raw.get('_annotation_issue')]
    return hashlib.sha256(json.dumps([variant.fingerprint(''),source],ensure_ascii=False,default=str).encode()).hexdigest()


def annotation_resolution_current(variant: Variant) -> bool:
    proof=variant.raw.get('_annotation_resolution',{})
    return (isinstance(proof,dict) and proof.get('status')=='verified'
            and proof.get('fingerprint')==annotation_fingerprint(variant))


def refresh_annotation_proof(variant: Variant) -> None:
    """Call only after independently proven same-event normalization."""
    proof=variant.raw.get('_annotation_resolution',{})
    if isinstance(proof,dict) and proof.get('status')=='verified':
        proof['fingerprint']=annotation_fingerprint(variant)


def source_row_groups(variants: list[Variant]) -> list[list[Variant]]:
    """Group only app-created alternatives, keeping unrelated equal rows distinct."""
    groups = []
    indices = {}
    for variant in variants:
        marker = annotation_group(variant)
        if not marker:
            groups.append([variant])
            continue
        key = (variant.analysis_id, variant.source_hash, variant.source_file,
               variant.raw.get('_sheet', ''), variant.source_row, marker['parent_id'])
        if key not in indices:
            indices[key] = len(groups)
            groups.append([])
        groups[indices[key]].append(variant)
    return groups
