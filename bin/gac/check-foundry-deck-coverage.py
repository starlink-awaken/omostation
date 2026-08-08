#!/usr/bin/env python3
"""check-foundry-deck-coverage: verify each governance axis has a foundry deck.

Scans the workspace for foundry deck definitions across multiple locations:

  1. ``projects/foundry/decks/`` — per-axis deck files (e.g. ``x1-deck.md``)
  2. ``.omo/_truth/registry/foundry-decks.yaml`` — registry listing with
     ``deck_id`` and ``axis`` fields
  3. ``.omo/_truth/x[1-4]-*.yaml`` — governance axis files that may embed
     a ``deck:``, ``deck_path:``, or ``foundry_deck:`` key
  4. ``docs/`` — files whose frontmatter or body reference "foundry deck"
     for a specific axis (e.g. ``foundry_deck: x1``)

For each governance axis (X1, X2, X3, X4), the check verifies that at least
one deck definition exists. If any axis is missing a deck, the check fails.

Output:
  - exit 0 = all axes have a deck
  - exit 1 = one or more axes are missing a deck
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


WORKSPACE = Path(__file__).resolve().parents[2]

GOVERNANCE_AXES = ["X1", "X2", "X3", "X4"]

# Paths to check for deck definitions.
DECK_DIR = WORKSPACE / "projects" / "foundry" / "decks"
DECK_REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "foundry-decks.yaml"
GOV_AXIS_FILES = [
    WORKSPACE / ".omo" / "_truth" / "x1-governance-policies.yaml",
    WORKSPACE / ".omo" / "_truth" / "x2-freshness-rules.yaml",
    WORKSPACE / ".omo" / "_truth" / "x3-value-stack.yaml",
    WORKSPACE / ".omo" / "_truth" / "x4-consistency-rules.yaml",
]
DOCS_DIR = WORKSPACE / "docs"


# ---------------------------------------------------------------------------
# 1.  Scan ``projects/foundry/decks/``
# ---------------------------------------------------------------------------

def _scan_deck_dir() -> dict[str, list[dict]]:
    """Return {axis: [deck_info, ...]} for per-axis files in the deck directory."""
    axis_re = re.compile(
        r"(?P<axis>[Xx][1-4])"
        r"[._-]?(?:deck|foundry|governance|md|yaml|yml)",
        re.IGNORECASE,
    )
    result: dict[str, list[dict]] = {}

    if not DECK_DIR.is_dir():
        return result

    for child in sorted(DECK_DIR.iterdir()):
        if child.is_file() and child.suffix in (".md", ".yaml", ".yml"):
            m = axis_re.search(child.stem)
            if m:
                axis = m.group("axis").upper()
                result.setdefault(axis, []).append({
                    "source": "deck_dir",
                    "path": str(child.relative_to(WORKSPACE)),
                    "filename": child.name,
                })
        elif child.is_dir():
            # Check if the directory name itself maps to an axis.
            dm = axis_re.search(child.name)
            if dm:
                axis = dm.group("axis").upper()
                result.setdefault(axis, []).append({
                    "source": "deck_dir",
                    "path": str(child.relative_to(WORKSPACE)),
                    "filename": child.name,
                })

    # Also check for an index file that lists decks.
    index_file = DECK_DIR / "index.yaml"
    if index_file.is_file():
        _merge_deck_index(index_file, result, "deck_dir_index")

    return result


# ---------------------------------------------------------------------------
# 2.  Scan ``.omo/_truth/registry/foundry-decks.yaml``
# ---------------------------------------------------------------------------

def _scan_deck_registry() -> dict[str, list[dict]]:
    """Return {axis: [deck_info, ...]} from the foundry-decks registry."""
    result: dict[str, list[dict]] = {}

    if not DECK_REGISTRY.is_file():
        return result

    raw = _load_yaml(DECK_REGISTRY)
    if not raw:
        return result

    # Support both single-doc and multi-doc YAML.
    docs = raw if isinstance(raw, list) else [raw]
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        for entry in doc.get("decks", doc.get("foundry_decks", [])):
            if not isinstance(entry, dict):
                continue
            axis = (entry.get("axis") or "").upper().strip()
            if axis not in GOVERNANCE_AXES:
                continue
            result.setdefault(axis, []).append({
                "source": "deck_registry",
                "deck_id": entry.get("deck_id", "?"),
                "path": entry.get("path", str(DECK_REGISTRY.relative_to(WORKSPACE))),
            })

    return result


# ---------------------------------------------------------------------------
# 3.  Scan governance axis YAML files (``.omo/_truth/x[1-4]-*.yaml``)
# ---------------------------------------------------------------------------

def _scan_gov_axis_files() -> dict[str, list[dict]]:
    """Return {axis: [deck_info, ...]} for deck references embedded in axis files."""
    axis_map = {
        "x1-governance-policies": "X1",
        "x2-freshness-rules": "X2",
        "x3-value-stack": "X3",
        "x4-consistency-rules": "X4",
    }
    result: dict[str, list[dict]] = {}

    for fpath in GOV_AXIS_FILES:
        if not fpath.is_file():
            continue
        stem = fpath.stem
        axis = axis_map.get(stem)
        if not axis:
            continue

        raw = _load_yaml(fpath)
        if not raw:
            # File exists but is empty or unparseable — no deck reference.
            continue

        doc = raw if isinstance(raw, dict) else (raw[0] if isinstance(raw, list) and raw else {})
        if not isinstance(doc, dict):
            continue

        # Check for explicit deck references.
        deck_ref = (
            doc.get("deck")
            or doc.get("deck_path")
            or doc.get("foundry_deck")
        )
        if deck_ref:
            result.setdefault(axis, []).append({
                "source": "gov_axis_file",
                "path": str(fpath.relative_to(WORKSPACE)),
                "deck_ref": str(deck_ref),
            })

    return result


# ---------------------------------------------------------------------------
# 4.  Scan ``docs/`` for files referencing "foundry deck" per axis
# ---------------------------------------------------------------------------

def _scan_docs() -> dict[str, list[dict]]:
    """Return {axis: [deck_info, ...]} for docs that reference a foundry deck per axis."""
    result: dict[str, list[dict]] = {}

    if not DOCS_DIR.is_dir():
        return result

    axis_re = re.compile(
        r"(?:foundry[_-]?deck|deck[_-]?(?:for|of)?[_-]?)"
        r"[:\s]*"
        r"(?P<axis>[Xx][1-4])",
        re.IGNORECASE,
    )

    for child in sorted(DOCS_DIR.rglob("*")):
        if not child.is_file():
            continue
        if child.suffix not in (".md", ".yaml", ".yml", ".rst"):
            continue
        try:
            text = child.read_text(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover
            continue

        # Check frontmatter first.
        fm = _parse_frontmatter(text)
        if fm:
            for key in ("foundry_deck", "deck", "deck_axis", "governance_deck"):
                val = fm.get(key)
                if val and str(val).upper().strip() in GOVERNANCE_AXES:
                    axis = str(val).upper().strip()
                    result.setdefault(axis, []).append({
                        "source": "doc_frontmatter",
                        "path": str(child.relative_to(WORKSPACE)),
                        "axis": axis,
                    })
                    break

        # Check body for axis-specific references.
        for m in axis_re.finditer(text):
            axis = m.group("axis").upper()
            if axis in GOVERNANCE_AXES:
                result.setdefault(axis, []).append({
                    "source": "doc_body",
                    "path": str(child.relative_to(WORKSPACE)),
                    "axis": axis,
                    "match": m.group().strip(),
                })

    return result


# ---------------------------------------------------------------------------
# 5.  Scan ``bin/decks/`` for existing deck scripts that may be axis-specific
# ---------------------------------------------------------------------------

def _scan_bin_decks() -> dict[str, list[dict]]:
    """Return {axis: [deck_info, ...]} for deck scripts in bin/decks/."""
    axis_re = re.compile(r"(?P<axis>[Xx][1-4])", re.IGNORECASE)
    result: dict[str, list[dict]] = {}
    decks_dir = WORKSPACE / "bin" / "decks"

    if not decks_dir.is_dir():
        return result

    for child in sorted(decks_dir.iterdir()):
        if not child.is_file() or child.suffix not in (".py", ".sh"):
            continue
        m = axis_re.search(child.stem)
        if m:
            axis = m.group("axis").upper()
            result.setdefault(axis, []).append({
                "source": "bin_decks",
                "path": str(child.relative_to(WORKSPACE)),
                "filename": child.name,
            })

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict | list | None:
    """Safely load a YAML file, returning None on failure."""
    if yaml is None:  # pragma: no cover
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover
        return None


def _parse_frontmatter(text: str) -> dict | None:
    """Extract YAML frontmatter from a markdown file."""
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end == -1:
        return None
    front = text[3:end].strip()
    if yaml is None:  # pragma: no cover
        return None
    try:
        return yaml.safe_load(front)
    except Exception:  # pragma: no cover
        return None


def _merge_deck_index(index_file: Path, result: dict[str, list[dict]], source: str) -> None:
    """Merge entries from a deck index.yaml into the result dict."""
    raw = _load_yaml(index_file)
    if not raw:
        return
    docs = raw if isinstance(raw, list) else [raw]
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        for entry in doc.get("decks", doc.get("foundry_decks", [])):
            if not isinstance(entry, dict):
                continue
            axis = (entry.get("axis") or "").upper().strip()
            if axis not in GOVERNANCE_AXES:
                continue
            result.setdefault(axis, []).append({
                "source": source,
                "deck_id": entry.get("deck_id", "?"),
                "path": entry.get("path", str(index_file.relative_to(WORKSPACE))),
            })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    # Collect deck info from all sources.
    all_sources = [
        ("deck_dir", _scan_deck_dir),
        ("deck_registry", _scan_deck_registry),
        ("gov_axis_files", _scan_gov_axis_files),
        ("docs", _scan_docs),
        ("bin_decks", _scan_bin_decks),
    ]

    decks_by_axis: dict[str, list[dict]] = {}
    source_stats: dict[str, int] = {}
    total_deck_count = 0

    for source_name, scanner in all_sources:
        found = scanner()
        for axis, entries in found.items():
            decks_by_axis.setdefault(axis, []).extend(entries)
            source_stats[source_name] = source_stats.get(source_name, 0) + len(entries)
            total_deck_count += len(entries)

    # Determine coverage per axis.
    axis_coverage: dict[str, dict] = {}
    for axis in GOVERNANCE_AXES:
        entries = decks_by_axis.get(axis, [])
        axis_coverage[axis] = {
            "covered": len(entries) > 0,
            "deck_count": len(entries),
            "decks": entries,
        }

    covered_axes = [a for a in GOVERNANCE_AXES if axis_coverage[a]["covered"]]
    missing_axes = [a for a in GOVERNANCE_AXES if not axis_coverage[a]["covered"]]

    ok = not missing_axes

    # Build report.
    report = {
        "ok": ok,
        "summary": {
            "total_decks_found": total_deck_count,
            "axes_total": len(GOVERNANCE_AXES),
            "axes_covered": len(covered_axes),
            "axes_missing": len(missing_axes),
            "covered_axes": covered_axes,
            "missing_axes": missing_axes,
            "sources": source_stats,
        },
        "axis_coverage": {
            axis: {
                "covered": axis_coverage[axis]["covered"],
                "deck_count": axis_coverage[axis]["deck_count"],
            }
            for axis in GOVERNANCE_AXES
        },
        "findings": [],
    }

    # Build human-readable findings for missing axes.
    for axis in missing_axes:
        report["findings"].append({
            "kind": "missing_deck",
            "axis": axis,
            "message": (
                f"Governance axis {axis} has no foundry deck definition. "
                f"Create a deck file in projects/foundry/decks/, "
                f"register in .omo/_truth/registry/foundry-decks.yaml, "
                f"or add a deck reference in .omo/_truth/{axis.lower()}-*.yaml."
            ),
        })

    # If decks exist, include detail paths.
    if total_deck_count > 0:
        report["deck_details"] = {}
        for axis in GOVERNANCE_AXES:
            details = []
            for entry in decks_by_axis.get(axis, []):
                details.append({
                    "source": entry.get("source", "?"),
                    "path": entry.get("path", "?"),
                    "filename": entry.get("filename", entry.get("deck_id", "?")),
                })
            if details:
                report["deck_details"][axis] = details

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-foundry-deck-coverage: {'PASS' if ok else 'FAIL'}")
        print(f"  Total decks found: {total_deck_count}")
        print(f"  Axes covered: {len(covered_axes)}/{len(GOVERNANCE_AXES)}")
        print(f"  Covered: {', '.join(covered_axes) if covered_axes else '(none)'}")
        if missing_axes:
            print(f"  Missing: {', '.join(missing_axes)}")
        if source_stats:
            parts = [f"{k}={v}" for k, v in sorted(source_stats.items())]
            print(f"  Sources: {', '.join(parts)}")
        for f in report["findings"]:
            print(f"  - {f.get('axis', '?')}: {f.get('message', '')}")
        if total_deck_count > 0:
            for axis in GOVERNANCE_AXES:
                details = decks_by_axis.get(axis, [])
                if not details:
                    continue
                print(f"\n  {axis} decks:")
                for entry in details:
                    loc = entry.get("path", "?")
                    filename = entry.get("filename", entry.get("deck_id", "?"))
                    src = entry.get("source", "?")
                    print(f"    - [{src}] {filename} ({loc})")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
