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
        flags.append(QualityFlag('Coverage', 'Feilet', f'Coverage {v.coverage:g} <500 på rad {v.source_row}.'))
    elif v.coverage is None and kind in {'snv', 'snp', 'indel', 'del', 'ins', 'mnp', 'complex'}:
        flags.append(QualityFlag('Coverage', 'Ukjent', 'Coverage mangler eller er ikke numerisk.'))
    if kind == 'cnv':
        if v.copy_number is None:
            flags.append(QualityFlag('CNV', 'Ukjent', 'Copy Number mangler eller er ikke numerisk.'))
        elif v.copy_number < 1:
            flags.append(QualityFlag('CNV', 'Feilet', f'Copy Number {v.copy_number:g} <1.'))
        elif v.copy_number == 1:
            flags.append(QualityFlag('CNV – kontroll', 'Kontroll', 'Copy Number =1; grenseverdien må vurderes.'))
    if kind == 'rnaexontiles' and v.call.upper() == 'NO CALL':
        flags.append(QualityFlag('Uttrykksubalanse', 'Feilet', 'RNAExonTiles: NO CALL.'))
    if kind == 'rnaexonvariant' and v.call.upper() == 'ABSENT':
        flags.append(QualityFlag('RNAExonVariant', 'Rapporteres', 'RNAExonVariant: ABSENT.'))
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
        reasons.append('Flere transkripter/gener')
    return reasons
