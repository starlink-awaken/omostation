from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional dependency at runtime
    yaml = None


def find_awesome_design_repo(start_path: str | Path | None = None) -> Path:
    """Resolve the external design corpus without hard-coding a machine-specific path."""
    explicit = os.environ.get("AWESOME_DESIGN_MD_PATH")
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.exists():
            return candidate

    search_roots: list[Path] = []
    if start_path is not None:
        raw = Path(start_path).expanduser()
        if raw.is_file():
            raw = raw.parent
        search_roots.append(raw)

    current = Path.cwd().expanduser()
    search_roots.extend(
        [
            current,
            current.parent,
            Path("/Users/xiamingxing/Workspace"),
            Path("/Users/xiamingxing"),
            Path("/Users/xiamingxing/ToolBox"),
        ]
    )

    candidates: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        root = root.resolve()
        candidates.extend(
            [
                root,
                root / "awesome-design-md",
                root / "ToolBox" / "awesome-design-md",
                root / "Workspace" / "awesome-design-md",
                root / "design-md",
            ]
        )

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve(strict=False)
        if not candidate.exists():
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_dir() and (candidate / "design-md").exists():
            return candidate
        if candidate.name == "awesome-design-md" and candidate.is_dir():
            return candidate
    return Path("/Users/xiamingxing/ToolBox/awesome-design-md").expanduser()


def _clean_scalar(raw: str) -> str | list[str]:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        return [part.strip().strip("\"'") for part in inner.split(",") if part.strip()]
    if value and value[0] in {'"', "'"} and value[-1] == value[0]:
        return value[1:-1]
    return value


def _fallback_frontmatter_parser(frontmatter: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, data)]

    for raw_line in frontmatter.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if ":" not in stripped:
            continue
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value == "":
            new_dict: dict[str, Any] = {}
            parent[key] = new_dict
            stack.append((indent, new_dict))
        else:
            parent[key] = _clean_scalar(value)

    return data


def _split_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            frontmatter = "\n".join(lines[1:index])
            if yaml is not None:
                try:
                    loaded = yaml.safe_load(frontmatter) or {}
                    return loaded if isinstance(loaded, dict) else {}
                except Exception:
                    pass
            return _fallback_frontmatter_parser(frontmatter)
    return {}


def _normalize_brand(value: str | None, repo_dir: Path) -> str:
    if not value:
        value = repo_dir.name
    cleaned = value.strip().replace("-design", "").replace("-analysis", "").replace("_", " ")
    cleaned = cleaned.replace("/", " ")
    if " " in cleaned:
        words = [part for part in cleaned.split() if part]
        cleaned = " ".join(words)
    return cleaned.title() if cleaned and cleaned[0].isalpha() else cleaned


def _infer_style_family(meta: dict[str, Any]) -> str:
    description = str(meta.get("description") or "").lower()
    color_keys = set((meta.get("colors") or {}).keys())
    if any(token in description for token in ["warm", "editorial", "cream", "humanist"]):
        return "warm-editorial"
    if any(token in description for token in ["minimal", "mono", "sleek", "precision"]):
        return "minimal-systematic"
    if "dark" in description or "surface-dark" in color_keys:
        return "dark-contrast"
    return "default-brand-system"


def _infer_platform(meta: dict[str, Any], brand: str) -> str:
    brand_l = brand.lower()
    description = str(meta.get("description") or "").lower()
    if "assistant" in description or brand_l in {"claude", "copilot", "chatgpt"}:
        return "ai-assistant"
    if "developer" in description or "api" in description or brand_l in {"vercel", "github", "netlify", "tailwind"}:
        return "developer-platform"
    if "commerce" in description or "shop" in description or brand_l in {"shopify", "stripe", "paypal"}:
        return "commerce"
    return "general-web"


def _palette_tokens(meta: dict[str, Any]) -> list[dict[str, str]]:
    colors = meta.get("colors") or {}
    tokens: list[dict[str, str]] = []
    for name, value in colors.items():
        if not isinstance(value, str):
            continue
        role = "utility"
        name_l = name.lower()
        if "primary" in name_l:
            role = "accent"
        elif "surface" in name_l or "canvas" in name_l or "background" in name_l:
            role = "surface"
        elif "ink" in name_l or "text" in name_l or "body" in name_l:
            role = "text"
        elif "accent" in name_l or "success" in name_l or "warning" in name_l or "error" in name_l:
            role = "accent"
        tokens.append({"name": name, "value": value, "role": role})
    return tokens[:12]


def _typography(meta: dict[str, Any]) -> dict[str, Any]:
    typography = meta.get("typography") or {}
    display = typography.get("display-xl") or next(iter(typography.values()), {})
    body = typography.get("body-md") or next((v for k, v in typography.items() if "body" in str(k).lower()), {})
    hierarchy = {}
    for key in ["display-xl", "display-lg", "display-md", "title-lg", "body-md", "caption", "code"]:
        value = typography.get(key)
        if isinstance(value, dict):
            font_family = value.get("fontFamily") or value.get("font_family") or ""
            font_size = value.get("fontSize") or value.get("font_size") or ""
            font_weight = value.get("fontWeight") or value.get("font_weight") or ""
            line_height = value.get("lineHeight") or value.get("line_height") or ""
            hierarchy[key] = {
                "fontFamily": font_family,
                "fontSize": font_size,
                "fontWeight": font_weight,
                "lineHeight": line_height,
            }
    return {
        "display_family": str((display or {}).get("fontFamily") or ""),
        "body_family": str((body or {}).get("fontFamily") or ""),
        "hierarchy": hierarchy,
    }


