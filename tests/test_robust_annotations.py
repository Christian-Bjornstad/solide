"""Annotation lists are candidates, never evidence of positional identity."""
from copy import deepcopy
import pytest
from solide.annotations import split_annotations,annotation_resolution_current,require_resolved_annotations,annotation_fingerprint
from solide.annotation_resolution import resolve_annotation
from solide.models import Variant


def source(**changes):
    fields=dict(gene='ARID1B,LOC115308161,MIR4466',
        transcript='NM_001371656.1, NR_163974.1, NR_039676.1',coding='c.1080delC',
        protein='p.Gly361AlafsTer91',locus='chr6:157099894',ref='CC',alt='C',assembly='GRCh37',kind='INDEL')
    fields.update(changes);return Variant(**fields)


class References:
    def __init__(self,genes=None):self.genes=genes or {};self.calls=[]
    def resolve(self,refs):
        self.calls.extend(refs)
        return {r:dict(transcript=r,gene=self.genes.get(r,'ARID1B'),status='resolved') for r in refs}


def normalized(probe,**changes):
    name=f'{probe.transcript}:{probe.coding}' if ':' not in probe.coding else probe.coding
    data={'original':name,'normalization':{'input_description':name,'normalized_description':name,
            'gene_id':probe.gene,'normalized_model':{},'protein':{}},
        'nomenclature_assessment':{'status':'Unchanged','identity_confirmed':True,
            'suggested_hgvs':name,'source_genomic_query':'chr6-157099894-CC-C'},
        'genomic_identity_check':{'matched_event':{'reference':'NC_000006.11','start':157099894,'end':157099895,'inserted':''}}}
    data.update(changes);return data


def test_three_and_many_references_are_independent_pending_candidates():
    v=source();raw=deepcopy(v.raw);children=split_annotations(v)
    assert len(children)==3 and len({c.id for c in children})==3
    assert [c.coding for c in children]==['c.1080delC','','']
    assert all(not c.selected for c in children) and v.raw==raw
    for child in children:
        with pytest.raises(ValueError):require_resolved_annotations(child)
    many=source(gene='GENE',transcript=', '.join(f'NM_{i}.1' for i in range(1,21)),coding='c.1A>T',protein='')
    assert len(split_annotations(many))==20


def test_bracketed_hgvs_commas_and_semicolons_are_not_annotation_separators():
    v=source(gene='GENE',transcript='NM_1.1',coding='c.[1A>T;2G>C]',protein='p.[Lys31Asn,Val25_Lys31del]')
    assert split_annotations(v)==[v]
    assert '_annotation_issue' not in v.raw


def test_unequal_counts_create_reference_choices_without_inventing_gene_pairs():
    children=split_annotations(source(gene='ARID1B,MIR4466',coding='c.1080delC'))
    assert len(children)==3
    assert all(c.gene=='' for c in children)
    assert all(not annotation_resolution_current(c) for c in children)


@pytest.mark.parametrize('tx_count,name_count',[(2,1),(3,2),(4,3),(1,3),(20,2)])
def test_coding_cardinality_never_discards_reference_choices(tx_count,name_count):
    children=split_annotations(source(gene='GENE',
        transcript=','.join(f'NM_{i}.1' for i in range(1,tx_count+1)),
        coding=','.join(f'c.{i}A>T' for i in range(1,name_count+1)),protein=''))
    assert len(children)==tx_count
    assert all(c.raw['_annotation_group']['coding_candidates']==[f'c.{i}A>T' for i in range(1,name_count+1)] for c in children)


def test_qualified_names_follow_reference_even_when_reordered():
    children=split_annotations(source(gene='A,B',transcript='NM_1.1,NM_2.2',
        coding='NM_2.2:c.2G>T,NM_1.1:c.1A>C',protein='p.X1Y,p.X2Y'))
    assert [(c.transcript,c.coding) for c in children]==[('NM_1.1','NM_1.1:c.1A>C'),('NM_2.2','NM_2.2:c.2G>T')]


def test_duplicate_references_do_not_make_duplicate_findings():
    children=split_annotations(source(gene='ARID1B',transcript='NM_1.1,NM_1.1,NM_2.2',coding='',protein=''))
    assert [c.transcript for c in children]==['NM_1.1','NM_2.2']


