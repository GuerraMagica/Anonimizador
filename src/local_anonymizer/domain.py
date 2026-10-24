"""Immutable session values. Sensitive contents deliberately have no repr."""

from dataclasses import dataclass, field
from enum import StrEnum
import math
from pathlib import Path
import re


class AnonymizerError(Exception):
    def __init__(self, code: str, *, cleanup_paths: tuple[Path, ...] = ()):
        self.code = code if re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', code) else 'INTERNAL_ERROR'
        self.cleanup_paths = cleanup_paths
        super().__init__(self.code)


class Category(StrEnum):
    PERSONA = 'PERSONA'
    ORGANIZACION = 'ORGANIZACION'
    UBICACION = 'UBICACION'
    CORREO = 'CORREO'
    TELEFONO = 'TELEFONO'
    DOCUMENTO = 'DOCUMENTO'
    IBAN = 'IBAN'
    FECHA = 'FECHA'
    DIRECCION = 'DIRECCION'
    PROYECTO = 'PROYECTO'
    PERSONAJE = 'PERSONAJE'
    CODIGO = 'CODIGO'
    CONFIDENCIAL = 'CONFIDENCIAL'


class Confidentiality(StrEnum):
    PII = 'PII'
    BUSINESS = 'BUSINESS'
    NARRATIVE = 'NARRATIVE'
    CONTEXT = 'CONTEXT'
    CUSTOM = 'CUSTOM'


class Disposition(StrEnum):
    PENDING = 'PENDING'
    ACCEPT = 'ACCEPT'
    REJECT = 'REJECT'


class Action(StrEnum):
    LABEL = 'LABEL'
    REDACT = 'REDACT'


@dataclass(frozen=True, slots=True)
class FileIdentity:
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class Document:
    session_id: str
    revision: int
    source_path: Path = field(repr=False)
    identity: FileIdentity
    text: str = field(repr=False)
    source_sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class Finding:
    id: str
    session_id: str
    start: int
    end: int
    category: Category
    confidentiality: Confidentiality
    provenance: tuple[str, ...]
    score: float | None = None
    group_id: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if (not self.id or not self.session_id or self.start < 0 or self.end <= self.start
                or not isinstance(self.category, Category)
                or not isinstance(self.confidentiality, Confidentiality)
                or not isinstance(self.provenance, tuple) or not self.provenance
                or any(not re.fullmatch(r'[A-Za-z0-9_:.-]{1,128}', p)
                       for p in self.provenance)
                or (self.score is not None
                    and (not math.isfinite(self.score) or not 0 <= self.score <= 1))):
            raise AnonymizerError('INVALID_FINDING')


@dataclass(frozen=True, slots=True)
class Decision:
    finding_id: str
    disposition: Disposition
    action: Action = Action.LABEL
    group_id: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class Review:
    document: Document
    findings: tuple[Finding, ...]
    decisions: tuple[Decision, ...]
    revision: int = 0
    coverage_complete: bool = False
    confirmed: bool = False


@dataclass(frozen=True, slots=True)
class Segment:
    output_start: int
    output_end: int
    source_start: int
    source_end: int
    finding_id: str | None = None


@dataclass(frozen=True, slots=True)
class Preview:
    text: str = field(repr=False)
    segments: tuple[Segment, ...]
    selected_values: tuple[str, ...] = field(repr=False)
    labels: tuple[tuple[str, str], ...] = field(repr=False)
    review_revision: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ResidualKey:
    session_id: str
    review_revision: int
    preview_sha256: str
    detector_fingerprint: str
    start: int
    end: int
    category: Category
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResidualDecision:
    key: ResidualKey


@dataclass(frozen=True, slots=True)
class ResidualCandidate:
    finding: Finding
    key: ResidualKey


@dataclass(frozen=True, slots=True)
class Verification:
    session_id: str
    review_revision: int
    preview_sha256: str
    detector_fingerprint: str
    ok: bool
    issues: tuple[str, ...]
    residuals: tuple[ResidualCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class Receipt:
    destination: Path = field(repr=False)
    identity: FileIdentity
    sha256: str
