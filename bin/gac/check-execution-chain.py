#!/usr/bin/env python3
"""Execution-chain coverage — fuse existing inventories, do not invent a new OS.

An item is in the chain if it appears in at least one inventory:

  script-registry × ci-surfaces × cron
  + capability-registry (mcp_servers, cli_commands)
  + agent-workflows
  + .agents/skills
  + .githooks files

Legal triggers (hook / CI / cron / manual) are derived from the same records.
Live items with no classified trigger are warnings. Active items injected via
extra_active that appear in none of the inventories fail-closed (CR-EXEC-CHAIN-01).

Usage:
    python3 bin/gac/check-execution-chain.py
    python3 bin/gac/check-execution-chain.py --json
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
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCRIPT_REGISTRY = ROOT / "bin" / "_registry" / "scripts"
DEFAULT_CI_SURFACES = ROOT / ".omo" / "_truth" / "registry" / "ci-surfaces.yaml"
DEFAULT_CRON = ROOT / ".omo" / "cron" / "registry.yaml"
DEFAULT_HOOKS = ROOT / ".githooks"
DEFAULT_CAPABILITY_REGISTRY = ROOT / "docs" / "generated" / "capability-registry.yaml"
DEFAULT_WORKFLOWS = ROOT / ".omo" / "_truth" / "registry" / "agent-workflows" / "workflows"
DEFAULT_SKILLS = ROOT / ".agents" / "skills"
BIN_IN_COMMAND = re.compile(r"(bin/[A-Za-z0-9_./-]+\.(?:py|sh))")
NONE_WORKFLOWS = {"", "(none)", "none", "null"}


def _load(path: Path):
    if yaml is None:
        raise RuntimeError("pyyaml required")
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    docs = [d for d in yaml.safe_load_all(text) if d is not None]
    if not docs:
        return None
    return docs[-1]


def _norm(path: str) -> str:
    p = str(path or "").strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p


def _extract_bin_paths(text: str) -> list[str]:
    return [_norm(m) for m in BIN_IN_COMMAND.findall(text or "")]


def _load_script_records(registry_dir: Path) -> list[dict]:
    records: list[dict] = []
    if not registry_dir.is_dir():
        return records
    for path in sorted(registry_dir.rglob("*.yaml")):
        data = _load(path)
        if isinstance(data, dict) and data.get("id"):
            records.append(data)
    return records


def _load_ci_surfaces(path: Path) -> list[dict]:
    data = _load(path)
    if not isinstance(data, dict):
        return []
    surfaces = data.get("surfaces") or []
    return [s for s in surfaces if isinstance(s, dict)]


def _load_cron_jobs(path: Path) -> list[dict]:
    data = _load(path)
    if not isinstance(data, dict):
        return []
    jobs = data.get("jobs") or []
    return [j for j in jobs if isinstance(j, dict)]


def _hook_files(hooks_dir: Path) -> list[Path]:
    if not hooks_dir.is_dir():
        return []
    return [p for p in sorted(hooks_dir.iterdir()) if p.is_file() and p.name != "README.md"]


def _hook_paths(hooks_dir: Path) -> set[str]:
    found: set[str] = set()
    for path in _hook_files(hooks_dir):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found.update(_extract_bin_paths(text))
    return found


def _load_capability_registry(path: Path) -> dict:
    data = _load(path)
    return data if isinstance(data, dict) else {}


def _load_workflows(workflows_dir: Path) -> list[dict]:
    records: list[dict] = []
    if not workflows_dir.is_dir():
        return records
    for path in sorted(workflows_dir.glob("*.yaml")):
        data = _load(path)
        if isinstance(data, dict) and data.get("id"):
            records.append(data)
    return records


def _load_skills(skills_dir: Path) -> list[str]:
    names: list[str] = []
    if not skills_dir.is_dir():
        return names
    for path in sorted(skills_dir.rglob("SKILL.md")):
        rel = path.parent.relative_to(skills_dir).as_posix()
        if rel and rel != ".":
            names.append(rel)
    return names


def check(
    *,
    script_registry_dir: Path | None = None,
    ci_surfaces_path: Path | None = None,
    cron_registry_path: Path | None = None,
    hooks_dir: Path | None = None,
    capability_registry_path: Path | None = None,
    workflows_dir: Path | None = None,
    skills_dir: Path | None = None,
    extra_active: list[str] | None = None,
) -> dict:
    """Fuse inventories and classify triggers.

    extra_active: claimed-active ids that must appear in at least one
    inventory. Live CLI leaves this empty so historical gaps are warnings.
    """
    script_registry_dir = Path(script_registry_dir or DEFAULT_SCRIPT_REGISTRY)
    ci_surfaces_path = Path(ci_surfaces_path or DEFAULT_CI_SURFACES)
    cron_registry_path = Path(cron_registry_path or DEFAULT_CRON)
    hooks_dir = Path(hooks_dir or DEFAULT_HOOKS)
    capability_registry_path = Path(capability_registry_path or DEFAULT_CAPABILITY_REGISTRY)
    workflows_dir = Path(workflows_dir or DEFAULT_WORKFLOWS)
    skills_dir = Path(skills_dir or DEFAULT_SKILLS)
    extra_active = [_norm(x) for x in (extra_active or []) if _norm(x)]

    scripts = _load_script_records(script_registry_dir)
    surfaces = _load_ci_surfaces(ci_surfaces_path)
    jobs = _load_cron_jobs(cron_registry_path)
    hook_files = _hook_files(hooks_dir)
    hook_hits = _hook_paths(hooks_dir)
    capreg = _load_capability_registry(capability_registry_path)
    mcp_servers = [s for s in (capreg.get("mcp_servers") or []) if isinstance(s, dict)]
    cli_commands = [c for c in (capreg.get("cli_commands") or []) if isinstance(c, dict)]
    workflows = _load_workflows(workflows_dir)
    skills = _load_skills(skills_dir)

    items: dict[str, dict] = {}

    def _ensure(item_id: str) -> dict:
        rec = items.setdefault(
            item_id,
            {"id": item_id, "triggers": set(), "sources": set()},
        )
        return rec

    def _add_manual(item_id: str, source: str) -> None:
        if not item_id:
            return
        row = _ensure(item_id)
        row["sources"].add(source)
        row["triggers"].add("manual")

    for rec in scripts:
        item_id = _norm(rec.get("id", ""))
        if not item_id:
            continue
        row = _ensure(item_id)
        row["sources"].add("script-registry")
        for trig in rec.get("triggers") or []:
            name = str(trig).strip().lower()
            if name in {"manual", "hook", "ci", "cron"}:
                row["triggers"].add("manual" if name == "manual" else name)
            elif name:
                row["triggers"].add("manual")

    for surf in surfaces:
        status = str(surf.get("status") or "active").lower()
        if status not in {"", "active"}:
            continue
        item_id = _norm(surf.get("tool") or "")
        if not item_id:
            continue
        row = _ensure(item_id)
        row["sources"].add("ci-surfaces")
        if surf.get("gate") is True:
            row["triggers"].add("hook")
        workflow = str(surf.get("workflow") or "").strip()
        declared = [str(t).strip().lower() for t in (surf.get("triggers") or [])]
        if workflow.lower() not in NONE_WORKFLOWS:
            row["triggers"].add("CI")
        if any(t in {"push", "per_pr", "pull_request", "schedule", "workflow_run"} for t in declared):
            row["triggers"].add("CI")
        if "manual" in declared:
            row["triggers"].add("manual")

    for job in jobs:
        command = str(job.get("command") or "")
        for item_id in _extract_bin_paths(command):
            row = _ensure(item_id)
            row["sources"].add("cron")
            row["triggers"].add("cron")

    for hook_file in hook_files:
        item_id = _norm(f".githooks/{hook_file.name}")
        row = _ensure(item_id)
        row["sources"].add("githooks")
        row["triggers"].add("hook")

    for item_id in hook_hits:
        if item_id in items:
            items[item_id]["triggers"].add("hook")
            items[item_id]["sources"].add("githooks")

    for server in mcp_servers:
        sid = _norm(str(server.get("id") or ""))
        if sid:
            _add_manual(f"mcp-server:{sid}", "mcp")

    for cmd in cli_commands:
        name = _norm(str(cmd.get("name") or cmd.get("id") or ""))
        if name:
            _add_manual(f"cli:{name}", "cli")

    for wf in workflows:
        wid = _norm(str(wf.get("id") or ""))
        if wid:
            _add_manual(f"workflow:{wid}", "workflow")

    for skill in skills:
        _add_manual(f"skill:{skill}", "skill")

    errors: list[str] = []
    warnings: list[str] = []
    viewed: list[dict] = []

    for item_id, row in sorted(items.items()):
        triggers = sorted(row["triggers"])
        sources = sorted(row["sources"])
        viewed.append({"id": item_id, "triggers": triggers, "sources": sources})
        if not triggers:
            warnings.append(
                f"{item_id}: in {','.join(sources)} but no legal trigger (hook/CI/cron/manual)"
            )

    universe = set(items)
    for item_id in extra_active:
        if item_id not in universe:
            errors.append(
                f"CR-EXEC-CHAIN-01: active item {item_id!r} in none of "
                "script-registry/ci-surfaces/cron/mcp/workflow/skill/cli/githooks"
            )

    serial_items = viewed[:40] if len(viewed) > 40 else viewed

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "inventories": {
            "script_registry": len(scripts),
            "ci_surfaces": len(surfaces),
            "cron_jobs": len(jobs),
            "githooks": len(hook_files),
            "mcp_servers": len(mcp_servers),
            "cli_commands": len(cli_commands),
            "workflows": len(workflows),
            "skills": len(skills),
        },
        "examined": len(viewed),
        "items": serial_items,
        "constraint_ids": ["CR-EXEC-CHAIN-01"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--script-registry-dir", type=Path, default=None)
    parser.add_argument("--ci-surfaces", type=Path, default=None)
    parser.add_argument("--cron-registry", type=Path, default=None)
    parser.add_argument("--hooks-dir", type=Path, default=None)
    parser.add_argument("--capability-registry", type=Path, default=None)
    parser.add_argument("--workflows-dir", type=Path, default=None)
    parser.add_argument("--skills-dir", type=Path, default=None)
    parser.add_argument("--extra-active", action="append", default=[])
    args = parser.parse_args(argv)
    result = check(
        script_registry_dir=args.script_registry_dir,
        ci_surfaces_path=args.ci_surfaces,
        cron_registry_path=args.cron_registry,
        hooks_dir=args.hooks_dir,
        capability_registry_path=args.capability_registry,
        workflows_dir=args.workflows_dir,
        skills_dir=args.skills_dir,
        extra_active=args.extra_active,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"execution-chain: {'PASS' if result['ok'] else 'FAIL'}")
        inv = result["inventories"]
        print(
            "  inventories "
            f"script_registry={inv['script_registry']} "
            f"ci_surfaces={inv['ci_surfaces']} "
            f"cron_jobs={inv['cron_jobs']} "
            f"githooks={inv['githooks']} "
            f"mcp_servers={inv['mcp_servers']} "
            f"cli_commands={inv['cli_commands']} "
            f"workflows={inv['workflows']} "
            f"skills={inv['skills']} "
            f"examined={result['examined']}"
        )
        for e in result["errors"]:
            print(f"  ERROR  {e}")
        for w in result["warnings"][:20]:
            print(f"  WARN   {w}")
        if len(result["warnings"]) > 20:
            print(f"  WARN   … {len(result['warnings']) - 20} more")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
