---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
superseded-by: architecture-remediation-plan-v2.md
note: "P53 R2: 历史整改 v1, 已被 v2 替代。当前架构健康/债务以 .omo/state/system.yaml + .omo/debt/ 为准"
---

# omostation 架构审计整改方案 v1

> 日期: 2026-06-03 | 基于审计报告缺口分析
> 方法: 按优先级(P0/P1/P2)分批次执行，每批独立验证
> 本文档保留历史整改提案、当时的问题分级与批次设计，不是当前项目状态、测试通过率、健康分或执行计划 SSOT。
> 当前项目身份/状态/入口收敛以 `/.omo/PROJECTS.yaml`、`AGENTS.md`、`docs/PANORAMA.md` 为准；当前目标与执行许可以 `/.omo/goals/current.yaml`、`/.omo/tasks/active/` 为准。

---

## 问题概览

| # | 问题 | 优先级 | 当前状态 | 目标状态 | 预估工作量 |
|---|------|:------:|:--------:|:--------:|:---------:|
| 1 | Hermes Console 骨架未有实际功能 | P0 | 296行骨架 | 可用的知识仪表盘+Agent控制台 | 1-2周 |
| 2 | agentmesh TS源码未归档 | P0 | 476文件原位 | 归档到_archived/agentmesh/ | 0.5天 |
| 3 | 测试通过率68% | P0 | 709/1038通过 | 85%+ (882+) | 3-5天 |
| 4 | shared-lib 143模块太胖 | P1 | 1个巨包 | 拆分为3-4个子包 | 2-3天 |
| 5 | sharedbrain-bridge闲置 | P1 | 桥接未激活 | 可用的神经元↔kairon桥接 | 1-2天 |
| 6 | SharedBrain遗留代码 | P1 | 旧nucleus/conductor代码 | 清理到_archived/ | 0.5天 |
| 7 | gbrain→kairon集成未验证 | P1 | 未测试 | E2E通路测试通过 | 1天 |
| 8 | 健康分75.2→97.0 | P2 | 2债务已解决 | 7债务resolved | 持续 |
| 9 | sharedbrain-standalone运营验证 | P2 | 代码存在未验证 | 能启动服务并响应请求 | 1天 |

---

## P0批次: 立即执行

### 批次1: agentmesh TS归档

**问题:** 476个TS文件(~60MB)仍占用agentmesh项目位置，Python迁移已完成但TS源未归档。

**步骤:**
1. `mkdir -p projects/_archived/agentmesh/`
2. `mv projects/agentmesh/* projects/_archived/agentmesh/`
3. 更新kairon AGENTS.md指向不再需要agentmesh
4. 验证kairon不依赖agentmesh路径
5. 更新 .omo/state/system.yaml 标记agentmesh状态

**验收:** `ls projects/agentmesh` 返回空(或只有README指向_archived)

---

### 批次2: Hermes Console功能实现

**目标:** 从296行骨架升级到可用的MCP客户端界面。

**子任务:**

**2.1 MCP客户端层 (`src/mcp/`)**
- `client.ts` — MCP连接管理(连接池+重连+心跳)
- `tools.ts` — 工具发现+调用代理
- `stream.ts` — SSE流处理
- `types.ts` — 共享类型定义

**2.2 知识仪表盘 (`src/dashboard/`)**
- `KnowledgeGraph.tsx` — D3/Cytoscape知识图谱可视化
- `SearchPanel.tsx` — 搜索+结果展示
- `StatsCards.tsx` — 统计数据卡片

**2.3 Agent控制台 (`src/agent/`)**
- `AgentList.tsx` — Agent列表+状态
- `ChatInterface.tsx` — 对话界面
- `TaskMonitor.tsx` — 任务监控

**2.4 健康监控 (`src/health/`)**
- `ServiceTopology.tsx` — 服务拓扑图
- `MetricsCharts.tsx` — 指标图表
- `AlertPanel.tsx` — 告警面板

**2.5 设置面板 (`src/settings/`)**
- `MCPConfig.tsx` — MCP配置
- `ProfileSettings.tsx` — 个人设置
- `SystemInfo.tsx` — 系统信息

**2.6 集成 (`src/App.tsx`)**
- 串联所有面板
- 连接状态管理
- 整体样式和UX

**验收:** `bun run dev` 可启动，4个Tab均能展示内容。

---

### 批次3: 测试修复

**目标:** 通过率从68%提升到85%+。

