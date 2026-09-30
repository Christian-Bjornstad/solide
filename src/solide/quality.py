from dataclasses import dataclass
import re
from .models import Variant

MANE_TARGETS = {'FGFR1': ('NM_001127500.3', 'NM_023110.3'),
                'MET': ('NM_001174067.1', 'NM_000245.4')}


@dataclass(frozen=True)
class QualityFlag:
    category: str
    status: str
    message: str


def kind_key(value: str) -> str:
    return value.replace(' ', '').lower()


def qc_flags(v: Variant) -> list[QualityFlag]:
    flags = []
    kind = kind_key(v.kind)
    if v.coverage is not None and v.coverage < 500:
        flags.append(QualityFlag('Coverage', 'Failed', f'Coverage {v.coverage:g} <500 on row {v.source_row}.'))
    elif v.coverage is None and kind in {'snv', 'snp', 'indel', 'del', 'ins', 'mnp', 'complex'}:
        flags.append(QualityFlag('Coverage', 'Unknown', 'Coverage missing or not numeric.'))
    if kind == 'cnv':
        if v.copy_number is None:
            flags.append(QualityFlag('CNV', 'Unknown', 'Copy Number missing or not numeric.'))
        elif v.copy_number < 1:
            flags.append(QualityFlag('CNV', 'Failed', f'Copy Number {v.copy_number:g} <1.'))
        elif v.copy_number == 1:
            flags.append(QualityFlag('CNV review', 'Review', 'Copy Number =1; review the boundary value.'))
    if kind == 'rnaexontiles' and v.call.upper() == 'NO CALL':
        flags.append(QualityFlag('Expression imbalance', 'Failed', 'RNAExonTiles: NO CALL.'))
    if kind == 'rnaexonvariant' and v.call.upper() == 'ABSENT':
        flags.append(QualityFlag('RNAExonVariant', 'Report', 'RNAExonVariant: ABSENT.'))
    return flags


def review_reasons(v: Variant) -> list[str]:
    reasons = []
    if 'delins' in v.coding.lower() or kind_key(v.kind) == 'complex':
        reasons.append('Mutalyzer')
    coding=v.corrected_hgvs or v.coding
    if any(1 <= int(n) <= 100 for n in re.findall(r'\d+[+-](\d+)', coding)):
        reasons.append('SpliceAI')
    target = MANE_TARGETS.get(v.gene)
    if target and (target[0] in v.transcript or not v.transcript):
        reasons.append('MANE')
    if ',' in v.transcript or ',' in v.gene:
        reasons.append('Multiple transcripts / genes')
    return reasons
