---
category: guides
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# 纯架构视角的包归属分析 (不受现状约束)

> 2026-06-07 | 基于 5+3+1 架构
> 问题: "从架构上，而非现状考虑，哪些应该被拆或者迁移？"

---

## 一、每包架构归属 vs 当前归属

| 包 | 当前归属 | 架构归属 | 结论 | 主要原因 |
|----|---------|---------|------|---------|
| **agora** | kairon L2 | **I0** | ❌ 应在 I0 | MCP 服务发现/路由/代理 — 是总线, 不是 L2 的一部分 |
| **cron-service** | kairon L2 | **L1 runtime** | ❌ 应在 L1 | 定时调度 — 是基础设施, 不是知识处理 |
| **agent-runtime** | kairon L2 | **L1 runtime + L3** | ❌ 位置错误 | 核心执行引擎 — 是 L1 基础设施; CLI — L3 入口 |
| **metaos** | kairon L2 | **L2 independent** | ❌ 应独立 | 编排引擎 — 7.8K行, 免疫/门控/层管理 — 不是知识处理功能 |
| **wksp** | kairon L2 | **L3 cockpit** | ❌ 错层 | 用户 CLI — 是入口, 不是知识处理 |
| **kairon-governance** | kairon L2 | **L2 omo** | ❌ 重复 | kairon 内治理 — 与 omo 范围重叠 |
| **ecos** | kairon L2 | **L0 protocol** | ❌ 错位 | SSB 协议 + 涌现计算 — 是 L0 协议编织层功能 |
| **engine-core** | kairon L2 | **L1 + L2 split** | ⚠️ 应拆 | 事件总线→L1, 任务存储→L2, 合着放在一起违反了分层 |
| **eidos** | kairon L2 | **L0 + L2 split** | ⚠️ 应拆 | Schema 类型→L0, 验证引擎→L2, 35K合着也违反了分层 |
| **shared-lib** | kairon L2 | **L0 foundation** | ⚠️ 层模糊 | 工具库被 4 包引用 — 作为基础层，应该可以被任何层使用, 但当前锁在 kairon 内 |
| kos | kairon L2 | **L2** | ✅ 正确 | 知识存储/搜索 |
| minerva | kairon L2 | **L2** | ✅ 正确 | 深度研究 |
| ontoderive | kairon L2 | **L2** | ✅ 正确 | 事实推导 |
| sophia | kairon L2 | **L2** | ✅ 正确 | 范式编译 |
| kronos | kairon L2 | **L2** | ✅ 正确 | 摄取 |
| iris | kairon L2 | **L2** | ✅ 正确 | 连接器 |
| codeanalyze | kairon L2 | **L2** | ✅ 正确 | 代码分析 |
| forge | kairon L2 | **L2** | ✅ 正确 | 工具注册 |
| gbrain | standalone | **L2 memory** | ✅ 正确 | 知识数据库 (TS) |
| omo | root repo | **L2 governance** | ✅ 正确 | 治理 CLI |
| runtime | standalone | **L1** | ✅ 正确 | 运行时基础设施 |

---

## 二、结论: 7 包放错位置

```
按架构归属分组:

L0 应该拥有:        eidos(类型部分), ecos(SSB协议), shared-lib(基础工具)
I0 应该拥有:        agora
L1 应该拥有:        cron-service, agent-runtime(核心), engine-core(事件总线部分)
L2 知识引擎应拥有:  eidos(验证部分), kos, minerva, ontoderive, sophia, kronos, iris, codeanalyze, forge
L2 编排引擎应拥有:  metaos
L2 治理面应拥有:    omo, kairon-governance(合并)
L2 记忆面应拥有:    gbrain
L3 入口层应拥有:    wksp
```

## 三、如何做 (不受现状约束的理想方案)

```
Step 1: agora 独立
  kairon/agora → projects/agora
  代价: 修改 5 包接口 (import→MCP 调用)

Step 2: metaos 独立  
  kairon/metaos → projects/metaos
  代价: 0 (自包含)

Step 3: L1 堆栈重新分配
  kairon/cron-service → runtime/scheduler/
  kairon/agent-runtime/core → runtime/executor/  (CLI 部分去 cockpit)
  kairon/engine-core/事件系统 → runtime/events/
  代价: 中 (需要更新 k8n 所有引用)

Step 4: ecos 独立
  kairon/ecos → projects/ecos (SSB 协议 + 涌现)
  代价: 0 (自包含)
  
Step 5: kairon-governance 功能合并
  omo 吸收 kairon-governance (ADR/审计/路由)
  代价: 中 (两个代码基的功能对齐)

Step 6: wksp 迁移
  kairon/wksp → cockpit/cli
  代价: 只依赖 agora

Step 7: shared-lib 解耦
  shared-lib → projects/shared (基础工具, 所有项目可用)
  代价: 高 (需更新 4 包引用)
```

## 四、对比: 应该移 vs 可以移

| 包 | 应该移 | 可以移 | 原因 |
|----|--------|--------|------|
| agora | ✅ | ✅ | 架构错误+自包含(被1包引) |
| metaos | ✅ | ✅ | 架构+自包含 |
| cron-service | ✅ | ✅ | 架构+L1归类 |
| ecos | ✅ | ✅ | 架构+自包含 |
| wksp | ✅ | ✅ | 架构+低依赖 |
| agent-runtime | ✅ | ⚠️ | 需要拆分(核心 vs CLI) |
| kairon-governance | ✅ | ⚠️ | 需要功能合并 |
| engine-core | ⚠️(部分) | ❌ | 紧耦合于 k8n 内部逻辑 |
| eidos | ⚠️(部分) | ❌ | 被 5 包引用 |
| shared-lib | ⚠️(解耦) | ❌ | 被 4 包引用 |

**结论**: 7 种包放错地方，其中 5 个可以解决，2 个(engine-core/eidos)难以独自动。
