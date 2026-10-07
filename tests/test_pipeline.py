"""End-to-end test over the generated sample pack.

The pack has known faults seeded into it, so these assertions are exact: if the
pipeline stops finding one of them, something has broken silently.

Run `python samples/generate.py` first; CI does.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from handover.model import DocType  # noqa: E402
from handover.pipeline import process  # noqa: E402

PACK = ROOT / "samples" / "pack"


@pytest.fixture(scope="module")
def report():
    if not PACK.exists() or not any(PACK.glob("*.pdf")):
        subprocess.run([sys.executable, str(ROOT / "samples" / "generate.py")],
                       check=True, cwd=ROOT)
    return process(PACK)


def test_register_is_read_in_full(report):
    assert len(report.assets) == 17, "every register row should be parsed"
    assert {a.tag for a in report.assets} >= {"AHU-01", "SP-01", "UPS-01"}


def test_the_same_unit_written_differently_is_not_counted_twice(report):
    """The certificates use 'AHU 01', 'fcu-2', 'DB02' and 'P-1'. If tag
    normalisation breaks, each becomes an orphan AND its register entry gains a
    phantom missing certificate - the report doubles in size and is worthless."""
    gaps = {g.asset.tag: g for g in report.gaps}
    for tag in ("AHU-01", "FCU-02", "DB-02", "P-01"):
        missing = gaps[tag].missing_docs if tag in gaps else []
        assert DocType.COMMISSIONING_CERT not in missing and DocType.TEST_CERT not in missing, (
            f"{tag} has a certificate in the pack under a different spelling")
    orphan_tags = {t for d in report.orphan_docs for t in d.asset_tags}
    assert orphan_tags == {"CH-01"}, f"unexpected orphans: {orphan_tags}"


def test_asset_with_nothing_at_all_is_ranked_worst(report):
    """SP-01 has no documents and an incomplete register row."""
    worst = report.gaps[0]
    assert worst.asset.tag == "SP-01"
    assert len(worst.missing_docs) == 4
    assert "serial number" in worst.missing_fields


def test_placeholder_serials_are_reported_as_missing(report):
    """AHU-02 and MCC-01 carry 'TBC' in the register. A gap report that calls
    that a serial number is worse than useless - it hides the gap."""
    by_tag = {g.asset.tag: g for g in report.gaps}
    for tag in ("AHU-02", "MCC-01"):
        assert "serial number" in by_tag[tag].missing_fields, (
            f"{tag} has a placeholder serial that must be reported missing")


def test_certificate_for_unregistered_plant_is_flagged(report):
    assert len(report.orphan_docs) == 1
    assert "ch-01" in report.orphan_docs[0].path


def test_unreadable_scans_are_listed_not_silently_dropped(report):
    """Both scans are image-only. Without OCR they yield nothing, and that
    failure must be visible: a document nobody read is not a document that
    isn't needed."""
    assert len(report.unreadable) == 2
    assert any("fcu-03" in n for n in report.unreadable)
    assert any("cws-01" in n for n in report.unreadable)


def test_unreadable_file_is_linked_to_the_gap_it_may_close(report):
    """The sharpest failure this tool can have: reporting that FCU-03 has no
    commissioning certificate while that certificate sits in the folder as an
    image. The report must connect the two rather than state the gap flatly."""
    hint_file = next(n for n in report.unreadable if "fcu-03" in n)
    assert "FCU-03" in report.unreadable_hints[hint_file]

    gap = next(g for g in report.gaps if g.asset.tag == "FCU-03")
    assert DocType.COMMISSIONING_CERT in gap.missing_docs, (
        "the gap is real given what is readable - the point is that the "
        "unreadable file is flagged as possibly closing it")

    from handover.cli import render
    text = render(report)
    assert "Read this file before chasing anyone" in text


def test_unreadable_file_for_unregistered_plant_says_so(report):
    """CWS-01 is unreadable AND absent from the register, which is a different
    problem from a scan that merely hides a known gap."""
    hint_file = next(n for n in report.unreadable if "cws-01" in n)
    assert "CWS-01" in report.unreadable_hints[hint_file]
    assert "CWS-01" not in {a.tag for a in report.assets}


def test_discipline_drives_which_documents_are_required(report):
    """Electrical plant needs a test certificate; mechanical plant needs a
    commissioning certificate. One checklist for both would be wrong."""
    by_tag = {g.asset.tag: g for g in report.gaps}
    assert DocType.TEST_CERT in by_tag["UPS-01"].missing_docs
    assert DocType.TEST_CERT not in by_tag.get("FCU-03").missing_docs
    assert DocType.COMMISSIONING_CERT in by_tag["FCU-03"].missing_docs


def test_documents_were_actually_classified(report):
    unknown = [d for d in report.documents if d.doc_type is DocType.UNKNOWN]
    assert not unknown, f"unclassified documents: {[d.path for d in unknown]}"
