#!/usr/bin/env python3
"""Run the local Governance-as-Code gate used by hooks and CI."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY_PATH = WORKSPACE / ".omo/_truth/registry/agent-workflows.yaml"


CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("gac-validate", ["bin/gac-validate.py", "--gate"]),
    ("gac-drift", ["bin/gac-drift.py"]),
    ("write-owner-audit", ["bin/write-owner-audit.py", "--staged"]),
    ("install-watch-agent", ["bin/install-watch-agent.py"]),
    ("test-mcp-kos", ["bin/test-mcp-kos.py"]),
    ("check-cockpit-ui-dist", ["bin/check-cockpit-ui-dist.py"]),
    ("agent-workflow-lint", ["bin/agent-workflow.py", "lint"]),
    ("agent-workflow-integrations", ["bin/agent-workflow.py", "integrations"]),
    ("agent-workflow-adapters", ["bin/agent-workflow.py", "adapters"]),
    ("agent-workflow-bootstrap", ["bin/agent-workflow.py", "bootstrap", "--skip-health"]),
    ("agent-workflow-verify-plan", ["bin/agent-workflow.py", "verify", "--file", "bin/agent-workflow.py"]),
    ("agent-workflow-compliance", ["bin/agent-workflow.py", "compliance"]),
    ("agent-workflow-doctor", ["bin/agent-workflow.py", "doctor"]),
    ("agent-workflow-observe", ["bin/agent-workflow.py", "observe"]),
    ("governance-evolution", ["bin/governance-evolution.py", "validate", "--json"]),
    ("mof-schema-validate", ["projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py", "--json"]),
    ("mof-state-bridge", ["projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py", "--json"]),
    ("mof-drift", ["bin/mof-drift"]),
    ("doc-ssot-lint", ["bin/doc-ssot-lint.py"]),
    ("project-layer-index", ["bin/project-layer-index.py", "--check"]),
    ("doc-ssot-snapshots", ["scripts/check-doc-ssot-snapshots.py"]),
    ("doc-link-check", ["bin/doc-link-check.py"]),
    ("change-lane-check", ["bin/change-lane-check.py", "--staged"]),
    # ISC-16: dependency-baseline drift 持续检测 (CI_ONLY: 本地 skip 避免 8 项真实 drift block 开发, CI strict 跑可见)
    ("dependency-baseline-drift", ["bin/gen-dependency-baseline.py", "--check"]),
    # ADR-0120: matrix SSOT consistency (port-registry + launchd)
    # Uses sys.executable + pyyaml inline (no separate uv run needed, gac-local-gate already runs under uv)
    ("matrix-consistency", ["bin/matrix-consistency-lint.py", "--skip-launchd"]),
    # ADR-0121 GCSI: governance convergence (rule registration + score + loop + SSOT)
    ("governance-convergence", ["bin/governance-convergence-lint.py"]),
    # governance-semantic-gate: 默认本地软门禁. 默认模式只阻断结构性 drift;
    # active runs / release package readiness 在 default 下是 warning, release hard gate 用
    # bin/governance-semantic-gate.py --release --json 显式执行.
    ("governance-semantic-gate", ["bin/governance-semantic-gate.py", "--json"]),
    # ADR-0122 S2 F-2 (ADR-0119 S2-5): state-freshness 纳入 gac-local-gate
    # 检查 OMO 状态面 SSOT (health/system_health/governance.jsonl/debt-dashboard/
    # governance-data) 的 generated_at 新鲜度, stale (>24h) 报 WARN, expired (>7d) 报 FAIL.
    # 默认 mode 跑 (派生快照应有 generated_at, 不可缺).
    ("state-freshness-check", ["bin/state-freshness-check.py", "--json"]),
    # ADR-0122 S1 F-6: check-* 工具按 false-positive 风险分级接入.
    # - dashboard-registry / toolbox-ssot: 静默 PASS, 接入 CHECKS 持续守.
    # - domain-m1-alignment: 非 strict 默认 PASS, 接入 CHECKS 持续守 (drift 不 block).
    # - check-boundary: 一次 CLI 工具 (check-boundary.py <pkg> [project]), 不接 auto-gate.
    # - cross-refs / dead-path-refs / alert-coverage: 报 issue 多/设计性未实, 在 CHECKS
    #   注册但仅 strict 跑 (见 CI_ONLY_CHECKS) — 默认模式不阻塞 pre-commit.
    ("check-dashboard-registry-consistency", ["bin/check-dashboard-registry-consistency.py"]),
    ("check-toolbox-ssot", ["bin/check-toolbox-ssot.py"]),
    ("check-domain-m1-alignment", ["bin/check-domain-m1-alignment.py"]),
    ("check-cross-refs", ["bin/check-cross-refs.py"]),
    ("check-dead-path-refs", ["bin/check-dead-path-refs.py"]),
    ("check-alert-coverage", ["bin/check-alert-coverage.py"]),
)


def normalize_repo_path(raw_path: str) -> str:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        path = path.resolve().relative_to(WORKSPACE)
    normalized = path.as_posix().strip("/")
    return normalized or "."


def load_run_state_dir() -> Path:
    if not REGISTRY_PATH.exists():
        return WORKSPACE / ".omo/_delivery/agent-workflows/runs"
    import yaml

    documents = [doc for doc in yaml.safe_load_all(REGISTRY_PATH.read_text(encoding="utf-8")) if doc]
    for document in documents:
        if isinstance(document, dict) and "runner" in document:
            run_dir = str((document.get("runner") or {}).get("run_state_dir") or "")
            if run_dir:
                return WORKSPACE / run_dir
    return WORKSPACE / ".omo/_delivery/agent-workflows/runs"


def load_run_claim_paths(run_id: str) -> list[str]:
    import yaml

    run_dir = load_run_state_dir()
    direct = run_dir / f"{run_id}.yaml"
    if direct.exists():
        path = direct
    else:
        matches = list(run_dir.glob(f"*{run_id}*.yaml")) if run_dir.exists() else []
        if len(matches) != 1:
            if matches:
                choices = ", ".join(str(item) for item in matches)
                raise ValueError(f"ambiguous run id for --scope run: {run_id} ({choices})")
            raise ValueError(f"run not found for --scope run: {run_id}")
        path = matches[0]
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    claims = payload.get("claims") if isinstance(payload, dict) else []
    files: set[str] = set()
    for claim in claims if isinstance(claims, list) else []:
        if not isinstance(claim, dict):
            continue
        for item in claim.get("paths") or []:
            if isinstance(item, str) and item.strip():
                files.add(normalize_repo_path(item))
    if not files:
        raise ValueError(f"run has no claimed paths for --scope run: {run_id}")
    return sorted(files)


def matched_files_from_env() -> list[str]:
    raw_files = os.environ.get("AGENT_WORKFLOW_MATCHED_FILES")
    if not raw_files:
        return []
    try:
        files = json.loads(raw_files)
    except json.JSONDecodeError:
        return []
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files) or not files:
        return []
    return sorted({normalize_repo_path(item) for item in files})


def change_lane_files_for_scope(scope: str, files: list[str] | None, run_id: str) -> list[str]:
    explicit_files = sorted({normalize_repo_path(item) for item in (files or []) if item})
    if scope == "files":
        if not explicit_files:
            raise ValueError("--scope files requires at least one --file")
        return explicit_files
    if scope == "run":
        if not run_id:
            raise ValueError("--scope run requires --run-id")
        return load_run_claim_paths(run_id)
    if scope == "staged":
        return matched_files_from_env()
    raise ValueError(f"unknown scope: {scope}")


def scoped_change_lane_command(
    scope: str = "staged",
    files: list[str] | None = None,
    run_id: str = "",
) -> list[str]:
    scoped_files = change_lane_files_for_scope(scope, files, run_id)
    if not scoped_files:
        return ["bin/change-lane-check.py", "--staged"]
    return ["bin/change-lane-check.py", *[part for path in scoped_files for part in ("--file", path)]]


def scoped_doc_link_command(
    scope: str = "staged",
    files: list[str] | None = None,
    run_id: str = "",
    strict: bool = False,
) -> list[str] | None:
    """doc-link-check scope staged (worktree-aware, Phase 2 C 治本 2026-06-30).

    非-strict: 只查 staged 文档的链接, 避免子模块未 init/generated/untracked
    在 worktree 误报断链 (主仓全 init PASS, worktree 按需 init). 无 staged md → None (skip).
    strict (CI): 跑全量兜底 (仓库整体链接健康).
    """
    if strict:
        return ["bin/doc-link-check.py"]
    scoped_files = change_lane_files_for_scope(scope, files, run_id)
    md_files = sorted({f for f in scoped_files if f.endswith(".md")})
    if not md_files:
        return None  # agent 没改文档 → 不需查链接, skip
    return ["bin/doc-link-check.py", "--files", *md_files]


# doctor/compliance/verify-plan 用 worktree-wide 命令, 并发 dirty 会污染.
# 只在 staged 涉 agent-workflow 时跑 (隔离并发), strict 模式 (CI) 跑全套.
AGENT_WORKFLOW_GATE_CHECKS = {"agent-workflow-verify-plan", "agent-workflow-compliance", "agent-workflow-doctor"}

# CI-only checks: 仓库级不变量, pre-commit (含 worktree) 跳过, strict (CI) 兜底.
#  - project-layer-index / dependency-baseline-drift: 全局 digest, hook stash unstaged +
#    并发 dirty 让 digest stale 不稳定 (doctor 那套 has_unstaged_dirty 检测对它们无效 —
#    gate 跑在 stash 后环境, 读不到原 dirty).
#  - governance-evolution: 仓库级 roadmap 不变量, 依赖 agora/cockpit 子模块 (worktree 按需
#    init 未覆盖) + 脚本本体. ISC-3f: worktree checkout 拿不到 → pre-commit 跳, CI strict 兜底.
#  - doc-ssot-lint: 仓库级 SSOT 契约, 依赖 docs/generated/* (gitignored, post-commit L0 萃取,
#    worktree checkout 没有). scoped 版 (doc-link-check --files) 留 pre-commit, 全量版归 CI.
#  ADR-0122 S1 F-6: 4 个 check-* 走 CI_ONLY (false-positive 风险高, 不应阻塞 pre-commit):
#  - check-cross-refs: 报 3173 链接 issue, 大头是 .omo/standards/*.md 引已删 SSOT +
#    .omo/_archive/ 历史快照 (P71 baseline recovery pattern 接受现状, 见 F-3 commit).
#  - check-dead-path-refs: 报 36 处, 大头是 scripts/ 子模块 (submodule 非 HEAD),
#    bin/check-* 工具对 submodule 内文件的引用本质上是 "跨子模块契约", 由子模块维护者管.
#  - check-alert-coverage: 4/11 rule 无 evaluator (x1-audit-fail/warn, x3-sla-violated,
#    x4-ci-missing), 属设计性 (X1 实时执行器/sla_violated/ci_count 数据源尚未实现).
#  - check-domain-m1-alignment: --strict 下报 3 layer drift (model-driven/omo-debt/
#    family-hub), 已知 ADR-0115 L4 治本路径, 本地+CI 走非 strict (报 drift 不 block),
#    接 CHECKS 保持续可见. 待 M1 治理治本 (F-14 roadmap) 后改 --strict.
CI_ONLY_CHECKS = {
    "project-layer-index",
    "dependency-baseline-drift",
    "governance-evolution",
    "doc-ssot-lint",
    "check-cross-refs",
    "check-dead-path-refs",
    "check-alert-coverage",
}

# CI 环境跳过的 check (CI fresh checkout 无运行时 env / generated 派生物, 跑恒红无意义).
# P0-fix (2026-07-02):
#  - agent-workflow-doctor: 查 omo/c2g/cockpit 集成健康, 依赖 .venv+CLI, CI 无 -> 永红. 本地运维 check.
#  - project-layer-index: docs/generated/ gitignored, CI 无 generated -> --check 必 stale. 本地 strict 照跑.
CI_SKIP_CHECKS = {
    "agent-workflow-doctor",
    "project-layer-index",
    # ADR-0120: R5 launchctl list CI 无 launchd job → 跳; matrix-consistency 用 --skip-launchd
    # 本地 strict 模式可跑全量 (不带 --skip-launchd)
    "matrix-consistency",
    "install-watch-agent",
}


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
            continue  # 全局 digest pre-commit 不稳定 (hook stash 并发 dirty) → CI 兜底
        if name in CI_SKIP_CHECKS and _is_ci_env():
            continue  # 本地运维 check (doctor), CI fresh checkout 无 .venv/CLI → 跳 (P0-fix)
        if name == "change-lane-check":
            result.append((name, scoped_change_lane_command(scope, files, run_id)))
        elif name == "doc-link-check":
            cmd = scoped_doc_link_command(scope, files, run_id, strict)
            if cmd is None:
                continue  # 无 staged md → skip (worktree-aware, Phase 2 C 治本)
            result.append((name, cmd))
        else:
            result.append((name, command))
    return tuple(result)


def run_check(name: str, command: list[str]) -> dict[str, object]:
    cmd = [sys.executable, *command]
    result = subprocess.run(
        cmd,
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "name": name,
        "command": " ".join(command),
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
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


def print_human(report: dict[str, object]) -> None:
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
    print("GaC local gate: " + ("PASS" if report["ok"] else "FAIL"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the shared local GaC gate")
    parser.add_argument("--scope", choices=["staged", "files", "run"], default="staged")
    parser.add_argument("--file", action="append", default=[], help="Repo path for --scope files")
    parser.add_argument("--run-id", default="", help="Run id for --scope run")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="跑全套 (CI 用; 默认 pre-commit skip: 不涉 agent-workflow 的 doctor/compliance/verify + project-layer-index 全局 digest)")
    args = parser.parse_args()

    try:
        report = run_gate(args.scope, args.file, args.run_id, args.strict)
    except ValueError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
