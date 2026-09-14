"""PDF report export — convert research reports to PDF."""

from __future__ import annotations

import html as _html
from pathlib import Path

# Reuse standard library HTML escaping
_esc = _html.escape


def markdown_to_html(md_path: str) -> str:
    """Convert a markdown report to styled HTML suitable for PDF printing."""
    path = Path(md_path).expanduser()
    if not path.exists():
        return ""

    md = path.read_text()
    lines = md.split("\n")
    out = []
    in_table = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("### "):
            out.append(f"<h3>{_esc(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{_esc(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{_esc(line[2:])}</h1>")
        elif line.startswith("> "):
            out.append(f"<blockquote>{_esc(line[2:])}</blockquote>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.startswith("|"):
            if not in_table:
                out.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.split("|")[1:-1]]
            out.append("<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in cells) + "</tr>")
        elif in_table and not line.startswith("|"):
            out.append("</table>")
            in_table = False
        elif line.startswith("- ") or line.startswith("* "):
            out.append(f"<li>{_esc(line[2:])}</li>")
        elif line.strip():
            out.append(f"<p>{_esc(line)}</p>")
        else:
            out.append("<br>")
        i += 1
    if in_table:
        out.append("</table>")

    return PDF_TEMPLATE.format(
        title=_esc(path.stem.replace("_EN", "").replace("_ZH", "")),
        content="\n".join(out),
    )


PDF_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>{title}</title>
<style>
  @page {{ margin: 20mm 18mm; size: A4; }}
  body {{ font-family: 'Helvetica Neue', Helvetica, Arial, 'Noto Sans SC', sans-serif; font-size: 11pt; line-height: 1.7; color: #1a1a2e; max-width: 180mm; }}
  h1 {{ font-size: 18pt; color: #b8860b; border-bottom: 2px solid #e0d5c1; padding-bottom: 6px; margin-top: 0; }}
  h2 {{ font-size: 14pt; color: #2c3e50; margin-top: 24px; border-bottom: 1px solid #ecf0f1; padding-bottom: 4px; }}
  h3 {{ font-size: 12pt; color: #34495e; margin-top: 18px; }}
  blockquote {{ border-left: 3px solid #b8860b; padding: 6px 14px; margin: 10px 0; color: #555; background: #faf8f5; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 9pt; }}
  th {{ background: #f5f0e8; padding: 6px 8px; text-align: left; border-bottom: 2px solid #d5c8b0; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #e8e0d5; }}
  hr {{ border: none; border-top: 1px solid #e0d5c1; margin: 18px 0; }}
  a {{ color: #b8860b; }}
  code {{ background: #f5f0e8; padding: 1px 4px; font-size: 9pt; }}
  p {{ margin: 6px 0; }}
  li {{ margin: 2px 0 2px 20px; }}
  @media print {{ body {{ font-size: 10pt; }} }}
</style></head><body>{content}</body></html>"""