@pytest.mark.parametrize('kind',['CNV','Fusion','RNAExonVariant'])
def test_structural_event_is_not_exploded_into_gene_alternatives(kind):
    v=source(kind=kind)
    assert split_annotations(v)==[v]


def test_unmatched_names_resolve_only_by_exact_gene_and_genomic_event():
    child=split_annotations(source(gene='WRONG,ARID1B',transcript='NM_1.1,NM_2.2',
        coding='c.1A>T,c.2G>T',protein='p.Wrong1,p.Wrong2'))[0]
    seen=[]
    def normalizer(probe):
        seen.append((probe.gene,probe.transcript,probe.coding,probe.protein))
        if probe.coding=='c.2G>T':return normalized(probe)
        return normalized(probe,nomenclature_assessment={'status':'Conflict','identity_confirmed':False})
    refs=References({'NM_1.1':'ARID1B'})
    assert resolve_annotation(child,refs,normalize=normalizer)
    assert child.gene=='ARID1B' and child.coding=='c.2G>T' and child.protein==''
    assert all(item[3]=='' for item in seen)
    assert annotation_resolution_current(child)
    child.alt='G'
    assert not annotation_resolution_current(child)
    with pytest.raises(ValueError):require_resolved_annotations(child)


def test_two_different_matching_names_remain_unresolved():
    child=split_annotations(source(gene='A,B',transcript='NM_1.1,NM_2.2',coding='c.1A>T,c.2G>T',protein=''))[0]
    assert not resolve_annotation(child,References(),normalize=normalized)
    assert not annotation_resolution_current(child)
    assert child.raw['_annotation_resolution']['status']=='unresolved'


def test_explicit_other_reference_name_is_never_tested_on_this_reference():
    child=split_annotations(source(gene='A,B',transcript='NM_1.1,NM_2.2',coding='NM_2.2:c.1A>T',protein=''))[0]
    seen=[]
    def normalize(probe):seen.append(probe.coding);return normalized(probe)
    assert not resolve_annotation(child,References(),normalize=normalize)
    assert all('NM_2.2:' not in name for name in seen)


def test_reference_failure_preserves_candidate_and_can_be_retried():
    child=split_annotations(source())[0];before=deepcopy(child)
    class Offline:
        def resolve(self,refs):return {refs[0]:{'status':'unresolved','reason':'network_error'}}
    assert not resolve_annotation(child,Offline(),normalize=lambda p:pytest.fail('No identity proof'))
    assert (child.gene,child.coding,child.protein)==(before.gene,before.coding,before.protein)
    assert resolve_annotation(child,References(),normalize=normalized)


def test_cancel_before_commit_does_not_change_interpreted_fields():
    child=split_annotations(source())[0];before=deepcopy(child);calls=[]
    class Cancelled(Exception):pass
    def checkpoint():
        calls.append(1)
        if len(calls)>2:raise Cancelled()
    with pytest.raises(Cancelled):resolve_annotation(child,References(),normalize=normalized,checkpoint=checkpoint)
    assert child==before


def test_multiallelic_and_invalid_source_annotation_never_run_candidates():
    for v in [source(alt='A,T'),source(transcript='23')]:
        child=split_annotations(v)[0]
        assert not resolve_annotation(child,References(),normalize=lambda p:pytest.fail('Invalid source'))


def test_proof_is_bound_to_source_analysis_and_row():
    child=split_annotations(source())[0]
    assert resolve_annotation(child,References(),normalize=normalized)
    assert annotation_fingerprint(child)
    child.source_row+=1
    assert not annotation_resolution_current(child)


def test_genomic_context_can_validate_names_outside_mrna_reference():
    child=split_annotations(source())[0]
    def normalize(probe):
        if probe.coding.startswith('NC_'):return normalized(probe)
        return normalized(probe,nomenclature_assessment={'status':'Review required','identity_confirmed':False})
    assert resolve_annotation(child,References(),normalize=normalize)
    assert child.coding=='NC_000006.11(NM_001371656.1):c.1080delC'
    assert annotation_resolution_current(child)


