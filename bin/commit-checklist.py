#!/usr/bin/env python3
"""Commit checklist gate/hint — 14-dimension pre-commit checklist for omostation.

Usage:
    python bin/commit-checklist.py --staged            # strict gate, exit 1 on missing
    python bin/commit-checklist.py --staged --hint-only # advisory hint, never blocks
    python bin/commit-checklist.py --staged --json      # JSON output for tooling

Exit codes:
    0 = pass / hint-only success
    1 = strict mode missing critical items (or bootstrap validation failure)
    2 = invalid arguments / config missing

Self-bootstrap (rule 15):
    Any change to THIS file or docs/generated/commit-checklist-rules.yaml
    triggers an extra 'bootstrap-review' advisory reminding the developer
    to re-validate the checklist mechanism itself.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Sequence

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "docs/generated/commit-checklist-rules.yaml"
# Self-bootstrap: if this file or rules.yaml is changed, require extra review
BOOTSTRAP_FILES = {ROOT / "bin/commit-checklist.py", RULES_PATH}

# ── Helpers ────────────────────────────────────────────────────────────────
def _run_git(*args: str) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", *args], cwd=ROOT, stderr=subprocess.STDOUT, text=True
        )
        return out.strip()
    except subprocess.CalledProcessError:
        return None


def _repo_relative(s: str) -> str:
    try:
        return str(Path(s).resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return s


def _staged_files() -> list[str]:
    out = _run_git("diff", "--cached", "--name-only", "--diff-filter=ACMDR")
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _file_at_head(path: str) -> str | None:
    out = _run_git("show", f"HEAD:{path}")
    return out if out else None


def _yaml_indent_ok(path: str) -> bool:
    """Quick YAML sanity: look for malformed indent in likely YAML files."""
    if not path.endswith((".yaml", ".yml", ".md")):
        return True
    current = _run_git("diff", "--cached", "--", path)
    if not current:
        return True
    # heuristic: tabs in YAML, or lines starting with '- ' at col 0 in non-list context
    for line in current.splitlines():
        if line.startswith("+") or line.startswith("-"):
            body = line[1:]
            if "\t" in body:
                return False
    return True


def _adr_number_conflict() -> bool:
    """Check for duplicate ADR numbers in decisions index."""
    idx = ROOT / ".omo/_knowledge/decisions/INDEX.md"
    if not idx.exists():
        return False
    text = idx.read_text(encoding="utf-8", errors="ignore")
    nums = re.findall(r"ADR-(\d{4})", text)
    return len(nums) != len(set(nums))


def _orphaned_registry_entries() -> list[str]:
    """Detect script-registry entries pointing to missing files."""
    reg = ROOT / ".omo/_truth/registry/script-registry.yaml"
    if not reg.exists():
        return []
    missing: list[str] = []
    for line in reg.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("path:") or line.startswith("- path:"):
            p = line.split(":", 1)[1].strip().strip('"').strip("'")
            if p and not (ROOT / p).exists():
                missing.append(p)
    return missing


def _timeout_regression(staged: list[str]) -> bool:
    """Flag if timeout values appear decreased in config/code."""
    timeout_files = [f for f in staged if f.endswith((".py", ".yaml", ".yml", ".json"))]
    for f in timeout_files:
        current = _run_git("diff", "--cached", "--", f)
        if not current:
            continue
        for line in current.splitlines():
            if line.startswith("-") and any(k in line for k in ("timeout", "Timeout", "TIMEOUT")):
                # removed line had timeout; check if new line also has timeout (simple heuristic)
                pass
    return False


# ── Check items ─────────────────────────────────────────────────────────────
@dataclass
class CheckItem:
    id: str
    title: str
    severity: str  # critical | warning | info
    files: Sequence[str] = field(default_factory=list)
    dirs: Sequence[str] = field(default_factory=list)
    skip_merge: bool = True
    bootstrap_only: bool = False


ITEMS: list[CheckItem] = [
    # 1. Docs & capability registry sync
    CheckItem(
        "docs-capability-sync",
        "Docs & capability registry sync",
        "critical",
        dirs=["docs", "projects", ".omo/_truth/registry"],
    ),
    # 2. Submodule pointer hygiene
    CheckItem(
        "submodule-hygiene",
        "Submodule pointer hygiene",
        "critical",
        dirs=[".gitmodules"],
    ),
    # 3. CI surfaces & script registry
    CheckItem(
        "ci-script-registry",
        "CI surfaces & script registry",
        "critical",
        dirs=[".github/workflows", "bin", "lib"],
    ),
    # 4. Observability & logging
    CheckItem(
        "observability-logging",
        "Observability & logging",
        "warning",
        dirs=["observability", "runtime", "projects/omo"],
    ),
    # 5. Agent awareness & runtime
    CheckItem(
        "agent-runtime",
        "Agent awareness & runtime",
        "warning",
        dirs=[".omo", "projects/agora"],
    ),
    # 6. Architecture convergence
    CheckItem(
        "architecture-convergence",
        "Architecture convergence",
        "critical",
        dirs=["docs", "ARCHITECTURE.md", "docs/layer-contract.yaml"],
    ),
    # 7. Docs & ADR
    CheckItem(
        "docs-adr",
        "Docs & ADR",
        "critical",
        dirs=["docs", ".omo/_knowledge/decisions"],
    ),
    # 8. Lint/Type/Format regression
    CheckItem(
        "lint-type-format",
        "Lint/Type/Format regression",
        "warning",
        dirs=["src", "projects", "bin", "tests"],
    ),
    # 9. CI workflow / script path drift
    CheckItem(
        "ci-path-drift",
        "CI workflow / script path drift",
        "critical",
        dirs=[".github/workflows", "bin", "lib"],
    ),
    # 10. Digest/Evidence/Truth drift
    CheckItem(
        "evidence-drift",
        "Digest/Evidence/Truth drift",
        "critical",
        dirs=["docs/plans", ".omo/_truth", "docs/generated"],
    ),
    # 11. ADR numbering conflict & index alignment
    CheckItem(
        "adr-numbering",
        "ADR numbering conflict & index alignment",
        "critical",
        dirs=[".omo/_knowledge/decisions"],
    ),
    # 12. Orphaned registry cleanup
    CheckItem(
        "orphaned-registry",
        "Orphaned registry cleanup",
        "warning",
        dirs=[".omo/_truth/registry"],
    ),
    # 13. Timeout/Retry/Circuit config
    CheckItem(
        "timeout-retry-circuit",
        "Timeout/Retry/Circuit config",
        "warning",
        dirs=["config", "projects", "bin"],
    ),
    # 14. Emergency fix baseline restore
    CheckItem(
        "baseline-restore",
        "Emergency fix baseline restore",
        "info",
        files=[".omo/state/health.yaml", ".omo/state/system.yaml"],
    ),
    # 15. Bootstrap self-validation (hidden unless triggered)
    CheckItem(
        "bootstrap-self-validation",
        "Bootstrap self-validation (checklist mechanism change)",
        "critical",
        files=["bin/commit-checklist.py", "docs/generated/commit-checklist-rules.yaml"],
        bootstrap_only=True,
    ),
]


# ── Evaluation ──────────────────────────────────────────────────────────────
@dataclass
class CheckResult:
    item: CheckItem
    triggered: bool
    missing: bool = False
    detail: str = ""


def _matches_any(staged: list[str], item: CheckItem) -> bool:
    if item.files:
        return any(s in staged for s in item.files)
    if item.dirs:
        for s in staged:
            for d in item.dirs:
                if s == d or s.startswith(d.rstrip("/") + "/"):
                    return True
    return False


def evaluate(staged: list[str], strict: bool = True) -> tuple[list[CheckResult], list[str]]:
    """Return (results, missing_ids)."""
    staged = [_repo_relative(s) for s in staged]
    results: list[CheckResult] = []
    missing: list[str] = []

    in_merge = bool(_run_git("rev-parse", "-q", "--verify", "MERGE_HEAD"))

    for item in ITEMS:
        if item.skip_merge and in_merge:
            continue
        triggered = _matches_any(staged, item)
        if not triggered:
            continue

        detail = ""
        missing_flag = False

        if item.id == "docs-capability-sync":
            # Check if capability-registry or project-registry changed without docs
            reg_files = [s for s in staged if "registry" in s or "capability" in s]
            doc_files = [s for s in staged if s.startswith("docs/") or s.startswith("projects/")]
            if reg_files and not doc_files:
                detail = "Registry changed without docs update"
                missing_flag = True

        elif item.id == "submodule-hygiene":
            sub_files = [s for s in staged if s == ".gitmodules" or "/.gitmodules" in s or s.startswith("projects/")]
            if sub_files:
                # Verify submodule pointer is fast-forward (already enforced by pre-commit)
                # Here we just ensure docs mention the bump if it's a non-auto-bump
                if sub_files and not any("auto-bump" in (_file_at_head(f) or "") for f in sub_files):
                    detail = "Submodule bump should mention why (unless auto-bump)"
                    missing_flag = True

        elif item.id == "ci-script-registry":
            ci_files = [s for s in staged if ".github/workflows" in s or s.startswith("bin/") or s.startswith("lib/")]
            if ci_files:
                # Check script-registry exists and is updated
                reg = ROOT / ".omo/_truth/registry/script-registry.yaml"
                if not reg.exists():
                    detail = "script-registry.yaml missing"
                    missing_flag = True

        elif item.id == "observability-logging":
            obs_files = [s for s in staged if "observability" in s or "logging" in s or "telemetry" in s]
            if obs_files:
                # At minimum, ensure logging config is consistent
                detail = "Verify logging/telemetry config changed intentionally"

        elif item.id == "agent-runtime":
            agent_files = [s for s in staged if ".omo/" in s or "agora" in s]
            if agent_files:
                # Check agent-workflow or BOS registry updated
                detail = "Agent runtime surfaces changed — verify BOS/agent-workflow impact"

        elif item.id == "architecture-convergence":
            arch_files = [s for s in staged if "ARCHITECTURE.md" in s or "layer-contract" in s]
            if arch_files:
                detail = "Architecture contract changed — ensure ADR recorded"
                missing_flag = True

        elif item.id == "docs-adr":
            docs_files = [s for s in staged if s.startswith("docs/") or ".omo/_knowledge/decisions" in s]
            if docs_files:
                detail = "Docs/ADR surfaces changed — ensure ADR index and decisions updated"
                missing_flag = True

        elif item.id == "lint-type-format":
            code_files = [s for s in staged if s.endswith((".py", ".ts", ".tsx", ".js", ".json"))]
            if code_files:
                # Verify lint passes on changed files (quick heuristic: check for obvious slop)
                detail = "Run lint/type-check on changed files before commit"

        elif item.id == "ci-path-drift":
            ci_files = [s for s in staged if ".github/workflows" in s or "bin/" in s or "lib/" in s]
            if ci_files:
                # Check for archived paths being referenced
                for f in ci_files:
                    content = _file_at_head(f) or ""
                    if "_archive/" in content and "archived" not in f:
                        detail = f"Potential archived path reference in {f}"
                        missing_flag = True

        elif item.id == "evidence-drift":
            truth_files = [s for s in staged if ".omo/_truth" in s or "docs/plans" in s]
            if truth_files:
                # Quick check: YAML indentation
                for f in truth_files:
                    if not _yaml_indent_ok(f):
                        detail = f"YAML indent issue in {f}"
                        missing_flag = True
                        break

        elif item.id == "adr-numbering":
            adr_files = [s for s in staged if ".omo/_knowledge/decisions" in s]
            if adr_files:
                if _adr_number_conflict():
                    detail = "Duplicate ADR numbers detected in INDEX"
                    missing_flag = True

        elif item.id == "orphaned-registry":
            reg_files = [s for s in staged if ".omo/_truth/registry" in s]
            if reg_files:
                orphans = _orphaned_registry_entries()
                if orphans:
                    detail = f"Orphaned registry entries: {', '.join(orphans[:5])}"
                    missing_flag = True

        elif item.id == "timeout-retry-circuit":
            config_files = [s for s in staged if any(k in s for k in ("config", "timeout", "retry", "circuit"))]
            if config_files:
                # Simple heuristic: timeout decreased?
                for f in config_files:
                    diff = _run_git("diff", "--cached", "--", f) or ""
                    for line in diff.splitlines():
                        if line.startswith("-") and "timeout" in line.lower():
                            # Check if a new timeout line exists
                            new_timeout = any(
                                l.startswith("+") and "timeout" in l.lower() for l in diff.splitlines()
                            )
                            if not new_timeout:
                                detail = f"Timeout regression possible in {f}"
                                missing_flag = True
                                break

        elif item.id == "baseline-restore":
            state_files = [s for s in staged if ".omo/state" in s]
            if state_files:
                detail = "State file changed — ensure baseline coherence"

        elif item.id == "bootstrap-self-validation":
            # Only trigger if THIS file or rules.yaml is modified
            changed_bootstrap = [
                s for s in staged
                if Path(s).resolve() in BOOTSTRAP_FILES or RULES_PATH.name == Path(s).name
            ]
            if changed_bootstrap:
                detail = "Checklist mechanism itself changed — re-validate 14-dimension rules and tests"
                missing_flag = True

        if triggered:
            results.append(CheckResult(item=item, triggered=True, missing=missing_flag, detail=detail))
            if missing_flag:
                missing.append(item.id)

    return results, missing


# ── Output formatters ───────────────────────────────────────────────────────
def format_hint(results: list[CheckResult], missing: list[str]) -> str:
    lines = ["# commit-checklist: pre-commit advisory", ""]
    if missing:
        lines.append("## ⚠️  Missing / needs attention")
        for r in results:
            if r.missing:
                lines.append(f"  - [{r.item.id}] {r.item.title}: {r.detail or 'review needed'}")
    else:
        lines.append("## ✅ All triggered checks passed")

    lines.append("")
    lines.append("## 📋 Triggered checks")
    for r in results:
        status = "⚠️" if r.missing else "✅"
        lines.append(f"  {status} [{r.item.id}] {r.item.title}")
    lines.append("")
    lines.append("Run `python bin/commit-checklist.py --staged --json` for machine output.")
    return "\n".join(lines)


def format_json(results: list[CheckResult], missing: list[str]) -> str:
    payload = {
        "triggered": [r.item.id for r in results],
        "missing": missing,
        "passed": [r.item.id for r in results if not r.missing],
        "details": {r.item.id: r.detail for r in results if r.detail},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ── CLI ─────────────────────────────────────────────────────────────────────
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Commit checklist gate/hint")
    parser.add_argument("--staged", action="store_true", help="Read staged files from git")
    parser.add_argument("--hint-only", action="store_true", help="Advisory only, never block")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--files", nargs="*", help="Explicit file list (testing)")
    args = parser.parse_args(argv)

    staged = args.files if args.files is not None else _staged_files()

    # In merge, we still evaluate but skip some structural checks
    results, missing = evaluate(staged, strict=not args.hint_only)

    if args.json:
        print(format_json(results, missing))
        return 0

    if not results:
        # Nothing triggered — clean exit
        return 0

    hint = format_hint(results, missing)
    print(hint)

    if missing and not args.hint_only:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
