#!/usr/bin/env python3
"""Run the local Governance-as-Code gate used by hooks and CI, driven by SGF-v1 metadata policy."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
SGF_POLICY_YAML = (
    WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "governance" / "sgf-policy.yaml"
)


def load_sgf_policy() -> dict:
    """Load SGF-v1 dynamic configuration. Fallback to hardcoded default values if missing."""
    if SGF_POLICY_YAML.is_file():
        try:
            import yaml

            return yaml.safe_load(SGF_POLICY_YAML.read_text(encoding="utf-8")) or {}
        except Exception as e:
            print(
                f"[WARN] Failed to load sgf-policy.yaml: {e}. Falling back to default policy.",
                file=sys.stderr,
            )
    return {}


# 默认降级策略 (防止 yaml 丢失崩溃)
DEFAULT_POLICY = {
    "settings": {"output": {"terminal_mode": "slim"}},
    "gates": [
        {"id": "gac-validate", "command": ["bin/gac/gac-validate.py", "--gate"]},
        {"id": "gac-drift", "command": ["bin/gac/gac-drift.py"]},
        {
            "id": "write-owner-audit",
            "command": ["bin/ssot/write-owner-audit.py", "--staged"],
        },
        {
            "id": "install-watch-agent",
            "command": ["bin/gac/install-watch-agent.py"],
            "ci_skip": True,
            "ops_only": True,
        },
        {"id": "test-mcp-kos", "command": ["bin/ssot/test-mcp-kos.py"]},
        {
            "id": "check-cockpit-ui-dist",
            "command": ["bin/ssot/check-cockpit-ui-dist.py"],
        },
        {"id": "agent-workflow-lint", "command": ["bin/agent-workflow.py", "lint"]},
        {
            "id": "capability-ownership",
            "command": ["bin/gac/check-capability-ownership.py"],
            "note": "CAP-OWN: 能力所有权 + 删除防腐 (差距治理 S1). 注册能力实现缺失(IMPL-EXISTS) → 阻断; owner 缺失/孤儿能力 → info",
        },
        {
            "id": "derived-only-fast-track",
            "command": ["bin/gac/check-derived-only-fast-track.py"],
            "note": "GOV-REBAL: 派生文档-only fast-track 判定 (差距治理 S5). 纯派生文档变更 → 建议轻量 workflow; 混入源码 → 常规 gate. 软信号, 不阻断",
        },
        {
            "id": "auto-fix-loop",
            "command": ["bin/gac/auto-fix-loop.py"],
            "note": "AUTO-FIX: 漂移检测→分类→修复闭环 (差距治理 S5). PATH-DRIFT error 级阻断; DERIVED-STALE/ORPHAN-SCRIPT 报告 + --apply 自动修复",
        },
        {
            "id": "command-discovery",
            "command": ["bin/gac/command-discovery.py"],
            "note": "UX-NOISE: 命令发现层 (差距治理 S5). 密度/重复/易混淆定位, 软信号不阻断",
        },
        {
            "id": "agent-workflow-integrations",
            "command": ["bin/agent-workflow.py", "integrations"],
        },
        {
            "id": "agent-workflow-adapters",
            "command": ["bin/agent-workflow.py", "adapters"],
        },
        {
            "id": "agent-workflow-bootstrap",
            "command": ["bin/agent-workflow.py", "bootstrap", "--skip-health"],
        },
        {
            "id": "agent-workflow-verify-plan",
            "command": [
                "bin/agent-workflow.py",
                "verify",
                "--file",
                "bin/agent-workflow.py",
            ],
            "agent_workflow_only": True,
        },
        {
            "id": "agent-workflow-compliance",
            "command": ["bin/agent-workflow.py", "compliance"],
            "agent_workflow_only": True,
        },
        {
            "id": "agent-workflow-doctor",
            "command": ["bin/agent-workflow.py", "doctor"],
            "ci_skip": True,
            "agent_workflow_only": True,
        },
        {
            "id": "agent-workflow-observe",
            "command": ["bin/agent-workflow.py", "observe"],
        },
        {
            "id": "governance-evolution",
            "command": ["bin/gac/governance-evolution.py", "validate", "--json"],
        },
        {
            "id": "mof-schema-validate",
            "command": [
                "projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py",
                "--json",
            ],
            "ci_skip": True,
            "agent_workflow_only": True,
        },
        {
            "id": "mof-state-bridge",
            "command": [
                "projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py",
                "--json",
            ],
        },
        {"id": "mof-drift", "command": ["bin/mof/mof-drift"]},
        {"id": "m4-bootstrap-reflex", "command": ["bin/mof/mof-bootstrap.py", "all"]},
        {"id": "doc-ssot-lint", "command": ["bin/ssot/doc-ssot-lint.py"]},
        {
            "id": "doc-governance",
            "command": ["bin/ssot/doc-governance-check.py", "--no-new-warnings"],
        },
        {
            "id": "project-layer-index",
            "command": ["bin/mof/project-layer-index.py", "--check"],
            "ci_only": True,
        },
        {"id": "doc-ssot-snapshots", "command": ["bin/ssot/doc-governance-check.py"]},
        {
            "id": "state-freshness-check",
            "command": ["bin/gac/state-freshness-check.py"],
            "ci_only": True,
        },
        {"id": "doc-link-check", "command": ["bin/ssot/doc-link-check.py"]},
        {
            "id": "change-lane-check",
            "command": ["bin/change-lane-check.py", "--staged"],
        },
        {
            "id": "dependency-baseline-drift",
            "command": ["bin/mof/gen-dependency-baseline.py", "--check"],
            "ci_only": True,
        },
        {
            "id": "matrix-consistency",
            "command": ["bin/ssot/matrix-consistency-lint.py", "--skip-launchd"],
            "ci_skip": True,
        },
        {
            "id": "governance-semantic-gate",
            "command": ["bin/gac/governance-semantic-gate.py", "--json"],
            "timeout": 60,
        },
        {"id": "adr-coverage", "command": ["bin/adr/adr-coverage.py", "--json"]},
        # ADR-0373 (C5): sweep history drift gate (CR-SWEEP-INDEX-AUTO)
        {"id": "sweep-index-check", "command": ["bin/sweep/sweep_index.py", "--check"]},
        {
            "id": "state-freshness-check",
            "command": ["bin/gac/state-freshness-check.py", "--json"],
        },
        {
            "id": "current-state-coherence",
            "command": ["bin/ssot/current-state-coherence.py", "--json"],
        },
        {
            "id": "check-dashboard-registry-consistency",
            "command": ["bin/ssot/check-dashboard-registry-consistency.py"],
        },
        {"id": "check-toolbox-ssot", "command": ["bin/ssot/check-toolbox-ssot.py"]},
        {
            "id": "check-domain-m1-alignment",
            "command": ["bin/ssot/check-domain-m1-alignment.py"],
        },
        {"id": "test-gac-engine", "command": ["bin/ssot/test-gac-engine.py"]},
        {
            "id": "service-config-validate",
            "command": ["bin/mof/gen-service-configs.py", "--validate"],
        },
        {
            "id": "service-config-drift",
            "command": ["bin/mof/gen-service-configs.py", "--check"],
            "ci_skip": True,
        },
        {"id": "bdsk-shadow-sandbox", "command": ["bin/gac/bdsk-shadow-sandbox.py"]},
        {
            "id": "gac-consensus-inject-check",
            "command": ["bin/gac/gac-consensus-inject.py", "--check"],
        },
        {
            "id": "gac-compute-onboard-check",
            "command": ["bin/gac/gac-compute-onboard.py", "--check"],
        },
        # P44 测试覆盖门禁: 每个 Python 项目必须有 tests/
        {"id": "test-coverage-check", "command": ["bin/gac/test-coverage-check.py"]},
        # P45 债务完整性门禁: seed_items 全部存在且非空
        {"id": "debt-integrity-check", "command": ["bin/gac/debt-integrity-check.py"]},
        # P45 W1 OMO state write guard: 检测 system.yaml 多写冲突 + 写权限违规
        {
            "id": "omo-state-write-guard",
            "command": ["bin/gac/omo-state-write-guard.py"],
        },
        # P45 W1 BRIEF.md protect: 检测 BRIEF.md 是否被外部覆盖
        {"id": "brief-protect", "command": ["bin/mof/generate-brief.py", "--protect"]},
        # P85 G1+G2: redline executability wiring. The redline registry
        # at .omo/_truth/registry/redlines.yaml points to these gates;
        # adding/removing rows there is the safe edit surface.
        {
            "id": "check-severity-registry",
            "command": ["bin/gac/check-severity-registry.py"],
        },
        {
            "id": "check-submodule-rewind",
            "command": ["bin/gac/check-submodule-rewind.py"],
        },
        {
            "id": "submodule-ancestry-gate",
            "command": [
                "bin/gac/check-submodule-rewind.py",
                "--range",
                "origin/main",
                "HEAD",
                "--no-write-debt",
            ],
            "timeout": 60,
        },
        {
            "id": "check-work-landed",
            "command": ["bin/gac/check-work-landed.py"],
            "timeout": 45,
        },
        {
            "id": "check-governance-ratio",
            "command": ["bin/gac/check-governance-ratio.py"],
        },
        {
            "id": "check-redline-coverage",
            "command": ["bin/gac/check-redline-coverage.py"],
        },
        # P85 G2.2: workorder schema is warn-only by default; promote
        # to --strict in CI after the grace period (G2 follow-up).
        {
            "id": "check-workorder-schema",
            "command": ["bin/gac/check-workorder-schema.py"],
        },
        # P85 G3: P84 dual-track守护. Three checks enforcing the
        # dual-track isolation contract (P84 §0).
        {
            "id": "check-dual-track-purity",
            "command": ["bin/gac/check-dual-track-purity.py"],
        },
        {"id": "check-silent-loss", "command": ["bin/gac/check-silent-loss.py"]},
        {
            "id": "check-adversarial-effectiveness",
            "command": ["bin/gac/check-adversarial-effectiveness.py"],
        },
        {
            "id": "check-evidence-honest-closure",
            "command": ["bin/gac/check-evidence-honest-closure.py"],
        },
        {
            "id": "check-gateway-status-doc",
            "command": ["bin/gac/check-gateway-status-doc.py"],
        },
        {
            "id": "check-foundry-deck-coverage",
            "command": ["bin/gac/check-foundry-deck-coverage.py"],
        },
        {
            "id": "check-evidence-freshness",
            "command": ["bin/gac/check-evidence-freshness.py"],
        },
        {
            "id": "check-governance-trend",
            "command": ["bin/gac/check-governance-trend.py"],
        },
        # P7x-bus-foundation-rollout (ADR-0180): dormant-adapter detector.
        # Catches the P71 class-A "declaration without execution" trap.
        {"id": "bus-usage-report", "command": ["bin/ssot/bus-usage-report.py"]},
        # P43 BOS 追踪门禁: bos-unimplemented.yaml 不准包含已实现服务
        {"id": "bos-tracking-gate", "command": ["bin/ssot/bos-tracking-gate.py"]},
        # P7x-bus-foundation-rollout follow-up: real cross-process ZMQ e2e.
        # Spawns 2 subprocesses + uses TCP sockets (~2-5s). ci_only=True so
        # pre-commit skips the cost; CI strict runs it.
        {
            "id": "bus-e2e-harness",
            "command": ["bin/ssot/bus-e2e-harness.py", "--count", "30", "--json"],
            "ci_only": True,
        },
        # Short-term improvement: INDEX 自动更新检查 (CI strict 跑, pre-commit 跳过)
        # 检测 docs/INDEX-*.md 是否与真实内容漂移
        {
            "id": "check-index-drift",
            "command": ["bin/ssot/check-index-drift.py"],
            "ci_only": True,
        },
        # P0-A + G2 (2026-07-28): 三锁接线. 均为 BLOCKING (不在 SOFT_CHECKS, exit!=0 → gate [FAIL]).
        #   layer-call-direction: new-violation blocking (baseline 存量 11 grace, 已实现 L213-229;
        #     G1 --files 增量快路径, pre-commit <1s, CI strict 全量 ~3s).
        #   mof-capabilities-drift: exit 1 on any drift (声明/执行鸿沟, 当前 drift=0).
        #   doc-claims: exit 1 on findings (scope=all 17 projects, 当前 0 findings).
        # 定位 SSOT: governance-checks.yaml (CR-X4-LAYER-CALL / CR-X4-REGISTRY-DRIFT / CR-X4-DOC-CLAIMS).
        # 旧注释 "exit=0 只报告不阻断 / 需另加 baseline" 已废 (baseline L213-229 早已实现, G2 核实).
        {
            "id": "mof-capabilities-drift-check",
            "command": ["bin/mof/check-mof-capabilities-drift.py"],
        },
        {"id": "doc-claims-check", "command": ["bin/mof/check-doc-claims.py"]},
        {
            "id": "layer-call-direction-check",
            "command": [
                "bin/ssot/check-layer-call-direction.py",
                "--baseline",
                ".omo/_truth/registry/layer-call-baseline.txt",
            ],
        },
    ],
}

# 动态读取并组装策略
POLICY = load_sgf_policy() or DEFAULT_POLICY
GATES_LIST = list(POLICY.get("gates", DEFAULT_POLICY["gates"]))

# Root-owned convergence and root-directory guards are intentionally appended outside
# the ecos submodule policy so a submodule update cannot silently remove them.
for _root_gate in (
    {
        "id": "root-directory-governance",
        "command": ["bin/ssot/root-directory-governance-scan.py", "--check", "--json"],
    },
    {
        "id": "bin-scripts-convergence-audit",
        "command": ["bin/ssot/bin-scripts-convergence-audit.py", "--check", "--json"],
    },
    {
        "id": "omo-runtime-final-tree",
        "command": [
            "bin/gac/omo-runtime-stamp-policy.py",
            "--treeish",
            "HEAD",
            "--json",
        ],
    },
):
    if not any(gate.get("id") == _root_gate["id"] for gate in GATES_LIST):
        GATES_LIST.append(_root_gate)

# Root-owned document governance is intentionally appended outside the ecos
# submodule policy so a submodule update cannot silently remove the gate.
if not any(gate.get("id") == "doc-governance" for gate in GATES_LIST):
    GATES_LIST.append(
        {
            "id": "doc-governance",
            "command": ["bin/ssot/doc-governance-check.py", "--no-new-warnings"],
        }
    )

# Root-owned current-state projection: the external ecos policy cannot remove
# the guard that keeps state, goals, tasks and Scene Card activation explicit.
if not any(gate.get("id") == "current-state-coherence" for gate in GATES_LIST):
    GATES_LIST.append(
        {
            "id": "current-state-coherence",
            "command": ["bin/ssot/current-state-coherence.py", "--json"],
        }
    )

# Root-owned conflict-marker guard (2026-08-07): 拦截 git 合并冲突标记 (<<<<<<< / >>>>>>>)
# 入库, 治本 ecos `0ff6ad3` 把冲突标记 commit 进 sgf-policy.yaml → test-gac-engine YAML 解析
# FAIL → 全仓 push 被卡. 放 root-owned 段, 防 ecos 子模块 policy 移除. 详见 ADR 见 evidence
# docs/operations/2026-08-07-pre-push-guard-regression-evidence.md (发现2).
if not any(gate.get("id") == "check-conflict-markers" for gate in GATES_LIST):
    GATES_LIST.append(
        {
            "id": "check-conflict-markers",
            "command": ["bin/gac/check-conflict-markers.py", "--all"],
        }
    )

if not any(gate.get("id") == "check-swarm-collision" for gate in GATES_LIST):
    GATES_LIST.append(
        {
            "id": "check-swarm-collision",
            "command": ["bin/gac/check-swarm-collision.py"],
        }
    )

# Root-owned 差距治理 gate (S1 CAP-OWN + S5 GOV-REBAL/AUTO-FIX/UX-NOISE):
# 放 root-owned 段防 ecos 子模块 sgf-policy 覆盖丢失 (S1 capability-ownership 曾被
# sgf-policy 覆盖, 未真正进 gate — 本段修复该盲区). 语义:
#   capability-ownership      CAP-OWN    能力删除防腐 (error 阻断)
#   derived-only-fast-track   GOV-REBAL  派生文档-only fast-track 判定 (软信号)
#   auto-fix-loop             AUTO-FIX   漂移检测→分类→修复闭环 (PATH-DRIFT error 阻断)
#   command-discovery         UX-NOISE   命令密度/重复/易混淆定位 (软信号)
#   sfop-slots                SFOP/DFSQ  COMP-WS 槽位 + 唯一 dispatcher (CR-SFOP-01/02 阻断)
#   execution-chain           脚本/CI/cron 触发链覆盖 (CR-EXEC-CHAIN-01 阻断)
for _gap_gate in (
    {
        "id": "capability-ownership",
        "command": ["bin/gac/check-capability-ownership.py"],
    },
    {
        "id": "derived-only-fast-track",
        "command": ["bin/gac/check-derived-only-fast-track.py"],
    },
    {
        "id": "auto-fix-loop",
        "command": ["bin/gac/auto-fix-loop.py"],
    },
    {
        "id": "command-discovery",
        "command": ["bin/gac/command-discovery.py"],
    },
    {
        "id": "sfop-slots",
        "command": ["bin/gac/check-sfop-slots.py", "--json"],
        "note": "SFOP/DFSQ: COMP-WS 必须声明 sfop_slot+dao_layer; 活跃 S 槽至多一个且为 COMP-WS-omo; H→B via F or cockpit.adapters; claimed-active cron must declare sfop_slot (CR-SFOP-01/02/05/06 阻断, 非 SOFT)",
    },
    {
        "id": "execution-chain",
        "command": ["bin/gac/check-execution-chain.py", "--json"],
        "timeout": 45,
        "note": "Fuse script-registry + ci-surfaces + cron; extra-active orphans fail-closed (CR-EXEC-CHAIN-01). Live gaps are warnings.",
    },
):
    if not any(gate.get("id") == _gap_gate["id"] for gate in GATES_LIST):
        GATES_LIST.append(_gap_gate)

# Root-owned DFSQ/v1 (2026-08-25): COMP-WS slot self-report + unique S=omo,
# plus fused constitution stack coverage (scripts × CI × cron × skill ×
# workflow × MCP × CLI × githooks). ecos sgf-policy.yaml may list these;
# append here so CHECKS cannot lose blocking ids on submodule overwrite.
# Not in SOFT_CHECKS / CI_ONLY / OPS_ONLY.
for _dfsq_gate in (
    {
        "id": "sfop-slots",
        "command": ["bin/gac/check-sfop-slots.py", "--json"],
    },
    {
        "id": "execution-chain",
        "command": ["bin/gac/check-execution-chain.py", "--json"],
        "timeout": 45,
    },
):
    if not any(gate.get("id") == _dfsq_gate["id"] for gate in GATES_LIST):
        GATES_LIST.append(_dfsq_gate)

# Root-owned bin 配额"变更侧问责" (2026-08-24, 并发 #2076): 每次变更自己负责守恒.
# 检查 <base>..HEAD 中 bin/ 下 .py/.sh 新增 vs 删除, 净增 → FAIL.
# 全局计数 (gac-validate subtraction-quota) 降级 advisory, 本 check 为增量问责.
# 放 root-owned 段, 防 ecos 子模块 policy 移除.
if not any(gate.get("id") == "bin-quota-diff" for gate in GATES_LIST):
    GATES_LIST.append(
        {
            "id": "bin-quota-diff",
            "command": ["bin/gac/check-bin-quota-diff.py", "--base", "origin/main"],
        }
    )

# 主仓 ci_only override (followup D 治本, 2026-07-03): 这俩 check 依赖全量子模块/generated,
# ci_only 原放 ecos sgf-policy (子模块), 被 ecos 主线开发覆盖丢失 (PR#93 ecos 184bca4 被 M3.GacRule 覆盖,
# origin/main gitlink 悬空). 移主仓强制 ci_only (non-strict pre-commit 跳, CI strict 兜底),
# 不依赖易被子模块主线覆盖的 ecos SSOT.
_CI_ONLY_OVERRIDE_MAIN = {"governance-evolution", "doc-ssot-lint"}
for _g in GATES_LIST:
    if _g["id"] in _CI_ONLY_OVERRIDE_MAIN:
        _g["ci_only"] = True

# Machine/runtime mutation must never be reached through a command named
# validate/check/gate.  The live ECOS policy predates the ops_only field, so
# keep a root-owned fail-safe until that projection is migrated.  Operators can
# still invoke the installer directly when they explicitly intend to mutate
# LaunchAgents and launchd state.
_OPS_ONLY_OVERRIDE_MAIN = {"install-watch-agent"}
for _g in GATES_LIST:
    if _g["id"] in _OPS_ONLY_OVERRIDE_MAIN:
        _g["ops_only"] = True

CHECKS = tuple((g["id"], g["command"]) for g in GATES_LIST)
CI_ONLY_CHECKS = {g["id"] for g in GATES_LIST if g.get("ci_only")}
CI_SKIP_CHECKS = {g["id"] for g in GATES_LIST if g.get("ci_skip")}
OPS_ONLY_CHECKS = {g["id"] for g in GATES_LIST if g.get("ops_only")}
AGENT_WORKFLOW_GATE_CHECKS = {g["id"] for g in GATES_LIST if g.get("agent_workflow_only")}
BROKEN_CHECKS = {g["id"] for g in GATES_LIST if g.get("broken")}
# Live sgf-policy.yaml often omits timeout; semantic-gate runs several
# subprocesses and false-timeouts at the 15s default. Named defaults apply
_DEFAULT_CHECK_TIMEOUTS = {
    "agent-workflow-doctor": 45,
    "governance-semantic-gate": 60,
    "execution-chain": 45,
    "layer-call-direction-check": 45,
    "gac-drift": 45,
    "mof-schema-validate": 45,
    "sfop-slots": 45,
}
_CHECK_TIMEOUTS = {
    g["id"]: g.get("timeout", _DEFAULT_CHECK_TIMEOUTS.get(g["id"], 15)) for g in GATES_LIST
}
# SOFT checks: finding_topics 仍输出, 但不翻转 gate (门禁降噪)
SOFT_CHECKS = {
    "governance-semantic-gate",  # evolution/release_ready 是软信号, 非门禁阻断
    "brief-protect",  # BRIEF.md protect 提示手工修改, 非门禁阻断
    "current-state-coherence",  # 运行态动态推导软信号
    "ci-surfaces-check",  # CI Surface 重叠软警告
    "derived-only-fast-track",  # GOV-REBAL (S5): 纯派生文档 fast-track 建议, 非阻断
    "command-discovery",  # UX-NOISE (S5): 命令密度/重复定位, 非阻断
    "resident-bos-check",  # CR-RESIDENT-BOS-01: agora bos-services.yaml 缺 resident 域, 非阻断
}


# Concurrent-write isolation (P79 治本):
#   多 agent 共享主树时, 一个 gate run 期间另一个 agent 写入 .omo/state/*.yaml
#   会让 read-then-check 的子进程看到 torn state. 解决方案: 在 gate 启动时
#   snapshot 所有 read 输入路径的 (mtime, size) 指纹, 每跑完一个 check 比对
#   一次, 如有变化 emit topic=concurrent-write-drift (severity=warn, blocking=False)
#   让用户知道 gate 结果可能受 concurrent 写干扰, 但不 fail. CI 上更彻底:
#   启动时 acquire fcntl 锁 .omo/_delivery/.gate-lock (5min timeout), 阻止其他
#   agent 的 omo state sync 同窗口跑. 本地用 flock 不阻塞其他 agent 走旁路.
SNAPSHOT_PATHS = (
    ".omo/state/health.yaml",
    ".omo/state/system.yaml",
    ".omo/state/system_health.yaml",
    ".omo/_control/governance-data.json",
    ".omo/_control/debt-dashboard/current.yaml",
    ".omo/_delivery/observability/events.jsonl",
    ".omo/_delivery/agent-workflows/events.jsonl",
    ".omo/_truth/registry/governance-checks.yaml",
)


def _read_state_fingerprint() -> dict[str, tuple[float, int]]:
    """Snapshot (mtime, size) for each known read-side state file."""
    fp: dict[str, tuple[float, int]] = {}
    for rel in SNAPSHOT_PATHS:
        p = WORKSPACE / rel
        try:
            st = p.stat()
            fp[rel] = (st.st_mtime, st.st_size)
        except FileNotFoundError:
            fp[rel] = (0.0, -1)
    return fp


_CONCURRENT_DRIFT = {"detected": False, "files": []}
_state_fingerprint_snapshot: dict[str, tuple[float, int]] = {}


def _check_drift(snapshot: dict[str, tuple[float, int]]) -> list[str]:
    """Diff current (mtime, size) against snapshot. Return list of drifted paths."""
    drift: list[str] = []
    for rel, before in snapshot.items():
        p = WORKSPACE / rel
        try:
            st = p.stat()
            now = (st.st_mtime, st.st_size)
        except FileNotFoundError:
            now = (0.0, -1)
        if now != before:
            drift.append(rel)
    return drift


def _update_drift_topic(report: dict, drift: list[str]) -> None:
    """Record concurrent-drift finding as a soft warning topic."""
    if not drift:
        return
    _CONCURRENT_DRIFT["detected"] = True
    _CONCURRENT_DRIFT["files"] = list(drift)
    topic = {
        "check": "gac-local-gate",
        "topic": "concurrent-write-drift",
        "label": "并发写盘漂移 (concurrent agent wrote during gate run)",
        "command": "git status --short .omo/ && uv run --with pyyaml python bin/agent-workflow.py compliance",
        "returncode": 1,
        "severity": "warn",
        "blocking": False,
        "summary": f"{len(drift)} state file(s) mutated mid-run: {', '.join(drift[:5])}",
        "finding_count": 1,
    }
    topics = report.get("finding_topics") or []
    topics.append(topic)
    report["finding_topics"] = topics


def _is_ci_env() -> bool:
    """CI 环境 (GitHub Actions 等). 本地运维 check (doctor 等) 在此跳过."""
    return os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"


def staged_files_git() -> list[str]:
    """git diff --cached 读 staged 文件."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def staged_touches_agent_workflow() -> bool:
    """staged 是否涉 agent-workflow (doctor/compliance/verify 只在涉时跑)."""
    return any(
        f in {
            "bin/agent-workflow.py",
            "lib/agent_workflow_projection.py",
            "tests/test_agent-workflow.py",
            "tests/test_agent_workflow_projection.py",
        }
        or f == ".omo/_truth/registry/agent-workflows.yaml"
        or f.startswith(".omo/_truth/registry/agent-workflows/")
        for f in staged_files_git()
    )


