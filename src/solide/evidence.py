from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import threading
import time
import uuid
from .models import Variant, Session
from .quality import review_reasons, MANE_TARGETS
from .nomenclature import hgvs_query, genomic_query, normalize_variant, spliceai_variant, spliceai_summary
from ._vendor.archer.core.models import VariantRecord
from ._vendor.archer.services.browser_review import BrowserReviewService, BrowserReviewCancelled
from ._vendor.archer.services.evidence_audit import audit_digest

SOURCES = ('ClinVar', 'Franklin', 'COSMIC', 'OncoKB', 'MTBP', 'Mutalyzer', 'SpliceAI')
COMPLETE = {'found', 'not_found', 'not_applicable', 'verified'}


def query_record(v: Variant, source: str = '') -> VariantRecord:
    if v.assembly != 'GRCh37':
        raise ValueError('Confirm GRCh37 / hg19 before searching.')
    if v.corrected_hgvs and not v.nomenclature_verified:
        raise ValueError('Approve corrected HGVS before database searches.')
    if ',' in v.gene or ',' in v.transcript:
        raise ValueError('Multiple genes / transcripts: resolve variant identity before searching.')
    reasons = review_reasons(v)
    if 'Mutalyzer' in reasons and not v.nomenclature_verified:
        raise ValueError('Review delins / complex variants in Mutalyzer before database searches.')
    if 'MANE' in reasons:
        target = MANE_TARGETS[v.gene][1]
        if not (v.nomenclature_verified and target in v.corrected_hgvs):
            raise ValueError(f'Review mapped HGVS on {target} before database searches.')
    hgvsc = ''
    try:
        hgvsc = hgvs_query(v)
    except ValueError:
        protein_only=(source in {'MTBP','OncoKB','Franklin'} and
                      bool(re.fullmatch(r'p\.[A-Za-z0-9_*?()=]+',v.protein)))
        cosmic_id_only=source=='COSMIC' and v.variant_id.startswith('COSM')
        if not (v.locus and v.ref and v.alt) and not protein_only and not cosmic_id_only:
            raise
    locus,ref,alt=v.locus,v.ref,v.alt
    if v.corrected_hgvs:
        locus,ref,alt='','',''
    if v.controlled_genomic:
        chrom,pos,ref,alt=genomic_query(v).split('-')
        locus=f'{chrom}:{pos}'
    # No local filenames, sample IDs, raw worksheet fields or comments sent downstream.
    pseudonym = 'S' + hashlib.sha256(v.patient.encode()).hexdigest()[:16]
    return VariantRecord(source_file=Path('variant.tsv'), source_row=0, sample=pseudonym,
        symbol=v.gene, hgvsc=hgvsc, hgvsp='' if v.corrected_hgvs else v.protein,
        transcript=hgvsc.split(':')[0] if hgvsc.startswith('NM_') else v.transcript,
        genomic_location=locus, ref_allele=ref, alt_allele=alt,
        variant_type=v.kind, cosmic_id=v.variant_id if v.variant_id.startswith('COSM') else '')


def batch_fingerprint(session: Session, patient: str) -> str:
    identities=sorted({v.fingerprint(session.tissue(patient)) for v in session.variants
                       if v.selected and v.patient==patient})
    return hashlib.sha256('|'.join(identities).encode()).hexdigest()


def evidence_is_current(v: Variant, evidence: dict, tissue: str, session: Session | None = None) -> bool:
    if evidence.get('fingerprint') != v.fingerprint(tissue):
        return False
    if evidence.get('database')=='MTBP' and session is not None:
        return evidence.get('mtbp_batch') == batch_fingerprint(session,v.patient)
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


