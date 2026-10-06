#!/usr/bin/env python3
"""GaC #38: OMO state write guard — detect multi-writer conflicts in .omo/ state plane.

Checks three things:
1. Duplicate top-level keys in system.yaml (multi-writer conflict)
2. Unauthorized writes per write-owners.yaml (write protocol violations)
3. Field-level write ownership coverage (undeclared / ghost / unresolvable owner)

Usage:
  python3 bin/gac/omo-state-write-guard.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

# ADR-0456 — 本 guard 自己也在被检查的两个根上: system.yaml 是写面 (profile 声明),
# write-owners.yaml 是读面 (治理 SSOT, 跟随检出)。两者都经 repo_root 取, 不反推 __file__。
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from repo_root import code_root, state_root  # noqa: E402

SYSTEM_YAML_REL = ".omo/state/system.yaml"
WORKSPACE = code_root()


def _system_yaml() -> Path:
    """ADR-0456 B1: resolve at call time — a module constant freezes the pre-profile root."""
    return state_root() / ".omo" / "state" / "system.yaml"


WRITE_OWNERS_YAML = WORKSPACE / ".omo" / "_truth" / "registry" / "write-owners.yaml"
OWNER_LEXICON = ("script:", "daemon:", "human:", "broker:")


# ── Check 1: Duplicate top-level keys ──


def check_duplicate_keys() -> list[dict]:
    """Scan system.yaml for duplicate top-level keys (multi-writer conflict)."""
    findings: list[dict] = []
    system_yaml = _system_yaml()
    if not system_yaml.exists():
        return findings

    text = system_yaml.read_text(encoding="utf-8")
    seen: dict[str, list[int]] = {}

    for i, line in enumerate(text.splitlines(), 1):
        raw = line.split("#")[0]
        if not raw.strip():
            continue
        if ":" in raw and not raw.startswith(" "):
            key = raw.split(":")[0].strip()
            seen.setdefault(key, []).append(i)

    for key, lines in sorted(seen.items()):
        if len(lines) > 1:
            findings.append(
                {
                    "check": "duplicate-key",
                    "key": key,
                    "occurrences": len(lines),
                    "lines": lines,
                    "message": f"Key '{key}' appears {len(lines)} times (lines {lines}) — multi-writer conflict risk",
                }
            )
    return findings


# ── Check 2: Write-owner protocol — detect unauthorized writers ──


def load_write_owners() -> dict:
    """Load write-owners.yaml, return {path: {field: owner}}."""
    if not WRITE_OWNERS_YAML.exists():
        return {}
    try:
        with open(WRITE_OWNERS_YAML) as f:
            data = yaml.safe_load(f)
        return data.get("fields", {})
    except Exception:
        return {}


def check_unauthorized_writes() -> list[dict]:
    """Detect unstaged deletions of protected directories (e.g. .omo/debt/)."""
    findings: list[dict] = []
    owners = load_write_owners()
    if not owners:
        return findings

    import subprocess

    # Check for unstaged deletions of protected paths via git status
    r = subprocess.run(
        ["git", "status", "--short", "--", ".omo/debt/"],
        capture_output=True,
        text=True,
        cwd=WORKSPACE,
        timeout=5,
    )
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("D ") or line.startswith(" D"):
            findings.append(
                {
                    "check": "unauthorized-delete",
                    "path": line[2:].strip() or ".omo/debt/",
                    "message": f"Protected path has unstaged deletion: {line} — only omo-debt system should modify .omo/debt/",
                }
            )
            break  # one finding per directory is enough

    return findings


# ── Check 3: Field-level write ownership coverage ──


def top_level_keys(text: str) -> list[str]:
    """Column-0 keys of a YAML mapping, order-preserving and de-duplicated.

    List items (``- ...``) are values, not mapping keys — skip them, else a
    list item containing ``:`` is misread as a top-level key (false
    undeclared-key positive).
    """
    keys = []
    for line in text.splitlines():
        raw = line.split("#")[0]
        if not raw.strip() or raw[0] in (" ", "\t"):
            continue
        if raw.startswith("- "):
            continue
        if ":" in raw:
            keys.append(raw.split(":")[0].strip())
    return list(dict.fromkeys(keys))


def owner_tokens(owner: object) -> list[str]:
    if isinstance(owner, str):
        return [owner]
    if isinstance(owner, list):
        return [str(item) for item in owner]
    return []


def resolve_owner(owner: str) -> tuple[bool, str]:
    """Validate one owner token against the C1 lexicon. (ok, detail)."""
    if owner == "anyone":
        return True, ""
    if not owner.startswith(OWNER_LEXICON):
        return False, f"owner '{owner}' has no lexicon prefix"
    if owner.startswith("script:"):
        rel = owner[len("script:") :].strip()
        candidate = Path(rel)
        if not rel or candidate.is_absolute() or ".." in candidate.parts:
            return False, f"script path '{rel}' is not a repo-relative path"
        target = code_root() / candidate
        if not target.is_file():
            return False, f"declared writer script does not exist: {rel}"
    return True, ""


def check_field_ownership() -> list[dict]:
    """Every top-level system.yaml key must have a resolvable declared owner."""
    findings: list[dict] = []
    system_yaml = _system_yaml()
    if not system_yaml.exists():
        return findings

    declared = load_write_owners().get(SYSTEM_YAML_REL)
    if declared is None:
        declared = {}
    if not isinstance(declared, dict):
        return [
            {
                "check": "unresolvable-owner",
                "key": SYSTEM_YAML_REL,
                "message": f"fields['{SYSTEM_YAML_REL}'] must be a mapping of key → owner",
            }
        ]

    present = top_level_keys(system_yaml.read_text(encoding="utf-8"))
    present_set = set(present)

    for key in present:
        if key not in declared:
            findings.append(
                {
                    "check": "undeclared-key",
                    "key": key,
                    "message": f"Top-level key '{key}' is written into {SYSTEM_YAML_REL} but has no owner in write-owners.yaml",
                }
            )
    for key in sorted(set(declared) - present_set):
        findings.append(
            {
                "check": "ghost-declaration",
                "key": key,
                "message": f"write-owners.yaml declares '{key}' but {SYSTEM_YAML_REL} has no such top-level key",
            }
        )
    for key in sorted(declared):
        tokens = owner_tokens(declared[key])
        if not tokens:
            findings.append(
                {
                    "check": "unresolvable-owner",
                    "key": key,
                    "message": f"'{key}' declares no owner",
                }
            )
            continue
        for owner in tokens:
            ok, detail = resolve_owner(owner)
            if not ok:
                findings.append(
                    {
                        "check": "unresolvable-owner",
                        "key": key,
                        "owner": owner,
                        "message": f"'{key}' declares {detail}",
                    }
                )
    return findings


# ── Main ──


def ownership_summary(findings: list[dict]) -> dict[str, int]:
    counts = {"undeclared-key": 0, "ghost-declaration": 0, "unresolvable-owner": 0}
    for f in findings:
        if f["check"] in counts:
            counts[f["check"]] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GaC #38 OMO state write guard")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    findings = []
    findings.extend(check_duplicate_keys())
    findings.extend(check_unauthorized_writes())
    ownership = check_field_ownership()
    findings.extend(ownership)

    if args.as_json:
        system_yaml = _system_yaml()
        present = (
            top_level_keys(system_yaml.read_text(encoding="utf-8"))
            if system_yaml.exists()
            else []
        )
        declared = load_write_owners().get(SYSTEM_YAML_REL)
        print(
            json.dumps(
                {
                    "targets": {
                        "system_yaml": str(system_yaml),
                        "write_owners_yaml": str(WRITE_OWNERS_YAML),
                    },
                    "declared": len(declared) if isinstance(declared, dict) else 0,
                    "present": len(present),
                    "ownership": ownership_summary(ownership),
                    "findings": findings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if findings else 0

    if not findings:
        print("[OMO-STATE-WRITE-GUARD] ✅ All checks passed — no conflicts detected")
        return 0

    print("[OMO-STATE-WRITE-GUARD] ❌ Write protocol violations detected!")
    for f in findings:
        print(f"  ⚠️  [{f['check']}] {f['message']}")

    print("  ℹ️  See .omo/_truth/registry/write-owners.yaml for ownership rules")
    return 1


if __name__ == "__main__":
    sys.exit(main())
