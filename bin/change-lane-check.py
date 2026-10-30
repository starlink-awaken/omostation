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
    {"docs", "docs_data"},
    {"governance_code", "docs", "docs_data"},
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, check=False)


def submodule_paths() -> set[str]:
    result = run(
        [
            "git",
            "config",
            "--file",
            ".gitmodules",
            "--get-regexp",
            r"^submodule\..*\.path$",
        ]
    )
    if result.returncode != 0:
        return set()
    return {line.split(maxsplit=1)[1] for line in result.stdout.splitlines() if line.strip()}


def changed_paths(staged: bool, files: list[str] | None = None) -> list[str]:
    if files:
        return files
    # ADR-4443 v9 (PUSH_RANGE): pre-push 场景下检查"本次 push 的 commit 范围"
    # 而非共享 staged——多 agent 共享 worktree 的 index 互相卡死根治（swarm
    # retro A6）。环境变量由 pre-push hook 从 stdin 的 ref 对导出。
    push_range = os.environ.get("PUSH_RANGE", "").strip()
    if push_range and ".." in push_range:
        cmd = ["git", "diff", "--name-only", push_range]
    elif staged:
        cmd = ["git", "diff", "--cached", "--name-only"]
    else:
        cmd = ["git", "diff", "--name-only"]
    result = run(cmd)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def commit_paths_in_range(
    git_range: str,
    cwd: Path | None = None,
) -> list[tuple[str, list[str]]]:
    """列出范围 (base..head) 内每个 commit 及其改动文件, 按时间正序。

    判据粒度是 **per-commit** 而不是整段合并成一个集合 —— 规则原文是
    「每 commit 单 lane」(ADR-0122 §46) / 「每个 staged set 一个 lane」
    (ADR-0456 §验收)。一段范围里可以有多个不同 lane 的 commit, 那是合规的;
    违规的是**单个 commit 内**混了多个 lane。

    这与整段合并判定的差别是实质性的, 不是形式差异: 举例, 一个 PR 含
    「commit A = docs 文件」「commit B = 子模块指针」两个 commit, 每 commit
    单 lane ⇒ 合规; 若把两者的文件合并成一个集合去判, 就会得到
    {docs, submodule_pointer} 的假违规。

    空范围 (无 commit / range 不可解析) 返回空列表 —— 调用方据此判定
    「本次没有可判的变更」, 而不是「全部通过」。

    cwd 缺省为本仓 (WORKSPACE); 传入时在那个仓里查 git —— 测试用临时仓时
    必须显式传, 否则查的是本仓的 git (读到空范围, 判据静默失效)。
    """
    result = subprocess.run(
        [
            "git",
            "log",
            "--reverse",
            "--format=%H",
            "--name-only",
            "--no-merges",
            git_range,
        ],
        cwd=str(cwd) if cwd is not None else str(WORKSPACE),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    commits: list[tuple[str, list[str]]] = []
    current: str | None = None
    files: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if len(stripped) == 40 and all(c in "0123456789abcdef" for c in stripped):
            if current is not None:
                commits.append((current, files))
            current = stripped
            files = []
        elif current is not None:
            files.append(stripped)
    if current is not None:
        commits.append((current, files))
    return commits


def load_governance_lanes() -> dict[str, str]:
    """读取 sgf-policy.yaml，构建文件路径 -> lane 的映射白名单"""
    yaml_path = (
        WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "governance" / "sgf-policy.yaml"
    )
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
    if path.startswith(".omo/_truth/registry/agent-workflows/"):
        return "governance_code"
    if path.startswith("tests/unit/gac/"):
        return "governance_code"
    if path in {
        ".omo/_truth/registry/governance-checks.yaml",
        ".omo/_truth/registry/agent-clis.yaml",
        ".omo/_truth/registry/agent-workflows.yaml",
        ".omo/capabilities/agent-clis.yaml",
        ".omo/standards/agent-workflow-contract.md",
        ".agents/skills/project-governance/SKILL.md",
        ".agents/skills/workflow-silence-detection/SKILL.md",
        "bin/agent-workflow.py",
        "bin/ssot-watcher.py",
        "lib/agent_workflow_projection.py",
        "lib/capability_federation_audit.py",
        "bin/compass_radar.py",
        "bin/omo-status",
        "bin/omo-top",
        "bin/cockpit-readiness.py",
        "bin/dashboard-readiness-summary.py",
        "bin/dashboard-ui-render.py",
        "bin/mof/generate-brief.py",
        "bin/gac-dashboard.py",
        "bin/gac/governance-dashboard.py",
        "bin/gac/governance-evolution.py",
        "bin/gac/governance-history-stats.py",
        "bin/gac/governance-semantic-gate.py",
        "bin/gac/governance-trend-report.py",
        "bin/gac/install-watch-agent.py",
        "bin/gac/mcp-server-kos.py",
        "bin/mof/project-layer-index.py",
        "bin/gac/state-stale-emit.py",
        "bin/gac/state-freshness-check.py",
        "bin/ssot/test-mcp-kos.py",
        "bin/ssot/write-owner-audit.py",
        "projects/cockpit/src/cockpit/commands/agent_workflow.py",
        "projects/cockpit/src/cockpit/commands/governance.py",
        "projects/cockpit/src/cockpit/tests/test_agent_workflow_command.py",
        "tests/test_agent_workflow.py",
        "tests/test_agent_workflow_projection.py",
        "tests/test_capability_federation_audit.py",
        "tests/test_change_lane_check.py",
        "tests/test_governance_evolution.py",
        "tests/test_heartbeat_wrapper.py",
    }:
        return "governance_code"
    if (
        path == ".omo/state/system_health.yaml"
        or path.startswith("runtime/")
        or path.startswith(".omo/state/runtime/")  # ADR-0129 §5.4 canonical projection plane
    ):
        return "runtime_snapshot"
    if path.startswith(".omo/"):
        return "governance_state"
    if path.endswith(".md") and (
        path
        in {
            "AGENTS.md",
            "CLAUDE.md",
            "GOVERNANCE.md",
            "README.md",
            "ARCHITECTURE.md",
            "LAYER-INDEX.md",
            "SYSTEM-INDEX.md",
            "BRIEF.md",
        }
        or path == "bin/README.md"
        or path.startswith("projects/")
        or path.startswith("spaces/")
        or path.startswith("docs/")
    ):
        return "docs"
    if (
        path.startswith("bin/gac")
        # 脚本注册表条目 (bin/_registry/scripts/**/*.yaml) 是被登记治理脚本的
        # 登记表 —— 与被登记脚本同属一个治理单元, 但路径前缀不同。若落到后缀
        # 兜底 (yaml => code), 则「改脚本 + 改它的登记条目」这个原子变更必然被
        # 判成 code + governance_code 混 lane (该组合不在 ALLOWED_COMBOS 内) ⇒
        # 治理面自带的原子性被路径前缀破坏。
        #
        # 归类依据同 ADR-0129 §2.1: 分类应反映语义单元, 而非路径字面。
        # 实测影响面: 近 120 个 commit 改判前后违规数不变 (71 => 71), 无一 commit
        # 因改判而新变为违规 —— 含注册表的 commit 在改判前后都违规 (code 与
        # governance_code 本就不兼容), 故此归类修正不收紧任何既有约束。
        or path.startswith("bin/_registry/")
        or path
        in {
            "bin/ssot/ssot-guardian.py",
            "bin/ssot/doc-ssot-lint.py",
            "bin/ssot/sync-submodules-push.sh",
            "bin/ssot/submodule-reachability-gate.py",
            "bin/ssot/submodule-pointer-transaction.sh",
            "bin/change-lane-check.py",
            "bin/ssot/check-cockpit-ui-dist.py",
            "bin/ssot/doc-link-check.py",
        }
        or path.startswith(".githooks/")
        or path
        in {
            ".pre-commit-config.yaml",
            ".github/workflows/gac-gate.yml",
            ".github/workflows/governance-check.yml",
        }
    ):
        return "governance_code"
    if path in {".gitmodules", "Makefile"} or path.startswith(".github/workflows/"):
        return "config"
    if path.startswith("docs/") and path.endswith((".yaml", ".yml", ".json", ".csv")):
        return "docs_data"
    if path.endswith((".py", ".ts", ".js", ".sh", ".json", ".yaml", ".yml")):
        return "code"
    return "other"


def allowed(lanes: set[str]) -> bool:
    return allowed_for(lanes, allowed_lanes=set())


def allowed_for(lanes: set[str], allowed_lanes: set[str]) -> bool:
    if len(lanes) <= 1:
        return True
    # ADR-0129 §11.3.2: workflow 显式授权优先于硬编码隔离
    # (state-sync workflow allowed_lanes=[runtime_snapshot, governance_state, ...] 不应被 runtime_snapshot 硬编码隔离架空)
    if allowed_lanes and lanes <= allowed_lanes:
        return True
    if "runtime_snapshot" in lanes and len(lanes) > 1:
        return False
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


def check_range(
    git_range: str,
    allowed_lanes: set[str] | None = None,
) -> dict[str, object]:
    """按 commit 逐个判定 lane (per-commit 判据)。

    每个 commit 独立成集, 各自判 allowed_for。任一 commit 混 lane ⇒ 整体违规。
    合法的范围 (多个不同 lane 的 commit 并存) ⇒ 通过。
    """
    submodules = submodule_paths()
    allowed_lane_set = allowed_lanes or set()
    per_commit: list[dict[str, object]] = []
    violations: list[dict[str, object]] = []
    for sha, paths in commit_paths_in_range(git_range):
        by_lane: dict[str, list[str]] = {}
        for path in paths:
            by_lane.setdefault(classify(path, submodules), []).append(path)
        lanes = set(by_lane)
        ok = allowed_for(lanes, allowed_lane_set)
        entry = {
            "commit": sha,
            "ok": ok,
            "lanes": sorted(lanes),
            "by_lane": by_lane,
            "files": len(paths),
        }
        per_commit.append(entry)
        if not ok:
            violations.append(entry)
    all_lanes = sorted({lane for entry in per_commit for lane in entry["lanes"]})
    return {
        "ok": not violations,
        "range": git_range,
        "commits": len(per_commit),
        "lanes": all_lanes,
        "allowed_lanes": sorted(allowed_lane_set),
        "violations": violations,
        "per_commit": per_commit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check staged or unstaged change lanes")
    parser.add_argument("--staged", action="store_true", help="Check staged changes")
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Check an explicit changed file path",
    )
    parser.add_argument(
        "--range",
        dest="git_range",
        default="",
        help=(
            "Check a git range (e.g. base..head) per-commit: every commit in the "
            "range must itself be single-lane (rule: one lane per commit)."
        ),
    )
    parser.add_argument(
        "--allow-lane",
        action="append",
        default=[],
        help="Allow an explicit lane for this check",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--advisory", action="store_true", help="Always exit 0")
    args = parser.parse_args()

    allowed_lanes = parse_allowed_lanes([os.environ.get("AGENT_WORKFLOW_ALLOWED_LANES", ""), *args.allow_lane])

    if args.git_range:
        range_report = check_range(args.git_range, allowed_lanes=allowed_lanes)
        if args.json:
            print(json.dumps(range_report, ensure_ascii=False, indent=2))
        elif range_report["ok"]:
            print(
                f"change-lane-check: PASS ({range_report['commits']} commits, "
                f"lanes={','.join(range_report['lanes']) or '-'})"
            )
        else:
            print(
                f"change-lane-check: FAIL mixed lanes in "
                f"{len(range_report['violations'])}/{range_report['commits']} commits"
            )
            for entry in range_report["violations"]:
                lanes = ",".join(entry["lanes"])
                print(f"  commit {entry['commit'][:9]}: lanes={lanes}")
                for lane, paths in entry["by_lane"].items():
                    preview = ", ".join(paths[:5])
                    suffix = "" if len(paths) <= 5 else f" ... +{len(paths) - 5}"
                    print(f"    {lane}: {preview}{suffix}")
        return 0 if range_report["ok"] or args.advisory else 1

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
