#!/usr/bin/env python3
"""Run the local Governance-as-Code gate used by hooks and CI, driven by SGF-v1 metadata policy."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY_PATH = WORKSPACE / ".omo/_truth/registry/agent-workflows.yaml"
SGF_POLICY_YAML = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "governance" / "sgf-policy.yaml"


def load_sgf_policy() -> dict:
    """Load SGF-v1 dynamic configuration. Fallback to hardcoded default values if missing."""
    if SGF_POLICY_YAML.is_file():
        try:
            import yaml
            return yaml.safe_load(SGF_POLICY_YAML.read_text(encoding="utf-8")) or {}
        except Exception as e:
            print(f"[WARN] Failed to load sgf-policy.yaml: {e}. Falling back to default policy.", file=sys.stderr)
    return {}


# 默认降级策略 (防止 yaml 丢失崩溃)
DEFAULT_POLICY = {
    "settings": {
        "output": {"terminal_mode": "slim"}
    },
    "gates": [
        {"id": "gac-validate", "command": ["bin/gac/gac-validate.py", "--gate"]},
        {"id": "gac-drift", "command": ["bin/gac/gac-drift.py"]},
        {"id": "write-owner-audit", "command": ["bin/ssot/write-owner-audit.py", "--staged"]},
        {"id": "install-watch-agent", "command": ["bin/gac/install-watch-agent.py"], "ci_skip": True},
        {"id": "test-mcp-kos", "command": ["bin/ssot/test-mcp-kos.py"]},
        {"id": "check-cockpit-ui-dist", "command": ["bin/ssot/check-cockpit-ui-dist.py"]},
        {"id": "agent-workflow-lint", "command": ["bin/agent-workflow.py", "lint"]},
        {"id": "agent-workflow-integrations", "command": ["bin/agent-workflow.py", "integrations"]},
        {"id": "agent-workflow-adapters", "command": ["bin/agent-workflow.py", "adapters"]},
        {"id": "agent-workflow-bootstrap", "command": ["bin/agent-workflow.py", "bootstrap", "--skip-health"]},
        {"id": "agent-workflow-verify-plan", "command": ["bin/agent-workflow.py", "verify", "--file", "bin/agent-workflow.py"], "agent_workflow_only": True},
        {"id": "agent-workflow-compliance", "command": ["bin/agent-workflow.py", "compliance"], "agent_workflow_only": True},
        {"id": "agent-workflow-doctor", "command": ["bin/agent-workflow.py", "doctor"], "ci_skip": True, "agent_workflow_only": True},
        {"id": "agent-workflow-observe", "command": ["bin/agent-workflow.py", "observe"]},
        {"id": "governance-evolution", "command": ["bin/gac/governance-evolution.py", "validate", "--json"]},
        {"id": "mof-schema-validate", "command": ["projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py", "--json"], "ci_skip": True, "agent_workflow_only": True},
        {"id": "mof-state-bridge", "command": ["projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py", "--json"]},
        {"id": "mof-drift", "command": ["bin/mof/mof-drift"]},
        {"id": "m4-bootstrap-reflex", "command": ["bin/mof/mof-bootstrap.py", "all"]},
        {"id": "m4-mcp-tool-integrity", "command": ["bin/gac/mcp-tool-data-complete.py"]},
        {"id": "doc-ssot-lint", "command": ["bin/ssot/doc-ssot-lint.py"]},
        {"id": "project-layer-index", "command": ["bin/mof/project-layer-index.py", "--check"], "ci_only": True},
        {"id": "doc-ssot-snapshots", "command": ["scripts/check-doc-ssot-snapshots.py"]},
        {"id": "doc-link-check", "command": ["bin/ssot/doc-link-check.py"]},
        {"id": "change-lane-check", "command": ["bin/change-lane-check.py", "--staged"]},
        {"id": "dependency-baseline-drift", "command": ["bin/mof/gen-dependency-baseline.py", "--check"], "ci_only": True},
        {"id": "matrix-consistency", "command": ["bin/ssot/matrix-consistency-lint.py", "--skip-launchd"], "ci_skip": True},
        {"id": "governance-convergence", "command": ["bin/gac/governance-convergence-lint.py"]},
        {"id": "governance-semantic-gate", "command": ["bin/gac/governance-semantic-gate.py", "--json"]},
        {"id": "state-freshness-check", "command": ["bin/gac/state-freshness-check.py", "--json"]},
        {"id": "check-dashboard-registry-consistency", "command": ["bin/ssot/check-dashboard-registry-consistency.py"]},
        {"id": "check-toolbox-ssot", "command": ["bin/ssot/check-toolbox-ssot.py"]},
        {"id": "check-domain-m1-alignment", "command": ["bin/ssot/check-domain-m1-alignment.py"]},
        {"id": "test-gac-engine", "command": ["bin/ssot/test-gac-engine.py"]},
        {"id": "service-config-validate", "command": ["bin/mof/gen-service-configs.py", "--validate"]},
        {"id": "service-config-drift", "command": ["bin/mof/gen-service-configs.py", "--check"], "ci_skip": True},
        {"id": "gac-mesh-router-check", "command": ["bin/gac/gac-mesh-router.py", "--check"]},
        {"id": "gac-consensus-inject-check", "command": ["bin/gac/gac-consensus-inject.py", "--check"]},
        {"id": "gac-compute-onboard-check", "command": ["bin/gac/gac-compute-onboard.py", "--check"]},
        # P44 测试覆盖门禁: 每个 Python 项目必须有 tests/
        {"id": "test-coverage-check", "command": ["bin/gac/test-coverage-check.py"]},
        # P45 债务完整性门禁: seed_items 全部存在且非空
        {"id": "debt-integrity-check", "command": ["bin/gac/debt-integrity-check.py"]},
        # P7x-bus-foundation-rollout (ADR-0180): dormant-adapter detector.
        # Catches the P71 class-A "declaration without execution" trap.
        {"id": "bus-usage-report", "command": ["bin/ssot/bus-usage-report.py"]},
        # P43 BOS 追踪门禁: bos-unimplemented.yaml 不准包含已实现服务
        {"id": "bos-tracking-gate", "command": ["bin/ssot/bos-tracking-gate.py"]},
        # P7x-bus-foundation-rollout follow-up: real cross-process ZMQ e2e.
        # Spawns 2 subprocesses + uses TCP sockets (~2-5s). ci_only=True so
        # pre-commit skips the cost; CI strict runs it.
        {"id": "bus-e2e-harness", "command": ["bin/ssot/bus-e2e-harness.py", "--count", "30", "--json"], "ci_only": True}
    ]
}

# 动态读取并组装策略
POLICY = load_sgf_policy() or DEFAULT_POLICY
GATES_LIST = POLICY.get("gates", DEFAULT_POLICY["gates"])

# 主仓 ci_only override (followup D 治本, 2026-07-03): 这俩 check 依赖全量子模块/generated,
# ci_only 原放 ecos sgf-policy (子模块), 被 ecos 主线开发覆盖丢失 (PR#93 ecos 184bca4 被 M3.GacRule 覆盖,
# origin/main gitlink 悬空). 移主仓强制 ci_only (non-strict pre-commit 跳, CI strict 兜底),
# 不依赖易被子模块主线覆盖的 ecos SSOT.
_CI_ONLY_OVERRIDE_MAIN = {"governance-evolution", "doc-ssot-lint"}
for _g in GATES_LIST:
    if _g["id"] in _CI_ONLY_OVERRIDE_MAIN:
        _g["ci_only"] = True

CHECKS = tuple((g["id"], g["command"]) for g in GATES_LIST)
CI_ONLY_CHECKS = {g["id"] for g in GATES_LIST if g.get("ci_only")}
CI_SKIP_CHECKS = {g["id"] for g in GATES_LIST if g.get("ci_skip")}
AGENT_WORKFLOW_GATE_CHECKS = {g["id"] for g in GATES_LIST if g.get("agent_workflow_only")}


def _is_ci_env() -> bool:
    """CI 环境 (GitHub Actions 等). 本地运维 check (doctor 等) 在此跳过."""
    return os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"


def staged_files_git() -> list[str]:
    """git diff --cached 读 staged 文件."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=WORKSPACE, capture_output=True, text=True, check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def staged_touches_agent_workflow() -> bool:
    """staged 是否涉 agent-workflow (doctor/compliance/verify 只在涉时跑)."""
    return any(
        "bin/agent-workflow.py" in f or "tests/test_agent-workflow.py" in f or "agent-workflows.yaml" in f
        for f in staged_files_git()
    )


