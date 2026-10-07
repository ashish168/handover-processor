"""Generate a synthetic O&M handover pack.

Entirely invented: no client material, no real projects, no real people. The
faults below are deliberate, because a pack where everything is present proves
nothing about a tool whose job is finding what is absent.

Seeded faults:
  * assets with no commissioning certificate at all
  * a certificate naming an asset that was never in the register
  * serial numbers left as 'TBC'
  * the same asset tag written four different ways across documents
  * two image-only scans, one of which is a certificate the report
    otherwise declares missing
"""

from __future__ import annotations

import random
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

OUT = Path(__file__).parent / "pack"
STYLES = getSampleStyleSheet()
PROJECT = "Northgate House — Level 3 Refurbishment"

# tag, description, make, model, serial, location, commissioned
ASSETS = [
    ("AHU-01", "Air handling unit, supply/extract", "Vortair", "VX-4000", "VX4K-22871", "Roof plant", "12/08/2026"),
    ("AHU-02", "Air handling unit, kitchen extract", "Vortair", "VX-2500", "TBC", "Roof plant", "12/08/2026"),
    ("FCU-01", "Fan coil unit, open plan north", "Thermaline", "TL-120", "TL120-9981", "Level 3 ceiling void", "19/08/2026"),
    ("FCU-02", "Fan coil unit, open plan south", "Thermaline", "TL-120", "TL120-9982", "Level 3 ceiling void", "19/08/2026"),
    ("FCU-03", "Fan coil unit, meeting rooms", "Thermaline", "TL-080", "", "Level 3 ceiling void", ""),
    ("BLR-01", "Gas fired boiler, 150kW", "Calderon", "CX-150", "CX150-40312", "Basement plant", "05/08/2026"),
    ("P-01", "LTHW circulating pump, duty", "Hydrastream", "HS-65", "HS65-11204", "Basement plant", "05/08/2026"),
    ("P-02", "LTHW circulating pump, standby", "Hydrastream", "HS-65", "HS65-11205", "Basement plant", "05/08/2026"),
    ("EF-01", "Toilet extract fan", "Airvane", "AV-30", "AV30-7741", "Level 3 riser", "21/08/2026"),
    ("DB-01", "Distribution board, Level 3 north", "Voltek", "VT-DB-12", "VTDB-55120", "Level 3 riser", "28/08/2026"),
    ("DB-02", "Distribution board, Level 3 south", "Voltek", "VT-DB-12", "VTDB-55121", "Level 3 riser", "28/08/2026"),
    ("MCC-01", "Motor control centre, plant", "Voltek", "VT-MCC-4", "TBC", "Basement plant", "26/08/2026"),
    ("LTG-01", "Lighting control panel", "Lumina", "LC-200", "LC200-3318", "Level 3 riser", "02/09/2026"),
    ("UPS-01", "Uninterruptible power supply, 10kVA", "Voltek", "VT-UPS-10", "VTUPS-9014", "Comms room", ""),
    ("HWS-01", "Hot water calorifier, 300L", "Aquaterm", "AQ-300", "AQ300-6652", "Basement plant", "08/08/2026"),
    ("BST-01", "Cold water booster set", "Aquaterm", "AQ-BST-2", "AQBST-2290", "Basement plant", "08/08/2026"),
    ("SP-01", "Sump pump, basement", "Hydrastream", "HS-SP-1", "", "Basement tank room", ""),
]

# Which assets get which documents. Absences here are the whole point.
COMMISSIONING = ["AHU-01", "AHU-02", "FCU-01", "FCU-02", "BLR-01", "P-01", "P-02",
                 "EF-01", "HWS-01", "BST-01"]
TEST_CERTS = ["DB-01", "DB-02", "LTG-01", "HWS-01", "BST-01"]
DATA_SHEETS = ["AHU-01", "AHU-02", "FCU-01", "FCU-02", "FCU-03", "BLR-01", "P-01",
               "P-02", "DB-01", "DB-02", "MCC-01", "LTG-01", "HWS-01", "BST-01"]
WARRANTIES = ["AHU-01", "BLR-01", "DB-01", "HWS-01", "LTG-01"]

# A certificate for plant that never appears in the register. Common, and a
# genuine signal: either the register is short or the cert is from another job.
ORPHAN = "CH-01"

# The same unit, written the way four different subcontractors would write it.
TAG_STYLES = {"AHU-01": "AHU 01", "FCU-02": "fcu-2", "DB-02": "DB02", "P-01": "P-1"}


def styled(tag: str) -> str:
    return TAG_STYLES.get(tag, tag)


def header(story, title: str, subtitle: str = ""):
    story.append(Paragraph(f"<b>{title}</b>", STYLES["Title"]))
    story.append(Paragraph(PROJECT, STYLES["Normal"]))
    if subtitle:
        story.append(Paragraph(subtitle, STYLES["Normal"]))
    story.append(Spacer(1, 8 * mm))


def build(name: str, story):
    OUT.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(
        str(OUT / name), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=name,
    ).build(story)


