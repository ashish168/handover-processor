"""Read a folder of handover documents and work out what is missing.

Reading order per file: use the embedded text layer if there is one, and only
fall back to OCR when there is not. OCRing a clean PDF is a way to introduce
errors into text that was already perfect.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pdfplumber

from .extract import (
    PLACEHOLDERS, classify_document, discipline_for, find_date, find_tags,
    normalise_tag, parse_date,
)
from .model import REQUIRED, Asset, AssetGap, DocType, Document, Report

log = logging.getLogger("handover")

# Below this, a page is treated as a scan rather than as text. A handful of
# stray characters from a drawing border is not a text layer.
TEXT_LAYER_MIN_CHARS = 40

REGISTER_HEADERS = {"tag", "description", "make", "model", "serial"}


def read_pdf(path: Path) -> tuple[str, list[list[list[str]]], int]:
    """Return (text, tables, page_count). Never raises on a bad file."""
    try:
        with pdfplumber.open(path) as pdf:
            text_parts, tables = [], []
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
                for t in page.extract_tables() or []:
                    tables.append([[(c or "").strip() for c in row] for row in t])
            return "\n".join(text_parts), tables, len(pdf.pages)
    except Exception as e:                      # corrupt, encrypted, not a PDF
        log.warning("could not read %s: %s", path.name, e)
        return "", [], 0


def ocr_pdf(path: Path) -> str:
    """OCR fallback. Optional on purpose: the pipeline must run without it."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        log.info("%s has no text layer and OCR is not installed", path.name)
        return ""
    try:
        return "\n".join(
            pytesseract.image_to_string(img)
            for img in convert_from_path(str(path), dpi=200)
        )
    except Exception as e:
        log.warning("OCR failed on %s: %s", path.name, e)
        return ""


def is_register(text: str, tables: list) -> bool:
    head = (text or "")[:400].lower()
    if "asset register" in head:
        return True
    for t in tables:
        if t and len({h.lower() for h in t[0]} & REGISTER_HEADERS) >= 4:
            return True
    return False


def parse_register(tables: list[list[list[str]]]) -> list[Asset]:
    """Pull assets out of the register table.

    Rows whose tag will not normalise are dropped rather than guessed at - a
    register row we cannot identify is worse than one we admit we skipped.
    """
    assets: list[Asset] = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        header = [h.lower().strip() for h in table[0]]
        if len(set(header) & REGISTER_HEADERS) < 4:
            continue
        idx = {name: header.index(name) for name in header}

        def col(row, *names):
            for n in names:
                i = idx.get(n)
                if i is not None and i < len(row):
                    v = (row[i] or "").strip()
                    # Same placeholder rule as the document parser: a register
                    # cell reading 'TBC' is a blank, not a value.
                    if v and v.lower() not in PLACEHOLDERS:
                        return v
            return ""

        for row in table[1:]:
            tag = normalise_tag(col(row, "tag"))
            if not tag:
                continue
            discipline, _ = discipline_for(tag)
            assets.append(Asset(
                tag=tag,
                description=col(row, "description"),
                discipline=discipline,
                make=col(row, "make"),
                model=col(row, "model"),
                serial=col(row, "serial"),
                location=col(row, "location"),
                commissioned=parse_date(col(row, "commissioned", "commissioning date")),
            ))
    return assets


def process(folder: str | Path) -> Report:
    folder = Path(folder)
    files = sorted(p for p in folder.glob("*.pdf"))
    if not files:
        raise SystemExit(f"no PDFs in {folder}")

    assets: list[Asset] = []
    documents: list[Document] = []
    unreadable: list[str] = []

    for path in files:
        text, tables, pages = read_pdf(path)
        ocr_used = False
        if len(text.strip()) < TEXT_LAYER_MIN_CHARS:
            ocr_text = ocr_pdf(path)
            if ocr_text.strip():
                text, ocr_used = ocr_text, True

        if len(text.strip()) < TEXT_LAYER_MIN_CHARS:
            unreadable.append(path.name)
            continue

        if is_register(text, tables):
            assets.extend(parse_register(tables))
            continue

        doc_type, _ = classify_document(text)
        documents.append(Document(
            path=path.name, doc_type=doc_type, asset_tags=find_tags(text),
            issued=find_date(text), pages=pages, ocr_used=ocr_used,
            text_chars=len(text),
        ))

    by_tag = {a.tag: a for a in assets}
    gaps = find_gaps(assets, documents)
    orphans = [d for d in documents
               if d.asset_tags and not any(t in by_tag for t in d.asset_tags)]
    return Report(assets, documents, gaps, orphans, unreadable)


def find_gaps(assets: list[Asset], documents: list[Document]) -> list[AssetGap]:
    """For every asset, which required documents are absent."""
    present: dict[str, set[DocType]] = {}
    for doc in documents:
        if doc.doc_type is DocType.UNKNOWN:
            continue
        for tag in doc.asset_tags:
            present.setdefault(tag, set()).add(doc.doc_type)

    gaps = []
    for a in assets:
        required = REQUIRED.get(a.discipline, set())
        missing = sorted(required - present.get(a.tag, set()), key=lambda d: d.value)
        fields = a.register_gaps()
        if missing or fields:
            gaps.append(AssetGap(a, missing, fields))
    gaps.sort(key=lambda g: (-g.severity, g.asset.tag))
    return gaps
