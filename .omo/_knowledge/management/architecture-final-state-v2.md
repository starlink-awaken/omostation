# eCOS 最终态架构 v2.0 (深度调查修正版)

> 2026-06-07 | 基于: 全量依赖分析 + 四个包深度解剖 + gbrain交互验证
> 修正: v1.0 误判 4 个包为废弃, 实际都有活跃功能
> 历史最终态修订提案 / reference only。本文记录当时的修正设计，不是当前项目数量、当前包边界、当前依赖真相或当前实施状态 SSOT。
> 当前架构与项目事实请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、`/.omo/standards/eCOS-v6-Architecture-Alignment.md`。

---

## 一、修正汇总

| v1.0 判断 | 实际发现 | v2.0 修正 |
|----------|---------|----------|
| sharedbrain-bridge 空壳可废弃 | 1,063行 + standalone server(267行) + bridge + 403行测试 | **保留**, 是实际运行的服务 |
| kairon-governance 与 omo 重叠 | 3,463行: ADR(559), 审计(579), 路由(304), 同步(619), 934行测试 | **保留**, 与 omo 并行, 范围不同 |
| metaos 归 omo | 7,812行: 引擎(515), 免疫(290), 层管理(1,528), 死锁(342), MCP(479), 1,611行测试 | **保留**, 是独立编排引擎 |
| ecos 归 kos | 6,288行: SSB协议(700), 涌现(408), 看板(365), 1,657行测试 | **保留**, SSB+涌现独立功能 |

仅 health-profile(0.2K) 可以安全吸收到 core-models。

---

## 二、最终项目布局 (7 项目, 非 5)

```
projects/
├── agora/              — I0 集成织层     (从 kairon 拆出, 38K→独立)
├── kairon/             — L2 知识引擎     (保留, 瘦身至 ~260K)
├── gbrain/             — L2 知识大脑     (保留, 163K TS)
├── omo/                — L2 治理 CLI     (保留, 从 root 移入 projects/)
├── runtime/            — L1 基础设施     (增厚, 3.7K→15K)
├── cockpit/            — L3 统一入口     (新建, wksp CLI + hermes 重启)
└── metaos/             — L2 编排引擎     (保留, 从 kairon 移出到独立项目)
```

---

## 三、逐项目详解

### 1. I0 — agora (独立项目)

```
当前:     kairon/packages/agora (38K)
去向:     projects/agora/ (独立)

拆出理由:
  - 架构上属于 I0, 不应在 kairon L2 内
  - 是所有跨层通信的唯一总线
  
拆出后变化:
  - agora 不能再 import kairon 包 (eidos/kos/minerva/core-models)
  - 全部通过 MCP 协议调用
  - 精简: 移除 dashboard(归 cockpit), 移除 A2A(保留在 metaos或 kairon)
  
预估: 38K→15K (精简掉非 I0 功能)
```

### 2. L2 — kairon (保留, 瘦身)

```
当前:     300K 行 (24 包)
瘦身后:   260K 行 (20 包)

移出:
  agora (38K)           → projects/agora
  agent-runtime 核心     → runtime/executor (保留 CLI 在 kairon)
  
kairon内调整:
  shared-lib        保持, 逐步标记功能边界 → 后续拆解
  core-models       保持
  eidos             保持
  ssot              保持
  kos               保持
  minerva           保持
  ontoderive        保持
  sophia            保持
  kronos            保持
  iris              保持
  codeanalyze       保持
  forge             保持
  symphony-protocol 保持
  kairon-governance 保持 (kairon 内部治理)
  sharedbrain-bridge 保持 (standalone server)
  wksp              CLI 部分迁到 cockpit
  
  不再移动的:
  cron-service       在 kairon (是 kairon 的定时任务, 不是通用 runtime)
  llm-gateway        在 kairon (是 kairon 的 LLM 抽象, runtime 通过它调用)
  
  废弃:
  health-profile     → 吸收到 core-models
```

### 3. L2 — gbrain (保留, 不动)

```
当前:     163K TS, 67 MCP tools
角色:     系统知识数据库 (存储/搜索/图谱/事实/任务)
交互:     通过 Agora MCP, 已运行验证
状态:     不移动, 不拆分, 不修改
```

### 4. L2 — omo (从 root 移到 projects/)

```
当前:     Workspace/root/projects/omo/ (在 root git 仓库内)
角色:     全局治理 CLI (goal/debt/state/standards/evidence/...)
去向:     projects/omo/ (独立 git 仓库)

理由:
  - 治理是第一公民, 应独立于任何特定项目
  - 在 root 仓库里不利于版本管理
  
与 kairon-governance 的关系:
  - omo: 全局治理 (跨项目)
  - kairon-governance: kairon 内部治理 (ADR/审计/路由)
  - 两者不合并, 保持并行
```

### 5. L1 — runtime (保留, 增厚)

