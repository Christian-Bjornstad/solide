from __future__ import annotations
from dataclasses import asdict, dataclass
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import uuid
from urllib.parse import quote
from functools import lru_cache
from PIL.Image import DecompressionBombError
from .models import Variant, Session
from .analyses import analysis_scoped_session, validate_analyses
from .annotations import needs_annotation_resolution, annotation_resolution_current,annotation_fingerprint
from .annotation_identity import TranscriptIdentityResolver
from .annotation_resolution import resolve_annotation
from .quality import review_reasons, MANE_TARGETS
from .nomenclature import hgvs_query, genomic_query, minimal_genomic_query, normalize_variant, apply_confirmed_normalization, retain_confirmed_normalization, spliceai_variant, spliceai_summary, validate_spliceai_response, confirmed_protein, normalization_unchanged
from .brca_exchange import brca_exchange_variant
from .public_capture import capture_spliceai,capture_mutalyzer,capture_brca_exchange,spliceai_url
from .source_failures import source_failure
from .public_http import public_api_run
from ._vendor.archer.core.models import VariantRecord,DatabaseEvidence
from ._vendor.archer.services.browser_review import BrowserReviewService, BrowserReviewCancelled,_cosmic_identifiers
from ._vendor.archer.services.evidence_audit import audit_digest,mtbp_legacy_matching_issue
from ._vendor.archer.services.capture_validation import validate_capture

SOURCES = ('ClinVar', 'Franklin', 'COSMIC', 'OncoKB', 'MTBP', 'Mutalyzer', 'SpliceAI', 'BRCA Exchange')
COMPLETE = {'found', 'not_found', 'not_applicable', 'verified'}
FAILED = {'error','timeout','identity_mismatch','partial_capture','login_required',
          'authentication_failed','verification_required','network_error','capture_failed','ambiguous_result',
          'unauthorized','rate_limited','quota_exhausted','token_required','invalid_query','unsupported_query',
          'layout_changed','ambiguous','transient','submission_unknown','deferred'}


def source_applies(variant, source):
    return (source != 'BRCA Exchange' or variant.gene in {'BRCA1','BRCA2'}
            or needs_annotation_resolution(variant) and not annotation_resolution_current(variant))


@dataclass(frozen=True)
class EvidenceAssessment:
    label: str
    reason: str
    retryable: bool = False


def capture_available(evidence):
    raw=evidence.get('raw',{})
    images=raw.get('screenshots',[]) or ([{'path':raw['screenshot']}] if raw.get('screenshot') else [])
    return bool(images) and all(valid_capture(i.get('path','')) for i in images)


@lru_cache(maxsize=512)
def _capture_valid_cached(path, modified_ns, size):
    try:return validate_capture(Path(path)).valid
    except (OSError,ValueError,DecompressionBombError):return False


def valid_capture(path):
    path=Path(path)
    try:
        if not path.is_file():return False
        stat=path.stat()
        return _capture_valid_cached(str(path.resolve()),stat.st_mtime_ns,stat.st_size)
    except OSError:return False


