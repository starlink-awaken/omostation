from __future__ import annotations

import json
from typing import Any


def _normalize_palette(raw: Any) -> list[dict[str, str]]:
    tokens: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("role") or "color")
                value = str(item.get("value") or item.get("hex") or "#000000")
                role = str(item.get("role") or "utility")
                tokens.append({"name": name, "value": value, "role": role})
    elif isinstance(raw, dict):
        for name, value in raw.items():
            if isinstance(value, str):
                tokens.append({"name": str(name), "value": value, "role": "utility"})
    if not tokens:
        return [
            {"name": "primary", "value": "#111827", "role": "accent"},
            {"name": "surface", "value": "#F9FAFB", "role": "surface"},
            {"name": "text", "value": "#111827", "role": "text"},
        ]
    return tokens[:6]


def _default_sections(layout_pattern: str, brand: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "hero",
            "title": f"{brand} experience",
            "subtitle": "High-clarity product narrative designed for conversion, trust, and brand recognition.",
            "cta": "Explore the experience",
        },
        {
            "type": "feature_grid",
            "title": "Core capabilities",
            "items": [
                "Clear value narrative",
                "Responsive product system",
                f"{layout_pattern.title()} composition",
            ],
        },
        {
            "type": "cta",
            "title": "Launch the next interaction layer",
            "body": "Translate the design language into a page system that stays consistent across surfaces.",
            "cta": "Build the experience",
        },
        {
            "type": "footer",
            "title": brand,
            "body": "Design system driven by palette, rhythm, and product clarity.",
        },
    ]


def build_page_spec(
    asset: dict[str, Any] | None = None,
    *,
    design_context: dict[str, Any] | None = None,
    sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source = asset or design_context or {}
    if isinstance(source, dict):
        source = dict(source)
    brand = str(source.get("brand") or source.get("title") or "Brand")
    style_family = str(source.get("style_family") or "default-brand-system")
    platform = str(source.get("platform") or "general-web")
    layout_pattern = str(source.get("layout_pattern") or "balanced-layout")
    palette_tokens = _normalize_palette(source.get("palette_tokens") or source.get("palette") or [])
    design_tags = source.get("design_tags") or source.get("tags") or []
    if isinstance(design_tags, str):
        design_tags = [tag.strip() for tag in design_tags.split(",") if tag.strip()]
    if sections is None:
        sections = _default_sections(layout_pattern, brand)
    content_strategy = {
        "tone": "premium, purposeful, and conversion-oriented",
        "layout_focus": layout_pattern,
        "brand_alignment": brand,
        "target_platform": platform,
        "design_tags": [str(tag) for tag in design_tags[:6]],
    }
    responsive_constraints = {
        "breakpoints": ["mobile: 320px", "tablet: 768px", "desktop: 1200px"],
        "priority": ["hero", "feature_grid", "cta"],
        "safe_area": "16px horizontal padding on mobile, 24px on larger screens",
    }
    return {
        "brand": brand,
        "style_family": style_family,
        "platform": platform,
        "layout_pattern": layout_pattern,
        "palette_tokens": palette_tokens,
        "sections": sections,
        "content_strategy": content_strategy,
        "responsive_constraints": responsive_constraints,
    }


def render_page_spec(page_spec: dict[str, Any], output_format: str = "html") -> str:
    spec = dict(page_spec)
    palette_tokens = _normalize_palette(spec.get("palette_tokens") or [])
    primary = palette_tokens[0].get("value") if palette_tokens else "#111827"
    secondary = palette_tokens[1].get("value") if len(palette_tokens) > 1 else "#6B7280"
    section_html = []
    for section in spec.get("sections") or []:
        kind = str(section.get("type") or "content")
        title = str(section.get("title") or "Section")
        subtitle = str(section.get("subtitle") or section.get("body") or "")
        if kind == "feature_grid":
            items = section.get("items") or []
            items_html = "".join(f"<li>{item}</li>" for item in items)
            section_html.append(
                f"<section class='section section--{kind}'><h2>{title}</h2><ul>{items_html}</ul></section>"
            )
        elif kind == "cta":
            cta_label = str(section.get("cta") or "Take action")
            section_html.append(
                f"<section class='section section--{kind}'><h2>{title}</h2><p>{subtitle}</p><button>{cta_label}</button></section>"
            )
        elif kind == "footer":
            section_html.append(
                f"<footer class='section section--{kind}'><h2>{title}</h2><p>{subtitle}</p></footer>"
            )
        else:
            cta_label = str(section.get("cta") or "Explore")
            section_html.append(
                f"<section class='section section--{kind}'><h1>{title}</h1><p>{subtitle}</p><button>{cta_label}</button></section>"
            )
    if output_format.lower() == "json":
        return json.dumps(spec, ensure_ascii=False, indent=2)
    brand = str(spec.get("brand") or "Brand")
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{brand} page spec</title>
  <style>
    :root {{
      --primary: {primary};
      --secondary: {secondary};
      --background: #ffffff;
      --surface: #f5f5f5;
      --text: #111827;
      --radius: 20px;
    }}
    body {{
      margin: 0; font-family: Inter, system-ui, -apple-system, sans-serif; background: var(--background); color: var(--text);
    }}
    .page {{
      max-width: 1200px; margin: 0 auto; padding: 24px;
    }}
    .section {{
      padding: 32px; border-radius: var(--radius); background: var(--surface); margin-bottom: 20px;
    }}
    h1, h2 {{ margin-top: 0; color: var(--primary); }}
    button {{
      border: none; background: var(--primary); color: white; border-radius: 999px; padding: 12px 20px; cursor: pointer;
    }}
    ul {{ padding-left: 20px; }}
  </style>
</head>
<body>
  <main class=\"page\">
    {''.join(section_html)}
  </main>
</body>
</html>
"""
