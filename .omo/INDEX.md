## 当前运行时状态
> 运行时状态不要在此页硬编码。
> 当前 phase / health / code_freeze / milestones 一律以 [state/system.yaml](state/system.yaml)、
> [goals/current.yaml](goals/current.yaml) 与对应 delivery/audit 证据为准。

---

# `.omo/` — OMO 治理状态面

> `.omo/` 不是治理执行内核，而是治理状态承载面。
> 权威边界定义见 [standards/omo-governance-surfaces.md](standards/omo-governance-surfaces.md)。

## 治理联动

`.omo/` 只是状态承载面，不是完整治理系统。

当前治理以三层联动为准：

| 层 | 位置 | 说明 |
|---|---|---|
| 状态面 | `.omo/` | 真相、控制、知识、交付、任务与证据 |
| 内核面 | `projects/omo/` | schema、governance、sync、overlay、promotion |
| 入口面 | `projects/c2g/` | Pitch / OpenSpec / Fast-Track 到 Planned Tasks |

权威标准与注册表：

- [standards/omo-governance-surfaces.md](standards/omo-governance-surfaces.md)
- [_truth/registry/omo-governance-surfaces.yaml](_truth/registry/omo-governance-surfaces.yaml)

---

## 当前状态入口

| 指标 | 权威读源 |
|------|----------|
| Phase / Wave / Health | [state/system.yaml](state/system.yaml) |
| Goals / code freeze / milestone | [goals/current.yaml](goals/current.yaml) |
| Active / Planned / Done Tasks | [tasks/](tasks/) |
| 审计证据 | [_delivery/](_delivery/) |
| 复盘与说明 | [_knowledge/](_knowledge/) |

---

## 状态面导航

| 平面 | 入口 | 回答的问题 |
|------|------|-----------|
| **控制面** | [_control/INDEX.md](_control/INDEX.md) | 我现在在哪？下一步做什么？ |
| **事实面** | [_truth/INDEX.md](_truth/INDEX.md) | 什么是真的？权威信息在哪？ |
| **知识面** | [_knowledge/INDEX.md](_knowledge/INDEX.md) | 我们知道了什么？ |
| **交付面** | [_delivery/INDEX.md](_delivery/INDEX.md) | 我们交付了什么？ |

---

## 快速入口

| 目标 | 位置 |
|------|------|
| 当前任务 | [tasks/active/](tasks/active/) |
| 当前目标 | [goals/current.yaml](goals/current.yaml) |
| 系统状态 | [state/system.yaml](state/system.yaml) |
| 债务仪表盘 | [debt/dashboard/current.yaml](debt/dashboard/current.yaml) |
| 质量标准 | [standards/](standards/) |
| 计划注册表 | [_knowledge/design/plans/README.md](_knowledge/design/plans/README.md) |
| 历史复盘 | [_knowledge/summaries/README.md](_knowledge/summaries/README.md) |
| 历史任务 | [tasks/done/](tasks/done/) |
| 架构基线 | [_knowledge/design/system-design-baseline.md](_knowledge/design/system-design-baseline.md) |
| 治理历史 (JSONL) | [_knowledge/governance-history.jsonl](_knowledge/governance-history.jsonl) |
| AppendOnlyLog 模式 | [_knowledge/management/append-only-log-pattern-2026-06-09.md](_knowledge/management/append-only-log-pattern-2026-06-09.md) |

---

## 核心规范与 SSOT

- [standards/omo-governance-surfaces.md](standards/omo-governance-surfaces.md) — `.omo` / `projects/omo` / `projects/c2g` 三层治理契约
- [_truth/registry/omo-governance-surfaces.yaml](_truth/registry/omo-governance-surfaces.yaml) — 机器可读治理面注册表
- [_truth/x1-governance-policies.yaml](_truth/x1-governance-policies.yaml) — X1 边界 / 写入 / 审计策略
- [_truth/x2-freshness-rules.yaml](_truth/x2-freshness-rules.yaml) — X2 保鲜规则
- [_truth/x3-value-stack.yaml](_truth/x3-value-stack.yaml) — X3 价值与成本归因
- [_truth/x4-consistency-rules.yaml](_truth/x4-consistency-rules.yaml) — X4 一致性规则

- [_archive/legacy-root-docs/DOC-ARCH.md](_archive/legacy-root-docs/DOC-ARCH.md) — 四平面文档架构定义
- [AGENT.md](_knowledge/usage/AGENT.md) — Agent 行为规范

---

## 治理历史

每次 governance audit 跑完会 append 一条到 `_knowledge/governance-history.jsonl`。

查看最近 30 天分数：

```bash
omo governance
```

记录格式：`{date, timestamp, total_score, grade, checks[], watchlist_count}`

---

*维护: 2026-06-19 · 此页只保留导航与指针，不再复制运行时事实*
