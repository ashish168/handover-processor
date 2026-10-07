"""Run the pipeline over a folder and print the gap report.

    python -m handover.cli samples/pack
    python -m handover.cli samples/pack --json out.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .model import REQUIRED, Report
from .pipeline import process

LABEL = {
    "commissioning_certificate": "commissioning certificate",
    "test_certificate": "test certificate",
    "manufacturer_data_sheet": "data sheet",
    "warranty": "warranty",
}


def rule(title: str = "") -> str:
    return f"\n{title}\n" + "─" * 72 if title else "─" * 72


def render(r: Report) -> str:
    out: list[str] = []
    blocking = [g for g in r.gaps if g.missing_docs]

    out.append(rule("HANDOVER PACK — GAP REPORT"))
    out.append(f"{len(r.assets)} assets in register · {len(r.documents)} documents read")
    out.append(f"{r.complete_assets} assets fully documented · "
               f"{len(blocking)} with missing documents")

    if blocking:
        out.append(rule("MISSING DOCUMENTS"))
        out.append("Every asset below is short of something the pack is supposed")
        out.append("to contain. Worst first.\n")
        for g in blocking:
            a = g.asset
            out.append(f"  {a.tag:<9} {a.description[:44]:<46} [{a.discipline.value}]")
            for d in g.missing_docs:
                out.append(f"            ✗ no {LABEL.get(d.value, d.value)}")
            for f in g.missing_fields:
                out.append(f"            · register has no {f}")
            out.append("")

    field_only = [g for g in r.gaps if not g.missing_docs and g.missing_fields]
    if field_only:
        out.append(rule("REGISTER INCOMPLETE"))
        out.append("Documents are present; the register itself has blanks.\n")
        for g in field_only:
            out.append(f"  {g.asset.tag:<9} missing {', '.join(g.missing_fields)}")
        out.append("")

    if r.orphan_docs:
        out.append(rule("DOCUMENTS FOR PLANT NOT IN THE REGISTER"))
        out.append("Either the register is short, or these came from another job.\n")
        for d in r.orphan_docs:
            out.append(f"  {d.path:<48} refers to {', '.join(d.asset_tags)}")
        out.append("")

    if r.unreadable:
        gap_tags = {g.asset.tag: g for g in r.gaps if g.missing_docs}
        out.append(rule("UNREADABLE — may be hiding the gaps above"))
        out.append("No text layer, and OCR produced nothing. A document nobody")
        out.append("read is not a document that is not needed.\n")
        for name in r.unreadable:
            out.append(f"  {name}")
            for tag in r.unreadable_hints.get(name, []):
                if tag in gap_tags:
                    missing = ", ".join(LABEL.get(d.value, d.value)
                                        for d in gap_tags[tag].missing_docs)
                    out.append(f"      ⚠ filename suggests {tag}, which is reported")
                    out.append(f"        above as missing: {missing}")
                    out.append(f"        Read this file before chasing anyone.")
                elif tag not in {a.tag for a in r.assets}:
                    out.append(f"      · filename suggests {tag}, which is not in "
                               f"the register at all")
        out.append("")

    out.append(rule())
    if blocking:
        worst = blocking[0]
        out.append(f"Start with {worst.asset.tag}: "
                   f"{len(worst.missing_docs)} documents missing.")
    else:
        out.append("No missing documents.")
    return "\n".join(out)


def as_dict(r: Report) -> dict:
    return {
        "summary": {
            "assets": len(r.assets),
            "documents": len(r.documents),
            "fully_documented": r.complete_assets,
            "with_missing_documents": len([g for g in r.gaps if g.missing_docs]),
            "orphan_documents": len(r.orphan_docs),
            "unreadable_files": len(r.unreadable),
        },
        "gaps": [
            {
                "tag": g.asset.tag,
                "description": g.asset.description,
                "discipline": g.asset.discipline.value,
                "missing_documents": [d.value for d in g.missing_docs],
                "missing_fields": g.missing_fields,
                "severity": g.severity,
            }
            for g in r.gaps
        ],
        "orphan_documents": [
            {"file": d.path, "refers_to": d.asset_tags} for d in r.orphan_docs
        ],
        "unreadable": r.unreadable,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="O&M handover pack gap report")
    ap.add_argument("folder", help="folder of handover PDFs")
    ap.add_argument("--json", metavar="PATH", help="also write the report as JSON")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    report = process(args.folder)
    print(render(report))

    if args.json:
        Path(args.json).write_text(json.dumps(as_dict(report), indent=2))
        print(f"\nJSON written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
