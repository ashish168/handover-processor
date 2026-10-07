"""Pure extraction rules. No file access, no network, no model calls.

Everything here is a function from text to a value, which is what makes the
awkward parts of a real handover pack testable: tags written five different
ways, dates in four formats, and certificates that name an asset that was never
in the register.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from .model import Confidence, Discipline, DocType, Field_

# Tag prefixes as they appear on UK building services drawings. The prefix is
# what makes a tag classifiable without reading the document.
PREFIX_DISCIPLINE: dict[str, Discipline] = {
    "AHU": Discipline.MECHANICAL,      # air handling unit
    "FCU": Discipline.MECHANICAL,      # fan coil unit
    "CH": Discipline.MECHANICAL,       # chiller
    "BLR": Discipline.MECHANICAL,      # boiler
    "P": Discipline.MECHANICAL,        # pump
    "EF": Discipline.MECHANICAL,       # extract fan
    "DB": Discipline.ELECTRICAL,       # distribution board
    "MCC": Discipline.ELECTRICAL,      # motor control centre
    "SWB": Discipline.ELECTRICAL,      # switchboard
    "LTG": Discipline.ELECTRICAL,      # lighting
    "UPS": Discipline.ELECTRICAL,
    "CWS": Discipline.PUBLIC_HEALTH,   # cold water service
    "HWS": Discipline.PUBLIC_HEALTH,   # hot water service
    "BST": Discipline.PUBLIC_HEALTH,   # booster set
    "SP": Discipline.PUBLIC_HEALTH,    # sump pump
}

# AHU-01 / AHU 01 / AHU01 / ahu-1 all name the same unit. Separators are
# optional and the number may or may not be padded.
TAG_RE = re.compile(
    r"\b(" + "|".join(sorted(PREFIX_DISCIPLINE, key=len, reverse=True)) + r")"
    r"[\s\-_/]?(\d{1,3})([A-Z])?\b",
    re.IGNORECASE,
)

DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d.%m.%Y")

DOC_PATTERNS: list[tuple[DocType, re.Pattern]] = [
    (DocType.COMMISSIONING_CERT,
     re.compile(r"commissioning\s+(certificate|record|result)", re.I)),
    (DocType.TEST_CERT,
     re.compile(r"(electrical installation certificate|test\s+certificate|"
                r"pressure\s+test|minor\s+works)", re.I)),
    (DocType.WARRANTY,
     re.compile(r"\bwarrant(y|ies)\b|guarantee\s+(period|certificate)", re.I)),
    (DocType.DATA_SHEET,
     re.compile(r"(technical|product|manufacturer'?s?)\s+(data\s*sheet|specification)"
                r"|\bO&M\s+(data|manual)\b|\bdata\s*sheet\b", re.I)),
]

# Values that look filled in but are not. A contractor writing 'TBC' has left a
# blank; recording it as the serial number hides the gap behind a value.
PLACEHOLDERS = {"n/a", "na", "tbc", "t.b.c", "-", "—", "–", "none", "nil", "?", "x"}

LABELLED = {
    "make": re.compile(r"(?:make|manufacturer)\s*[:\-]\s*([^\n\r]{2,40})", re.I),
    "model": re.compile(r"(?:model(?:\s+no\.?)?|type)\s*[:\-]\s*([^\n\r]{2,40})", re.I),
    "serial": re.compile(r"(?:serial(?:\s+(?:no\.?|number))?)\s*[:\-]\s*([^\n\r]{2,40})", re.I),
    "location": re.compile(r"(?:location|room|level)\s*[:\-]\s*([^\n\r]{2,40})", re.I),
}


def normalise_tag(raw: str) -> str | None:
    """Collapse the ways one asset tag gets written into a single key.

    'ahu 1', 'AHU-01' and 'AHU01' are the same unit. Without this the gap
    report invents missing certificates that are sitting right there.
    """
    m = TAG_RE.fullmatch(raw.strip())
    if not m:
        return None
    prefix, number, suffix = m.group(1).upper(), int(m.group(2)), m.group(3)
    return f"{prefix}-{number:02d}" + (suffix.upper() if suffix else "")


def find_tags(text: str) -> list[str]:
    """Every asset tag mentioned, normalised, in first-seen order."""
    seen: dict[str, None] = {}
    for m in TAG_RE.finditer(text or ""):
        tag = normalise_tag(m.group(0))
        if tag:
            seen.setdefault(tag, None)
    return list(seen)


def discipline_for(tag: str) -> tuple[Discipline, Confidence]:
    """Discipline from the tag prefix. Inferred, never certain."""
    prefix = tag.split("-")[0].upper()
    d = PREFIX_DISCIPLINE.get(prefix)
    if d is None:
        return Discipline.UNKNOWN, Confidence.UNVERIFIED
    return d, Confidence.INFERRED


def parse_date(raw: str | None) -> date | None:
    """Handover dates arrive in whatever the subcontractor's template used."""
    if not raw:
        return None
    s = raw.strip().replace(",", "")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def find_date(text: str, labels=("date of issue", "issued", "date", "completed")) -> date | None:
    for label in labels:
        m = re.search(rf"{label}\s*[:\-]\s*([0-9A-Za-z/\-. ]{{6,20}})", text or "", re.I)
        if m:
            d = parse_date(m.group(1))
            if d:
                return d
    return None


def classify_document(text: str) -> tuple[DocType, Confidence]:
    """What kind of document this is, from its own wording.

    Order matters: a commissioning certificate often contains the word 'test',
    so the more specific patterns are checked first.
    """
    head = (text or "")[:1500]
    for doc_type, pattern in DOC_PATTERNS:
        if pattern.search(head):
            return doc_type, Confidence.CERTAIN
    return DocType.UNKNOWN, Confidence.UNVERIFIED


def labelled_field(text: str, key: str) -> Field_:
    """A 'Make: Daikin' style field. Absent is a gap, not an error."""
    pattern = LABELLED.get(key)
    if not pattern:
        return Field_(None, Confidence.UNVERIFIED, "no rule")
    m = pattern.search(text or "")
    if not m:
        return Field_(None, Confidence.UNVERIFIED, "not found")
    value = m.group(1).strip().rstrip(".;,")
    # A label with nothing after it is a blank in the source, not a value.
    if not value or value.lower() in PLACEHOLDERS:
        return Field_(None, Confidence.UNVERIFIED, f"placeholder {value!r}")
    return Field_(value, Confidence.CERTAIN, f"labelled '{key}'")
