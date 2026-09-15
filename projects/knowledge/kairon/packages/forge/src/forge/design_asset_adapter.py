from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


DEFAULT_MANIFEST = {
    "schema": "design-asset-manifest/v1",
    "source_type": "external_design_corpus",
    "access_mode": "read-only",
    "layer": "X/forge",
    "governance": {
        "control_plane": "omostation",
        "rules": [
            "read-only asset ingestion",
            "forge owns style matching and prompt orchestration",
            "l4 remains self-governance only",
        ],
    },
}


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "design-asset"


def _extract_frontmatter(text: str) -> dict[str, Any]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return {}
    try:
        payload = yaml.safe_load(match.group(1) or "")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_title(text: str) -> str:
    metadata = _extract_frontmatter(text)
    if metadata.get("name"):
        return str(metadata["name"]).strip()
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else "Design Asset"


def _extract_headings(text: str) -> list[str]:
    headings = re.findall(r"^#+\s+(.+)$", text, re.MULTILINE)
    cleaned = [h.strip() for h in headings if h.strip()]
    return cleaned[:8]


def _extract_palette(text: str) -> list[str]:
    colors = re.findall(r"#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})", text)
    unique = []
    for color in colors:
        if color not in unique:
            unique.append(color)
    return unique[:6]


def _infer_platform(text: str) -> str:
    lowered = text.lower()
    if "mobile" in lowered or "ios" in lowered or "android" in lowered:
        return "mobile"
    if "desktop app" in lowered or "native desktop" in lowered or "windows app" in lowered:
        return "desktop"
    if "dashboard" in lowered or "saas" in lowered or "webapp" in lowered or "landing page" in lowered:
        return "web"
    return "web"


def _infer_style_family(text: str, brand: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["dark", "neon", "terminal"]):
        return "dark-technical"
    if any(token in lowered for token in ["luxury", "premium", "elegant", "editorial"]):
        return "premium-editorial"
    if any(token in lowered for token in ["saas", "product", "dashboard"]):
        return "saas-product"
    return f"{brand}-systematic"


def _infer_layout(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["sidebar", "navigation", "dashboard"]):
        return "sidebar-dashboard"
    if any(token in lowered for token in ["card", "grid", "tile"]):
        return "card-grid"
    return "landing-page"


def _extract_summary(text: str) -> str:
    metadata = _extract_frontmatter(text)
    if isinstance(metadata.get("description"), str) and metadata["description"].strip():
        return metadata["description"].strip()[:220]

    paragraphs = re.split(r"\n\s*\n", text.strip())
    for paragraph in paragraphs:
        cleaned = re.sub(r"^#+\s*", "", paragraph.strip())
        cleaned = re.sub(r"\s+", " ", cleaned)
        if cleaned and not cleaned.startswith("#"):
            return cleaned[:220]
    return "Design reference"


def _metadata_from_design_file(file_path: Path) -> dict[str, Any]:
    text = file_path.read_text(encoding="utf-8")
    brand = file_path.parent.name
    title = _extract_title(text)
    if brand in {"design-md", ".", ""}:
        brand = title
    summary = _extract_summary(text)
    tags = _extract_headings(text)
    return {
        "id": _slugify(f"{brand}-{file_path.parent.name}"),
        "brand": brand,
        "title": title,
        "summary": summary,
        "source_repo": str(file_path.parents[2]),
        "source_path": str(file_path.relative_to(file_path.parents[2])).replace("\\", "/"),
        "layer": "forge",
        "access_mode": "read-only",
        "platform": _infer_platform(text),
        "style_family": _infer_style_family(text, brand),
        "layout_pattern": _infer_layout(text),
        "palette_tokens": _extract_palette(text),
        "tags": tags,
        "governance": {
            "context": "external design corpus only",
            "read_only": True,
            "allowed_usage": "prompt-injection for UI generation and style matching",
        },
    }


def scan_design_assets(repo_path: str | Path) -> list[dict[str, Any]]:
    root = Path(repo_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"design asset repo not found: {root}")

    assets: list[dict[str, Any]] = []
    for design_file in sorted(root.rglob("DESIGN.md")):
        if ".git" in design_file.parts:
            continue
        assets.append(_metadata_from_design_file(design_file))
    return sorted(assets, key=lambda item: (item.get("brand", "").lower(), item.get("title", "").lower()))


