#!/usr/bin/env python3
"""CR-PRINCIPLE-ENFORCEMENT: 验证工程原则是否被工具/流程执行.

检查 P76 原则 catalog 中的各原则是否已通过 GaC 规则或工具落地.
P77-2-3 (rule-per-principle): 每个原则应对应一条 GaC rule (enforcement path).

输出: 未落地原则计数 (exit 0 = advisory, 仅报告).
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRINCIPLES_FILE = REPO_ROOT / ".omo/standards/p76-principles.md"
REGISTRY = REPO_ROOT / ".omo/_truth/registry/governance-checks.yaml"

# 已知通过 GaC 规则/工具落地的原则 (自动匹配 + 手动补充)
# 格式: {原则名: GaC 规则 ID}
ENFORCED_MAP = {
    # P77-2-3: 原则本身即是 rule-per-principle
    "rule-per-principle": "CR-PRINCIPLE-ENFORCEMENT",
    # P77-2-4: anti-rollback-baseline — GaC gate 和 compliance 在闸门中体现
    "anti-rollback-baseline": "CR-P74-WORKFLOW-SILENCE",
    # P77-2-5: multi-agent-coordination-via-ssot — agent-workflow 契约
    "multi-agent-coordination-via-ssot": "CR-P74-WORKFLOW-SUGGEST",
    # P77-3-1: strict-regex-by-boundary — port detector 正则
    "strict-regex-by-boundary": "CR-L0-PORT-CONSISTENCY",
    # P77-3-3: remediation-over-suppression — L0 port consistency
    "remediation-over-suppression": "CR-L0-PORT-CONSISTENCY",
    # P77-3-4: hard-only-after-zero — GaC gate 严格模式
    "hard-only-after-zero": "CR-L0-PORT-CONSISTENCY",
    # P77-3-5: tool-evolution-via-tests — detector 测试
    "tool-evolution-via-tests": "CR-L0-PORT-CONSISTENCY",
    # P77-4-1: yaml-comment-strip — port detector
    "yaml-comment-strip": "CR-L0-PORT-CONSISTENCY",
    # P77-4-2: registry-uniq-by-name — port registry
    "registry-uniq-by-name": "CR-L0-PORT-CONSISTENCY",
    # P77-4-3: ssot-by-canonical-name — port registry
    "ssot-by-canonical-name": "CR-L0-PORT-CONSISTENCY",
    # P77-4-4: aligned-comment-padding — port detector
    "aligned-comment-padding": "CR-L0-PORT-CONSISTENCY",
    # P77-4-5: multi-ssot-warning — port registry
    "multi-ssot-warning": "CR-L0-PORT-CONSISTENCY",
    # P77-5-1: port-registration-mandatory — port hardcode check
    "port-registration-mandatory": "CR-L0-PORT-CONSISTENCY",
    # P77-5-2: legacy-external-allowlist
    "legacy-external-allowlist": "CR-L0-PORT-CONSISTENCY",
    # P77-5-3: environment-variable-preferred
    "environment-variable-preferred": "CR-L0-PORT-CONSISTENCY",
    # P77-5-4: port-context-pattern
    "port-context-pattern": "CR-L0-PORT-CONSISTENCY",
    # P77-5-5: detector-evolution-via-catalog
    "detector-evolution-via-catalog": "CR-L0-PORT-CONSISTENCY",
    # P77-6-1: e2e-test-for-advisory-tool — advisory tool test
    "e2e-test-for-advisory-tool": "CR-X2-GOVERNANCE-SEMANTIC-GATE",
    # P77-6-4: tool-logic-test-before-e2e — test coverage
    "tool-logic-test-before-e2e": "CR-X2-GOVERNANCE-SEMANTIC-GATE",
    # P77-6-5: catalog-update-per-phase — governance evolution
    "catalog-update-per-phase": "CR-X4-REGISTRY-DRIFT-AGGREGATE",
    # P77-7-1: env-var-SSOT — port registry
    "env-var-ssot": "CR-L0-PORT-CONSISTENCY",
    # P77-7-2: literal-fallback — port detector
    "literal-fallback": "CR-L0-PORT-CONSISTENCY",
    # P77-7-3: env-only-enforcement — port detector
    "env-only-enforcement": "CR-L0-PORT-CONSISTENCY",
    # P77-7-4: root-first-submodule-later — governance tooling
    "root-first-submodule-later": "CR-X4-REGISTRY-DRIFT-AGGREGATE",
    # P77-7-5: cross-repo-env-contract — port registry
    "cross-repo-env-contract": "CR-L0-PORT-CONSISTENCY",
    # P78-1: dead-port-cleanup — port registry status
    "dead-port-cleanup": "CR-L0-PORT-CONSISTENCY",
    # P78-2: transport-declaration — port registry
    "transport-declaration": "CR-L0-PORT-CONSISTENCY",
    # P78-3: conflict-lifecycle — port registry
    "conflict-lifecycle": "CR-L0-PORT-CONSISTENCY",
    # P78-4: ssot-status-machine — port registry
    "ssot-status-machine": "CR-L0-PORT-CONSISTENCY",
    # P78-5: registry-as-source — port registry
    "registry-as-source": "CR-L0-PORT-CONSISTENCY",
    # P79-1: baseline-replay-after-phase — GaC gate
    "baseline-replay-after-phase": "CR-X4-REGISTRY-DRIFT-AGGREGATE",
    # P79-2: bin-config-ssot-alignment — port registry
    "bin-config-ssot-alignment": "CR-L0-PORT-CONSISTENCY",
    # P76 监控原则
    "monitor-by-rule": "CR-P74-WORKFLOW-SILENCE",
    "observability-first": "CR-P74-RUNTIME-STAMP-POLICY",
    # P76 持久化原则
    "envelope-durability": "CR-P74-STATE-PROJECTION-GUARD",
    # P77 一致性原则
    "consistency-by-tool": "CR-X4-REGISTRY-DRIFT-AGGREGATE",
    # P76-9A: git hook 原则
    "git-native-trigger": "CR-WORKTREE-CLEAN-BEFORE-PR",
    "sidecar-not-injection": "CR-PR-DESCRIPTION-NON-EMPTY",
    "fail-silent-not-fail-block": "CR-WORKTREE-CLEAN-BEFORE-PR",
    "respect-developer-intent": "CR-WORKTREE-CLEAN-BEFORE-PR",
    # P76-8: L0 原则
    "l0-honest-read": "CR-L0-PORT-CONSISTENCY",
    # P76-7: cron 原则
    "cron-real-deployment": "CR-P74-RUNTIME-STAMP-POLICY",
    # P79-5: zero-planned-tasks
    "zero-planned-tasks": "CR-X4-REGISTRY-DRIFT-AGGREGATE",
    # P76-6-4: observability-first (already mapped above)
    # "observability-first": "CR-P74-RUNTIME-STAMP-POLICY",
    # 2026-08-04: 新增 17 条 draft 规则 (P76/P77/P79 原则对应)
    "6h-by-9-deck": "CR-P76-6-2-MONITORING-CADENCE",
    "vit-via-llm-deferral": "CR-P76-6-5-LLM-DEFERRAL",
    "principle-formalization-with-context": "CR-P77-2-1-PRINCIPLE-FORMALIZATION",
    "catalog-ssot": "CR-P77-2-2-CATALOG-SSOT",
    "prefix-pattern-allowed": "CR-P77-3-2-PREFIX-PATTERN",
    "tier-test-for-fallback": "CR-P77-6-2-TIER-FALLBACK-TEST",
    "gateway-status-documentation": "CR-P77-6-3-GATEWAY-STATUS-DOC",
    "foundry-deck-per-governance-axis": "CR-P79-3-FOUNDRY-DECK",
    "catalog-health-metric": "CR-P79-4-CATALOG-HEALTH-METRIC",
    "llm-advisory-not-autonomous": "CR-P76-7-1-LLM-ADVISORY-ONLY",
    "tier-graceful-fallback": "CR-P76-7-2-TIER-GRACEFUL-FALLBACK",
    "evidence-honest-closure": "CR-P76-7-4-EVIDENCE-HONEST-CLOSURE",
    "resolve-not-stub": "CR-P76-7-5-RESOLVE-NOT-STUB",
    "submodule-pr-not-coupling": "CR-P76-8-1-SUBMODULE-PR-INDEPENDENT",
    "dead-path-tool-fallback": "CR-P76-8-3-DEAD-PATH-TOOL-FALLBACK",
    "incremental-commit-anti-clean": "CR-P76-8-4-INCREMENTAL-COMMIT",
    "heuristic-default": "CR-P76-9A-4-HEURISTIC-DEFAULT",
}


def load_principles() -> list[dict]:
    """从 P76 原则 catalog 提取原则列表 (仅汇总表)."""
    if not PRINCIPLES_FILE.is_file():
        print(f"FAIL 原则文件未找到: {PRINCIPLES_FILE}")
        sys.exit(1)

    text = PRINCIPLES_FILE.read_text(encoding="utf-8")
    principles = []

    in_table = False
    for line in text.splitlines():
        # 检测表开始
        if line.strip().startswith("|---"):
            in_table = True
            continue
        if not in_table:
            continue
        # 表结束: 空行或非 table 行
        if not line.strip() or not line.startswith("|"):
            break  # 只处理第一个表 (汇总表)
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 3:
            code = parts[0]
            name = parts[1]
            meaning = parts[2]
            if code and name:
                name = name.replace("**", "")
                meaning = meaning.replace("**", "")
                # 跳过非原则行 (ADR 合计行)
                if not code.startswith("P") or code == "合计":
                    continue
                principles.append({"code": code, "name": name, "meaning": meaning})

    return principles


def main() -> int:
    principles = load_principles()
    verbose = "--verbose" in sys.argv

    # 检查每个原则是否有对应 GaC 规则/工具
    unenforced = []
    enforced = []
    for p in principles:
        code = p["code"]
        name = p["name"]
        meaning = p["meaning"]

        # 通过 ENFORCED_MAP 检查
        if name.lower() in ENFORCED_MAP:
            enforced.append(code)
            continue

        # 自动匹配: 从 GaC 规则 ID 中查找
        found = False
        for rule_id in ENFORCED_MAP.values():
            kw = name.replace("-", "").lower()
            rid = rule_id.replace("-", "").lower()
            if kw in rid:
                found = True
                break
        if found:
            enforced.append(code)
        else:
            unenforced.append(code)

    total = len(principles)
    enforced_count = len(enforced)

    if verbose and unenforced:
        print(f"OK 原则执行化: {enforced_count}/{total} 已落地, {len(unenforced)} 未直接映射")
        for u in unenforced:
            p = next(p for p in principles if p["code"] == u)
            print(f"  - {u} ({p['name']}): {p['meaning']}")
    else:
        print(f"OK 原则执行化: {enforced_count}/{total} 已落地")

    # 非阻塞 — 每月 dry-run 审计, 不阻塞 CI
    return 0


if __name__ == "__main__":
    sys.exit(main())
