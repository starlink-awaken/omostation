---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0164-p77-phase1-cross-repo-consistency.md
  - STRAT-P77-strategic-roadmap.md (Phase 2 启动)
  - ../../../standards/p76-principles.md
  - ../../../../../tests/test_p76_principles.py
supersedes: []
---

# ADR-0165: P77 Phase 2 — 演化护栏 catalog (15 原则形式化 + 5 新 GaC rules)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P77 STRAT § 2 Phase 2 的实施收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **原则 catalog** | ✅ | `.omo/standards/p76-principles.md` (15 原则, 5 phase 分类) |
| **5 新 GaC rules** | ✅ | 165 → **169** rules |
| **catalog 验证测试** | ✅ | `tests/test_p76_principles.py` (≥6 PASSED) |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

STRAT-P77 § 2 Phase 2: 治本 #2. 把 P76 沉淀的 40 原则 (实际 15, see catalog § 0 注) 形式化, 防回退.

ROOT CAUSE: 原则散在各 ADR 文档, 没有 catalog. 后续 phase 找不到 / 重复创造 / 借不到前任 wisdom. STRAT-P77 § 4 P77-2 / P77-3 / P77-4 沉淀原则 already named.

### 1.2 WHAT — catalog

`.omo/standards/p76-principles.md`:
- 5 章节 (Phase 6/7/8/9A/P77-1)
- 15 原则每条带 code + name + 含义 + 反例 + 实践
- § 6 列 5 个新 GaC rules 计划
- § 7 演进指南
- § 8 现状快照

### 1.3 WHAT — 5 新 GaC rules (本 ADR 实施)

```yaml
- CR-PRINCIPLE-FOLLOWED (X1, meta, advisory)
  任意 phase 主交付前的 ADR § 2 沉淀原则 列全
  source: .omo/standards/p76-principles.md

- CR-EVIDENCE-DECLARED (X4, meta, advisory)
  ADR closeout 引用 ≥1 evidence path
  source: docs/SPEC § 4 evidence_required

- CR-PR-CHECKLIST-COMPLETE (X1, meta, advisory)
  PR body ≥ 1 行非空 + 含 WHY/WHAT
  source: gh pr view --json body

- CR-CROSS-REPO-CHECK (X3, meta, advisory → hard by Phase 3)
  bin/check-cross-repo-consistency.py unregistered ≤ threshold (default 20, Phase 3 治本降至 0)
  source: bin/check-cross-repo-consistency.py

- CR-BASELINE-REPLAYED (X2, meta, advisory)
  每次阶段尾 governance score 必 ≥ 起点
  source: omo governance --json
```

### 1.4 NEXT — Phase 3 入口

| 候选 | ROI |
|------|-----|
| 跨仓 unregistered 治本 (Phase 3 治本 + threshold 20→0) | 高 |
| CR-CROSS-REPO-CHECK 升 hard | 高 |
| Foundry v2 web dashboard (降优先级) | 低 |

## 2. 沉淀原则 (P77-2)

| # | 原则 | 含义 |
|---|------|------|
| P77-2-1 | **principle-formalization-with-context** | 原则形式化保留"上下文", 不变成死的 checkbox |
| P77-2-2 | **catalog-SSOT** | 原则 catalog 是 SSOT, ADR § 2 是 mirror — 防 source split |
| P77-2-3 | **rule-per-principle** | 每个原则对应一条 GaC rule (enforcement path) |
| P77-2-4 | **anti-rollback-baseline** | 阶段尾必重放 baseline (governance ≥ 起点), 防回退 |
| P77-2-5 | **multi-agent-coordination-via-ssot** | 跨 agent 协作走 catalog (single source), 不靠"应该都知道" |

## 3. 不在本 ADR 范围

- ❌ 5 GaC rules 的真实施代码 (`bin/*` 守门) — 写到 P77 Phase 2.5 (plugin 化)
- ❌ 跨仓 unregistered 的实际治本 — 留给 P77 Phase 3 (W5-6)
- ❌ LLM-assisted commit 默认开启的 aetherforge tier — P77 Phase 4 (W7-9)

## 4. 验证清单

- [x] `.omo/standards/p76-principles.md` 创建 (15 原则 + 5+ 下一步)
- [x] 5 个新 GaC rules 注册 (169 total)
- [x] 单元测试 `tests/test_p76_principles.py` (≥6 PASSED)
- [x] M1 sync (169 ↔ 169, 0/0/0)
- [x] ADR-0165 ACCEPTED + INDEX

## 5. 关联

- STRAT-P77 § 4 P77-2 沉淀原则 (formality + with-context)
- ADR-0164 (Phase 1 cross-repo)
- ADR-0160..0163 (P76 全部 15 原则来源)
- .omo/standards/p76-principles.md (本 ADR 治本产物)

---

*最后更新: 2026-07-07 · P77 Phase 2 演化护栏 catalog 收口 · ACCEPTED*
