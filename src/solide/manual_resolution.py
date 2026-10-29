"""Derive a manual HGVS interpretation's alleles on exact public GRCh37 references.

These checks establish a public-reference mapping of the user's interpretation.
They do not prove that the interpretation was observed in the sample or that
nearby source calls are in cis. Parent rows supply provenance, never alleles.
"""
from __future__ import annotations

from copy import deepcopy
import re

import requests

from .annotations import annotation_fingerprint, annotation_resolution_current
from .nomenclature import (
    _FULL_HGVS, _GRCH37_REFERENCES, _delins_identity, _genomic_projection,
    _normalize_description, _source_allele_description, _transcript, genomic_query,
)
from .public_http import public_api_session

_MAX_EVENT = 10_000
_CHROMOSOMES = {reference: chrom for chrom, reference in _GRCH37_REFERENCES.items()}
_RETRYABLE_REFERENCE = {'network_error', 'timeout', 'rate_limited', 'http_error',
                        'invalid_xml', 'oversized_response'}


class _Http:
    """Checkpoint each request; replay identical checks within one resolution."""
    def __init__(self, http, checkpoint):
        self.http, self.checkpoint, self.cache = http, checkpoint, {}

    def get(self, url, **kwargs):
        self.checkpoint()
        key = (url, tuple(sorted(kwargs.get('params', {}).items())))
        if key not in self.cache:
            response = self.http.get(url, **kwargs)
            self.checkpoint()
            self.cache[key] = response
        return self.cache[key]


def _single_name(description):
    if not isinstance(description, str) or len(description) > 20_000:
        raise ValueError('Oppgi én avgrenset, fullstendig HGVS-endring.')
    if not _FULL_HGVS.fullmatch(description):
        raise ValueError('Oppgi ett fullstendig HGVS-navn med versjonert referanse.')
    coordinate = description.split(':', 1)[1]
    if any(char in coordinate for char in '[]();,?='):
        raise ValueError('Usikre posisjoner, flere alleler eller flere hendelser må avklares først.')


def _checked_normalization(http, description, basis, *, transcript='', gene=''):
    _single_name(description)
    result = _normalize_description(http, description, basis)
    _validate_normalization(result, description, transcript=transcript, gene=gene)
    return result


def _validate_normalization(result, description, *, transcript='', gene=''):
    data = result['normalization']
    if (data.get('errors') or data.get('input_description') != description
            or not isinstance(data.get('normalized_model'), dict)):
        raise ValueError('Mutalyzer kunne ikke bekrefte det oppgitte HGVS-navnet.')
    name = data.get('normalized_description')
    _single_name(name)
    if transcript and _transcript(name) != transcript:
        raise ValueError('Normaliseringen endret det eksakte transkriptet.')
    if description.startswith('NC_') and name.split('(', 1)[0].split(':', 1)[0] != description.split('(', 1)[0].split(':', 1)[0]:
        raise ValueError('Normaliseringen endret den eksakte genomiske referansen.')
    if gene and data.get('gene_id') and data['gene_id'] != gene:
        raise ValueError('Normaliseringens gen avviker fra transkriptets bekreftede gen.')


def _manual_normalization(http, description, transcript, gene):
    result = _normalize_description(http, description, 'manual_hgvs')
    data = result['normalization']
    errors = data.get('errors')
    # mRNA has no introns. Use only genomic context explicitly returned for the
    # exact requested transcript and GRCh37; never guess a chromosome from gene.
    if (not description.startswith('NC_') and data.get('input_description') == description
            and isinstance(errors, list) and errors
            and all(isinstance(error, dict) and error.get('code') in {'EINTRONIC', 'EOUTOFBOUNDARY'}
                    for error in errors)):
        references = set()
        for error in errors:
            assemblies = error.get('assemblies', {})
            context = assemblies.get('GRCh37', {}).get(transcript, {})
            if context.get('chr_id') in _CHROMOSOMES:
                references.add(context['chr_id'])
            elif error.get('code') == 'EINTRONIC':
                raise ValueError('Intronsvaret mangler entydig GRCh37-kontekst for eksakt transkript.')
        if len(references) != 1:
            raise ValueError('Ingen entydig GRCh37-kontekst for intron-/grenseposisjonen.')
        contextual = f'{references.pop()}({transcript}):{description.split(":", 1)[1]}'
        result['contextual_normalization'] = _checked_normalization(http, contextual,
            'manual_genomic_transcript_grch37', transcript=transcript, gene=gene)
    else:
        _validate_normalization(result, description, transcript=transcript, gene=gene)
    return result