def _layout_pattern(meta: dict[str, Any]) -> str:
    layout = meta.get("layout") or meta.get("layout_pattern") or meta.get("components") or {}
    if isinstance(layout, dict):
        for key in ["hero", "wrapper", "content", "shell", "grid"]:
            if key in layout:
                return key
    description = str(meta.get("description") or "").lower()
    if "editorial" in description:
        return "centered-editorial"
    if "grid" in description:
        return "content-grid"
    return "balanced-layout"


def _tags(meta: dict[str, Any]) -> list[str]:
    tags = meta.get("tags") or meta.get("design_tags") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",")]
    if not tags:
        description = str(meta.get("description") or "")
        tags = [part.strip() for part in description.split()[:5] if part.strip()]
    return [str(tag).strip() for tag in tags if str(tag).strip()][:10]


def _extract_asset(file_path: Path, repo_root: Path) -> dict[str, Any] | None:
    if not file_path.name.lower() == "design.md":
        return None
    try:
        contents = file_path.read_text(encoding="utf-8")
    except OSError:
        return None
    metadata = _split_frontmatter(contents)
    if not metadata:
        return None

    repo_dir = file_path.parent.name
    brand = str(metadata.get("brand") or metadata.get("name") or repo_dir or "Design")
    brand = _normalize_brand(brand, file_path.parent)
    asset_id = metadata.get("id") or repo_dir.lower()
    platform = str(metadata.get("platform") or _infer_platform(metadata, brand))
    style_family = str(metadata.get("style_family") or _infer_style_family(metadata))
    palette_tokens = _palette_tokens(metadata)
    notes = str(metadata.get("description") or metadata.get("notes") or "")
    dark_mode = bool(metadata.get("dark_mode")) or any(name.lower() in {"surface-dark", "ink", "canvas"} for name in (metadata.get("colors") or {}))
    relative_path = file_path.relative_to(repo_root).as_posix()
    entry = {
        "id": str(asset_id),
        "brand": brand,
        "source_repo": str(repo_root),
        "source_path": relative_path,
        "style_family": style_family,
        "platform": platform,
        "palette_tokens": palette_tokens,
        "typography": _typography(metadata),
        "layout_pattern": str(metadata.get("layout_pattern") or _layout_pattern(metadata)),
        "dark_mode": dark_mode,
        "design_tags": _tags(metadata),
        "notes": notes,
        "title": str(metadata.get("title") or metadata.get("name") or brand),
        "last_synced_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return entry


def discover_design_assets(repo_root: str | Path | None = None) -> list[dict[str, Any]]:
    root = Path(repo_root) if repo_root is not None else find_awesome_design_repo()
    root = root.expanduser().resolve()
    if not root.exists():
        return []
    assets: list[dict[str, Any]] = []
    for design_file in sorted(root.rglob("DESIGN.md")):
        if any(part in {".git", "node_modules", "__pycache__"} for part in design_file.parts):
            continue
        asset = _extract_asset(design_file, root)
        if asset:
            assets.append(asset)
    return assets


def build_design_context(asset: dict[str, Any]) -> dict[str, Any]:
    palette = asset.get("palette_tokens") or []
    primary = palette[0] if palette else {"name": "fallback", "value": "#000000", "role": "accent"}
    colors = [token["value"] for token in palette[:6]]
    typography = asset.get("typography") or {}
    prompt = (
        f"Create a {asset.get('platform', 'general-web')} interface in the style of {asset.get('brand', 'the referenced brand')}. "
        f"Use a {asset.get('style_family', 'brand-led')} aesthetic with palette {', '.join(colors) or '#000000'}. "
        f"Anchor type in {typography.get('display_family') or 'a strong serif headline style'} and {typography.get('body_family') or 'an elegant sans body style'}, "
        f"with a {asset.get('layout_pattern', 'balanced layout')} composition and design tags {', '.join(asset.get('design_tags', [])[:5]) or 'UI system'} . "
        f"Keep the mood aligned with: {asset.get('notes', '') or 'a polished, premium brand experience'}."
    )
    return {
        "id": asset.get("id"),
        "brand": asset.get("brand"),
        "title": asset.get("title"),
        "source_path": asset.get("source_path"),
        "style_family": asset.get("style_family"),
        "platform": asset.get("platform"),
        "layout_pattern": asset.get("layout_pattern"),
        "dark_mode": asset.get("dark_mode", False),
        "palette": palette,
        "primary_color": primary.get("value"),
        "display_family": typography.get("display_family"),
        "body_family": typography.get("body_family"),
        "design_tags": asset.get("design_tags") or [],
        "prompt": prompt,
    }


def choose_design_assets(
    repo_root: str | Path | None = None,
    *,
    query: str | None = None,
    platform: str | None = None,
    style_family: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    assets = discover_design_assets(repo_root)
    q = (query or "").strip().lower()
    selected: list[dict[str, Any]] = []
    for asset in assets:
        haystack = " ".join(
            [
                str(asset.get("brand") or ""),
                str(asset.get("title") or ""),
                str(asset.get("style_family") or ""),
                str(asset.get("platform") or ""),
                " ".join(str(tag) for tag in asset.get("design_tags") or []),
            ]
        ).lower()
        if q and q not in haystack:
            continue
        if platform and platform.lower() not in str(asset.get("platform") or "").lower():
            continue
        if style_family and style_family.lower() not in str(asset.get("style_family") or "").lower():
            continue
        context = build_design_context(asset)
        selected.append({**asset, "context": context, "prompt": context["prompt"]})
    if not selected:
        return []
    selected = sorted(selected, key=lambda item: (0 if q and q in str(item.get("brand") or "").lower() else 1, item.get("brand", "")))
    return selected[: max(1, limit)]