def gate_checks(
    scope: str = "staged",
    files: list[str] | None = None,
    run_id: str = "",
    strict: bool = False,
    risk_profile: str | None = None,
) -> tuple[tuple[str, list[str]], ...]:
    touch_aw = strict or staged_touches_agent_workflow()
    result: list[tuple[str, list[str]]] = []
    for name, command in CHECKS:
        if name in OPS_ONLY_CHECKS:
            continue  # explicit operator action; automatic verification is read-only
        if name in AGENT_WORKFLOW_GATE_CHECKS and not touch_aw:
            continue  # staged 不涉 agent-workflow → skip, 隔离并发 dirty
        if name in CI_ONLY_CHECKS and not strict:
            continue  # 全局 digest pre-commit 不稳定 → CI 兜底
        if name in CI_SKIP_CHECKS and _is_ci_env():
            continue  # 本地运维 check (doctor), CI 无 .venv/CLI → 跳
        if name in BROKEN_CHECKS and not strict:
            continue  # 已知不可用 (broken: True), 仅 strict 模式下检查
        if risk_profile == "low" and name not in {
            "doc-governance",
            "doc-link-check",
            "check-conflict-markers",
            "layer-call-direction-check",
            "doc-claims-check",
            "check-submodule-rewind",
        }:
            continue
        if risk_profile == "medium" and name not in RISK_AWARE_CHECKS:
            continue
        if name == "change-lane-check":
            result.append((name, scoped_change_lane_command(scope, files, run_id)))
        elif name == "doc-link-check":
            cmd = scoped_doc_link_command(scope, files, run_id, strict)
            if cmd is None:
                continue  # 无 staged md → skip
            result.append((name, cmd))
        elif name == "layer-call-direction-check":
            # G1: pre-commit 增量快路径 (--files staged <1s), CI strict 全量 baseline
            result.append((name, scoped_layer_call_command(scope, files, command, strict)))
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