def assess_evidence(v, evidence, session):
    if not evidence:
        return EvidenceAssessment('Pending','No search has been run.')
    if not evidence_is_current(v,evidence,session.tissue_for(v),session):
        return EvidenceAssessment('Outdated','Variant, tissue or MTBP selection changed.',True)
    status=evidence.get('status','unknown');raw=evidence.get('raw',{})
    resolution=v.raw.get('_annotation_resolution',{})
    if status=='needs_review' and resolution.get('status')=='unresolved' and resolution.get('retryable') is True:
        return EvidenceAssessment('Recheck required',resolution.get('reason','Prøv koblingskontrollen igjen.'),True)
    if status=='needs_review' and raw.get('blocked_by_annotations') and raw.get('retryable') is True:
        return EvidenceAssessment('Recheck required',evidence.get('summary','Prøv annotasjonskontrollen igjen.'),True)
    if evidence.get('database')=='MTBP':
        issue=mtbp_legacy_matching_issue(DatabaseEvidence('MTBP',status,raw=raw))
        if issue:return EvidenceAssessment('Recheck required',issue,True)
    identity=raw.get('identity_verification',{})
    if status=='identity_mismatch' or identity.get('accepted') is False:
        return EvidenceAssessment('Identity mismatch','Returned identity does not match the request.',True)
    if status in FAILED:
        return EvidenceAssessment({'partial_capture':'Partial capture','login_required':'Sign-in required',
            'timeout':'Timeout','ambiguous_result':'Ambiguous match','unauthorized':'Access required',
            'token_required':'Access required','rate_limited':'Rate limited','quota_exhausted':'Quota reached',
            'invalid_query':'Review query','unsupported_query':'Review query','layout_changed':'Layout changed',
            'ambiguous':'Ambiguous match','submission_unknown':'Submission uncertain','deferred':'Deferred'}.get(status,'Failed'),evidence.get('summary','Search did not complete.'),True)
    if status=='not_found':return EvidenceAssessment('No match','Search completed without a matching record.')
    if status=='not_applicable':return EvidenceAssessment('Not applicable',evidence.get('summary',''))
    if evidence.get('database')=='Mutalyzer' and status=='verified':
        if normalization_unchanged(v,raw) and raw.get('nomenclature_application',{}).get('applied') is not True:
            return EvidenceAssessment('Verified match','Variantnavnet er kontrollert og uendret.')
        applied=raw.get('nomenclature_application',{})
        checked=raw.get('nomenclature_assessment',{})
        if (applied.get('applied') is True and checked.get('identity_confirmed') is True
                and checked.get('status') in {'Normalized','Unchanged'} and v.nomenclature_verified
                and applied.get('to_hgvs')==v.corrected_hgvs):
            if not capture_available(evidence):
                return EvidenceAssessment('Missing capture','Checked normalized name retained; retry the Mutalyzer screenshot.',True)
            return EvidenceAssessment('Verified match','The normalized name matches the explicit source sequence event.')
    if status=='found':
        source=evidence.get('database','')
        if source=='BRCA Exchange':
            capture=raw.get('capture')
            if (raw.get('capture_issue') or capture is not None and
                    (not capture_available(evidence) or capture.get('identity_confirmed') is not True
                     or capture.get('classification_confirmed') is not True)):
                return EvidenceAssessment('Missing capture','Verified API result retained; retry the BRCA Exchange source screenshot.',True)
        if source in (*SOURCES[:5],'SpliceAI'):
            if not capture_available(evidence):
                return EvidenceAssessment('Missing capture','Result screenshot is missing.',True)
            if source=='SpliceAI':
                capture=raw.get('capture',{})
                if (capture.get('score_identity_confirmed') is not True or capture.get('dom_identity_confirmed') is not True
                        or capture.get('query')!=raw.get('query') or len(raw.get('screenshots',[]))!=2
                        or capture.get('settings')!={'hg':37,'distance':500,'mask':1,'bc':'basic','ref_alt':True}):
                    return EvidenceAssessment('Missing capture','Recapture the verified query/settings and complete transcript scores.',True)
            if source=='MTBP' and not valid_capture(raw.get('patient_report_screenshot','')):
                return EvidenceAssessment('Missing capture','Full MTBP report screenshot is missing.',True)
        if raw.get('query_basis')=='gene_cdna':
            return EvidenceAssessment('Review match','Gene / cDNA search; confirm the transcript and genomic identity.')
        if raw.get('query_basis')=='gene_protein_or_identifier':
            return EvidenceAssessment('Review match','Gene / protein or identifier search; genomic identity unconfirmed.')
        genomic_verified=raw.get('assembly_verified')=='GRCh37' and bool(raw.get('matched_location'))
        exact_identity=identity.get('accepted') is True and bool(identity.get('requested')) and identity.get('requested')==identity.get('returned')
        splice_verified=False
        if source=='SpliceAI':
            try:
                requested=genomic_query(v)
                if raw.get('query')==requested:
                    validate_spliceai_response(raw.get('response',{}),requested)
                    splice_verified=bool(raw.get('response',{}).get('scores'))
            except ValueError as exc:
                return EvidenceAssessment('Review required',f'SpliceAI response requires validation: {exc}')
        if genomic_verified or exact_identity or splice_verified:
            basis='versioned HGVS' if identity.get('method')=='full_hgvs' else 'genomic identity'
            return EvidenceAssessment('Verified match',f'Returned {basis} matches the request. Review clinical interpretation separately.')
        return EvidenceAssessment('Review match','Result found; confirm variant identity in the source.')
    return EvidenceAssessment('Review required',evidence.get('summary','Review the source response.'))


