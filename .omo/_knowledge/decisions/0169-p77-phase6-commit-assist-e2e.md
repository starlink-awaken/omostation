---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0163-p76-phase9a-commit-assist-hook.md
  - 0165-p77-phase2-evolution-guardrails.md
  - 0168-p77-phase5-hardcoded-ports.md
  - STRAT-P77-strategic-roadmap.md (Phase 6)
  - ../../../../../bin/commit-assist.py
  - ../../../../../tests/test_commit_assist_e2e.py
  - ../../../../../.githooks/prepare-commit-msg-commit-assist
supersedes: []
---

# ADR-0169: P77 Phase 6 — LLM-assisted commit 端到端验收 (19 测试 + heuristic bug 修)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P77 STRAT § 2 Phase 6 收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **commit-assist E2E 测试** | ✅ | `tests/test_commit_assist_e2e.py` (19 tests, 全 PASSED) |
| **heuristic_subject bug 修复** | ✅ | `bin/commit-assist.py` `[-1]` → `[0]` (解析文件路径, 非 diff 统计) |
| **3-tier graceful degradation 验证** | ✅ | aetherforge(不可达)→ollama(超时)→heuristic(回落, 所有 case) |
| **aetherforge gateway 状态** | ✅ | **不可达** (超时 5s, 需 infra 修复) |
| **CR-COMMIT-ASSIST-E2E GaC 规则** | ✅ | governance-checks.yaml **171** rules |
| **catalog 45 原则** | ✅ | p76-principles.md 40→45 (P77-6-1..5) |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

P77 STRAT § 2 Phase 6 入口: P77-5 port-registration-mandatory 治本完成, 转向
"LLM-assisted commit 真验证层". 修真修真反模式:

- `bin/commit-assist.py` 从 Phase 7 (2026-06-23) 开始就无测试覆盖
- `heuristic_subject()` 用 `[-1]` 取 diff 统计而非文件路径 → 路径引导全失效, 永远回退到 `chore(misc)`
- 3-tier (aetherforge → ollama → heuristic) 从未端到端验证
- commit-assist hook 虽然是 advisory, 但无测试证明其真不阻塞 commit

### 1.2 WHAT — heuristic_subject bug 根因

```python
# 旧: heuristic_subject 取 line.split()[-1] — diff 统计 (+- / ++++), 非文件路径
# 路径匹配 6 个 if/elif 永不触发 → 永远 chome(misc)
# 修: line.split()[0] — 取文件路径

def heuristic_subject(stat: str) -> tuple[str, str]:
    files = [line.split()[0] for line in stat.splitlines() if "|" in line]
    #                          ^^ [-1] → [0]  (bug fix)
```

影响: 所有 heuristic 模式下的 commit-assist 建议类型不准确:
- `.omo/_truth/registry/` 改动 → `chore(misc)` 而非 `feat(gac)`
- 测试断言: 7 个 path-specific 测试 (gac/adr/docs/bin/omo/projects) 全 PASSED 验证治本

### 1.3 WHAT — 19 测试覆盖

```
tests/test_commit_assist_e2e.py
├── heuristic_subject (8 tests)  — 7 path patterns + 1 empty
├── clean_suggestion (3 tests)   — noop / fence / fence-lang
├── 72-char truncation (2 tests)  — over/under
├── ctype format (1 test)         — scope 含在 ctype 中
├── CONVENTIONAL_TYPES (1 test)   — 11 types
├── integration (2 tests)         — dry-run + empty staged
└── tier fallback (2 tests)       — aetherforge + ollama unreachable
```

### 1.4 WHAT — aetherforge gateway 状态

**结论: aetherforge gateway (100.96.126.35:4000) 当前不可达.**

| 测试 | 结果 |
|------|:----:|
| HTTP 连接 (5s timeout) | 超时 (unreachable) |
| query_aetherforge() 测试 | 返回 None (graceful fallback, 不崩溃) |
| ollama local (gemma4:31b-mlx) | 超时 (31B 模型响应慢) |
| 最终 fallback | heuristic (100% 工作) |

这意味着 P77-6 当前 3-tier = 2-tier (aetherforge + ollama 都不可达 → heuristic).
**治本**: `gac-compute-onboard` infra 修复 (已知 cc-switch 0 credentials 问题).

### 1.5 WHAT — CR-COMMIT-ASSIST-E2E GaC 规则

新规则 `CR-COMMIT-ASSIST-E2E` (X4, consistency_drift):

- 守护: commit-assist 测试必须通过 (19/19)
- target: `tests/test_commit_assist_e2e.py`
- executor: `[ci_gate, gac_local_gate]`
- enforcement: `advisory` (测试可通过)

### 1.6 NEXT — Phase 7 入口

| 候选 | ROI | 依赖 |
|------|-----|------|
| **aetherforge gateway 修复 + 真 3-tier E2E** | 高 | `gac-compute-onboard` infra |
| **端口硬编码 → env var 重构** | 中 | 慢 |
| **commit-assist hook 升级 3-tier** | 中 | 当前 heuristic-only |
| **Foundry v2 web dashboard** | 低 | — |

## 2. 沉淀原则 (P77-6)

| # | 原则 | 含义 |
|---|------|------|
| P77-6-1 | **e2e-test-for-advisory-tool** | advisory 工具必须有 E2E 测试验证不动手时无害 (P76-7-1 fail-safe) |
| P77-6-2 | **tier-test-for-fallback** | 每级 fallback 都必须有测试证明不崩溃 (P76-7-2 特化) |
| P77-6-3 | **gateway-status-documentation** | 外部 LLM gateway 不可达时, 必须文档化不可达状态 + 时间戳, 不留"应该可用"假设 |
| P77-6-4 | **tool-logic-test-before-e2e** | 测试先覆盖纯逻辑函数 (heuristic/parser), 再 E2E — 修真修真反模式 |
| P77-6-5 | **catalog-update-per-phase** | 每 phase 收口必更新 catalog 原则表 (P77-2-2 强化) |