def scoped_layer_call_command(scope: str, files: list[str] | None, base_command: list[str], strict: bool) -> list[str]:
    """G1: layer-call 增量快路径 (治 CI >25s 超时, 2026-07-28).

    strict (CI) → base_command 全量 baseline 检查 (覆盖完整, ~3s).
    非 strict (pre-commit) → 只扫 staged .py/.ts/.tsx, base_command 追加 --files (<1s).
    无 staged 代码文件 → base_command (全量, 保持覆盖, 不跳过).
    """
    if strict:
        return base_command
    if scope == "staged":
        staged = staged_files_git()
    elif scope == "files":
        staged = files or _matched_files_from_env()
    else:
        staged = files or []
    code_files = [f for f in staged if f.endswith((".py", ".ts", ".tsx"))]
    if not code_files:
        return base_command
    return base_command + ["--files"] + code_files


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


# ADR-0209 A6: three finding-topic checks — classify structured issues even on soft warn.
FINDING_TOPIC_CHECKS: dict[str, dict[str, str]] = {
    "governance-semantic-gate": {
        "topic": "governance-semantic",
        "label": "治理语义门 (semantic / evolution / service-config)",
    },
    "gac-compute-onboard-check": {
        "topic": "compute-onboard",
        "label": "算力并网自检 (AetherForge 五渠连通)",
    },
    "bus-usage-report": {
        "topic": "bus-dormant-adapter",
        "label": "总线休眠适配器 (declaration without execution)",
    },
}

