---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0146-8stage-stability-declaration.md
  - 0147-mcptool-adder-guide.md
  - 0140-m4-health-score.md
  - ../../../AGENTS.md
supersedes: []
---

# ADR-0148: Round-Trip 流程文档化 (Round 5c)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

把 R0..R5b (22+ commits + 17 ADRs) 沉淀成可复用的"round-trip playbook",
写入 `AGENTS.md` §10 新小节。
**核心价值**: Round 6+ 不必再 walk 5 阶段 38 里程碑,直接 follow 7 步 playbook。

---

## 1. 决策

### 1.1 Round-Trip 7 步 (沉淀自 R0..R5b)

每轮 (Round X) 工程 → commit → ADR → 测的循环:

```
Round X 的 7 步:

0. baseline: 跑 m4-health-score, 留当前分数快照
   uv run --with pyyaml python bin/mof/m4-health-score.py --emit
1. single-worktree: bash bin/gac/gac-worktree.sh claim round-{X}
2. deliver: 实施 N 个 deliverable (每 PR 1 deliverable)
   - 每次 commit: git log --oneline e2f8f4d7..HEAD
3. tests: 加 T-X 系列测试, 跑 regression
   uv run --with pyyaml python tests/integration/m4_metamodel/run_all.py
4. self-reflex: 5-check strict all PASS
   uv run --with pyyaml python bin/mof/mof-bootstrap.py all
5. ADR: 写新 ADR (X-NNN-decision-title.md), INDEX append
6. health-check: 跑 m4-health-score.py, delta 对比
   uv run --with pyyaml python bin/mof/m4-health-score.py --compare
7. close: 写 docs/{round}/SUMMARY.md (从 baseline → closeout diff),
   准备 PR, 显式 commit PR | round-X-final

end-of-round: commit 数 ≤ previous_round × 1.5
       test count ≥ previous_round × 1.1
       health score ≥ previous_round (不回退)
```

### 1.2 round-trip quality gates

每 Round 必过 3 个 gate:

| Gate | 工具 | 期望 |
|------|------|------|
| **G-Tests** | `tests/integration/m4_metamodel/run_all.py` | N+1/N+1 PASS (N+1 ≥ 上一轮 +1) |
| **G-Reflex** | `bin/mof/mof-bootstrap.py all` | 5-check strict 0 err |
| **G-Health** | `bin/mof/m4-health-score.py --compare` | 不回退 (delta ≥ 0) |

如果任一 gate 不达, Round 不 closed。

### 1.3 AGENTS.md §10 新章节

新增 `## 10. Round Workflow Playbook` 子节, 写 7 步 + 3 gate。

---

## 2. 不在本 ADR 范围

- ❌ 改 AGENTS.md 其他章节
- ❌ 限制 Round 数量 (用户随时触发)
- ❌ 自动 commit (人工 review 必须)

---

## 3. 关联

- [ADR-0146](./0146-8stage-stability-declaration.md) (M4 元模型稳定)
- [ADR-0140](./0140-m4-health-score.md) (质量分数 source)
- [ADR-0147](./0147-mcptool-adder-guide.md) (单 deliverable 模板)
- [AGENTS.md](../../../AGENTS.md) (本 ADR 实施目标)

---

## 4. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (R5c, 7-step round-trip playbook 沉淀入 AGENTS.md §10) |