def _has_uncertainty(value):
    if isinstance(value, dict):
        return any((key in {'uncertain', 'uncertainty'} and bool(item)) or _has_uncertainty(item)
                   for key, item in value.items())
    return isinstance(value, list) and any(_has_uncertainty(item) for item in value)


def _event(http, description, reference, checks):
    event = _delins_identity(http, description, reference, checks)
    payload = checks['delins_responses'][description]
    if _has_uncertainty(payload['delins_model']):
        raise ValueError('Hendelsesmodellen inneholder usikre koordinater eller sekvenser.')
    return event


def _projection(http, data, transcript, checks):
    name = data['normalized_description']
    if name.startswith('NC_'):
        reference = name.split('(', 1)[0]
    else:
        response = http.get('https://mutalyzer.nl/api/map/', params={
            'description': name, 'reference_id': 'GRCh37',
            'selector_id': transcript, 'filter_out': 'true'}, timeout=45)
        response.raise_for_status()
        mapping = response.json()
        if not isinstance(mapping, dict) or mapping.get('errors'):
            raise ValueError('Mutalyzer kunne ikke mappe transkriptet entydig til GRCh37.')
        genomic = mapping.get('genomic_description')
        if not isinstance(genomic, str):
            raise ValueError('Mappingen mangler et genomisk HGVS-navn.')
        reference = genomic.split(':', 1)[0]
    if reference not in _CHROMOSOMES:
        raise ValueError('Den genomiske referansen er ikke en eksakt primær GRCh37-referanse.')
    # This reuses the discovery response and validates exact selector, assembly,
    # and any filtered reference-sequence differences using the existing checker.
    genomic = _genomic_projection(http, data, reference, checks)
    return reference, genomic


def _reference_sequence(http, reference, start, stop, checks):
    """Fetch one forward-strand FASTA interval, with 1-based inclusive bounds.

    EFetch's seq_start/seq_stop/strand parameters are documented at
    https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.EFetch
    Reject an unbounded, redirected, truncated, or differently labelled record.
    """
    if not 1 <= start <= stop or stop - start + 1 > _MAX_EVENT + 1:
        raise ValueError('Referanseintervallet er for stort eller ugyldig.')
    response = http.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi', params={
        'db': 'nuccore', 'id': reference, 'rettype': 'fasta', 'retmode': 'text',
        'seq_start': start, 'seq_stop': stop, 'strand': 1, 'tool': 'solide'},
        timeout=30, allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise ValueError('NCBI returnerte ikke det forespurte referanseintervallet.')
    text = response.text
    if len(text) > 64_000:
        raise ValueError('NCBI returnerte et uventet stort referansesvar.')
    lines = text.strip().splitlines()
    token = lines[0].split()[0] if lines else ''
    if token != f'>{reference}:{start}-{stop}':
        raise ValueError('NCBI-svarets accession eller koordinater avviker fra forespørselen.')
    sequence = ''.join(lines[1:]).upper()
    if len(sequence) != stop - start + 1 or not re.fullmatch('[ACGT]+', sequence):
        raise ValueError('Referansesekvensen er ufullstendig eller ikke entydig.')
    checks['reference_sequence'] = dict(source='NCBI RefSeq EFetch', reference=reference,
        start=start, stop=stop, strand=1, sequence=sequence)
    return sequence


def _alleles(http, reference, genomic, event, checks):
    _, start, end, inserted = event
    if end - start > _MAX_EVENT or len(inserted) > _MAX_EVENT:
        raise ValueError('Manuell automatisk mapping støtter høyst 10 000 baser per hendelse.')
    # An explicitly named substitution already contains its REF, validated by
    # Mutalyzer on this exact genomic reference. No reference download is needed.
    snv = re.fullmatch(re.escape(reference) + r':g.([1-9]\d*)([ACGT])>([ACGT])', genomic)
    if snv:
        if (int(snv[1]) - 1, int(snv[1]), snv[3]) != (start, end, inserted):
            raise ValueError('HGVS-navnet og hendelsesmodellen beskriver ulike substitusjoner.')
        position, ref, alt = int(snv[1]), snv[2], inserted
    elif start < end and inserted:
        position = start + 1
        ref = _reference_sequence(http, reference, position, end, checks)
        alt = inserted
    elif start > 0:
        # A deletion/insertion requires an unchanged VCF base to the left.
        position = start
        ref = _reference_sequence(http, reference, position, max(end, start), checks)
        alt = ref[0] + inserted
    else:
        # No left base exists at the start of a chromosome: pad on the right.
        position = 1
        ref = _reference_sequence(http, reference, 1, end + 1, checks)
        alt = inserted + ref[-1]
    if ref == alt:
        raise ValueError('REF og ALT beskriver ingen sekvensendring.')
    return position, ref, alt


