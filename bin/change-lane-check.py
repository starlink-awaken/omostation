#!/usr/bin/env python3
"""Guard against mixing unrelated change lanes in one commit."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
ALLOWED_COMBOS = [
    {"governance_code", "docs"},
    {"governance_code", "config"},
    {"governance_code", "docs", "config"},
    {"submodule_pointer", "config"},
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, check=False)


def submodule_paths() -> set[str]:
    result = run(["git", "config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"])
    if result.returncode != 0:
        return set()
    return {line.split(maxsplit=1)[1] for line in result.stdout.splitlines() if line.strip()}


def changed_paths(staged: bool, files: list[str] | None = None) -> list[str]:
    if files:
        return files
    cmd = ["git", "diff", "--cached", "--name-only"] if staged else ["git", "diff", "--name-only"]
    result = run(cmd)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def load_governance_lanes() -> dict[str, str]:
    """读取 sgf-policy.yaml，构建文件路径 -> lane 的映射白名单"""
    yaml_path = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "governance" / "sgf-policy.yaml"
    mapping = {}
    if yaml_path.is_file():
        try:
            import yaml
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            for gate in data.get("gates", []):
                cmd_parts = gate.get("command", [])
                if cmd_parts:
                    script_path = cmd_parts[0]
                    mapping[script_path] = gate.get("lane", "governance_code")
        except Exception:
            pass
    return mapping


def classify(path: str, submodules: set[str]) -> str:
    gov_mappings = load_governance_lanes()
    if path in gov_mappings:
        return gov_mappings[path]
    if path in submodules:
        return "submodule_pointer"
    if path in {
        ".omo/_truth/registry/governance-checks.yaml",
        ".omo/_truth/registry/agent-clis.yaml",
        ".omo/_truth/registry/agent-workflows.yaml",
        ".omo/capabilities/agent-clis.yaml",
        ".omo/standards/agent-workflow-contract.md",
        ".agents/skills/project-governance/SKILL.md",
        "bin/agent-workflow.py",
        "bin/cockpit-readiness.py",
        "bin/dashboard-readiness-summary.py",
        "bin/dashboard-ui-render.py",
        "bin/gac-dashboard.py",
        "bin/governance-dashboard.py",
        "bin/governance-evolution.py",
        "bin/governance-history-stats.py",
        "bin/governance-semantic-gate.py",
        "bin/governance-trend-report.py",
        "bin/install-watch-agent.py",
        "bin/mcp-server-kos.py",
        "bin/project-layer-index.py",
        "bin/state-freshness-check.py",
        "bin/test-mcp-kos.py",
        "bin/write-owner-audit.py",
        "projects/cockpit/src/cockpit/commands/agent_workflow.py",
        "projects/cockpit/src/cockpit/commands/governance.py",
        "projects/cockpit/src/cockpit/tests/test_agent_workflow_command.py",
        "tests/test_agent_workflow.py",
        "tests/test_governance_evolution.py",
    }:
        return "governance_code"
    if path == ".omo/state/system_health.yaml" or path.startswith("runtime/"):
        return "runtime_snapshot"
    if path.startswith(".omo/"):
        return "governance_state"
    if path.endswith(".md") and (
        path in {"AGENTS.md", "CLAUDE.md", "README.md", "ARCHITECTURE.md", "LAYER-INDEX.md", "BRIEF.md"}
        or path.startswith("projects/")
        or path.startswith("spaces/")
        or path.startswith("docs/")
    ):
        return "docs"
    if (
        path.startswith("bin/gac")
        or path in {
            "bin/ssot-guardian.py",
            "bin/doc-ssot-lint.py",
            "bin/sync-submodules-push.sh",
            "bin/submodule-reachability-gate.py",
            "bin/submodule-pointer-transaction.sh",
            "bin/change-lane-check.py",
            "bin/check-cockpit-ui-dist.py",
            "bin/doc-link-check.py",
        }
        or path.startswith(".githooks/")
        or path in {".pre-commit-config.yaml", ".github/workflows/gac-gate.yml", ".github/workflows/governance-check.yml"}
    ):
        return "governance_code"
    if path in {".gitmodules", "Makefile"} or path.startswith(".github/workflows/"):
        return "config"
    if path.endswith((".py", ".ts", ".js", ".sh", ".json", ".yaml", ".yml")):
        return "code"
    return "other"


def allowed(lanes: set[str]) -> bool:
    return allowed_for(lanes, allowed_lanes=set())


def allowed_for(lanes: set[str], allowed_lanes: set[str]) -> bool:
    if len(lanes) <= 1:
        return True
    if "runtime_snapshot" in lanes and len(lanes) > 1:
        return False
    if allowed_lanes and lanes <= allowed_lanes:
        return True
    if "submodule_pointer" in lanes and not any(lanes <= combo for combo in ALLOWED_COMBOS):
        return False
    if "governance_state" in lanes and len(lanes) > 1:
        return False
    return any(lanes <= combo for combo in ALLOWED_COMBOS)


def parse_allowed_lanes(values: list[str]) -> set[str]:
    lanes: set[str] = set()
    for value in values:
        for lane in value.split(","):
            normalized = lane.strip()
            if normalized:
                lanes.add(normalized)
    return lanes


def check(
    staged: bool,
    files: list[str] | None = None,
    allowed_lanes: set[str] | None = None,
) -> dict[str, object]:
    submodules = submodule_paths()
    paths = changed_paths(staged, files)
    by_lane: dict[str, list[str]] = {}
    for path in paths:
        lane = classify(path, submodules)
        by_lane.setdefault(lane, []).append(path)
    lanes = set(by_lane)
    allowed_lane_set = allowed_lanes or set()
    return {
        "ok": allowed_for(lanes, allowed_lane_set),
        "staged": staged,
        "lanes": sorted(lanes),
        "allowed_lanes": sorted(allowed_lane_set),
        "by_lane": by_lane,
        "files": len(paths),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check staged or unstaged change lanes")
    parser.add_argument("--staged", action="store_true", help="Check staged changes")
    parser.add_argument("--file", action="append", default=[], help="Check an explicit changed file path")
    parser.add_argument("--allow-lane", action="append", default=[], help="Allow an explicit lane for this check")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--advisory", action="store_true", help="Always exit 0")
    args = parser.parse_args()

    allowed_lanes = parse_allowed_lanes([os.environ.get("AGENT_WORKFLOW_ALLOWED_LANES", ""), *args.allow_lane])
    report = check(staged=args.staged, files=args.file, allowed_lanes=allowed_lanes)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["ok"]:
        print(f"change-lane-check: PASS ({report['files']} files, lanes={','.join(report['lanes']) or '-'})")
    else:
        print(f"change-lane-check: FAIL mixed lanes={','.join(report['lanes'])}")
        for lane, paths in report["by_lane"].items():
            preview = ", ".join(paths[:5])
            suffix = "" if len(paths) <= 5 else f" ... +{len(paths) - 5}"
            print(f"  {lane}: {preview}{suffix}")
    return 0 if report["ok"] or args.advisory else 1


if __name__ == "__main__":
    sys.exit(main())