**策略:**
1. 识别"假阴性"测试(网络依赖/外部依赖) → 加skip标记
2. 修复"真阴性"测试(代码逻辑错误) → 修复代码
3. 新增关键包(core-models, agent-runtime core)的测试覆盖

**目标包:** agora(15失败)、ecos(设置错误)、agent-runtime(5失败)

**验收:** `make test-fast` 失败数≤25，通过率≥85%。

---

## P1批次: 短期执行

### 批次4: shared-lib包拆分

**现状:** shared-lib/src/kairon_lib/ 下143个模块，单一包。

**拆分方案:**
```
kairon_lib/ → 保留为轻量壳子(仅re-exports)
  ├── governance/    ← 治理相关 (governance_engine, policy_registry, rbac, voting...)
  ├── security/      ← 安全相关 (security, threat, audit, quarantine...)
  ├── agent/         ← Agent工具 (patterns, conversation, reasoning, consensus...)
  ├── knowledge/     ← 知识工具 (knowledge_graph, rag_engine, memory_store...)
  ├── infra/         ← 基础设施 (middleware, events, error_system...)
  └── toolkit/       ← agentmesh toolkit (architecture, errors, context, core...)
```

**步骤:**
1. 创建子包目录结构
2. 按模块domain移动文件
3. `__init__.py` re-export保持向后兼容
4. 更新所有import路径
5. 编译+测试验证

**验收:** 子包模块可独立import，`from kairon_lib import X` 仍然可用。

---

### 批次5: sharedbrain-bridge激活

**现状:** bridge包(3文件, 壳子)未实际连接SharedBrain和kairon。

**步骤:**
1. 使用sharedbrain-standalone的HTTP API注册kairon服务
2. bridge + NeuralCenter实现服务发现
3. 实现健康检查回路
4. E2E测试: bridge→standalone→NeuralCenter通路

**验收:** bridge可主动查询SharedBrain状态，健康检查<5s。

---

### 批次6: SharedBrain遗留代码清理

**步骤:**
1. `mv nucleus/Z-Microkernel → _archived/nucleus/Z-Microkernel`
2. `mv conductor/ → _archived/conductor/` (如果不在使用)
3. 清理organs/目录下残留的D-Execution symlink
4. 更新README确认当前角色

**验收:** nucleus下无活跃业务代码，所有旧实现可追溯到_archived。

---

### 批次7: gbrain→kairon集成验证

**步骤:**
1. 确认gbrain MCP Server运行正常
2. 从kairon发起MCP调用(gbrain工具)
3. E2E测试: kairon知识查询 → gbrain 存储/检索
4. 记录延迟和可用性

**验收:** kairon→gbrain MCP通路延迟<500ms，数据正确。

---

## P2批次: 中期

### 批次8-9: 健康分提升 + standalone运营验证

**步骤:**
1. 持续解决债务项 (7项 unresolved → resolved)
2. sharedbrain-standalone启动测试: `uv run sharedbrain-standalone`
3. 验证HTTP端点(health, circuit, neural)响应正常
4. 更新system.yaml健康分

**验收:** 健康分≥90.0，standalone服务端口响应正常。

---

## 执行优先级矩阵

```
高影响/低成本 (先做):
  ├── agentmesh TS归档 (0.5天, P0)
  ├── SharedBrain legacy清理 (0.5天, P1)
  └── gbrain集成验证 (1天, P1)

高影响/中成本 (重点):
  ├── 测试修复 (3-5天, P0)
  ├── shared-lib拆分 (2-3天, P1)
  └── sharedbrain-bridge激活 (1-2天, P1)

高影响/高成本 (分批):
  └── Hermes Console功能实现 (1-2周, P0) ← 分解为6子任务分批次

低影响/低成本 (有空做):
  └── 健康分提升 + standalone验证 (2天, P2)
```

---

## 交叉审阅检查表

- [ ] 方案是否覆盖审计报告中的所有关键差距?(P0/P1/P2全部覆盖)
- [ ] 每项任务是否有明确的验收标准?(有，见每项)
- [ ] 工作量估算是否合理?(老实话: Hermes可能被低估)
- [ ] 执行顺序是否有依赖冲突?(Hermes独立，可并行)
- [ ] shared-lib拆分是否有向后兼容保证?(__init__ re-export)
- [ ] agentmesh TS归档是否可回退?(mv而非rm)
- [ ] 测试修复策略是否避免"刷通过率"? (区分真/假阴性)
