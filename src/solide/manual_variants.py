"""User-entered interpretations, kept separate from imported source events."""
from __future__ import annotations
import re
from .models import Session,Variant
from .localtime import oslo_now


def validate_manual_fields(*,transcript,coding,protein='',gene='',locus=''):
    fields=dict(transcript=transcript,coding=coding,protein=protein,gene=gene,locus=locus)
    if any(not isinstance(value,str) or len(value)>500 for value in fields.values()):
        raise ValueError('Variantfeltene må være tekst på høyst 500 tegn.')
    fields={key:value.strip() for key,value in fields.items()}
    transcript=fields['transcript'];coding=fields['coding']
    if not re.fullmatch(r'(?:NM|NR)_\d{6,9}\.[1-9]\d*',transcript):
        raise ValueError('Oppgi ett NM-/NR-nummer med versjon, for eksempel NM_000314.8.')
    if ':' in coding:
        prefix,coding=coding.rsplit(':',1)
        if prefix!=transcript:
            raise ValueError('Transkriptet i nukleotidendringen må være likt transkriptfeltet.')
    coordinate='n' if transcript.startswith('NR_') else 'c'
    if (not re.fullmatch(coordinate+r'\.[0-9*+_\-ACGTNacgtn>delinsup]+',coding)
            or not re.search(r'>|del|ins|dup',coding)):
        raise ValueError('Oppgi én nukleotidendring, for eksempel c.19G>A eller c.19_20delinsAT.')
    fields['coding']=coding
    if fields['gene'] and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*',fields['gene']):
        raise ValueError('Oppgi ett gennavn, eller la feltet stå tomt for kontroll mot transkriptet.')
    if fields['protein'] and not re.fullmatch(r'p\.[A-Za-z0-9_*?()=]+',fields['protein']):
        raise ValueError('Aminosyreendringen må starte med p., eller feltet kan stå tomt.')
    if fields['locus'] and not re.fullmatch(r'(?:chr)?(?:[1-9]|1[0-9]|2[0-2]|X|Y|M):[1-9]\d*',fields['locus'],re.I):
        raise ValueError('Lokus må være kromosom:posisjon, for eksempel chr10:89624245.')
    return fields


def add_manual_variant(session: Session,analysis_id: str,*,transcript: str,coding: str,
                       protein: str='',gene: str='',locus: str='',parent_ids=()) -> Variant:
    fields=validate_manual_fields(transcript=transcript,coding=coding,protein=protein,gene=gene,locus=locus)
    analysis=session.analysis(analysis_id)
    parents=list(dict.fromkeys(parent_ids))
    allowed={v.id for v in session.analysis_variants(analysis_id)}
    if any(parent not in allowed for parent in parents):
        raise ValueError('Alle markerte kilderader må høre til den aktive analysen.')
    coding=fields['coding']
    kind='complex' if 'delins' in coding or 'del' in coding and 'ins' in coding else (
        'del' if 'del' in coding else 'ins' if 'ins' in coding or 'dup' in coding else 'snp')
    created=oslo_now().isoformat()
    v=Variant(patient=analysis.patient,analysis_id=analysis.id,assembly=analysis.assembly,
        kind=kind,call='MANUAL',selected=True,platform='Manual',**fields)
    inputs={**fields,'parent_ids':parents,'created_at':created}
    v.raw={'Type':kind,'Genes':fields['gene'],'Transcript':fields['transcript'],
        'Coding':coding,'Amino Acid Change':fields['protein'],'Locus':fields['locus'],
        'Origin':'Manuelt registrert','Parent row IDs':'; '.join(parents),
        '_manual_variant':inputs,'_source_row_id':v.id}
    session.variants.append(v)
    session.history.append({'event':'manual_variant_added','id':v.id,'analysis_id':analysis.id,
        'time':created,'inputs':inputs.copy()})
    return v