def asset_register():
    story = []
    header(story, "Asset Register", "Issue 3 — for inclusion in O&amp;M manual")
    rows = [["Tag", "Description", "Make", "Model", "Serial", "Location", "Commissioned"]]
    rows += [[a[0], a[1], a[2], a[3], a[4] or "—", a[5], a[6] or "—"] for a in ASSETS]
    t = Table(rows, colWidths=[18*mm, 46*mm, 22*mm, 22*mm, 26*mm, 28*mm, 24*mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    build("00-asset-register.pdf", story)


def cert(kind: str, tag: str, body: list[str], idx: int, issued: str):
    story = []
    header(story, kind, f"Asset reference: {styled(tag)}")
    rows = [["Field", "Value"]] + [r.split("|") for r in body]
    t = Table(rows, colWidths=[52*mm, 100*mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(f"Date of Issue: {issued}", STYLES["Normal"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Signed on behalf of the installing contractor.", STYLES["Normal"]))
    slug = kind.lower().replace(" ", "-").replace("'", "")
    build(f"{idx:02d}-{slug}-{tag.lower()}.pdf", story)


def scanned_certificate(idx: int, tag: str, title: str, body: list[str], note: str):
    """A certificate that exists only as pixels.

    Real packs are full of these: someone photographed a signed sheet and
    dropped the image in. There is content, but no text layer, so a text-only
    reader must say so rather than quietly treat the file as empty.
    """
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    W, H = 1240, 1754                       # A4 at 150 dpi
    img = Image.new("RGB", (W, H), (249, 247, 242))
    d = ImageDraw.Draw(img)

    big = ImageFont.load_default(size=40)
    mid = ImageFont.load_default(size=26)
    small = ImageFont.load_default(size=22)

    y = 110
    d.text((110, y), title, fill=(26, 26, 30), font=big); y += 70
    d.text((110, y), PROJECT.replace("—", "-"), fill=(60, 60, 66), font=mid); y += 46
    d.text((110, y), f"Asset reference: {tag}", fill=(26, 26, 30), font=mid); y += 70
    for line in body:
        d.text((110, y), line, fill=(40, 40, 46), font=small); y += 40
    y += 40
    d.text((110, y), "Date of Issue: 09/09/2026", fill=(40, 40, 46), font=small); y += 60
    d.text((110, y), "Signed: ..............................", fill=(40, 40, 46), font=small)
    d.text((110, H - 160), note, fill=(120, 120, 126), font=small)

    img = img.rotate(-0.6, expand=False, fillcolor=(249, 247, 242))   # never square on the glass

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    OUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT / f"{idx:02d}-scan-{tag.lower()}.pdf"), pagesize=A4)
    c.drawImage(ImageReader(buf), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()


def main():
    random.seed(7)
    for f in OUT.glob("*.pdf"):
        f.unlink()

    asset_register()
    by_tag = {a[0]: a for a in ASSETS}
    i = 1

    for tag in COMMISSIONING:
        a = by_tag[tag]
        cert("Commissioning Certificate", tag, [
            f"Plant item|{a[1]}", f"Make|{a[2]}", f"Model No|{a[3]}",
            f"Serial No|{a[4] or 'TBC'}", f"Location|{a[5]}",
            "Design air volume|as drawing M-204", "Measured on site|within tolerance",
            "Result|Pass",
        ], i, a[6] or "01/09/2026"); i += 1

    for tag in TEST_CERTS:
        a = by_tag[tag]
        cert("Electrical Installation Certificate", tag, [
            f"Installation|{a[1]}", f"Make|{a[2]}", f"Model No|{a[3]}",
            f"Serial No|{a[4] or 'TBC'}", f"Location|{a[5]}",
            "Insulation resistance|&gt;299 M&#937;", "Earth continuity|Satisfactory",
            "Result|Pass",
        ], i, a[6] or "01/09/2026"); i += 1

    for tag in DATA_SHEETS:
        a = by_tag[tag]
        cert("Manufacturer's Data Sheet", tag, [
            f"Product|{a[1]}", f"Make|{a[2]}", f"Model No|{a[3]}",
            f"Serial No|{a[4] or 'TBC'}", "Maintenance interval|6 months",
            "Spares|refer to parts list",
        ], i, "15/07/2026"); i += 1

    for tag in WARRANTIES:
        a = by_tag[tag]
        cert("Warranty Certificate", tag, [
            f"Equipment|{a[1]}", f"Make|{a[2]}", f"Model No|{a[3]}",
            "Warranty period|24 months from practical completion",
            "Conditions|subject to servicing at stated intervals",
        ], i, "20/09/2026"); i += 1

    # The orphan: a real-looking certificate for plant not in the register.
    cert("Commissioning Certificate", ORPHAN, [
        "Plant item|Air cooled chiller, 200kW", "Make|Calderon", "Model No|CC-200",
        "Serial No|CC200-77310", "Location|Roof plant", "Result|Pass",
    ], i, "11/08/2026"); i += 1

    # Two scans, chosen to show two different consequences of the same defect.
    #
    # FCU-03: the report says this asset has NO commissioning certificate. It
    # does - this is it. Because the file is pixels, the tool cannot see it,
    # and a gap report that quietly ignored unreadable files would state a
    # falsehood with total confidence. This is why they are listed.
    scanned_certificate(
        i, "FCU-03", "COMMISSIONING CERTIFICATE",
        ["Plant item: Fan coil unit, meeting rooms",
         "Make: Thermaline        Model No: TL-080",
         "Serial No: TL080-9983",
         "Location: Level 3 ceiling void",
         "Measured air volume: within tolerance",
         "Result: Pass"],
        "Scanned document - no text layer. OCR required.")
    i += 1

    # CWS-01: plant that is not in the register either. Unreadable AND
    # unregistered, so nothing in the pack knows this tank exists.
    scanned_certificate(
        i, "CWS-01", "COMMISSIONING CERTIFICATE",
        ["Plant item: Cold water storage tank, 2000L",
         "Make: Aquaterm        Model No: AQ-CWS-2000",
         "Serial No: AQCWS-11827",
         "Location: Roof tank room",
         "Chlorination: completed to BS 8558",
         "Result: Pass"],
        "Scanned document - no text layer. OCR required.")

    print(f"wrote {len(list(OUT.glob('*.pdf')))} files to {OUT}")


if __name__ == "__main__":
    main()