ADAPTIVE_CHECKS: set[str] = {
    "check-submodule-rewind",
}

RISK_AWARE_CHECKS: set[str] = {
    "doc-governance",
    "doc-link-check",
    "check-conflict-markers",
    "layer-call-direction-check",
    "doc-claims-check",
    "mof-capabilities-drift-check",
    "change-lane-check",
    "check-submodule-rewind",
    "submodule-ancestry-gate",
    "check-work-landed",
    "check-governance-ratio",
    "check-redline-coverage",
    "check-workorder-schema",
    "check-dual-track-purity",
    "check-silent-loss",
    "check-adversarial-effectiveness",
    "check-evidence-honest-closure",
    "check-gateway-status-doc",
    "check-foundry-deck-coverage",
    "check-evidence-freshness",
    "check-governance-trend",
    "bus-usage-report",
    "bos-tracking-gate",
    "check-index-drift",
    "gac-validate",
    "gac-drift",
    "write-owner-audit",
    "test-mcp-kos",
    "check-cockpit-ui-dist",
    "agent-workflow-lint",
    "agent-workflow-integrations",
    "agent-workflow-adapters",
    "agent-workflow-bootstrap",
    "agent-workflow-observe",
    "governance-evolution",
    "mof-schema-validate",
    "mof-state-bridge",
    "mof-drift",
    "m4-bootstrap-reflex",
    "doc-ssot-lint",
    "doc-ssot-snapshots",
    "dependency-baseline-drift",
    "matrix-consistency",
    "governance-semantic-gate",
    "adr-coverage",
    "sweep-index-check",
    "state-freshness-check",
    "current-state-coherence",
    "check-dashboard-registry-consistency",
    "check-toolbox-ssot",
    "check-domain-m1-alignment",
    "test-gac-engine",
    "service-config-validate",
    "service-config-drift",
    "gac-consensus-inject-check",
    "gac-compute-onboard-check",
    "test-coverage-check",
    "debt-integrity-check",
    "omo-state-write-guard",
    "brief-protect",
    "check-severity-registry",
    "derived-only-fast-track",
    "auto-fix-loop",
    "command-discovery",
}