def run_queue(session: Session, sources: list[str], root: Path, control: QueueControl,
              emit, progress, background=True) -> None:
    selected = [v for v in session.variants if v.selected]
    if not selected:
        raise ValueError('Select at least one variant in Variants.')
    if any(not v.patient for v in selected):
        raise ValueError('Confirm patient identity for all selected rows.')
    def store(v, source, evidence):
        evidence.update(fingerprint=v.fingerprint(session.tissue(v.patient)),
                        captured_at=datetime.now(timezone.utc).isoformat(),
                        tissue=session.tissue(v.patient), database=source)
        if source=='MTBP':
            evidence['mtbp_batch']=batch_fingerprint(session,v.patient)
        v.evidence[source] = evidence
        emit(v.id, source, evidence)
    def pending(v, source):
        e=v.evidence.get(source, {})
        complete=e.get('status') in COMPLETE
        if e.get('status')=='found' and source in SOURCES[:5]:
            images=e.get('raw',{}).get('screenshots',[])
            complete=bool(images) and all(Path(i.get('path','')).is_file() for i in images)
            if source=='MTBP':
                complete=complete and Path(e.get('raw',{}).get('patient_report_screenshot','')).is_file()
        return not (evidence_is_current(v,e,session.tissue(v.patient),session) and complete)
    last_splice = 0.0
    for patient in sorted({v.patient for v in selected}):
        variants = [v for v in selected if v.patient == patient]
        # Nomenclature comes first. Normalization candidates require human acceptance.
        for source in ('Mutalyzer', 'SpliceAI'):
            if source not in sources:
                continue
            for v in variants:
                control.checkpoint()
                if not pending(v, source):
                    continue
                progress(f'{source}: {v.gene} {v.coding}')
                if source == 'SpliceAI' and 'SpliceAI' not in review_reasons(v):
                    store(v,source,{'status':'not_applicable','summary':'Outside the ±100 bp intronic rule.'})
                    continue
                try:
                    if source == 'Mutalyzer':
                        data=normalize_variant(v)
                        norm=data['normalization']
                        errors=norm.get('errors') or []
                        status='error' if errors else 'needs_review'
                        summary=norm.get('normalized_description') or 'See the Mutalyzer response.'
                        if data.get('mapping'):
                            summary += '\nMANE suggestion: ' + str(data['mapping'].get('mapped_description',data['mapping']))
                        store(v,source,{'status':status,'summary':summary,'raw':data,
                                      'url':'https://mutalyzer.nl/normalizer/'})
                    else:
                        control.wait(max(0, 30 - (time.monotonic() - last_splice)))
                        data=spliceai_variant(v)
                        last_splice=time.monotonic()
                        scores=data.get('response',{}).get('scores',[])
                        store(v,source,{'status':'found' if scores else 'needs_review',
                                      'summary':spliceai_summary(data)+'\nGRCh37, distance=500, mask=1.',
                                      'raw':data,'url':'https://spliceailookup.broadinstitute.org/'})
                except Exception as exc:
                    if source == 'SpliceAI':
                        last_splice=time.monotonic()
                    store(v,source,{'status':'error','summary':str(exc)})
        service=BrowserReviewService(profile_root=Path.home()/'.solide'/'browser_profiles',
            mtbp_cancer_type=session.tissue(patient), stop_requested=control.stopped.is_set,
            pause_wait=control.checkpoint, browser_background=background)
        patient_directory=root/hashlib.sha256(patient.encode()).hexdigest()[:16]/uuid.uuid4().hex[:12]
        # Run each provider as one patient batch, retaining every returned checkpoint.
        for source in SOURCES[:5]:
            control.checkpoint()
            if source not in sources:
                continue
            force_batch=source=='MTBP' and any(pending(v,source) for v in variants)
            mapping={}
            for v in variants:
                if not force_batch and not pending(v,source):
                    continue
                try:
                    record=query_record(v,source)
                    mapping.setdefault(service.variant_key(record),[]).append((v,record))
                except ValueError as exc:
                    store(v,source,{'status':'needs_review','summary':str(exc)})
            records=[]
            active={}
            for key, pairs in mapping.items():
                todo=[v for v,r in pairs if force_batch or pending(v,source)]
                if todo:
                    records.append(pairs[0][1]);active[key]=todo
            if not records:
                continue
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
                            returned.add(v.id)
                            data=asdict(result)
                            record=mapping[key][0][1]
                            if not record.hgvsc and not record.ref_allele:
                                data.setdefault('raw',{})['query_basis']='gene_protein_or_identifier'
                                data['summary']+='\nGene / protein or variant ID search; genomic identity unconfirmed.'
                            store(v,result.database,data)
            try:
                service.search_variants(records,[source],patient_directory,
                                        progress=progress,checkpoint=checkpoint)
                for vv in active.values():
                    for v in vv:
                        if v.id not in returned:
                            store(v,source,{'status':'error','summary':'Source returned no variant status. Retry.'})
            except BrowserReviewCancelled:
                raise
            except Exception as exc:
                for vv in active.values():
                    for v in vv:
                        if pending(v,source):
                            store(v,source,{'status':'error','summary':str(exc)})
            finally:
                if original_audit is not None:
                    service._write_audit=original_audit
