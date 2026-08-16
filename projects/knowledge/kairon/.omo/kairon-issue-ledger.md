---
title: kairon-issue-ledger
type: doc
status: active
---

# kairon 问题台账 · 5+3+1 架构对齐计划

> 2026-06-06 | 基于全面分析 · 按优先级排序 · 含状态追踪

---

## 一、已完成 ✅

| ID | 类别 | 问题 | 解决方案 | 完成 |
|----|------|------|---------|------|
| DONE-1 | 耦合 | shared-lib 38K 15 子域聚合 | 拆出 5 独立包 (events/utils/plugin-sdk/observability/pipeline) | 2026-06-06 |
| DONE-2 | 迁移 | ecos 在 kairon 内 → L0 | 拆出 `projects/ecos/` | P31-W0 |
| DONE-3 | 迁移 | metaos 在 kairon 内 → L2 | 拆出 `projects/metaos/` | P30-W1 |
| DONE-4 | 迁移 | wksp 在 kairon 内 → L3 | 拆出 `projects/cockpit/` | P30-W1 |
| DONE-5 | 归档 | kairon-assistant/kairon-voice | 归档至 `_archived/` | P28-W2 |
| DONE-6 | 归档 | kaironcloud-billing | 归档至 `_archived/` | P28-W6 |
| DONE-7 | 清理 | local_reflex_test.py 在 src/ 内 | 删除 | 2026-06-06 |
| DONE-8 | 文档 | 新 5 包 + shared-lib README | 创建 | 2026-06-06 |
| DONE-9 | 文档 | CLAUDE.md + AGENTS.md 包数 | 20→30 更新 | 2026-06-06 |
| DONE-10 | 文档 | LAYER-INDEX.md 完全重写 | 对齐 5+3+1 当前状态 | 2026-06-06 |
| DONE-11 | 文档 | architecture-complete-plan.md 行数 | 更新 shared-lib 行数 | 2026-06-06 |
| DONE-12 | 配置 | `[tool.uv.sources]` 幽灵引用清理 | 验证无幽灵引用存在 | 2026-06-06 |

---

## 二、P1 待执行 🔴 (按优先级排序)

| ID | 类别 | 问题 | 影响范围 | 方案 | 预计时间 |
|----|------|------|---------|------|---------|
| P1-1 | 架构 | agora 仍在 kairon 内 → 应独立为 I0 项目 | 5 包 (eidos, kos, minerva, iris, engine-core 需改接口) | 搬家至 `projects/agora/`，内部依赖改为 MCP 调用 | 3-4d |
| P1-2 | 架构 | cron-service 应归属 L1 runtime | 自包含包 (1.8K)，cost 低 | 搬家至 `projects/runtime/scheduler/` | 1d |
| P1-3 | 架构 | agent-runtime 功能混合 → L1+L3 | 涉及 cron 任务、CLI | 核心执行→L1 runtime，CLI→L3 cockpit | 2-3d |
| P1-4 | 入口 | cockpit 统一入口未完工 | wksp CLI 已移入但功能未集成 | 完成 CLI + Web 面板集成 | 1-2d |

## 三、P2 待执行 🟡

| ID | 类别 | 问题 | 方案 | 预计时间 |
|----|------|------|------|---------|
| P2-1 | 代码 | shared-lib 126 facade 文件历史包袱 | 逐步废弃，标记 DeprecationWarning | 1d |
| P2-2 | 架构 | kairon-governance → omo 合并 | 治理功能对齐，2.5K 代码 | 1d |
| P2-3 | 架构 | engine-core L1+L2 混合 | 事件总线→L1，存储→L2 | 待评估 |
| P2-4 | 架构 | eidos L0+L2 混合 | 类型定义→L0，验证逻辑→L2 | 待评估 |

## 四、P3 横向切面 🟢

| ID | 类别 | 问题 | 方案 | 预计时间 |
|----|------|------|------|---------|
| P3-1 | X1 审计 | KEI 告警回路待建 | 审计→告警→修复→验证闭环 | 按需 |
| P3-2 | X2 抗熵 | 保鲜机制部分实现 | 自动校验→审计→周报 | 按需 |
| P3-3 | X3 价值栈 | LLM 成本无汇总 | Token 统计+服务计量+成本归因 | 按需 |

## 五、最终目标

```
当前: 5 项目 → 目标: 9 项目
=====================================
agora/     I0 · MCP Hub (从 kairon)  [待做]
kairon/    L2 · 知识引擎 (14 核心包)  [✅]
gbrain/    L2 · 记忆面 (163K TS)     [✅]
omo/       L2 · 治理面 (15K)         [✅]
metaos/    L2 · 编排引擎 (7.8K)      [✅]
ecos/      L0 · SSB 协议 (6.3K)      [✅]
runtime/   L1 · 运行时 (3.7K + cron + agent) [待扩张]
cockpit/   L3 · 统一入口 (CLI + Web)  [待完成]
protocols/ L0 · 协议 YAML             [✅]
```

### 完成度

- **项目维度**: 5/9 项目就绪 (56%)
- **kairon 内部**: shared-lib 拆解完成, 剩余 I0/L1 包待拆
- **横向切面**: X1-X3 基础框架存在, 闭环待完善
- **代码总量**: ~460K 行, 0 新增代码计划

---

*最后更新: 2026-06-06 |
*来源: architecture-complete-plan.md + 实际包状态分析
