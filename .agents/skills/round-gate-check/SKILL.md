---
title: Round Gate Check
type: skill
owner: governance-team
version: "1.0"
status: active
triggers:
  - round start
  - PR creation
  - architecture change
---

# round-gate-check — Round 三门槛守门

> 将 AGENTS.md §10.2 P72/P52/P74 三门槛转为可执行 skill

## 三个门槛

### P72 — 路径不过载

检查: 单 PR 修改路径数 <= 10，单文件修改 <= 200 行。

### P52 — 不动元模型/引擎

检查: 不修改 `projects/ecos/src/ecos/ssot/mof/` 下的元模型定义。

### P74 — Governance 自闭环

检查: `p74_solidification.warn_count == 0`。

```bash
make agent-workflow-compliance
```

## 执行

```bash
# 运行三门槛检查
python3 bin/gac/round-gate-check.py --pr <pr-number>
```

输出: PASS / FAIL (含具体失败项)

## 相关

- AGENTS.md §7 — Historical Patterns
- `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`
- `bin/agent-workflow.py compliance` — P74 检查