```
当前:     3.7K (16 modules)
增厚后:   15K (吸收部分功能)

吸收:
  无 — 深度调查后发现不需要吸收
  
理由:
  - cron-service 是 kairon 的定时任务, 不是通用 runtime 功能
  - llm-gateway 是 kairon 的 LLM 抽象, runtime 通过它调用
  - agent-runtime 核心已在 runtime 启动时通过 MCP 调用

  runtime 本身的功能已完整:
    Matrix 注册表 ✅
    健康监控 ✅
    KEI 沙箱 ✅
    协议管理 ✅
    事件消费 ✅
    定时调度 ✅ (scheduler.py)
```

### 6. L3 — cockpit (新建)

```
新建     projects/cockpit/
从 wksp 迁出: CLI 核心 (~8K)
从 hermes-console: Web UI (>修复构建后)
角色:     统一用户/Agent 入口

结构:
  cockpit/
  ├── cli/           — Python CLI (wksp 核心)
  ├── web/           — TypeScript Vite (hermes-console 重启)
  └── mcp/           — MCP Server (runtime MCP 合并)
```

### 7. L2 — metaos (从 kairon 移出到独立项目)

```
当前:     kairon/packages/metaos (7.8K)
角色:     编排引擎: 决策门控、免疫监控、死锁检测、多层管理
去向:     projects/metaos/ (独立)

理由:
  - 7.8K 行是一个完整引擎, 不是 kairon 内部包
  - 核心实体 (引擎/免疫/门控/层管理) 让 kairon 功能膨胀
  - 独立后可以在其他项目复用编排功能

接口:
  - metaos MCP server (已有 479行)
  - 通过 Agora 注册
```

### 8. ecos (保留在 kairon)

```
保留理由:
  - SSB 协议实现 (700行) — ecos 的核心功能
  - 涌现计算 (408行) — 认知层
  - 与 kairon 内 kos/ssot 紧密集成
  
修正:    不合并到 kos。保留为独立包, 因 SSB 是独立协议
```

---

## 四、每包终态判定

| 包 | 行数 | v2.0 判定 | 动作 |
|----|------|----------|------|
| agenda | 38K | 拆出 | → projects/agora |
| shared-lib | 38K | 保留 | 边界标记, 后续拆 |
| eidos | 35K | 保留 | 不动 |
| minerva | 25K | 保留 | 不动 |
| engine-core | 25K | 保留 | 不动 |
| agent-runtime | 20K | 保留 | CLI 迁 cockpit, 核心留 kairon |
| wksp | 15K | 部分迁 | CLI→cockpit, storage留 kairon |
| ssot | 14K | 保留 | 不动 |
| kos | 14K | 保留 | 不动 |
| iris | 8K | 保留 | 不动 |
| metaos | 7.8K | 独立 | → projects/metaos |
| codeanalyze | 7K | 保留 | 不动 |
| ontoderive | 6K | 保留 | 不动 |
| ecos | 6.3K | 保留 | 不动 |
| kairon-governance | 3.5K | 保留 | 不动,与 omo 并行 |
| kronos | 2.9K | 保留 | 不动 |
| llm-gateway | 3K | 保留 | 不动 |
| cron-service | 1.8K | 保留 | 不动 |
| core-models | 1.6K | 保留 | 吸收 health-profile |
| sophia | 1.4K | 保留 | 不动 |
| sharedbrain-bridge | 1.1K | 保留 | 不动, standalone server |
| symphony-protocol | 1K | 保留 | 不动 |
| health-profile | 0.2K | 废弃 | → core-models |

---

## 五、实际的搬家清单 (从 5 条减到 3 条)

对比 v1.0 的长搬家清单，v2.0 精简为:

| 项目 | 动作 | 代码量 | 收益 |
|------|------|--------|------|
| agora → projects/agora | 拆出 | 38K | I0 归于原位 |
| metaos → projects/metaos | 移出 | 7.8K | 编排独立 |
| wksp CLI → cockpit | 部分迁 | 8K | 入口统一 |

不动的: shared-lib(边界标记), engine-core, sharedbrain-bridge(already works), ecos(独立协议)

---

## 六、新项目全景

```
projects/
├── agora/          ← 38K, I0 MCP Hub (拆出)
├── kairon/         ← ~260K, 知识工程 (20包)
├── gbrain/         ← 163K TS, 知识数据库
├── metaos/         ← 7.8K, 编排引擎 (移出)
├── omo/            ← 15K, 治理 CLI
├── runtime/        ← 3.7K, L1 基础设施
└── cockpit/        ← ~12K, 统一入口 (新建)

protocols/           ← L0 协议
.omo/               ← 治理数据
```

### 对比 v1.0

| 维度 | v1.0 | v2.0 (修正) |
|------|------|-----------|
| 废弃包 | 5 个 | 1 个 (health-profile) |
| 搬家项 | 11 条 | 3 条 |
| kairon 保留包 | 15 包 | 20 包 |
| 新增项目 | 3 个 | 3 个 (agora/metaos/cockpit) |
| 代价 | ~9 天 | ~5 天 |
| 最大变化 | shared-lib full 拆解 | shared-lib 边界标记(不拆) |