def _derived_allele_description(probe, reference):
    # Short alleles include the full REF for the extra Mutalyzer check. Larger
    # deletions already have their REF checked by the bounded exact EFetch
    # interval; omit that sequence in HGVS to keep the GET URL bounded.
    if len(probe.ref) + len(probe.alt) + 100 < 5000:
        return _source_allele_description(probe)
    query = genomic_query(probe)
    position = int(probe.locus.split(':')[1])
    end = position + len(probe.ref) - 1
    location = str(position) if position == end else f'{position}_{end}'
    return query, f'{reference}:g.{location}delins{probe.alt}'


def _locus_matches(locus, chrom, position, event):
    if not locus:
        return
    match = re.fullmatch(r'(?:chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M):([1-9]\d*)', locus, re.I)
    # For indels accept either the explicit VCF anchor or first event base.
    # Insertions use their left flank (the same coordinate as their VCF anchor).
    first_base = event[1] + 1 if event[1] < event[2] else max(1, event[1])
    if not match or match[1].upper() != chrom or int(match[2]) not in {position, first_base}:
        raise ValueError('Oppgitt lokus avviker fra GRCh37-mappingen (VCF-anker eller første endrede base).')


def _protein(data, reference):
    protein, transcript = reference.get('protein', ''), reference['transcript']
    name = data.get('protein', {}).get('description', '')
    if not protein or not isinstance(name, str):
        return ''
    selector = r'\(' + re.escape(protein) + r'\)'
    references = [re.escape(transcript) + selector]
    context = re.fullmatch(r'(NC_\d+\.\d+)\(' + re.escape(transcript) + r'\)',
                           data['normalized_description'].split(':', 1)[0])
    if context:
        nc = re.escape(context[1])
        references.extend([nc + selector, nc + r'\(' + re.escape(transcript) + selector + r'\)'])
    match = re.fullmatch(r'(?:' + '|'.join(references) + r'):(' + r'p\.[A-Za-z0-9_*?()=;\[\].]+)', name)
    return match[1] if match else ''


