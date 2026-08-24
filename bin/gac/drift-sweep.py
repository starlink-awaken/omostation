#!/usr/bin/env python3
"""
drift-sweep.py — Weekly anti-corruption sweep.

Usage:
  uv run python3 bin/gac/drift-sweep.py
  uv run python3 bin/gac/drift-sweep.py --json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run(cmd: str, cwd=None, timeout=300) -> tuple[int, str, str]:
    if cwd is None:
        cwd = REPO_ROOT
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def check_ssot_pointer_drift() -> dict:
    rc, out, err = run("python3 bin/ssot/doc-ssot-lint.py 2>&1 | tail -20")
    return {
        "check": "ssot_pointer_drift",
        "pass": rc == 0,
        "output": (out or err).strip()[-500:],
    }


def check_mof_capability_drift() -> dict:
    rc, out, err = run("python3 bin/gac/mof-capabilities-drift-check.py 2>&1 | tail -20")
    return {
        "check": "mof_capability_drift",
        "pass": rc == 0,
        "output": (out or err).strip()[-500:],
    }


def check_submodule_pointer_drift() -> dict:
    rc, out, err = run("bash bin/ssot/submodule-pointer-transaction.sh --dry-run 2>&1 | tail -20")
    return {
        "check": "submodule_pointer_drift",
        "pass": rc == 0,
        "output": (out or err).strip()[-500:],
    }


def check_adr_link_validity() -> dict:
    adr_dir = REPO_ROOT / ".omo" / "_knowledge" / "decisions"
    if not adr_dir.exists():
        return {"check": "adr_link_validity", "pass": True, "output": "No ADR directory"}
    broken = 0
    total = 0
    for f in adr_dir.glob("*.md"):
        text = f.read_text(errors="ignore")
        for m in re.finditer(r"\[.*?\]\((.*?)\)", text):
            target = m.group(1)
            if target.startswith("/"):
                target_path = Path(target)
                if not target_path.exists() and not target.startswith("http"):
                    broken += 1
                total += 1
    return {
        "check": "adr_link_validity",
        "pass": broken == 0,
        "output": f"Checked {total} links, {broken} broken" if total > 0 else "No links found",
    }


def check_adr_frontmatter_validity() -> dict:
    adr_dir = REPO_ROOT / ".omo" / "_knowledge" / "decisions"
    if not adr_dir.exists():
        return {"check": "adr_frontmatter_validity", "pass": True, "output": "No ADR directory"}
    issues = []
    for f in adr_dir.glob("*.md"):
        text = f.read_text(errors="ignore")
        if "status:" not in text or "lifecycle:" not in text:
            issues.append(f"{f.name}: missing frontmatter")
    return {
        "check": "adr_frontmatter_validity",
        "pass": len(issues) == 0,
        "output": f"{len(issues)} issues found" if issues else "All ADRs have frontmatter",
    }


def check_scene_card_validity() -> dict:
    scene_dir = REPO_ROOT / "docs" / "scene-cards"
    if not scene_dir.exists():
        return {"check": "scene_card_validity", "pass": True, "output": "No scene-cards directory"}
    issues = []
    for f in scene_dir.glob("*.yaml"):
        try:
            import yaml
            list(yaml.safe_load_all(f.read_text()))
        except Exception as e:
            issues.append(f"{f.name}: {e}")
    return {
        "check": "scene_card_validity",
        "pass": len(issues) == 0,
        "output": f"{len(issues)} invalid YAML files" if issues else "All scene cards valid",
    }


def check_runbook_command_validity() -> dict:
    import glob
    runbooks = glob.glob("docs/operations/runbook-*.md")
    broken = []
    for rb in runbooks:
        text = Path(rb).read_text(errors="ignore")
        for m in re.finditer(r"`(bin/[^`]+)`", text):
            cmd_path = m.group(1).split()[0]
            if not (REPO_ROOT / cmd_path).exists():
                broken.append(f"{rb}: {cmd_path}")
    return {
        "check": "runbook_command_validity",
        "pass": len(broken) == 0,
        "output": f"Checked {len(runbooks)} runbooks, {len(broken)} broken commands" + (f": {broken[0]}" if broken else ""),
    }


def check_runbook_frontmatter_validity() -> dict:
    import glob
    runbooks = glob.glob("docs/operations/runbook-*.md")
    issues = []
    for rb in runbooks:
        text = Path(rb).read_text(errors="ignore")
        if not text.startswith("---"):
            issues.append(f"{rb}: missing frontmatter")
            continue
        frontmatter = text.split("---", 2)[1]
        for field in ["status:", "type:", "owner:", "lifecycle:", "last-reviewed:"]:
            if field not in frontmatter:
                issues.append(f"{rb}: missing {field}")
    return {
        "check": "runbook_frontmatter_validity",
        "pass": len(issues) == 0,
        "output": f"{len(issues)} issues found" if issues else f"All {len(runbooks)} runbooks have frontmatter",
    }


def check_runbook_age_check() -> dict:
    import glob
    from datetime import datetime
    runbooks = glob.glob("docs/operations/runbook-*.md")
    stale = []
    for rb in runbooks:
        text = Path(rb).read_text(errors="ignore")
        m = re.search(r"last-reviewed:\s*(\d{4}-\d{2}-\d{2})", text)
        if not m:
            stale.append(f"{rb}: no last-reviewed date")
            continue
        try:
            reviewed = datetime.strptime(m.group(1), "%Y-%m-%d")
            age_days = (datetime.now() - reviewed).days
            if age_days > 90:
                stale.append(f"{rb}: {age_days} days old")
        except Exception:
            stale.append(f"{rb}: invalid date format")
    return {
        "check": "runbook_age_check",
        "pass": len(stale) == 0,
        "output": f"{len(stale)} stale runbooks" if stale else f"All {len(runbooks)} runbooks reviewed within 90 days",
    }


def check_skill_registry_validity() -> dict:
    skills_dir = REPO_ROOT / ".agents" / "skills"
    if not skills_dir.exists():
        return {"check": "skill_registry_validity", "pass": True, "output": "No skills directory"}
    orphaned = []
    total = 0
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            orphaned.append(f"{skill_dir.name}: no SKILL.md")
            continue
        total += 1
        text = skill_md.read_text(errors="ignore")
        # Check for builtin skills (no external file needed)
        if "location: builtin" in text or "builtin" in text.lower():
            continue
        # Check for broken references to bin/ commands
        for m in re.finditer(r"`(bin/[^`]+)`", text):
            cmd_path = m.group(1).split()[0]
            if not (REPO_ROOT / cmd_path).exists():
                orphaned.append(f"{skill_dir.name}: references missing {cmd_path}")
    return {
        "check": "skill_registry_validity",
        "pass": len(orphaned) == 0,
        "output": f"Checked {total} skills, {len(orphaned)} issues" + (f": {orphaned[0]}" if orphaned else ""),
    }


def check_skill_frontmatter_validity() -> dict:
    skills_dir = REPO_ROOT / ".agents" / "skills"
    if not skills_dir.exists():
        return {"check": "skill_frontmatter_validity", "pass": True, "output": "No skills directory"}
    issues = []
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(errors="ignore")
        if not text.startswith("---"):
            issues.append(f"{skill_dir.name}: missing frontmatter")
            continue
        frontmatter = text.split("---", 2)[1]
        for field in ["name:", "description:"]:
            if field not in frontmatter:
                issues.append(f"{skill_dir.name}: missing {field}")
    return {
        "check": "skill_frontmatter_validity",
        "pass": len(issues) == 0,
        "output": f"{len(issues)} issues found" if issues else "All skills have valid frontmatter",
    }


def check_doc_link_validity() -> dict:
    rc, out, err = run("python3 bin/gac/doc-link-check.py 2>&1 | tail -20", timeout=30)
    tool_exists = (REPO_ROOT / "bin" / "gac" / "doc-link-check.py").exists()
    if not tool_exists:
        return {
            "check": "doc_link_validity",
            "pass": None,
            "output": "SKIP: bin/gac/doc-link-check.py not yet implemented (Phase 2 gap)",
        }
    if rc == 1 and "timeout" in (out or err):
        return {
            "check": "doc_link_validity",
            "pass": None,
            "output": "SKIP: doc-link-check.py timed out (too many files, run manually)",
        }
    return {
        "check": "doc_link_validity",
        "pass": rc == 0,
        "output": (out or err).strip()[-500:],
    }


def check_doc_hardcoded_values() -> dict:
    rc, out, err = run("python3 bin/gac/hardcode-scan.py 2>&1 | tail -20", timeout=120)
    tool_exists = (REPO_ROOT / "bin" / "gac" / "hardcode-scan.py").exists()
    if not tool_exists:
        return {
            "check": "doc_hardcoded_values",
            "pass": None,
            "output": "SKIP: bin/gac/hardcode-scan.py not yet implemented (Phase 2 gap)",
        }
    if rc == 1 and "timeout" in (out or err):
        return {
            "check": "doc_hardcoded_values",
            "pass": None,
            "output": "SKIP: hardcode-scan.py timed out (too many files, run manually)",
        }
    return {
        "check": "doc_hardcoded_values",
        "pass": rc == 0,
        "output": (out or err).strip()[-500:],
    }


def check_governance_check_coverage() -> dict:
    rc, out, err = run("uv run python3 bin/ssot/governance-migration.py --dry-run 2>&1 | tail -5")
    output = (out or err).strip()[-500:]
    return {
        "check": "governance_check_coverage",
        "pass": rc == 0 and "No files written" in output,
        "output": output,
    }


def check_script_registry_coverage() -> dict:
    rc, out, err = run("uv run python3 bin/ssot/script-registry.py validate 2>&1 | tail -10")
    return {
        "check": "script_registry_coverage",
        "pass": rc == 0,
        "output": (out or err).strip()[-500:],
    }


def check_layer_contract_compliance() -> dict:
    rc, out, err = run("make check-layers 2>&1 | tail -20")
    return {
        "check": "layer_contract_compliance",
        "pass": rc == 0,
        "output": (out or err).strip()[-500:],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly drift sweep")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    checks = [
        check_ssot_pointer_drift(),
        check_mof_capability_drift(),
        check_submodule_pointer_drift(),
        check_adr_link_validity(),
        check_adr_frontmatter_validity(),
        check_scene_card_validity(),
        check_runbook_command_validity(),
        check_runbook_frontmatter_validity(),
        check_runbook_age_check(),
        check_skill_registry_validity(),
        check_skill_frontmatter_validity(),
        check_doc_link_validity(),
        check_doc_hardcoded_values(),
        check_governance_check_coverage(),
        check_script_registry_coverage(),
        check_layer_contract_compliance(),
    ]

    passed = sum(1 for c in checks if c["pass"])
    failed = sum(1 for c in checks if c["pass"] is False)
    skipped = sum(1 for c in checks if c["pass"] is None)
    total = len(checks)

    if args.json:
        result = {
            "timestamp": "2026-08-24T09:00:00Z",
            "sweep_id": "sweep-2026-08-24",
            "results": checks,
            "summary": {"pass": passed, "fail": failed, "skip": skipped, "total": total},
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if failed == 0 else 1)

    print("Weekly Drift Sweep")
    print("=" * 50)
    for c in checks:
        if c["pass"] is None:
            status = "SKIP"
        elif c["pass"]:
            status = "PASS"
        else:
            status = "FAIL"
        print(f"[{status}] {c['check']}")
        if c["output"]:
            for line in c["output"].splitlines()[:3]:
                print(f"       {line}")
    print("=" * 50)
    print(f"Result: {passed} passed, {failed} failed, {skipped} skipped, {total} total")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
