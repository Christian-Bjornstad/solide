from copy import deepcopy

import pytest
import requests

from solide.models import Variant, Session
from solide.annotations import split_annotations
from solide.annotation_resolution import resolve_annotation
from solide.reporting import export_analysis
from solide.analyses import add_analysis
from solide.models import ImportResult


def unresolved():
    rows = split_annotations(Variant(gene='KLLN,PTEN', transcript='NM_001126049.2,NM_000314.8',
        coding='c.-2001C>T,c.19G>A', locus='chr10:89624245', ref='G', alt='A',
        assembly='GRCh37', source_row=42))
    row = rows[1]; row.selected = True
    return row


def test_annotation_transport_failure_retains_the_real_failure_type():
    row = unresolved()
    class References:
        def resolve(self, refs):
            return {refs[0]: {'status': 'resolved', 'transcript': refs[0], 'gene': 'PTEN'}}
    def offline(probe):
        raise requests.exceptions.SSLError('Synthetic certificate failure')
    assert not resolve_annotation(row, References(), normalize=offline)
    proof = row.raw['_annotation_resolution']
    assert proof['retryable'] is True
    assert proof['failure']['type'] == 'SSLError'
    assert 'sertifikat' in proof['reason'].lower()


def test_export_failure_identifies_the_specific_row_and_action(tmp_path):
    row = unresolved()
    row.raw['_annotation_resolution'] = {'status': 'unresolved', 'reason': 'Mutalyzer: sertifikatfeil.', 'retryable': True}
    session = Session()
    analysis = add_analysis(session, ImportResult([row]), '00OUM00001', 'GRCh37', 'Ion Torrent', 'Childhood')
    session.variants[0].selected = True
    with pytest.raises(ValueError) as caught:
        export_analysis(session, analysis.id, tmp_path)
    message = str(caught.value)
    assert 'NM_000314.8' in message and '42' in message
    assert 'Mutalyzer' in message and 'valget' in message.lower()
    assert not list(tmp_path.glob('*.xlsx'))
