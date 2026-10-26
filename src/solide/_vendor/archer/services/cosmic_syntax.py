"""Exact native COSMIC syntax selection; never accept a fuzzy search row."""
import re
from urllib.parse import urlsplit,parse_qs
from .genomic_notation import normalize_vcf_change


def _syntax_key(value):
    """HGVS permits the deleted/duplicated bases to be omitted, not moved."""
    value=value.strip()
    match=re.fullmatch(r'(c\.([0-9]+)(?:_([0-9]+))?(?:del|dup))([ACGT]+)',value)
    if match and len(match[4])==int(match[3] or match[2])-int(match[2])+1:
        return match[1]
    return value


def gene_cdna_query(variant):
    change=variant.hgvsc.rsplit(':',1)[-1].strip()
    if (re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*',variant.symbol)
            and re.fullmatch(r'c\.[0-9*()_+\-ACGTNacgtn;\[\]delinsupv>=?.]+',change)):
        return variant.symbol+':'+change
    return ''


def syntax_candidates(rows,variant):
    query=gene_cdna_query(variant)
    if not query:return []
    gene,change=query.split(':',1);candidates=[]
    for row in rows:
        url=row.get('url','');address=urlsplit(url)
        if (row.get('gene','').strip().casefold()!=gene.casefold()
                or _syntax_key(row.get('syntax',''))!=_syntax_key(change)):continue
        if (address.scheme!='https' or address.hostname!='cancer.sanger.ac.uk'
                or address.path!='/cosmic/mutation/overview'
                or not re.fullmatch(r'\d+',parse_qs(address.query).get('id',[''])[0])):continue
        if url not in candidates:candidates.append(url)
    return candidates


def syntax_page_identity(body,variant):
    """Require gene, exact CDS syntax and matching returned GRCh37 event span.

    COSMIC's native overview does not expose genomic REF/ALT. This is a source
    gene/CDS match with a checked coordinate span, not independent allele proof.
    """
    query=gene_cdna_query(variant);event=normalize_vcf_change(variant.genomic_location,variant.ref_allele,variant.alt_allele)
    gene=re.search(r'\bGene name\s+([A-Za-z0-9-]+)\b',body)
    coding=re.search(r'\bCDS mutation\s+(c\.\S+)',body)
    locus=re.search(r'\bGenomic coordinates\s+GRCh37,\s*(?:chr)?([0-9XYM]+):(\d+)\.\.(\d+)\b',body)
    return bool(query and event and gene and coding and locus and gene[1].casefold()==variant.symbol.casefold()
        and _syntax_key(coding[1])==_syntax_key(query.split(':',1)[1]) and locus[1]==event.chromosome
        and int(locus[2])==event.start and int(locus[3])==event.end)