def _adaptive_threshold(metrics_file: Path, check: str, window: int = 50) -> int | None:
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE / "bin" / "gac" / "adaptive-gate.py"),
                "--check",
                check,
                "--window",
                str(window),
                "--file",
                str(metrics_file),
            ],
            capture_output=True,
            text=True,
            cwd=WORKSPACE,
            timeout=10,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout)
        return int(data.get("recommended_warn_threshold") or 0) or None
    except Exception:
        return None


def run_check(name: str, command: list[str]) -> dict[str, object]:
    # Gate commands are either bare script paths (legacy) or carry an explicit
    # interpreter token (new ecos sgf-policy gates, e.g. ["python3", "bin/..."]).
    # Strip a leading interpreter token so we don't double-invoke the interpreter
    # (sys.executable + "python3" -> python3: can't open file 'python3').
    cmd = list(command)
    if cmd and cmd[0] in {"python3", "python"}:
        cmd = cmd[1:]
        cmd = [sys.executable, *cmd] if cmd else [sys.executable]
    elif cmd and cmd[0] in {"bash", "sh"}:
        cmd = cmd[1:] or ["true"]
    else:
        cmd = [sys.executable, *cmd] if cmd else [sys.executable]
    timeout = _CHECK_TIMEOUTS.get(name, 15)
    started_ns = time.time_ns()
    try:
        result = subprocess.run(
            cmd,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        duration_ms = int((time.time_ns() - started_ns) / 1_000_000)
        return {
            "name": name,
            "command": " ".join(command),
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time_ns() - started_ns) / 1_000_000)
        return {
            "name": name,
            "command": " ".join(command),
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"TIMEOUT after {timeout}s",
            "duration_ms": duration_ms,
        }


