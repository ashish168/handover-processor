"""Tests for the pure extraction rules.

These cover the cases that actually go wrong in a real handover pack, not the
happy path: a tag written five ways, a label with nothing after it, a date in
whichever format the subcontractor's template used.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handover.extract import (  # noqa: E402
    classify_document, discipline_for, find_date, find_tags,
    labelled_field, normalise_tag, parse_date,
)
from handover.model import Confidence, Discipline, DocType  # noqa: E402


# --------------------------------------------------------------- tag handling

def test_one_asset_written_five_ways_is_one_tag():
    """The single most expensive bug available here: the same unit counted
    twice means inventing a missing certificate that is sitting right there."""
    for raw in ("AHU-01", "AHU 01", "AHU01", "ahu-1", "AHU-1"):
        assert normalise_tag(raw) == "AHU-01", f"{raw!r} should normalise to AHU-01"


def test_tag_suffix_is_kept_because_it_is_a_different_unit():
    assert normalise_tag("AHU-01A") == "AHU-01A"
    assert normalise_tag("AHU-01A") != normalise_tag("AHU-01")


def test_find_tags_dedupes_and_keeps_order():
    text = "Serving AHU-02 and ahu 2, then DB-7, then AHU-02 again."
    assert find_tags(text) == ["AHU-02", "DB-07"]


def test_non_tags_are_not_invented():
    assert normalise_tag("HELLO") is None
    assert normalise_tag("") is None
    assert find_tags("No plant referenced in this document.") == []


# ------------------------------------------------------------------ discipline

def test_discipline_from_prefix_is_inferred_not_certain():
    d, conf = discipline_for("AHU-01")
    assert d is Discipline.MECHANICAL
    assert conf is Confidence.INFERRED, "a prefix is evidence, not proof"


def test_unknown_prefix_is_unverified_not_guessed():
    d, conf = discipline_for("ZZZ-01")
    assert d is Discipline.UNKNOWN
    assert conf is Confidence.UNVERIFIED


def test_each_prefix_family_lands_in_the_right_discipline():
    assert discipline_for("BLR-01")[0] is Discipline.MECHANICAL
    assert discipline_for("DB-04")[0] is Discipline.ELECTRICAL
    assert discipline_for("HWS-02")[0] is Discipline.PUBLIC_HEALTH


# ----------------------------------------------------------------------- dates

def test_dates_in_the_formats_subcontractors_actually_use():
    expected = date(2026, 3, 14)
    for raw in ("14/03/2026", "14-03-2026", "14 Mar 2026", "14 March 2026",
                "2026-03-14", "14.03.2026"):
        assert parse_date(raw) == expected, f"failed on {raw!r}"


def test_unparseable_date_is_none_not_today():
    assert parse_date("sometime in spring") is None
    assert parse_date("") is None
    assert parse_date(None) is None


def test_find_date_reads_the_label():
    assert find_date("Date of Issue: 02/09/2026") == date(2026, 9, 2)
    assert find_date("Completed : 2026-09-02") == date(2026, 9, 2)
    assert find_date("no date anywhere") is None


# ------------------------------------------------------------- classification

def test_document_types_are_recognised_from_their_own_wording():
    cases = [
        ("AIR HANDLING UNIT COMMISSIONING CERTIFICATE", DocType.COMMISSIONING_CERT),
        ("Electrical Installation Certificate", DocType.TEST_CERT),
        ("Manufacturer's Data Sheet", DocType.DATA_SHEET),
        ("Warranty Certificate — 24 months", DocType.WARRANTY),
    ]
    for text, expected in cases:
        got, conf = classify_document(text)
        assert got is expected, f"{text!r} -> {got}, expected {expected}"
        assert conf is Confidence.CERTAIN


def test_commissioning_beats_test_when_both_words_appear():
    """Commissioning records nearly always contain the word 'test'. If the
    looser pattern wins, every commissioning cert is filed as a test cert and
    the gap report says commissioning is missing across the whole pack."""
    text = "COMMISSIONING CERTIFICATE\nAll test results recorded below."
    assert classify_document(text)[0] is DocType.COMMISSIONING_CERT


def test_unrecognised_document_is_unknown_not_assumed():
    got, conf = classify_document("Site meeting minutes, 4 March.")
    assert got is DocType.UNKNOWN
    assert conf is Confidence.UNVERIFIED


# -------------------------------------------------------------- labelled fields

def test_labelled_field_reads_value_and_marks_it_certain():
    f = labelled_field("Make: Daikin\nModel: FXMQ100", "make")
    assert f.value == "Daikin"
    assert f.confidence is Confidence.CERTAIN
    assert bool(f) is True


def test_placeholder_is_treated_as_missing_not_as_a_value():
    """'Serial No: TBC' is a blank the contractor left. Recording 'TBC' as the
    serial hides a real gap behind a value that looks filled in."""
    for placeholder in ("TBC", "N/A", "-", "none"):
        f = labelled_field(f"Serial No: {placeholder}", "serial")
        assert f.value is None, f"{placeholder!r} must not become a value"
        assert bool(f) is False


def test_absent_field_is_unverified_not_an_error():
    f = labelled_field("Nothing useful here", "model")
    assert f.value is None
    assert f.confidence is Confidence.UNVERIFIED