def gate_checks(
    scope: str = "staged",
    files: list[str] | None = None,
    run_id: str = "",
    strict: bool = False,
) -> tuple[tuple[str, list[str]], ...]:
    touch_aw = strict or staged_touches_agent_workflow()
    result: list[tuple[str, list[str]]] = []
    for name, command in CHECKS:
        if name in AGENT_WORKFLOW_GATE_CHECKS and not touch_aw:
            continue  # staged 不涉 agent-workflow → skip, 隔离并发 dirty
        if name in CI_ONLY_CHECKS and not strict:
            continue  # 全局 digest pre-commit 不稳定 → CI 兜底
        if name in CI_SKIP_CHECKS and _is_ci_env():
            continue  # 本地运维 check (doctor), CI 无 .venv/CLI → 跳
        if name == "change-lane-check":
            result.append((name, scoped_change_lane_command(scope, files, run_id)))
        elif name == "doc-link-check":
            cmd = scoped_doc_link_command(scope, files, run_id, strict)
            if cmd is None:
                continue  # 无 staged md → skip
            result.append((name, cmd))
        else:
            result.append((name, command))
    return tuple(result)


def _matched_files_from_env() -> list[str]:
    raw = os.environ.get("AGENT_WORKFLOW_MATCHED_FILES", "")
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload if str(item)]


