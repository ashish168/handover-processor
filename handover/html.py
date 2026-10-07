"""Render the report as a single self-contained HTML file.

Same data as the terminal output, for the person who will not read a terminal.
No assets, no CDN, no JavaScript — it opens from a file, survives being emailed
as an attachment, and prints.
"""

from __future__ import annotations

import html as _html
from datetime import date

from .model import REQUIRED, Report

LABEL = {
    "commissioning_certificate": "commissioning certificate",
    "test_certificate": "test certificate",
    "manufacturer_data_sheet": "data sheet",
    "warranty": "warranty",
}

CSS = """
:root{--ink:#16181d;--body:#3f434c;--mute:#787f8b;--line:#e3e2de;--bg:#faf9f7;
      --card:#fff;--bad:#b4442e;--warn:#9a6b10;--warnbg:#fdf8ec;--ok:#1f7a4d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--body);font:15px/1.6 -apple-system,
     BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:60rem;margin:0 auto;padding:2.5rem 1.25rem 4rem}
h1{font-size:1.5rem;color:var(--ink);margin:0 0 .3rem;letter-spacing:-.01em}
h2{font-size:1.05rem;color:var(--ink);margin:2.5rem 0 .4rem}
.sub{color:var(--mute);font-size:.85rem;margin:0 0 2rem}
.note{color:var(--mute);font-size:.88rem;margin:0 0 1rem;max-width:62ch}
.tiles{display:flex;gap:.75rem;flex-wrap:wrap;margin:1.5rem 0 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:7px;
      padding:.9rem 1.1rem;min-width:8.5rem}
.tile b{display:block;font-size:1.5rem;color:var(--ink);line-height:1.2}
.tile span{font-size:.76rem;color:var(--mute)}
.tile.bad b{color:var(--bad)}
.asset{background:var(--card);border:1px solid var(--line);border-radius:7px;
       padding:1rem 1.1rem;margin-bottom:.7rem}
.asset .top{display:flex;gap:.7rem;align-items:baseline;flex-wrap:wrap}
.tag{font-weight:700;color:var(--ink);font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.desc{color:var(--body)}
.disc{font-size:.7rem;text-transform:uppercase;letter-spacing:.08em;color:var(--mute);
      border:1px solid var(--line);border-radius:3px;padding:.1rem .4rem}
ul{margin:.6rem 0 0;padding-left:1.1rem}
li{margin:.2rem 0;font-size:.92rem}
li.miss{color:var(--bad)}
li.field{color:var(--mute)}
.warnbox{background:var(--warnbg);border:1px solid #e8c877;border-radius:7px;
         padding:1rem 1.1rem;margin-bottom:.7rem}
.warnbox .hint{color:var(--warn);font-size:.9rem;margin-top:.5rem}
table{width:100%;border-collapse:collapse;font-size:.9rem;background:var(--card)}
th{text-align:left;font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;
   color:var(--mute);border-bottom:1px solid var(--line);padding:.5rem .7rem}
td{padding:.6rem .7rem;border-bottom:1px solid var(--line)}
footer{margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--line);
       color:var(--mute);font-size:.8rem;line-height:1.7}
@media print{body{background:#fff}.wrap{padding:0}}
"""


def e(s) -> str:
    return _html.escape(str(s or ""))


def render_html(r: Report, title: str = "O&M handover pack") -> str:
    blocking = [g for g in r.gaps if g.missing_docs]
    field_only = [g for g in r.gaps if not g.missing_docs and g.missing_fields]
    gap_tags = {g.asset.tag: g for g in blocking}
    out: list[str] = []
    w = out.append

    w(f"<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    w("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    w(f"<title>Gap report — {e(title)}</title><style>{CSS}</style></head><body><div class='wrap'>")

    w(f"<h1>Handover pack — gap report</h1>")
    w(f"<p class='sub'>{e(title)} · generated {date.today():%d %B %Y}</p>")

    w("<div class='tiles'>")
    w(f"<div class='tile'><b>{len(r.assets)}</b><span>assets in register</span></div>")
    w(f"<div class='tile'><b>{len(r.documents)}</b><span>documents read</span></div>")
    w(f"<div class='tile'><b>{r.complete_assets}</b><span>fully documented</span></div>")
    cls = " bad" if blocking else ""
    w(f"<div class='tile{cls}'><b>{len(blocking)}</b><span>missing documents</span></div>")
    if r.unreadable:
        w(f"<div class='tile bad'><b>{len(r.unreadable)}</b><span>unreadable files</span></div>")
    w("</div>")

    if blocking:
        w("<h2>Missing documents</h2>")
        w("<p class='note'>Each asset below is short of something the pack is supposed "
          "to contain. Worst first.</p>")
        for g in blocking:
            a = g.asset
            w("<div class='asset'><div class='top'>")
            w(f"<span class='tag'>{e(a.tag)}</span><span class='desc'>{e(a.description)}</span>")
            w(f"<span class='disc'>{e(a.discipline.value.replace('_',' '))}</span></div><ul>")
            for d in g.missing_docs:
                w(f"<li class='miss'>no {e(LABEL.get(d.value, d.value))}</li>")
            for f in g.missing_fields:
                w(f"<li class='field'>register has no {e(f)}</li>")
            w("</ul></div>")

    if field_only:
        w("<h2>Register incomplete</h2>")
        w("<p class='note'>Documents are present; the register itself has blanks.</p>")
        w("<table><tr><th>Asset</th><th>Missing from the register</th></tr>")
        for g in field_only:
            w(f"<tr><td class='tag'>{e(g.asset.tag)}</td>"
              f"<td>{e(', '.join(g.missing_fields))}</td></tr>")
        w("</table>")

    if r.orphan_docs:
        w("<h2>Documents for plant not in the register</h2>")
        w("<p class='note'>Either the register is short, or these came from another job.</p>")
        w("<table><tr><th>File</th><th>Refers to</th></tr>")
        for d in r.orphan_docs:
            w(f"<tr><td>{e(d.path)}</td><td class='tag'>{e(', '.join(d.asset_tags))}</td></tr>")
        w("</table>")

    if r.unreadable:
        w("<h2>Unreadable — may be hiding the gaps above</h2>")
        w("<p class='note'>No text layer, and OCR produced nothing. A document nobody "
          "read is not a document that is not needed.</p>")
        for name in r.unreadable:
            w(f"<div class='warnbox'><strong>{e(name)}</strong>")
            for tag in r.unreadable_hints.get(name, []):
                if tag in gap_tags:
                    missing = ", ".join(LABEL.get(d.value, d.value)
                                        for d in gap_tags[tag].missing_docs)
                    w(f"<div class='hint'>Filename suggests <strong>{e(tag)}</strong>, "
                      f"reported above as missing: {e(missing)}. "
                      f"Read this file before chasing anyone.</div>")
                elif tag not in {a.tag for a in r.assets}:
                    w(f"<div class='hint'>Filename suggests <strong>{e(tag)}</strong>, "
                      f"which is not in the register at all.</div>")
            w("</div>")

    w("<footer>Reports what is absent from a set of documents. It does not certify that "
      "anything present is correct, valid or signed by someone competent.<br>"
      "Requirements differ by discipline: "
      + " · ".join(f"{k.value.replace('_',' ')} needs "
                   f"{len(v)} document{'s' if len(v) != 1 else ''}"
                   for k, v in REQUIRED.items() if k.value != "unknown")
      + "</footer>")
    w("</div></body></html>")
    return "\n".join(out)
