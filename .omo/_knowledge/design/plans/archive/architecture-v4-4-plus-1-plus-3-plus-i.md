---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# 4+1+3+I 架构修订方案 v4

> 基于红队分析 | 2026-05-28 | 最终版

---

## 一、修订总览

### 接受: I0 — 集成织物层

```
P0 ─── 产品界面层
I0 ─── 集成织物层  ← 新增
L4 ─── 自我层
L3 ─── 协作层
L2 ─── 能力层
L1 ─── 契约层
X1 ─── 治理
X2 ─── 抗熵
X3 ─── 价值堆栈
```

### I0 包含项目（经红队审查）

```
I0 正式成员:
  Agora (27 MCP tools)  ← 从 X1 移入
  hermes-ops (21 tools) ← 从横切面正规化，标记 I0b(运维子层)

I0 协议:
  MCP (13/14 项目采纳)
  pipeline:json v1.1

拒绝移入:
  Iris → 留 L2 (独立能力层，非仅集成)
  PipelineTracer → 留 L3 (协作追踪，非集成)
```

### 红队 6 项修订完成

| # | 修订 | 状态 |
|:--:|------|:----:|
| 1 | I0 正式定义 | ✅ |
| 2 | Forge sync-agora.sh → agora/adapters/ | ✅ |
| 3 | KOS→hermes-ops HTTP → MCP | ✅ |
| 4 | Agora→hermes-ops → 事件总线 | ✅ |
| 5 | MCP → I0 协议 | ✅ |
| 6 | hermes-ops 层标识 I0b | ✅ |

---

## 二、完整项目→层映射

```
P0 — 产品界面 (4)
  hermes-webui :8787 │ pallas CLI │ gstack 53 orch │ agent-panel

I0 — 集成织物 (3)
  Agora :7430 (27 MCP)   ← 服务路由
  hermes-ops  (21 MCP)   ← 运维 (I0b 运维子层)
  MCP 协议                ← 集成标准

L4 — 自我层 (2)
  KOS self  (26 MCP)     ← 角色/愿景/认知框架
  metacog                 ← 认知理论基座

L3 — 协作层 (3)
  KOS collab (26 MCP)    ← TaskObject CRUD
  phase-lock              ← 相位锁定 EG5
  PipelineTracer          ← 执行追踪

L2 — 能力层 (11)
  agentmesh (22 MCP)     ← Agent 运行时
  ontoderive (5 MCP)     ← 事实推导
  minerva (~10 MCP)      ← 研究
  sophia                  ← 符号编译
  Forge (166 tools)       ← 工具图谱
  gbrain (74 MCP)        ← 持久记忆
  kronos                  ← ETL 摄取
  Iris (7 MCP)            ← 连接器
  MetaOS                  ← 系统编排
  codeanalyze             ← 代码分析
  DigitalBrainOS          ← Agent schema

L1 — 契约层 (2)
  eidos (5 MCP)          ← 元模型 Schema
  SSOT (5 MCP)           ← 配置一致性

X1 — 治理
  arcnode (21 验证脚本)   ← 约束执行
  SECRETS                 ← 密钥管理

X2 — 抗熵
  x2-freshness-cron       ← 知识保鲜
  x2-retrospect           ← 复盘
  x2-healt-report         ← 健康报告

X3 — 价值堆栈
  KOS consensus           ← 三级共识
  provenance_chain        ← 引用追溯
  trace_consensus()       ← 追溯 MCP 工具
```

---

## 三、架构宪法更新

```
原: 4+1+3 架构
      8 层: P0 L4 L3 L2 L1 X1 X2 X3
      
新: 4+1+3+I 架构 
      9 层: P0 I0 L4 L3 L2 L1 X1 X2 X3

宪法 §架构.A 更新:
  新增 I0 集成织物层定义
  I0 协议: MCP (强制), pipeline:json (推荐)
  I0 成员: Agora, hermes-ops
  I0 不允许: 承载业务逻辑 (纯路由/调度/运维)

层间引用规则更新:
  I0 可被所有层引用 ← 这是唯一跨层引用例外
  非 I0 层之间禁止直接引用 ← 保持不变
```

---

## 四、执行方案（Phase I — 集成织物）

### Wave 1 (I0 正式化, ~2h)

```
I1.1 AGENTS.md 更新: I0 层定义 + 项目归属修正   [30min]
I1.2 Forge sync 迁移: → agora/adapters/           [30min]
I1.3 KOS→hermes-ops: HTTP → MCP 事件              [1h]
```

### Wave 2 (Agora→hermes-ops 总线, ~2h)

```
I2.1 Agora 事件总线适配: 订阅 → events 转发        [1h]
I2.2 I0 验证脚本: arcnode 约束 I0-1 ~ I0-3         [1h]
```

### Wave 3 (文档全量更新, ~1h)

```
I3.1 架构图更新: 加入 I0 层                          [30min]
I3.2 .omo/standards/ 补充 I0 定义                    [15min]
I3.3 AGENTS.md 红队建议条目                         [15min]
```

---

## 五、最终评分预测

```
           v3.1 (当前)    v4 (I0修订后)    变化
架构设计     9.0            9.5            +0.5
代码规范     8.5            9.0            +0.5
测试质量     8.5            9.0            +0.5
运维成熟度   8.5            9.5            +1.0
文档一致性   9.0            9.5            +0.5
安全         9.0            9.5            +0.5
工具链       9.0            9.5            +0.5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
综合         8.9            9.4            +0.5
```

要开始执行 Phase I 吗？