def extract_finding_topics(results: list[dict[str, object]]) -> list[dict[str, object]]:
    """Expand A6 checks into classified finding topics for agents/dashboards.

    Hard FAIL (returncode != 0) → severity error.
    Soft JSON findings with ok=false / non-empty findings → severity warn (does not
    flip gate ok by itself; the check's returncode still owns gate pass/fail).
    """
    topics: list[dict[str, object]] = []
    for item in results:
        name = str(item.get("name") or "")
        meta = FINDING_TOPIC_CHECKS.get(name)
        if not meta:
            continue
        base = {
            "check": name,
            "topic": meta["topic"],
            "label": meta["label"],
            "command": item.get("command"),
            "returncode": item.get("returncode"),
        }
        if not item.get("ok"):
            topics.append(
                {
                    **base,
                    "severity": "error",
                    "blocking": True,
                    "summary": (str(item.get("stderr") or item.get("stdout") or "")[:400] or "check failed"),
                }
            )
            continue
        # Soft findings from JSON-capable checks (e.g. governance-semantic-gate)
        stdout = str(item.get("stdout") or "")
        if not stdout.lstrip().startswith(("{", "[")):
            continue
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            continue
        findings_raw: list[object] = []
        if isinstance(payload, dict):
            if payload.get("ok") is False:
                findings_raw.append(payload.get("summary") or payload.get("message") or "ok=false")
            nested = payload.get("findings") or payload.get("checks") or []
            if isinstance(nested, list):
                for row in nested:
                    if not isinstance(row, dict):
                        continue
                    if row.get("ok") is False or row.get("findings"):
                        findings_raw.append(
                            f"{row.get('id') or row.get('name') or 'item'}: "
                            f"{row.get('findings') or row.get('message') or 'not ok'}"
                        )
        if findings_raw:
            topics.append(
                {
                    **base,
                    "severity": "warn",
                    "blocking": False,
                    "summary": "; ".join(str(x) for x in findings_raw[:8]),
                    "finding_count": len(findings_raw),
                }
            )
    return topics


def _apply_adaptive_thresholds(
    checks: tuple[tuple[str, list[str]], ...],
    metrics_file: Path,
    window: int = 50,
) -> tuple[tuple[str, list[str]], ...]:
    result: list[tuple[str, list[str]]] = []
    for name, command in checks:
        if name not in ADAPTIVE_CHECKS:
            result.append((name, command))
            continue
        threshold = _adaptive_threshold(metrics_file, name, window=window)
        if threshold is None:
            result.append((name, command))
            continue
        new_command = [*command, "--warn-threshold", str(threshold)]
        result.append((name, new_command))
    return tuple(result)


