"""Domain types for an O&M handover pack.

A handover pack is an asset register plus the certificates and data sheets that
are supposed to back every asset in it. The job is to work out which backing
documents are actually there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Discipline(str, Enum):
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    PUBLIC_HEALTH = "public_health"
    UNKNOWN = "unknown"


class DocType(str, Enum):
    COMMISSIONING_CERT = "commissioning_certificate"
    TEST_CERT = "test_certificate"
    DATA_SHEET = "manufacturer_data_sheet"
    WARRANTY = "warranty"
    UNKNOWN = "unknown"


# What a complete handover looks like per discipline. Electrical work needs an
# installation certificate; mechanical plant needs commissioning results. The
# difference is why "is the pack complete?" cannot be one checklist.
REQUIRED: dict[Discipline, set[DocType]] = {
    Discipline.MECHANICAL: {
        DocType.COMMISSIONING_CERT, DocType.DATA_SHEET, DocType.WARRANTY,
    },
    Discipline.ELECTRICAL: {
        DocType.TEST_CERT, DocType.DATA_SHEET, DocType.WARRANTY,
    },
    Discipline.PUBLIC_HEALTH: {
        DocType.COMMISSIONING_CERT, DocType.TEST_CERT,
        DocType.DATA_SHEET, DocType.WARRANTY,
    },
    Discipline.UNKNOWN: {DocType.DATA_SHEET},
}


class Confidence(str, Enum):
    """How a value got here. Anything not CERTAIN must be visible as such.

    The point of the pipeline is that a wrong value stated confidently is worse
    than an admitted gap, so extraction never silently upgrades its own trust.
    """
    CERTAIN = "certain"        # parsed from structured text by a rule
    INFERRED = "inferred"      # derived, e.g. discipline from a tag prefix
    UNVERIFIED = "unverified"  # proposed by the model, failed or skipped checks


@dataclass(frozen=True)
class Field_:
    value: str | None
    confidence: Confidence = Confidence.CERTAIN
    source: str = ""

    def __bool__(self) -> bool:
        return bool(self.value)


@dataclass
class Asset:
    tag: str
    description: str = ""
    discipline: Discipline = Discipline.UNKNOWN
    make: str = ""
    model: str = ""
    serial: str = ""
    location: str = ""
    commissioned: date | None = None

    def register_gaps(self) -> list[str]:
        """Fields the register itself should have carried and does not."""
        missing = []
        if not self.serial:
            missing.append("serial number")
        if self.commissioned is None:
            missing.append("commissioning date")
        if not self.make:
            missing.append("make")
        return missing


@dataclass
class Document:
    path: str
    doc_type: DocType = DocType.UNKNOWN
    asset_tags: list[str] = field(default_factory=list)
    issued: date | None = None
    pages: int = 0
    ocr_used: bool = False
    text_chars: int = 0


@dataclass
class AssetGap:
    asset: Asset
    missing_docs: list[DocType]
    missing_fields: list[str]

    @property
    def severity(self) -> int:
        """Crude rank so the worst assets surface first."""
        return len(self.missing_docs) * 2 + len(self.missing_fields)


@dataclass
class Report:
    assets: list[Asset]
    documents: list[Document]
    gaps: list[AssetGap]
    orphan_docs: list[Document]      # reference a tag not in the register
    unreadable: list[str]            # files nothing could be read from
    # Unreadable file -> tags it probably covers, taken from its filename.
    # An unreadable document is not just a nuisance: it may be the very
    # certificate the report is calling missing, and saying so turns a
    # complaint into the next action.
    unreadable_hints: dict[str, list[str]] = field(default_factory=dict)

    @property
    def complete_assets(self) -> int:
        return len(self.assets) - len([g for g in self.gaps if g.missing_docs])