def match_assets(
    assets: list[dict[str, Any]],
    *,
    brand: str | None = None,
    platform: str | None = None,
    style_family: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    query_tokens = {part.lower() for part in re.findall(r"[a-z0-9]+", (query or ""))}
    for asset in assets:
        candidate = asset.get("brand", "").lower()
        if brand and brand.lower() not in candidate and brand.lower() not in str(asset.get("title", "")).lower():
            continue
        if platform and asset.get("platform") != platform:
            continue
        if style_family and asset.get("style_family") != style_family:
            continue
        if query_tokens:
            haystack = " ".join(
                [
                    str(asset.get("title", "")),
                    str(asset.get("brand", "")),
                    " ".join(str(tag) for tag in asset.get("tags", [])),
                    str(asset.get("summary", "")),
                ]
            ).lower()
            if not query_tokens.issubset(set(re.findall(r"[a-z0-9]+", haystack))):
                continue
        matches.append(asset)
    return matches


def write_manifest(repo_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_path).expanduser().resolve()
    assets = scan_design_assets(root)
    contents = {
        **DEFAULT_MANIFEST,
        "source_repo": str(root),
        "asset_count": len(assets),
        "assets": assets,
    }
    target = Path(output_path) if output_path else root / "design-asset-manifest.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(contents, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return contents


def build_design_context(asset: dict[str, Any], brief: str) -> dict[str, Any]:
    palette = asset.get("palette_tokens") or ["#0f172a", "#e2e8f0", "#f8fafc"]
    style_family = asset.get("style_family", "systematic")
    layout = asset.get("layout_pattern", "landing-page")
    brand = asset.get("brand", "brand")
    title = asset.get("title", brand)
    summary = asset.get("summary", "Design reference")
    tags = asset.get("tags") or ["ui", "product"]
    platform = asset.get("platform", "web")

    return {
        "brand": brand,
        "title": title,
        "summary": summary,
        "platform": platform,
        "style_family": style_family,
        "layout_pattern": layout,
        "palette_tokens": palette,
        "typography": {
            "headline": "high-contrast brand-led display",
            "body": "clean sans-serif product interface",
            "tone": "premium editorial" if "editorial" in style_family.lower() else "product-first",
        },
        "layout_intent": {
            "composition": layout,
            "density": "balanced" if "dashboard" in layout.lower() else "airy",
            "primary_focus": "conversion-driven product storytelling",
        },
        "ui_traits": [str(tag) for tag in tags[:6]],
        "brief": brief,
        "governance": {
            "control_plane": "omostation",
            "read_only": True,
            "allowed_usage": "design-context injection for UI generation",
        },
    }


def build_design_prompt(asset: dict[str, Any], brief: str) -> str:
    context = build_design_context(asset, brief)
    palette = ", ".join(context["palette_tokens"]) or "#0f172a"
    style_family = context["style_family"]
    layout = context["layout_pattern"]
    brand = context["brand"]
    title = context["title"]
    summary = context["summary"]
    tags = ", ".join(context["ui_traits"]) or "ui, product"
    platform = context["platform"]

    return (
        "Use the following design reference as a read-only inspiration source for a UI generation task.\n"
        f"Title: {title}\n"
        f"Brand: {brand}\n"
        f"Summary: {summary}\n"
        f"Style family: {style_family}\n"
        f"Platform: {platform}\n"
        f"Layout pattern: {layout}\n"
        f"Tags: {tags}\n"
        f"Palette tokens: {palette}\n"
        f"Task brief: {brief}\n"
        "Constraints: keep omostation governance as the control plane; do not treat this as runtime logic; "
        "favour consistent spacing, high contrast, product clarity, and a design system that reads like a premium SaaS UI."
    )


def choose_design_assets(
    repo_path: str | Path,
    *,
    brand: str | None = None,
    platform: str | None = None,
    style_family: str | None = None,
    query: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    assets = scan_design_assets(repo_path)
    matched = match_assets(assets, brand=brand, platform=platform, style_family=style_family, query=query)
    return matched[:limit]


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Scan an external design corpus and build a Forge-compatible manifest.")
    parser.add_argument("repo", nargs="?", default=".", help="Path to the design corpus root (e.g., /Users/xiamingxing/ToolBox/awesome-design-md)")
    parser.add_argument("--output", default=None, help="Path for the generated YAML manifest; defaults to <repo>/design-asset-manifest.yaml")
    args = parser.parse_args()

    manifest = write_manifest(args.repo, args.output)
    print(f"Scanned {len(manifest['assets'])} design assets")
    if manifest["assets"]:
        sample = manifest["assets"][0]
        print(f"Sample: {sample['brand']} -> {sample['source_path']}")


if __name__ == "__main__":
    _cli()