def scoped_change_lane_command(
    scope: str = "files",
    files: list[str] | None = None,
    run_id: str = "",
) -> list[str]:
    cmd = ["bin/change-lane-check.py"]
    if scope == "staged":
        cmd.append("--staged")
    elif scope == "files":
        for file in sorted(files or _matched_files_from_env()):
            cmd.extend(["--file", file])
    elif scope == "run":
        for file in sorted(change_lane_files_for_scope(scope, files, run_id)):
            cmd.extend(["--file", file])
    return cmd


def scoped_doc_link_command(scope: str, files: list[str] | None, run_id: str, strict: bool) -> list[str] | None:
    if strict:
        return ["bin/ssot/doc-link-check.py"]
    
    staged = staged_files_git()
    md_files = [f for f in staged if f.endswith(".md")]
    if not md_files:
        return None
    return ["bin/ssot/doc-link-check.py", "--files"] + md_files


def change_lane_files_for_scope(scope: str, files: list[str] | None, run_id: str) -> list[str]:
    if scope == "staged":
        return staged_files_git()
    if scope == "files" and files:
        return files
    if scope == "run" and run_id:
        run_file = WORKSPACE / f".omo/_delivery/agent-workflows/runs/{run_id}.yaml"
        if run_file.is_file():
            try:
                import yaml
                run_data = yaml.safe_load(run_file.read_text(encoding="utf-8")) or {}
                return run_data.get("claim_policy", {}).get("files", [])
            except Exception:
                pass
    return []


def run_check(name: str, command: list[str]) -> dict[str, object]:
    cmd = [sys.executable, *command]
    try:
        result = subprocess.run(
            cmd,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        return {
            "name": name,
            "command": " ".join(command),
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "command": " ".join(command),
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"TIMEOUT after 15s",
        }


def run_gate(
    scope: str = "staged",
    files: list[str] | None = None,
    run_id: str = "",
    strict: bool = False,
) -> dict[str, object]:
    change_lane_files = change_lane_files_for_scope(scope, files, run_id)
    results = [run_check(name, command) for name, command in gate_checks(scope, files, run_id, strict)]
    return {
        "ok": all(item["ok"] for item in results),
        "scope": scope,
        "run_id": run_id or None,
        "change_lane_files": change_lane_files,
        "checks": results,
    }


def print_human(report: dict[str, object], verbose: bool = False) -> None:
    output_cfg = POLICY.get("settings", {}).get("output", {})
    terminal_mode = output_cfg.get("terminal_mode", "slim")
    
    is_ok = report["ok"]
    checks_count = len(report["checks"])
    
    if is_ok and terminal_mode == "slim" and not verbose:
        print("═══ GaC local gate ═══")
        print(f"scope={report['scope']} change_lane_files={len(report['change_lane_files'])}")
        print(f"GaC local gate: PASS ({checks_count} checks executed, ALL GREEN)")
        return
        
    print("═══ GaC local gate ═══")
    print(f"scope={report['scope']} change_lane_files={len(report['change_lane_files'])}")
    for item in report["checks"]:
        status = "PASS" if item["ok"] else "FAIL"
        print(f"[{status}] {item['name']} :: {item['command']}")
        if not item["ok"]:
            if item["stdout"]:
                print(item["stdout"])
            if item["stderr"]:
                print(item["stderr"], file=sys.stderr)
    print("GaC local gate: " + ("PASS" if is_ok else "FAIL"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the shared local GaC gate")
    parser.add_argument("--scope", choices=["staged", "files", "run"], default="staged")
    parser.add_argument("--file", action="append", default=[], help="Repo path for --scope files")
    parser.add_argument("--run-id", default="", help="Run id for --scope run")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="跑全套 (CI 用)")
    parser.add_argument("--verbose", action="store_true", help="Print passing gate details under slim mode")
    args = parser.parse_args()

    try:
        report = run_gate(args.scope, args.file, args.run_id, args.strict)
    except ValueError as exc:
        parser.error(str(exc))
    
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report, args.verbose)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
