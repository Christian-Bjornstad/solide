from __future__ import annotations
from dataclasses import dataclass, field, asdict
import hashlib
import json
import uuid


@dataclass
class Variant:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    patient: str = ''
    gene: str = ''
    transcript: str = ''
    coding: str = ''
    protein: str = ''
    locus: str = ''
    ref: str = ''
    alt: str = ''
    kind: str = ''
    call: str = ''
    af_percent: float | None = None
    coverage: float | None = None
    copy_number: float | None = None
    variant_id: str = ''
    assembly: str = 'Ukjent'
    platform: str = ''
    source_file: str = ''
    source_row: int = 0
    source_hash: str = ''
    selected: bool = False
    comment: str = ''
    corrected_hgvs: str = ''
    controlled_genomic: str = ''
    nomenclature_verified: bool = False
    raw: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    def fingerprint(self, tissue: str) -> str:
        # Sample identifiers deliberately absent; only evidence inputs determine freshness.
        values = [self.gene, self.transcript, self.coding, self.protein, self.locus,
                  self.ref, self.alt, self.assembly, self.corrected_hgvs,
                  self.controlled_genomic, tissue]
        return hashlib.sha256(json.dumps(values).encode()).hexdigest()


@dataclass
class ImportResult:
    variants: list[Variant]
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    assembly: str = 'Ukjent'
    sample_hint: str = ''


@dataclass
class Session:
    variants: list[Variant] = field(default_factory=list)
    tissues: dict[str, str] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    schema_version: int = 1

    @property
    def patients(self) -> list[str]:
        return sorted({v.patient for v in self.variants if v.patient})

    def tissue(self, patient: str) -> str:
        return self.tissues.get(patient, 'Other')

    def to_dict(self) -> dict:
        return asdict(self)
