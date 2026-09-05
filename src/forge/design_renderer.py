from __future__ import annotations

import json
from typing import Any

from .design_asset_adapter import build_design_context


def build_page_spec(asset: dict[str, Any], *, query: str | None = None) -> dict[str, Any]:
    """Convert a selected design asset into a page blueprint usable by a renderer."""
    if not isinstance(asset, dict):
        raise TypeError("asset must be a mapping")

    context = asset.get("context") or build_design_context(asset)
    palette = context.get("palette") or asset.get("palette_tokens") or []
    primary_value = palette[0].get("value") if palette and isinstance(palette[0], dict) else "#111827"
    accent_value = palette[1].get("value") if len(palette) > 1 and isinstance(palette[1], dict) else primary_value
    design_tags = context.get("design_tags") or asset.get("design_tags") or []
    section_titles = [
        {"id": "hero", "type": "hero", "eyebrow": context.get("platform") or "product", "headline": f"{context.get('brand') or 'Brand'} experience"},
        {"id": "features", "type": "feature_grid", "title": "Core product story"},
        {"id": "cta", "type": "cta", "title": "Turn inspiration into a polished interface"},
        {"id": "footer", "type": "footer", "title": "Preserve brand intent"},
    ]

    spec = {
        "page_spec_version": "1.0",
        "brand": context.get("brand") or asset.get("brand"),
        "title": context.get("title") or asset.get("title") or context.get("brand"),
        "style_family": context.get("style_family") or asset.get("style_family"),
        "platform": context.get("platform") or asset.get("platform"),
        "layout_pattern": context.get("layout_pattern") or asset.get("layout_pattern"),
        "palette_tokens": palette,
        "primary_color": primary_value,
        "accent_color": accent_value,
        "design_tags": list(design_tags)[:8],
        "sections": section_titles,
        "content_strategy": {
            "voice": "confident and premium",
            "mood": context.get("style_family") or "brand-led",
            "target": context.get("platform") or "general-web",
            "copy_direction": "clear, conversion-minded, and visually calm",
        },
        "responsive_constraints": {
            "mobile_breakpoint": 768,
            "desktop_max_width": 1280,
            "supports_dark_mode": bool(context.get("dark_mode") or asset.get("dark_mode")),
        },
        "source_path": asset.get("source_path"),
        "query": query,
        "prompt": context.get("prompt"),
    }
    return spec


def render_page_spec(spec: dict[str, Any], *, output_format: str = "json") -> str:
    """Render a page spec as json or a lightweight HTML shell."""
    fmt = (output_format or "json").lower()
    if fmt == "html":
        brand = spec.get("brand") or "Brand"
        primary = spec.get("primary_color") or "#111827"
        accent = spec.get("accent_color") or primary
        section_html = "\n".join(
            f"<section class=\"{section.get('type', 'block')}\">"
            f"<h2>{section.get('title') or section.get('headline') or section.get('id', 'Section')}</h2>"
            f"</section>"
            for section in spec.get("sections") or []
        )
        return (
            "<html><head><meta charset=\"utf-8\"><style>"
            "body{font-family:Inter,system-ui,sans-serif;margin:0;padding:32px;background:#f4f4f5;color:#111827;}"
            f".shell{{max-width:1200px;margin:0 auto;padding:24px;border:1px solid {accent};border-radius:20px;background:linear-gradient(135deg,{primary},white);box-shadow:0 12px 32px rgba(15,23,42,.10);}}"
            "section{margin-top:18px;padding:18px 20px;border-radius:16px;background:rgba(255,255,255,.5);}"
            "h1,h2{margin:0 0 8px 0;}"
            "</style></head><body><div class=\"shell\"><h1>{brand}</h1>{section_html}</div></body></html>"
        )
    return json.dumps(spec, ensure_ascii=False, indent=2)