def build_search_plan(session, sources, mode='pending', chosen=None):
    if mode not in {'pending','failed','all','chosen'}:
        raise ValueError('Unknown search mode.')
    plan=set();chosen=set(chosen or ())
    selected=[v for v in session.variants if v.selected]
    for v in selected:
        for source in sources:
            if source not in SOURCES:raise ValueError('Unknown database source.')
            if not source_applies(v,source):continue
            evidence=v.evidence.get(source,{})
            assessment=assess_evidence(v,evidence,session)
            pending=not evidence_is_current(v,evidence,session.tissue_for(v),session) or evidence.get('status') not in COMPLETE
            if assessment.retryable:pending=True
            failed=bool(evidence) and (evidence.get('status') in FAILED or assessment.label in {'Missing capture','Identity mismatch','Recheck required'})
            if mode=='all' or (mode=='chosen' and (v.id,source) in chosen) or (mode=='pending' and pending) or (mode=='failed' and failed):
                plan.add((v.id,source))
    mtbp_groups={_analysis_group(v) for v in selected if (v.id,'MTBP') in plan}
    plan.update((v.id,'MTBP') for v in selected if _analysis_group(v) in mtbp_groups)
    return plan


def _analysis_group(v: Variant) -> tuple[str, str]:
    return ('analysis', v.analysis_id) if v.analysis_id else ('legacy', v.patient)


def query_record(v: Variant, source: str = '') -> VariantRecord:
    from .annotations import require_resolved_annotations
    require_resolved_annotations(v)
    if v.assembly != 'GRCh37':
        raise ValueError('Confirm GRCh37 / hg19 before searching.')
    if v.corrected_hgvs and not v.nomenclature_verified:
        raise ValueError('Approve corrected HGVS before database searches.')
    if ',' in v.gene or ',' in v.transcript:
        raise ValueError('Multiple genes / transcripts: resolve variant identity before searching.')
    reasons = review_reasons(v)
    normalization=v.evidence.get('Mutalyzer',{})
    if normalization.get('fingerprint')==v.fingerprint(normalization.get('tissue','Other')):
        assessment=normalization.get('raw',{}).get('nomenclature_assessment',{})
        if assessment.get('status')=='Conflict':
            raise ValueError('Mutalyzer found a conflict between the variant name and source alleles. Review identity before searching.')
        if assessment.get('status')=='Normalized' and not v.nomenclature_verified:
            raise ValueError('Review the normalized Mutalyzer name before database searches.')
    if 'Mutalyzer' in reasons and not v.nomenclature_verified:
        raise ValueError('Review delins / complex variants in Mutalyzer before database searches.')
    if 'MANE' in reasons:
        target = MANE_TARGETS[v.gene][1]
        if not (v.nomenclature_verified and target in v.corrected_hgvs):
            raise ValueError(f'Review mapped HGVS on {target} before database searches.')
    hgvsc = '';cosmic_ids=','.join(_cosmic_identifiers(v.variant_id))
    try:
        hgvsc = hgvs_query(v)
    except ValueError:
        if source=='Franklin' and re.fullmatch(r'c\.\S+',v.coding):
            hgvsc=v.coding
        protein_only=(source in {'MTBP','OncoKB','Franklin'} and
                      bool(re.fullmatch(r'p\.[A-Za-z0-9_*?()=]+',v.protein)))
        cosmic_id_only=source=='COSMIC' and bool(cosmic_ids)
        if not hgvsc and not (v.locus and v.ref and v.alt) and not protein_only and not cosmic_id_only:
            raise
    locus,ref,alt=v.locus,v.ref,v.alt
    if v.corrected_hgvs:
        locus,ref,alt='','',''
    if v.controlled_genomic or (not v.corrected_hgvs and locus and ref and alt):
        chrom,pos,ref,alt=minimal_genomic_query(v).split('-')
        locus=f'{chrom}:{pos}'
    # No local filenames, sample IDs, raw worksheet fields or comments sent downstream.
    pseudonym = 'S' + hashlib.sha256(v.patient.encode()).hexdigest()[:16]
    return VariantRecord(source_file=Path('variant.tsv'), source_row=0, sample=pseudonym,
        symbol=v.gene, hgvsc=hgvsc, hgvsp=confirmed_protein(v) if v.corrected_hgvs else v.protein,
        transcript=hgvsc.split(':')[0] if hgvsc.startswith('NM_') else v.transcript,
        genomic_location=locus, ref_allele=ref, alt_allele=alt,
        variant_type=v.kind, cosmic_id=cosmic_ids)