def resolve_manual_variant(variant, resolver, *, checkpoint=lambda: None, http=None) -> bool:
    """Atomically resolve one manual interpretation; retain all input on failure."""
    if annotation_resolution_current(variant):
        return True
    checkpoint()
    checks = {}
    reference_identity = {}

    def unresolved(reason, *, retryable=False):
        checkpoint()
        variant.raw['_annotation_resolution'] = dict(status='unresolved', reason=reason,
            retryable=retryable, provenance='manual HGVS mapped to GRCh37',
            independent_source_alleles=False, reference=deepcopy(reference_identity), checks=checks)
        return False

    owned = http is None
    try:
        if not isinstance(variant.raw.get('_manual_variant'), dict):
            raise ValueError('Raden mangler den opprinnelige manuelle tolkningen.')
        transcript = variant.transcript
        if not re.fullmatch(r'(?:NM|NR)_\d+\.\d+', transcript):
            raise ValueError('Oppgi ett eksakt, versjonert NM-/NR-transkript.')
        if variant.assembly != 'GRCh37':
            raise ValueError('Manuell mapping krever GRCh37 / hg19.')
        if ',' in variant.ref or ',' in variant.alt:
            raise ValueError('Flere REF-/ALT-alleler må avklares før mapping.')
        if (variant.corrected_hgvs or variant.controlled_genomic) and not variant.nomenclature_verified:
            raise ValueError('Kontroller og godkjenn den lagrede identitetsrettelsen før nytt søk.')
        coding = variant.coding
        description = variant.corrected_hgvs or (coding if ':' in coding else transcript + ':' + coding)
        _single_name(description)
        if _transcript(description) != transcript:
            raise ValueError('HGVS-navnet må bruke det oppgitte eksakte transkriptet.')
        if not description.split(':', 1)[1].startswith('n.' if transcript.startswith('NR_') else 'c.'):
            raise ValueError('HGVS-koordinatsystemet stemmer ikke med NM-/NR-transkriptet.')
        if description.startswith('NC_') and description.split('(', 1)[0] not in _CHROMOSOMES:
            raise ValueError('Oppgitt genomisk referanse er ikke GRCh37.')
        reference_identity = resolver.resolve([transcript]).get(transcript, {})
        checkpoint()
        if (reference_identity.get('status') != 'resolved'
                or reference_identity.get('source') not in {'NCBI RefSeq', 'Mutalyzer RefSeq'}
                or reference_identity.get('transcript') != transcript or not reference_identity.get('gene')):
            return unresolved('Transkriptets eksakte referanse og gen kunne ikke bekreftes.',
                retryable=reference_identity.get('reason') in _RETRYABLE_REFERENCE)
        gene = reference_identity['gene']
        if variant.gene and variant.gene != gene:
            raise ValueError('Oppgitt gen avviker fra transkriptets bekreftede gen.')
        if owned:
            http = public_api_session()
        checked_http = _Http(http, checkpoint)
        result = _manual_normalization(checked_http, description, transcript, gene)
        data = result.get('contextual_normalization', {}).get('normalization') or result['normalization']
        reference, projection = _projection(checked_http, data, transcript, checks)
        genomic_result = _checked_normalization(checked_http, projection, 'manual_genomic_grch37')
        genomic = genomic_result['normalization']['normalized_description']
        if not genomic.startswith(reference + ':g.'):
            raise ValueError('Den normaliserte genomiske referansen avviker fra GRCh37-mappingen.')
        checks['mapped_genomic_normalization'] = genomic_result
        event = _event(checked_http, genomic, reference, checks)
        position, ref, alt = _alleles(checked_http, reference, genomic, event, checks)
        chrom = _CHROMOSOMES[reference]
        # The row's current locus is derived after a successful lookup. Only the
        # locus actually entered by the user constrains later reviewed edits.
        _locus_matches(variant.raw['_manual_variant'].get('locus', ''), chrom, position, event)
        probe = deepcopy(variant)
        probe.gene, probe.locus, probe.ref, probe.alt = gene, f'chr{chrom}:{position}', ref, alt
        probe.corrected_hgvs = probe.controlled_genomic = ''
        probe.nomenclature_verified = False
        derived_query, derived_description = _derived_allele_description(probe, reference)
        if variant.controlled_genomic:
            reviewed_query = genomic_query(variant)
            baseline = deepcopy(variant)
            baseline.corrected_hgvs = baseline.controlled_genomic = ''
            try:
                previous_derived = genomic_query(baseline)
            except ValueError:
                previous_derived = ''
            if reviewed_query != previous_derived and reviewed_query != derived_query:
                raise ValueError('Den lagrede genomiske rettelsen avviker fra HGVS-mappingens REF/ALT.')
        derived = _checked_normalization(checked_http, derived_description, 'manual_derived_alleles')
        derived_name = derived['normalization']['normalized_description']
        if _event(checked_http, derived_name, reference, checks) != event:
            raise ValueError('De avledede REF-/ALT-allelene samsvarer ikke med den mappede hendelsen.')
        checks['derived_allele_normalization'] = derived
        checks['matched_event'] = dict(reference=reference, start=event[1], end=event[2], inserted=event[3])
        result['genomic_identity_check'] = checks
        result['reference_identity'] = deepcopy(reference_identity)
        name = data['normalized_description']
        result['nomenclature_assessment'] = dict(
            status='Unchanged' if name == description else 'Normalized', identity_confirmed=True,
            suggested_hgvs=name, source_genomic_query=derived_query,
            reason='Manual HGVS and derived GRCh37 alleles describe the same public-reference event.',
            provenance='manual HGVS mapped to GRCh37', independent_source_alleles=False,
            genomic_hgvs=genomic, candidates=[dict(description=name, transcript=transcript, label='Manual transcript')])
        probe.coding = name.split(':', 1)[1]
        probe.protein = _protein(data, reference_identity)
        probe.corrected_hgvs, probe.controlled_genomic, probe.nomenclature_verified = name, derived_query, True
        proof = dict(status='verified', reason='Manuell HGVS-tolkning mappet til GRCh37 og eksakt transkript.',
            provenance='manual HGVS mapped to GRCh37', independent_source_alleles=False,
            reference=deepcopy(reference_identity), normalization=result,
            source_genomic_query=genomic_query(probe), fingerprint=annotation_fingerprint(probe))
        checkpoint()
        for field in ('gene', 'transcript', 'coding', 'protein', 'locus', 'ref', 'alt',
                      'corrected_hgvs', 'controlled_genomic', 'nomenclature_verified'):
            setattr(variant, field, getattr(probe, field))
        variant.raw['_annotation_resolution'] = proof
        return True
    except requests.RequestException:
        return unresolved('Offentlig referansetjeneste svarte ikke. Prøv igjen.', retryable=True)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        return unresolved(str(exc) if isinstance(exc, ValueError) else 'Ufullstendig svar fra referansetjenesten.')
    finally:
        if owned and http is not None:
            http.close()