def run_gate(
    scope: str = "staged",
    files: list[str] | None = None,
    run_id: str = "",
    strict: bool = False,
    agt_backend: bool = False,
    adaptive: bool = False,
    risk_profile: str | None = None,
) -> dict[str, object]:
    # Concurrent-write isolation snapshot (P79 治本).
    # 在所有 check 启动前拍下 read-side 状态指纹, 跑完后比对漂移.
    global _state_fingerprint_snapshot
    _state_fingerprint_snapshot = _read_state_fingerprint()
    change_lane_files = change_lane_files_for_scope(scope, files, run_id)
    checks = gate_checks(scope, files, run_id, strict, risk_profile=risk_profile)
    metrics_file = WORKSPACE / ".omo" / "state" / "metrics-store.jsonl"
    if adaptive:
        checks = _apply_adaptive_thresholds(checks, metrics_file)
    results = [run_check(name, command) for name, command in checks]
    if agt_backend:
        agt_results = run_agt_policy_engine()
        results.extend(agt_results)
    finding_topics = extract_finding_topics(results)

    # HARD/SOFT 分离: soft checks 不翻转 gate
    hard_fails = [r for r in results if not r["ok"] and r["name"] not in SOFT_CHECKS]
    soft_warns = [r for r in results if not r["ok"] and r["name"] in SOFT_CHECKS]
    ok = len(hard_fails) == 0

    # Concurrent-write isolation: 比对所有 check 跑完后的 fingerprint
    drift = _check_drift(_state_fingerprint_snapshot)
    report = {
        "ok": ok,
        "hard_fails": hard_fails,
        "soft_warns": soft_warns,
        "scope": scope,
        "run_id": run_id or None,
        "change_lane_files": change_lane_files,
        "checks": results,
        "finding_topics": finding_topics,
        "agt_backend": agt_backend,
    }
    _update_drift_topic(report, drift)
    return report