def batch_fingerprint(session: Session, patient: str, analysis_id: str | None = None) -> str:
    """MTBP selection identity within one analysis; legacy hashes stay compatible."""
    variants=[v for v in session.variants if v.patient==patient]
    if analysis_id is None:
        groups={v.analysis_id for v in variants}
        if len(groups)>1:
            raise ValueError('Choose one analysis before building an MTBP batch.')
        analysis_id=next(iter(groups),'')
    identities=sorted({v.fingerprint(session.tissue_for(v)) for v in variants
                       if v.selected and v.analysis_id==analysis_id})
    if analysis_id:
        analysis=session.analysis(analysis_id)
        if analysis.patient!=patient:
            raise ValueError('Analysis sample differs from its variant rows.')
        payload=json.dumps([analysis_id,analysis.profile,analysis.assay,identities],separators=(',',':'))
    else:
        payload='|'.join(identities)
    return hashlib.sha256(payload.encode()).hexdigest()


def _annotation_evidence_stamp(v):
    proof=v.raw.get('_annotation_resolution',{})
    return {'status':proof.get('status'),'fingerprint':proof.get('fingerprint'),
            'source_fingerprint':annotation_fingerprint(v)} if isinstance(proof,dict) and proof else None


def evidence_is_current(v: Variant, evidence: dict, tissue: str, session: Session | None = None) -> bool:
    if evidence.get('fingerprint') != v.fingerprint(tissue):
        return False
    if needs_annotation_resolution(v):
        resolution=_annotation_evidence_stamp(v)
        if not resolution or evidence.get('annotation_resolution')!=resolution:
            return False
        if not annotation_resolution_current(v) and evidence.get('status')!='needs_review':
            return False
    if evidence.get('database')=='MTBP' and session is not None:
        if v.analysis_id and evidence.get('analysis_id')!=v.analysis_id:
            return False
        try:
            return evidence.get('mtbp_batch') == batch_fingerprint(session,v.patient,v.analysis_id)
        except ValueError:
            return False
    return True


