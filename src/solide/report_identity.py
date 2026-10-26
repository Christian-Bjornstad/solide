"""Copyable reporting notation from the reviewed variant identity."""
import re
from .nomenclature import display_identity
from ._vendor.archer.services.browser_review import _cosmic_identifiers


def report_variant_text(v,session=None):
    coding,protein,transcript=display_identity(v)
    reference=transcript
    if ':' in coding:
        prefix,coding=coding.rsplit(':',1)
        if not reference and re.fullmatch(r'(?:NM|NR|NC|NG)_\d+\.\d+',prefix):reference=prefix
    identity=f'{reference}({v.gene})' if reference else v.gene
    text=f'{identity}: {coding}' if coding else identity
    if protein not in ('','p.?','p.(?)','?'):text+='; '+protein
    identifiers=_cosmic_identifiers(v.variant_id)
    item=v.evidence.get('COSMIC',{})
    if session is not None and item:
        from .evidence import assess_evidence
        assessment=assess_evidence(v,item,session).label
        if assessment in {'Verified match','Review match'}:
            identifiers=_cosmic_identifiers(item.get('accession','')) or identifiers
        elif assessment=='Identity mismatch':identifiers=[]
    identifiers=[value for value in identifiers if value.startswith('COSM')] or identifiers
    if identifiers:text+=' ('+', '.join(identifiers)+')'
    return text