def test_foreign_predicted_protein_is_not_copied_from_normalizer():
    child=split_annotations(source())[0]
    class ProteinRef(References):
        def resolve(self,refs):
            result=super().resolve(refs);result[refs[0]]['protein']='NP_001358585.1';return result
    def normalize(probe):
        result=normalized(probe)
        result['normalization']['protein']={'description':probe.transcript+'(NP_999999.1):p.Wrong'}
        return result
    assert resolve_annotation(child,ProteinRef(),normalize=normalize)
    assert child.protein==''


def test_normalizer_protein_requires_exact_transcript_and_protein_reference():
    child=split_annotations(source())[0]
    class ProteinRef(References):
        def resolve(self,refs):
            result=super().resolve(refs);result[refs[0]]['protein']='NP_001358585.1';return result
    def normalize(probe):
        result=normalized(probe)
        result['normalization']['protein']={'description':probe.transcript+'(NP_001358585.1):p.(Gly361AlafsTer91)'}
        return result
    assert resolve_annotation(child,ProteinRef(),normalize=normalize)
    assert child.protein=='p.(Gly361AlafsTer91)'


def test_stop_is_checked_between_normalizer_http_calls_and_closes_owned_session(monkeypatch):
    import solide.nomenclature as module
    from solide.evidence import QueueControl
    from solide._vendor.archer.services.browser_review import BrowserReviewCancelled
    control=QueueControl()
    class Http:
        calls=0;closed=False
        def get(self,*args,**kwargs):
            self.calls+=1;control.stopped.set();return object()
        def close(self):self.closed=True
    http=Http();monkeypatch.setattr(module,'system_trust_session',lambda:http)
    v=source(gene='ARID1B',transcript='NM_001371656.1')
    with pytest.raises(BrowserReviewCancelled):module.normalize_variant(v,checkpoint=control.checkpoint)
    assert http.calls==1 and http.closed


def test_more_than_sixteen_names_can_resolve_without_positional_pairing():
    child=split_annotations(source(gene='ARID1B',transcript='NM_1.1,NM_2.2',
        coding=','.join(f'c.{i}A>T' for i in range(1,21)),protein=''))[0]
    def normalize(probe):
        if not probe.coding:return {'normalization':{'equivalent_descriptions':{}}}
        if probe.coding=='c.19A>T':return normalized(probe)
        return normalized(probe,nomenclature_assessment={'status':'Conflict','identity_confirmed':False})
    assert resolve_annotation(child,References(),normalize=normalize)
    assert child.coding=='c.19A>T' and annotation_resolution_current(child)


def test_safety_state_changes_invalidate_proof():
    for mutation in [lambda v:setattr(v,'nomenclature_verified',not v.nomenclature_verified),
                     lambda v:v.raw.update(_annotation_issue='New source conflict')]:
        child=split_annotations(source())[0]
        assert resolve_annotation(child,References(),normalize=normalized)
        mutation(child)
        assert not annotation_resolution_current(child)


def test_table_marks_source_gene_proposals_until_the_mapping_is_checked():
    from solide.table_model import VariantTableModel
    child=split_annotations(source())[0];model=VariantTableModel([child])
    assert model.data(model.index(0,2))=='ARID1B ?'
    assert resolve_annotation(child,References(),normalize=normalized)
    assert model.data(model.index(0,2))=='ARID1B'


def test_noncoding_hgvs_can_be_saved_for_independent_resolution():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PyQt6.QtWidgets import QApplication
    from solide.gui import MainWindow
    from solide.models import Session
    app=QApplication.instance() or QApplication([]);view=MainWindow()
    v=source(gene='LOC115308161',transcript='NR_163974.1',coding='',protein='',patient='00OUM00001')
    view.session=Session(variants=[v]);view.refresh();errors=[];view.notify_error=errors.append
    try:
        view.variant_table.selectRow(0);app.processEvents()
        view.hgvs_edit.setText('NR_163974.1:n.206C>T')
        view.genomic_edit.setText('chr6-157099894-C-T');view.verified_check.setChecked(True)
        view.save_identity()
        assert not errors
        assert v.corrected_hgvs=='NR_163974.1:n.206C>T'
    finally:view.close()