class QueueControl:
    def __init__(self):
        self.stopped = threading.Event()
        self.paused = threading.Event()

    def checkpoint(self):
        while self.paused.is_set() and not self.stopped.is_set():
            self.stopped.wait(0.2)
        if self.stopped.is_set():
            raise BrowserReviewCancelled()

    def wait(self, seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            self.checkpoint()
            self.stopped.wait(min(0.2, until - time.monotonic()))


def _resolve_queue_annotations(selected,plan,control,progress,identity_resolved,refresh_plan):
    """Resolve only requested selected interpretations before any provider runs."""
    attempted=set();blocked=set()
    def next_candidate():
        return next((variant for variant in selected if variant.id not in attempted
            and needs_annotation_resolution(variant) and not annotation_resolution_current(variant)
            and any(row_id==variant.id for row_id,_ in plan)),None)
    if next_candidate() is None:return blocked
    with TranscriptIdentityResolver(checkpoint=control.checkpoint) as resolver:
        while (variant:=next_candidate()) is not None:
            control.checkpoint()
            attempted.add(variant.id)
            before=deepcopy(variant)
            progress(f'Kontrollerer annotasjon: {variant.transcript or variant.gene}')
            try:
                accepted=resolve_annotation(variant,resolver,checkpoint=control.checkpoint)
                control.checkpoint()
            except BrowserReviewCancelled:
                variant.__dict__.clear();variant.__dict__.update(deepcopy(before.__dict__))
                raise
            except Exception as exc:
                variant.__dict__.clear();variant.__dict__.update(deepcopy(before.__dict__))
                variant.raw['_annotation_resolution']={'status':'unresolved',
                    'reason':f'Kontroll av annotasjonen mislyktes ({type(exc).__name__}).'}
                accepted=False
            if not accepted or not annotation_resolution_current(variant):
                blocked.add(variant.id)
            if identity_resolved:
                identity_resolved(variant.id,{'variant':deepcopy(variant),
                    'input_fingerprint':before.fingerprint(''),'analysis_id':before.analysis_id})
            if variant.id not in blocked:refresh_plan(variant)
    return blocked


@public_api_run()
def run_queue(session: Session, sources: list[str], root: Path, control: QueueControl,
              emit, progress, background=True, *, plan=None, credentials=None,
              plan_changed=None, expand_after_normalization=True, identity_resolved=None) -> None:
    selected = [v for v in session.variants if v.selected]
    if not selected:
        raise ValueError('Select at least one variant in Variants.')
    if any(not v.patient for v in selected):
        raise ValueError('Confirm patient identity for all selected rows.')
    validate_analyses(session,allow_unassigned_rows=True)
    grouped={}
    for variant in selected:
        grouped.setdefault(_analysis_group(variant),[]).append(variant)
    scopes={}
    for group,variants in grouped.items():
        if group[0]=='analysis':
            scopes[group]=analysis_scoped_session(session,group[1])
        else:
            # Older in-memory callers retain their patient grouping until the
            # session importer assigns explicit independent analysis bindings.
            scopes[group]=Session(variants=[v for v in session.variants
                if not v.analysis_id and v.patient==group[1]],tissues=session.tissues,history=session.history)
    plan=build_search_plan(session,sources,'pending') if plan is None else build_search_plan(session,sources,'chosen',plan)
    def store(v, source, evidence):
        tissue=session.tissue_for(v)
        evidence.update(fingerprint=v.fingerprint(tissue),
                        captured_at=datetime.now(timezone.utc).isoformat(),
                        tissue=tissue, database=source,analysis_id=v.analysis_id)
        if needs_annotation_resolution(v):
            evidence['annotation_resolution']=_annotation_evidence_stamp(v)
        if source=='MTBP':
            evidence['mtbp_batch']=batch_fingerprint(session,v.patient,v.analysis_id)
        v.evidence[source] = evidence
        emit(v.id, source, evidence)
    def pending(v, source):
        return (v.id,source) in plan
    def refresh_normalized_plan(v):
        if not expand_after_normalization:return
        # A checked new name invalidates that row's completed searches and the
        # shared MTBP batch. Respect the requested sources and selected rows;
        # unrelated patients and analyses must keep their original plan.
        group_ids={row.id for row in selected if _analysis_group(row)==_analysis_group(v)}
        additions={(row_id,source) for row_id,source in build_search_plan(session,sources,'pending')
                   if row_id==v.id or source=='MTBP' and row_id in group_ids}
        if additions-plan:
            plan.update(additions)
            if plan_changed:plan_changed(set(plan))
    blocked=_resolve_queue_annotations(selected,plan,control,progress,identity_resolved,refresh_normalized_plan)
    for variant in selected:
        if variant.id not in blocked:continue
        reason=variant.raw.get('_annotation_resolution',{}).get('reason') or 'Annotasjonen kunne ikke avklares.'
        for source in sources:
            if pending(variant,source):
                store(variant,source,{'status':'needs_review','summary':reason})
    blocked_mtbp_groups={_analysis_group(variant) for variant in selected if variant.id in blocked
                         and any(pending(row,'MTBP') for row in selected if _analysis_group(row)==_analysis_group(variant))}
    def blocked_batch_summary(group):
        rows=[row for row in selected if _analysis_group(row)==group and row.id in blocked]
        identities=', '.join((row.transcript or row.gene or 'variant')
            +(f' (kilderad {row.source_row})' if row.source_row else '') for row in rows[:5])
        reason=rows[0].raw.get('_annotation_resolution',{}).get('reason','') if rows else ''
        return (f'MTBP venter på avklaring av {len(rows)} valgt(e) rad(er): {identities}. '
            +reason+' Kjør søket på nytt, eller fjern valget for disse radene i Varianter.')
    for variant in selected:
        if _analysis_group(variant) in blocked_mtbp_groups and pending(variant,'MTBP') and variant.id not in blocked:
            store(variant,'MTBP',{'status':'needs_review',
                'summary':blocked_batch_summary(_analysis_group(variant)),
                'raw':{'blocked_by_annotations':[row.id for row in selected
                    if _analysis_group(row)==_analysis_group(variant) and row.id in blocked],
                    'retryable':any(row.raw.get('_annotation_resolution',{}).get('retryable') is True
                        for row in selected if _analysis_group(row)==_analysis_group(variant) and row.id in blocked)}})
    last_splice = 0.0
    for group in sorted(grouped):
        variants=grouped[group]
        if not any(pending(v,source) for v in variants for source in sources):
            continue
        scoped=scopes[group]
        patient=variants[0].patient
        analysis_root=root/'analyses'/hashlib.sha256(group[1].encode()).hexdigest()[:16] if group[0]=='analysis' else root
        patient_directory=analysis_root/hashlib.sha256(patient.encode()).hexdigest()[:16]/uuid.uuid4().hex[:12]
        # Nomenclature comes first. Only independently proven same-event names
        # are applied; conflicts and incomplete validation remain reviewable.
        for source in ('Mutalyzer', 'SpliceAI', 'BRCA Exchange'):
            if source not in sources:
                continue
            for v in variants:
                control.checkpoint()
                if v.id in blocked or not pending(v, source):
                    continue
                progress(f'{source}: {v.gene} {v.coding}')
                if not source_applies(v,source):
                    store(v,source,{'status':'not_applicable','summary':'Ikke et BRCA1-/BRCA2-funn.'})
                    continue
                if source == 'SpliceAI' and 'SpliceAI' not in review_reasons(v):
                    store(v,source,{'status':'not_applicable','summary':'Outside the ±100 bp intronic rule.'})
                    continue
                try:
                    if source == 'Mutalyzer':
                        if needs_annotation_resolution(v) and annotation_resolution_current(v):
                            data=normalize_variant(v,checkpoint=control.checkpoint,
                                reference_identity=v.raw['_annotation_resolution'].get('reference'))
                        else:data=normalize_variant(v)
                        norm=data['normalization']
                        errors=norm.get('errors') or []
                        status='needs_review'
                        summary=norm.get('normalized_description') or 'See the Mutalyzer response.'
                        if errors:
                            summary='HGVS validation requires review:\n'+'\n'.join(
                                f"{error.get('code','Validation error')}: {error.get('details') or error.get('message') or error}"
                                if isinstance(error,dict) else str(error) for error in errors)
                        if data.get('mapping'):
                            summary += '\nMANE suggestion: ' + str(data['mapping'].get('mapped_description',data['mapping']))
                        if data.get('mapping_issue'):
                            summary += '\n' + data['mapping_issue']
                        candidate=data.get('genomic_normalization',{}).get('normalization',{}).get('normalized_description')
                        if candidate:
                            summary += '\nGRCh37 genomic candidate (review required): ' + candidate
                        if data.get('genomic_normalization_issue'):
                            summary += '\n' + data['genomic_normalization_issue']
                        assessment=data.get('nomenclature_assessment',{})
                        if assessment:summary='Nomenclature: '+assessment['status']+'\n'+assessment.get('reason','')+'\n'+summary
                        unchanged=(normalization_unchanged(v,data) and not v.corrected_hgvs
                            and not (not v.transcript and 'Mutalyzer' in review_reasons(v)))
                        if not unchanged and ((not errors and norm.get('normalized_description')) or
                                (assessment.get('identity_confirmed') and data.get('contextual_normalization'))):
                            try:
                                captured=capture_mutalyzer(data,patient_directory/'Mutalyzer',background=background,
                                                          checkpoint=control.checkpoint,progress=progress)
                                if captured:data.update(screenshots=captured['screenshots'],capture=captured)
                            except BrowserReviewCancelled:raise
                            except Exception as exc:data['capture_issue']=str(exc)
                        applied=apply_confirmed_normalization(v,data)
                        if applied or retain_confirmed_normalization(v,data,session.tissue_for(v)):
                            status='verified'
                            progress('Mutalyzer: verified normalized name applied')
                        elif unchanged:
                            status='verified';summary='Variantnavnet er kontrollert og uendret.'
                        store(v,source,{'status':status,'summary':summary,'raw':data,
                                      'url':'https://mutalyzer.nl/normalizer/'+quote(data.get('original',''),safe='')})
                        if applied:refresh_normalized_plan(v)
                    elif source == 'BRCA Exchange':
                        query_record(v,source)
                        item=brca_exchange_variant(v)
                        if item.get('status')=='found':
                            try:
                                captured=capture_brca_exchange(item,patient_directory/'BRCAExchange',background=background,
                                    checkpoint=control.checkpoint,progress=progress)
                                item['raw'].update(screenshots=captured['screenshots'],capture=captured)
                            except BrowserReviewCancelled:raise
                            except Exception as exc:
                                item['raw']['capture_issue']=str(exc)
                                progress('BRCA Exchange: API result retained; screenshot requires retry')
                        store(v,source,item)
                    else:
                        genomic_query(v)
                        control.wait(max(0, 30 - (time.monotonic() - last_splice)))
                        try:
                            data=spliceai_variant(v)
                        finally:
                            last_splice=time.monotonic()
                        scores=data.get('response',{}).get('scores',[])
                        if scores:
                            try:
                                captured=capture_spliceai(data,patient_directory/'SpliceAI',background=background,
                                                         checkpoint=control.checkpoint,progress=progress)
                                data.update(screenshots=captured['screenshots'],capture=captured)
                            except BrowserReviewCancelled:raise
                            except Exception as exc:
                                data['capture_issue']=str(exc);progress('SpliceAI: scores retained; screenshot requires retry')
                        store(v,source,{'status':'found' if scores else 'needs_review',
                                      'summary':spliceai_summary(data)+'\nGRCh37, distance=500, mask=1.',
                                      'raw':data,'url':spliceai_url(data)})
                except BrowserReviewCancelled:raise
                except ValueError as exc:
                    store(v,source,source_failure(source,exc))
                except Exception as exc:
                    store(v,source,source_failure(source,exc))
        service=BrowserReviewService(profile_root=Path.home()/'.solide'/'browser_profiles',
            mtbp_cancer_type=scoped.tissue_for(variants[0]), stop_requested=control.stopped.is_set,
            pause_wait=control.checkpoint, browser_background=background, **(credentials or {}))
        # Run each provider as one patient batch, retaining every returned checkpoint.
        for source in SOURCES[:5]:
            control.checkpoint()
            if source not in sources:
                continue
            if source=='MTBP':
                if group in blocked_mtbp_groups:continue
                unresolved=any(needs_annotation_resolution(row) and not annotation_resolution_current(row) for row in variants)
                if unresolved:
                    for row in variants:
                        if pending(row,source):
                            store(row,source,{'status':'needs_review',
                                'summary':'MTBP-gruppen er stoppet fordi en valgt annotasjon må avklares.'})
                    continue
            force_batch=source=='MTBP' and any(pending(v,source) for v in variants)
            mapping={};invalid_queries=set()
            for v in variants:
                if v.id in blocked:continue
                if not force_batch and not pending(v,source):
                    continue
                try:
                    record=query_record(v,source)
                    mapping.setdefault(service.variant_key(record),[]).append((v,record))
                except ValueError as exc:
                    invalid_queries.add(v.id)
                    store(v,source,{'status':'needs_review','summary':str(exc)})
            if source=='MTBP' and invalid_queries:
                for v in variants:
                    if v.id not in invalid_queries and (force_batch or pending(v,source)):
                        store(v,source,{'status':'needs_review',
                            'summary':'MTBP-gruppen er stoppet fordi en valgt variant ikke kan søkes entydig.'})
                continue
            records=[]
            active={}
            for key, pairs in mapping.items():
                todo=[v for v,r in pairs if force_batch or pending(v,source)]
                if todo:
                    records.append(pairs[0][1]);active[key]=todo
            if not records:
                continue
            prior={}
            if source=='MTBP':
                fields=('database','status','summary','accession','clinical_significance','url','raw')
                for key,pairs in mapping.items():
                    for v,_ in pairs:
                        previous=v.evidence.get(source,{})
                        if previous.get('raw',{}).get('analysis_id') and evidence_is_current(v,previous,scoped.tissue_for(v),scoped):
                            data={field:previous[field] for field in fields if field in previous}
                            if data.get('raw',{}).get('provisional_status')=='submission_unknown':data['status']='submission_unknown'
                            prior[key]=[DatabaseEvidence(**data)]
                            break
            returned=set()
            original_audit=getattr(service,'_write_audit',None)
            digests={audit_digest(source,record):service.variant_key(record) for record in records}
            def provisional_audit(evidence,path):
                original_audit(evidence,path)
                key=digests.get(Path(path).name[:16])
                if key is None:return
                for v in active.get(key,[]):
                    data=asdict(evidence)
                    data['raw']['provisional_status']=data['status']
                    data['status']='partial_capture'
                    data['summary']+='\nProvisional capture; source search not completed.'
                    store(v,source,data)
            if original_audit is not None:
                service._write_audit=provisional_audit
            def checkpoint(results):
                for key, entries in results.items():
                    for result in entries:
                        for v in active.get(key,[]):
                            data=asdict(result)
                            if 'provisional_status' not in data.get('raw',{}):returned.add(v.id)
                            record=mapping[key][0][1]
                            if source=='Franklin' and record.hgvsc.startswith('c.'):
                                data.setdefault('raw',{})['query_basis']='gene_cdna'
                                data['summary']+='\nGene / cDNA search; transcript and genomic identity require review.'
                            if not record.hgvsc and not record.ref_allele:
                                data.setdefault('raw',{})['query_basis']='gene_protein_or_identifier'
                                data['summary']+='\nGene / protein or variant ID search; genomic identity unconfirmed.'
                            store(v,result.database,data)
            def finish_unreturned(v,message,error=None):
                previous=v.evidence.get(source,{})
                if previous.get('raw',{}).get('provisional_status')=='submission_unknown':
                    data={field:previous[field] for field in ('status','summary','url','raw') if field in previous}
                    data['raw']=dict(data.get('raw',{}));data['raw'].pop('provisional_status',None)
                    data['status']='submission_unknown';data['summary']=message+'\nRetained report ID must be reconciled before resubmission.'
                else:data=source_failure(source,error) if error else {'status':'error','summary':message}
                store(v,source,data)
            try:
                service.search_variants(records,[source],patient_directory,
                                        progress=progress,checkpoint=checkpoint,**({'prior_evidence':prior} if prior else {}))
                for vv in active.values():
                    for v in vv:
                        if v.id not in returned:
                            finish_unreturned(v,'Source returned no final variant status. Retry.')
            except BrowserReviewCancelled:
                raise
            except Exception as exc:
                for vv in active.values():
                    for v in vv:
                        if v.id not in returned:
                            finish_unreturned(v,str(exc),exc)
            finally:
                if original_audit is not None:
                    service._write_audit=original_audit