def run_agt_policy_engine() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    try:
        proc = subprocess.run(
            ["agora", "resolve", "bos://governance/agt/policy"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            results.append(
                {
                    "name": "agt-policy-engine",
                    "ok": True,
                    "command": ["agora", "resolve", "bos://governance/agt/policy"],
                    "stdout": "AGT Policy Engine backend active",
                    "stderr": "",
                    "duration_ms": 0,
                }
            )
        else:
            results.append(
                {
                    "name": "agt-policy-engine",
                    "ok": False,
                    "command": ["agora", "resolve", "bos://governance/agt/policy"],
                    "stdout": "",
                    "stderr": proc.stderr or "AGT policy engine unavailable",
                    "duration_ms": 0,
                }
            )
    except FileNotFoundError:
        results.append(
            {
                "name": "agt-policy-engine",
                "ok": False,
                "command": ["agora", "resolve", "bos://governance/agt/policy"],
                "stdout": "",
                "stderr": "AGT policy engine unavailable (agora CLI not found)",
                "duration_ms": 0,
            }
        )
    except subprocess.TimeoutExpired:
        results.append(
            {
                "name": "agt-policy-engine",
                "ok": False,
                "command": ["agora", "resolve", "bos://governance/agt/policy"],
                "stdout": "",
                "stderr": "AGT policy engine timeout",
                "duration_ms": 5000,
            }
        )
    return results


def print_human(
    report: dict[str, object],
    verbose: bool = False,
    emit_events: bool = False,
) -> None:
    output_cfg = POLICY.get("settings", {}).get("output", {})
    terminal_mode = output_cfg.get("terminal_mode", "slim")

    checks_list: list[dict] = report["checks"]  # type: ignore[assignment]
    change_lane: list[str] = report["change_lane_files"]  # type: ignore[assignment]
    is_ok: bool = report["ok"]  # type: ignore[assignment]
    checks_count = len(checks_list)

    if is_ok and terminal_mode == "slim" and not verbose:
        print("═══ GaC local gate ═══")
        print(f"scope={report['scope']} change_lane_files={len(change_lane)}")
        print(f"GaC local gate: PASS ({checks_count} checks executed, ALL GREEN)")
        if BROKEN_CHECKS:
            print(f"  ⚠️  {len(BROKEN_CHECKS)} broken/known-unavailable checks skipped (use --strict to include)")
        if emit_events:
            _emit_gate_events(is_ok, report.get("hard_fails"), report.get("soft_warns"))
        return

    print("═══ GaC local gate ═══")
    print(f"scope={report['scope']} change_lane_files={len(change_lane)}")
    for item in checks_list:
        if item["ok"]:
            status = "PASS"
        elif item["name"] in SOFT_CHECKS:
            status = "WARN"
        else:
            status = "FAIL"
        print(f"[{status}] {item['name']} :: {item['command']}")
        if not item["ok"]:
            if item["stdout"]:
                print(item["stdout"])
            if item["stderr"]:
                print(item["stderr"], file=sys.stderr)
    topics_raw = report.get("finding_topics")
    topics: list[object] = topics_raw if isinstance(topics_raw, list) else []
    if topics:
        print(f"finding_topics={len(topics)}")
        for topic in topics:
            t = topic if isinstance(topic, dict) else {}
            print(f"  [{str(t.get('severity', 'info')).upper()}] {t.get('topic')}: {t.get('summary')}")
    if BROKEN_CHECKS:
        print(f"  ⚠️  {len(BROKEN_CHECKS)} broken/known-unavailable checks skipped (use --strict to include)")
    hard_raw = report.get("hard_fails")
    hard_count = len(hard_raw) if isinstance(hard_raw, list) else 0
    soft_raw = report.get("soft_warns")
    soft_count = len(soft_raw) if isinstance(soft_raw, list) else 0
    parts = []
    if is_ok:
        parts.append("PASS")
    else:
        parts.append("FAIL")
    if soft_count:
        parts.append(f"{soft_count} SOFT WARN")
    print("GaC local gate: " + " | ".join(parts))
    if emit_events:
        _emit_gate_events(is_ok, hard_raw, soft_raw)


def _emit_gate_events(is_ok: bool, hard_raw: Any, soft_raw: Any) -> None:
    """门禁结果 → 统一事件面 (governance:gate_failed / governance:gate_passed).

    非阻断: emit 失败不影响 gate 退出码. 事件面由 observability-events.py 提供.
    """
    if os.environ.get("OBSERVABILITY_EVENTS") == "0":
        return
    events_script = WORKSPACE / "bin" / "ssot" / "observability-events.py"
    if not events_script.exists():
        return
    import json as _json

    try:
        if not is_ok and isinstance(hard_raw, list):
            for r in hard_raw[:5]:
                name = r.get("name") if isinstance(r, dict) else str(r)
                payload = _json.dumps({"check": name, "gate": "gac-local-gate"}, ensure_ascii=False)
                subprocess.run(
                    [
                        sys.executable,
                        str(events_script),
                        "emit",
                        "--domain",
                        "governance",
                        "--type",
                        "governance:gate_failed",
                        "--severity",
                        "critical",
                        "--source",
                        "gac-local-gate",
                        "--payload",
                        payload,
                    ],
                    capture_output=True,
                    check=False,
                    timeout=30,
                )
        else:
            subprocess.run(
                [
                    sys.executable,
                    str(events_script),
                    "emit",
                    "--domain",
                    "governance",
                    "--type",
                    "governance:gate_passed",
                    "--severity",
                    "info",
                    "--source",
                    "gac-local-gate",
                    "--payload",
                    '{"gate": "gac-local-gate"}',
                ],
                capture_output=True,
                check=False,
                timeout=30,
            )
    except Exception:  # 非阻断
        pass


def _load_rule_vitality_tracker():
    """Lazy-load rule-vitality-tracker module (hyphenated filename needs importlib)."""
    import importlib.util

    tracker_path = WORKSPACE / "bin" / "gac" / "rule-vitality-tracker.py"
    if not tracker_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("rule_vitality_tracker", str(tracker_path))
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _record_rule_vitality(report: dict[str, object]) -> None:
    """Record per-rule vitality entries from gate check results (BET-Y1Q2-T6-01)."""
    tracker = _load_rule_vitality_tracker()
    if tracker is None:
        return

    import yaml as _yaml

    mapping_path = WORKSPACE / ".omo" / "_truth" / "registry" / "rule-gate-mapping.yaml"
    if not mapping_path.exists():
        return
    try:
        mapping_data = _yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return
    gate_to_rules = mapping_data.get("gate_to_rules", {})
    if not gate_to_rules:
        return

    enforcement_map: dict[str, str] = {}
    rules_path = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    if rules_path.exists():
        try:
            docs = [d for d in _yaml.safe_load_all(rules_path.read_text(encoding="utf-8")) if d]
            if docs:
                for r in docs[-1].get("gac", {}).get("rules", []):
                    enforcement_map[r["id"]] = r.get("enforcement", "required")
        except Exception:
            pass

    for item in report.get("checks", []):
        if not isinstance(item, dict):
            continue
        check_name = item.get("name", "")
        check_ok = bool(item.get("ok"))
        duration = int(item.get("duration_ms") or 0)
        for rule_id in gate_to_rules.get(check_name, []):
            try:
                tracker.record_vitality(
                    rule_id,
                    check_name,
                    violated=not check_ok,
                    enforcement=enforcement_map.get(rule_id, "required"),
                    duration_ms=duration,
                )
            except Exception:
                pass


def append_metrics(report: dict[str, object]) -> None:
    metrics_file = WORKSPACE / ".omo" / "state" / "metrics-store.jsonl"
    try:
        import yaml
    except Exception:
        yaml = None  # type: ignore[assignment]
    for item in report.get("checks", []):
        if not isinstance(item, dict):
            continue
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "check": item.get("name", ""),
            "ok": bool(item.get("ok")),
            "duration_ms": int(item.get("duration_ms") or 0),
        }
        if item.get("stderr"):
            entry["reason"] = item["stderr"][:200]
        elif item.get("stdout"):
            entry["reason"] = item["stdout"][:200]
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with metrics_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    _record_rule_vitality(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the shared local GaC gate")
    parser.add_argument("--scope", choices=["staged", "files", "run"], default="staged")
    parser.add_argument("--file", action="append", default=[], help="Repo path for --scope files")
    parser.add_argument("--run-id", default="", help="Run id for --scope run")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="跑全套 (CI 用)")
    parser.add_argument(
        "--emit-events",
        action="store_true",
        help="Explicitly append gate results to the shared observability event log",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print passing gate details under slim mode",
    )
    parser.add_argument(
        "--agt-backend",
        action="store_true",
        help="Use AGT Policy Engine as GaC rule execution backend",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Record check results to metrics-store.jsonl",
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Enable adaptive threshold adjustment for supported checks",
    )
    parser.add_argument(
        "--risk-profile",
        choices=["low", "medium", "high"],
        help="Risk-aware gate filtering",
    )
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Generate Markdown summary of gate report",
    )
    parser.add_argument(
        "--alert",
        action="store_true",
        help="Run anomaly detection on metrics-store.jsonl after gate",
    )
    args = parser.parse_args()

    try:
        report = run_gate(
            args.scope,
            args.file,
            args.run_id,
            args.strict,
            args.agt_backend,
            args.adaptive,
            args.risk_profile,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if args.summarize:
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(report, tmp, ensure_ascii=False, indent=2)
                tmp_path = tmp.name
            proc = subprocess.run(
                [
                    sys.executable,
                    str(WORKSPACE / "bin" / "gac" / "governance-summarizer.py"),
                    "--report",
                    tmp_path,
                ],
                capture_output=True,
                text=True,
                cwd=WORKSPACE,
            )
            if proc.returncode == 0:
                print(proc.stdout)
            else:
                print(f"[WARN] summarizer failed: {proc.stderr}", file=sys.stderr)
        except Exception as exc:
            print(f"[WARN] summarize failed: {exc}", file=sys.stderr)

    if args.metrics:
        try:
            append_metrics(report)
        except Exception as exc:
            print(f"[WARN] metrics append failed: {exc}", file=sys.stderr)

    if args.alert:
        try:
            anomaly_script = WORKSPACE / "bin" / "gac" / "anomaly-detector.py"
            proc = subprocess.run(
                [sys.executable, str(anomaly_script)],
                capture_output=True,
                text=True,
                cwd=WORKSPACE,
            )
            if proc.returncode == 0:
                print(proc.stdout)
            else:
                print(f"[WARN] anomaly detector failed: {proc.stderr}", file=sys.stderr)
        except Exception as exc:
            print(f"[WARN] alert run failed: {exc}", file=sys.stderr)

    if args.emit_events:
        _emit_gate_events(
            bool(report["ok"]),
            report.get("hard_fails"),
            report.get("soft_warns"),
        )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report, args.verbose)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