@pytest.mark.parametrize('failure',['network_error','timeout','rate_limited','http_error'])
def test_transient_reference_failure_is_included_in_retry_failed_plan(failure):
    from solide.models import Session
    from solide.evidence import build_search_plan,assess_evidence,_annotation_evidence_stamp
    child=split_annotations(source())[0];child.selected=True;child.patient='00OUM00001'
    class Offline:
        def resolve(self,refs):return {refs[0]:{'status':'unresolved','reason':failure}}
    assert not resolve_annotation(child,Offline(),normalize=normalized)
    child.evidence['ClinVar']={'database':'ClinVar','status':'needs_review','fingerprint':child.fingerprint('Other'),
        'annotation_resolution':_annotation_evidence_stamp(child)}
    session=Session(variants=[child])
    assert assess_evidence(child,child.evidence['ClinVar'],session).retryable
    assert build_search_plan(session,['ClinVar'],'failed')=={(child.id,'ClinVar')}


@pytest.mark.parametrize('change',['valid','absent','wrong_gene','wrong_transcript','unresolved','contradictory_gene','secondary_timeout'])
def test_missing_normalizer_gene_requires_an_exact_independent_reference(monkeypatch,change):
    import solide.nomenclature as module
    v=source(gene='KLLN',transcript='NM_001126049.2',coding='NC_000010.10(NM_001126049.2):c.-2001C>T',
        locus='chr10:89624245',ref='G',alt='A',protein='')
    full=v.coding;genomic='NC_000010.10:g.89624245G>A'
    data={'original':full,'normalization':{'input_description':full,'normalized_description':full,
        'normalized_model':{},'equivalent_descriptions':{'g':[{'description':genomic}]}}}
    data['genomic_normalization']={'original':genomic,'normalization':{
        'input_description':genomic,'normalized_description':genomic,'normalized_model':{}}}
    identity={'status':'resolved','transcript':v.transcript,'gene':'KLLN','source':'NCBI RefSeq'}
    if change=='absent':identity=None
    if change=='wrong_gene':identity['gene']='PTEN'
    if change=='wrong_transcript':identity['transcript']='NM_000314.8'
    if change=='unresolved':identity['status']='unresolved'
    if change=='contradictory_gene':data['normalization']['gene_id']='PTEN'
    def event(*args):
        if change=='secondary_timeout':
            import requests
            raise requests.Timeout()
        return ('NC_000010.10',89624244,89624245,'A')
    monkeypatch.setattr(module,'_delins_identity',event)
    module._assess_normalization(v,object(),data,reference_identity=identity)
    assert data['nomenclature_assessment']['identity_confirmed']==(change=='valid')
    if change=='valid':assert data['reference_identity']==identity
    if change=='secondary_timeout':assert data['nomenclature_assessment']['retryable'] is True


@pytest.mark.parametrize('missing',[False,True])
def test_secondary_mutalyzer_network_failure_stays_retryable(missing):
    child=split_annotations(source())[0]
    if missing:child.raw['_annotation_group']['coding_candidates']=[];child.coding=''
    def normalize(probe):
        return normalized(probe,nomenclature_assessment={'status':'Review required','identity_confirmed':False,'retryable':True})
    assert not resolve_annotation(child,References(),normalize=normalize)
    assert child.raw['_annotation_resolution']['retryable'] is True


def test_mutalyzer_provider_reuses_only_current_exact_reference_identity(monkeypatch,tmp_path):
    import solide.evidence as module
    from solide.models import Session
    child=split_annotations(source())[0];child.patient='00OUM00001';child.selected=True
    assert resolve_annotation(child,References(),normalize=normalized)
    calls=[]
    def normalize(probe,**kwargs):calls.append(kwargs);return normalized(probe)
    monkeypatch.setattr(module,'normalize_variant',normalize)
    monkeypatch.setattr(module,'capture_mutalyzer',lambda *args,**kwargs:None)
    module.run_queue(Session(variants=[child]),['Mutalyzer'],tmp_path,module.QueueControl(),lambda *args:None,lambda message:None)
    assert calls[0]['reference_identity']==child.raw['_annotation_resolution']['reference']
    assert callable(calls[0]['checkpoint'])
