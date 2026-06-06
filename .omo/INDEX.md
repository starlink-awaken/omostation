## 当前 Phase: 31 预备 (废弃债务清零) — 🚀 进行中

- **本次操作**: Phase 31 债务修复第一/二波
- **已解决债务**: BYPASS-003/004/005 (ShareBrain 直连), I0-AGORA_SSE_DEAD, I0-AGORA_DUAL_INSTANCE
- **健康分**: ~67+ (估算，修复后待 audit 确认)
- **agora 状态**: native :7430 运行正常 (PID 20658)，无 Docker 双实例冲突
- **omo daemon**: launchd 跑着
- **下一步**: P0-AGENTRT_CRITICAL 修复 + C1-HERMES_BUILD_BROKEN 修复

---

# `.omo/` — OMO 治理内核

> 个人 AI 操作系统 (Personal AI Operating System) 的治理层。
> 四平面架构：控制面 · 事实面 · 知识面 · 交付面
>
> 参考: [DOC-ARCH.md](DOC-ARCH.md)

---

## 当前状态

| 指标 | SSOT | 值 |
|------|------|-----|
| **Phase** | [state/system.yaml](state/system.yaml) | **Phase 30** — eCOS 物理拆分 + 治理整合（✅ 收官） |
| **Wave** | [state/system.yaml](state/system.yaml) | **W2** — 全 6 项目 E2E 验证 + 健康分收尾 |
| **Health** | [state/system.yaml](state/system.yaml) | **57.2 / 100** (F, omo audit-final 2026-06-06) |
| **Active tasks** | [tasks/active/](tasks/active/) | **0** (P30-W2-VERIFY 收官) |
| **Goals** | [_truth/goals/current.yaml](_truth/goals/current.yaml) | Phase 30 收官 → Phase 31 可观测性 + agora 物理独立评估 |

---

## 四平面导航

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
| 当前目标 | [_truth/goals/current.yaml](_truth/goals/current.yaml) |
| 系统状态 | [state/system.yaml](state/system.yaml) |
| 债务仪表盘 | [_control/debt-dashboard/current.yaml](_control/debt-dashboard/current.yaml) |
| 质量标准 | [standards/](standards/) |
| 计划注册表 | [_knowledge/design/plans/README.md](_knowledge/design/plans/README.md) |
| **Phase 15 治理闭环计划** | [_knowledge/design/plans/phase15-autonomous-governance-preplanning.md](_knowledge/design/plans/phase15-autonomous-governance-preplanning.md) |
| **Phase 16 产品入口收敛计划** | [_knowledge/design/plans/phase16-product-surface-convergence-preplanning.md](_knowledge/design/plans/phase16-product-surface-convergence-preplanning.md) |
| **OMO Fusion 蓝图** | [_knowledge/design/plans/omo-fusion-optimization-blueprint.md](_knowledge/design/plans/omo-fusion-optimization-blueprint.md) |
| **Phase 17-27 多Phase执行计划** | [_knowledge/design/plans/gentle-toasting-mango.md](_knowledge/design/plans/gentle-toasting-mango.md) |
| **Phase 28 可观测知识工作流** | [_knowledge/design/plans/phase28-observable-knowledge-workflow.md](_knowledge/design/plans/phase28-observable-knowledge-workflow.md) |
| **Phase 29 工具体系韧性** | [_knowledge/management/plan-phase29-toolchain.md](_knowledge/management/plan-phase29-toolchain.md) |
| 历史复盘 | [_knowledge/summaries/README.md](_knowledge/summaries/README.md) |
| 历史任务 | [tasks/done/](tasks/done/) |
| **治理历史 (JSONL)** | [_knowledge/governance-history.jsonl](_knowledge/governance-history.jsonl) |
| 架构基线 | [_knowledge/design/system-design-baseline.md](_knowledge/design/system-design-baseline.md) |

---

## 核心规范

- [_archive/legacy-root-docs/DOC-ARCH.md](_archive/legacy-root-docs/DOC-ARCH.md) — 四平面文档架构定义
- [AGENT.md](_knowledge/usage/AGENT.md) — Agent 行为规范

---

## 治理历史

每次 `kairon-governance audit` 跑完会 append 一条到 `_knowledge/governance-history.jsonl` (P29-W2 / ADR-0005 阶段 2)。

查看最近 30 天分数：

```bash
kairon-governance history --limit 30
```

查看 ASCII 趋势图：

```bash
kairon-governance history --trend
```

记录格式：`{date, timestamp, total_score, grade, checks[], watchlist_count}`

---

## 当前 Phase 蓝图参考

- [_knowledge/design/plans/omo-fusion-optimization-blueprint.md](_knowledge/design/plans/omo-fusion-optimization-blueprint.md) — 四平面融合升级战略蓝图
- [_knowledge/design/plans/gentle-toasting-mango.md](_knowledge/design/plans/gentle-toasting-mango.md) — Phase 17-27 多Phase执行计划（已完成）

---

*维护: 2026-06-06 · 状态以 state/system.yaml 为准*
