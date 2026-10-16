"""Independent analysis binding and compatibility for older review sessions."""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import hashlib

from .models import Analysis, ImportResult, Session

PROFILES = ('OPA', 'Ion Torrent', 'Unassigned')
ASSEMBLIES = ('GRCh37', 'GRCh38', 'Unknown')


def validate_analyses(session: Session, *, allow_unassigned_rows=False) -> None:
    ids = [analysis.id for analysis in session.analyses]
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError('Session contains invalid or duplicate analysis IDs.')
    rows = [variant.id for variant in session.variants]
    if any(not isinstance(value, str) or not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError('Session contains invalid or duplicate row IDs.')
    for analysis in session.analyses:
        if analysis.profile not in PROFILES or analysis.assembly not in ASSEMBLIES:
            raise ValueError('Unknown analysis profile or assembly.')
        if not isinstance(analysis.metadata, dict) or not isinstance(analysis.patient, str):
            raise ValueError('Invalid analysis metadata or sample identity.')
    by_id = {analysis.id: analysis for analysis in session.analyses}
    for variant in session.variants:
        if not variant.analysis_id and allow_unassigned_rows:
            continue
        analysis = by_id.get(variant.analysis_id)
        if analysis is None:
            raise ValueError('Variant refers to an unknown analysis.')
        if variant.patient != analysis.patient:
            raise ValueError('Variant sample differs from its analysis.')


def _retained_metadata(variants) -> dict:
    for variant in variants:
        for key in ('_source_metadata', '_metadata'):
            metadata = variant.raw.get(key)
            if isinstance(metadata, dict) and metadata:
                return deepcopy(metadata)
    return {}


def ensure_analyses(session: Session) -> None:
    """Bind legacy rows to independent sources; preserve all existing row IDs."""
    validate_analyses(session, allow_unassigned_rows=True)
    groups = defaultdict(list)
    for variant in session.variants:
        if not variant.analysis_id:
            groups[variant.patient, variant.source_file, variant.source_hash, variant.assembly].append(variant)
    for (patient, source_file, source_hash, source_assembly), variants in groups.items():
        formats = {variant.platform for variant in variants if variant.platform}
        source_format = next(iter(formats)) if len(formats) == 1 else ''
        assembly = source_assembly if source_assembly in ASSEMBLIES else 'Unknown'
        metadata = _retained_metadata(variants)
        assay = metadata.get('workflowName') or metadata.get('assayName') or 'Unknown'
        analysis = Analysis(patient=patient,
            profile='Ion Torrent' if source_format == 'Ion Reporter' else 'Unassigned',
            assay=assay if isinstance(assay, str) else 'Unknown', source_format=source_format,
            source_file=source_file, source_hash=source_hash, metadata=metadata, assembly=assembly)
        session.analyses.append(analysis)
        for variant in variants:
            variant.analysis_id = analysis.id
    session.schema_version = 2
    validate_analyses(session)


def add_analysis(session: Session, result: ImportResult, patient: str, assembly: str,
                 profile: str, assay: str) -> Analysis:
    """Confirm one source, retaining imported cells and metadata as original data."""
    if not isinstance(patient, str) or not patient.strip():
        raise ValueError('Confirm the sample identity before adding an analysis.')
    if profile not in PROFILES or assembly not in ASSEMBLIES:
        raise ValueError('Choose a valid analysis profile and assembly.')
    if not result.variants or not isinstance(result.metadata, dict):
        raise ValueError('An analysis requires imported source rows and metadata.')
    sources = {(variant.source_file, variant.source_hash) for variant in result.variants}
    if len(sources) != 1:
        raise ValueError('An analysis must contain one source file.')
    source_ids = [variant.id for variant in result.variants]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError('The imported source contains duplicate row IDs.')
    patient = patient.strip()
    assay = assay.strip() if isinstance(assay, str) and assay.strip() else 'Unknown'
    source_file, source_hash = next(iter(sources))
    ensure_analyses(session)
    for existing in session.analyses:
        if source_hash and (existing.patient, existing.source_hash, existing.profile, existing.assay) == (
                patient, source_hash, profile, assay):
            if existing.assembly != assembly:
                raise ValueError('The existing analysis uses a different assembly. Review its identity before reimporting.')
            return existing
    formats = {variant.platform for variant in result.variants if variant.platform}
    source_format = next(iter(formats)) if len(formats) == 1 else ''
    analysis = Analysis(patient=patient, profile=profile, assay=assay,
        source_format=source_format, source_file=source_file, source_hash=source_hash,
        metadata=deepcopy(result.metadata), assembly=assembly)
    variants = deepcopy(result.variants)
    for variant in variants:
        variant.raw['_source_row_id'] = variant.id
        variant.id = hashlib.sha256(f'{analysis.id}:{variant.id}'.encode()).hexdigest()[:24]
        variant.analysis_id = analysis.id
        variant.patient = patient
        variant.assembly = assembly
    session.analyses.append(analysis)
    session.variants.extend(variants)
    validate_analyses(session)
    return analysis


def analysis_scoped_session(session: Session, analysis_id: str) -> Session:
    """Expose one complete analysis with the same row objects and its tissue."""
    validate_analyses(session, allow_unassigned_rows=True)
    analysis = session.analysis(analysis_id)
    variants = session.analysis_variants(analysis_id)
    if not variants:
        raise ValueError('No source rows belong to this analysis.')
    tissue = session.tissues.get(analysis.id, session.tissue(analysis.patient))
    return Session(variants=variants, analyses=[analysis],
        tissues={analysis.patient: tissue, analysis.id: tissue}, history=session.history)


def rename_analysis_sample(session: Session, analysis_id: str, patient: str) -> None:
    """Change only this file's binding; preserve source identity and other samples."""
    validate_analyses(session)
    if not isinstance(patient,str) or not patient.strip():raise ValueError('Enter the OUM / sample ID.')
    analysis=session.analysis(analysis_id);rows=session.analysis_variants(analysis_id)
    if analysis.patient==patient.strip():return
    if rows:session.tissues[analysis.id]=session.tissue_for(rows[0])
    previous=analysis.patient;analysis.patient=patient.strip()
    for variant in rows:variant.patient=analysis.patient
    session.history.append({'event':'sample_identity_changed','analysis_id':analysis.id,
                            'previous_sample':previous,'sample':analysis.patient})
    validate_analyses(session)
