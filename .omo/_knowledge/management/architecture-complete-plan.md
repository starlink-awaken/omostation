# eCOS Workspace 全量架构方案

> 2026-06-07 | 版本: Final Review
> 基于: 全量 import 依赖分析 · 深度包调查 · gbrain 交互验证 · 5+3+1 分层
> 审查本: 供人类审批后执行
> **2026-06-06 更新**: shared-lib 已拆出 5 子包 (events/utils/plugin-sdk/observability/pipeline) → kairon 30 包

---

## 一、当前基线

```
全系统: 467,839 行代码 · 5 个项目 · 24 kairon 包 · 2 种语言

项目分布:
  kairon/            299K  (24 包 Python, 知识工程+infra+入口+I0)
  gbrain/            163K  (TypeScript, Postgres 知识脑, 67 MCP 工具)
  omo/                15K  (Python, 治理 CLI)
  runtime/           3.7K  (Python, L1 基础设施)
  hermes-console/    1.4K  (TypeScript, Web面板, 构建失败)
```

### 核心问题

```
1. kairon 是 4 层的混合体 (L0/I0/L1/L2 混在一个 monorepo 里)
2. I0(agora) 在 kairon 内 → 跨层依赖变成项目内依赖
3. 7 个自包含包没有独立项目 → 缺乏独立演进能力
4. 入口碎片化 (wksp CLI + hermes Web + runtime MCP)
5. shared-lib(25K) 模块名 `kairon_lib`, 只服务 kairon 内 4 包 (5 子包已于 2026-06-06 拆出)
```

---

## 二、依赖分析结果

### 被引用最多的包 (不能移)

| 包 | 行数 | 被引用 | 引用者 |
|----|------|--------|--------|
| eidos | 35K | 5 | agora, codeanalyze, iris, kos, minerva |
| kos | 14K | 4 | agora, eidos, kronos, minerva |
| shared-lib | 38K | 4 | agora, engine-core, minerva, ontoderive |
| minerva | 25K | 3 | agora, iris, llm-gateway |

### 自包含包 (可自由移动)

| 包 | 行数 | 移动代价 |
|----|------|---------|
| cron-service | 1.8K | 0 |
| ecos | 6.3K | 0 |
| forge | 8K | 0 |
| kairon-governance | 2.5K | 0 |
| metaos | 7.8K | 0 |
| sophia | 1.4K | 0 |
| symphony-protocol | 1K | 0 |

### 双向依赖 (不能单独拆)

```
kos ↔ eidos      (双方互相引用, 必须同时移动)
minerva ↔ llm-gateway  (同上)
```

---

## 三、5+3+1 分层归属

每条线的判断标准: **包的功能属于哪一层**

### 包归属判定

| 包 | 当前层 | 应属层 | 判定 | 原因 |
|----|--------|--------|------|------|
| **agora** | kairon L2 | **I0** | 🔴 搬家 | MCP 总线框架 |
| **cron-service** | kairon L2 | **L1** | 🔴 搬家 | 定时调度 |
| **agent-runtime** | kairon L2 | **L1+L3** | 🔴 拆分 | 执行→L1, CLI→L3 |
| **metaos** | kairon L2 | **L2 独立** | 🔴 搬家 | 编排引擎 |
| **wksp** | kairon L2 | **L3** | 🔴 搬家 | 用户 CLI |
| **ecos** | kairon L2 | **L0** | 🔴 搬家 | SSB 协议 |
| **kairon-governance** | kairon L2 | **L2 omo** | 🟡 合并 | 治理重复 |
| engine-core | kairon L2 | L1+L2 | 🟡 后续 | 事件+L1, 存储+L2 |
| eidos | kairon L2 | L0+L2 | 🟡 后续 | 类型+L0, 验证+L2 |
| shared-lib | kairon L2 | L0 | 🟡 后续 | 基础工具, 应全层可用 |
| core-models | kairon L2 | L2 ✅ | 🟢 不动 | |
| ssot | kairon L2 | L2 ✅ | 🟢 不动 | |
| kos | kairon L2 | L2 ✅ | 🟢 不动 | |
| minerva | kairon L2 | L2 ✅ | 🟢 不动 | |
| ontoderive | kairon L2 | L2 ✅ | 🟢 不动 | |
| sophia | kairon L2 | L2 ✅ | 🟢 不动 | |
| kronos | kairon L2 | L2 ✅ | 🟢 不动 | |
| iris | kairon L2 | L2 ✅ | 🟢 不动 | |
| codeanalyze | kairon L2 | L2 ✅ | 🟢 不动 | |
| forge | kairon L2 | L2 ✅ | 🟢 不动 | |
| llm-gateway | kairon L2 | L2 ✅ | 🟢 不动 | 双向循环保护 |
| sharedbrain-bridge | kairon L2 | L2 ✅ | 🟢 不动 | |
| symphony | kairon L2 | L2 ✅ | 🟢 不动 | |
| health-profile | kairon L2 | L2 ✅ | 🟢 不动 | |

---

## 四、最终方案: 从 5 项目 → 9 项目

### 9 项目布局

```
Workspace/
├── projects/
│   ├── agora/          I0 · MCP Hub (从 kairon)
│   ├── kairon/         L2 · 知识引擎 (14 包, ~220K)
│   ├── gbrain/         L2 · 知识数据库 (163K TS)
│   ├── omo/            L2 · 治理面 (合并 kairon-governance)
│   ├── metaos/         L2 · 编排引擎 (从 kairon)
│   ├── ecos/           L0 · SSB协议+涌现 (从 kairon)
│   ├── runtime/        L1 · 运行时 (吸收 cron + agent-runtime)
│   ├── cockpit/        L3 · 统一入口 (合并 wksp CLI + hermes)
│   └── (其他: 无新增代码)
│
├── protocols/          L0 · 协议注册表 (YAML, 不变)
├── .omo/              治理数据 (跨项目)
├── data/              共享数据层
├── spaces/             用户空间
└── tests/               集成测试
```

### 各包去向汇总

| 动作 | 包 | 从 | 到 | 行数 | 代价 |
|------|----|----|----|------|------|
| 🔴 搬家 | agora | kairon | projects/agora | 38K | 改 5 包接口 |
| 🔴 搬家 | cron-service | kairon | runtime/scheduler | 1.8K | 低 (自包含) |
| 🔴 搬家 | agent-runtime | kairon | runtime(核心) + cockpit(CLI) | 20K | 中 |
| 🔴 搬家 | metaos | kairon | projects/metaos | 7.8K | 低 (自包含) |
| 🔴 搬家 | wksp | kairon | cockpit/cli | 15K | 低 (仅依赖 agora) |
| 🔴 搬家 | ecos | kairon | projects/ecos | 6.3K | 低 (自包含) |
| 🟡 合并 | kairon-governance | kairon | omo | 2.5K | 功能对齐 |
| 🟢 保留 | 其他 17 包 | kairon | kairon (不动) | ~207K | 0 |

### 每项目规模

| 项目 | 包数 | 代码量 | 核心职责 |
|------|------|--------|---------|
| **kairon** | 14 | ~220K | 知识工程流水线 (eidos/kos/minerva/ontoderive/...) |
| **gbrain** | 1 | 163K TS | Postgres 知识脑 · 67 工具 |
| **agora** | 1 | ~15K | MCP Hub · 服务发现/路由/代理 (精简后) |
| **omo** | 1 | ~17K | 治理 CLI (合并后) |
| **metaos** | 1 | 7.8K | 编排引擎 |
| **ecos** | 1 | 6.3K | SSB 协议 + 涌现 |
| **runtime** | 5 | ~10K | 运行时: 注册表/健康/调度/沙箱 |
| **cockpit** | 2 | ~12K | 入口: CLI(Py) + Web(TS) |
| **protocols/** | — | — | L0 协议 YAML |

---

## 五、实施计划 (4 步)

| 步骤 | 操作 | 行数移动 | 时间 | 风险 |
|------|------|---------|------|------|
| **M1** | agora 独立 + 精简 | 38K → projects/agora | 3-4天 | **高** (改 5 包接口) |
| **M2** | cron + agent-runtime 分拆 | 22K → runtime + cockpit | 2-3天 | **中** |
| **M3** | metaos + ecos + wksp 搬家 | 29K → 各自项目 | 1-2天 | **低** (自包含) |
| **M4** | kairon-governance → omo | 2.5K 功能对齐 | 1天 | **低** |

优先级: M3 (最容易) → M2 (中等) → M1 (最难) → M4 (收尾)
全部完成后: 5项目 → 9项目, kairon 从 300K → 220K

---

## 六、不变和风险

### 不变项

- gbrain (163K TS) — 全不改
- 所有不动的 17 个 kairon 包 — 全不改
- .omo/ 治理数据层 — 全不改
- data/ 数据层 — 全不改

### 主要风险

| 风险 | 缓解措施 |
|------|---------|
| agora 独立时 import 断裂 | 先走 M1, 用 MCP 替换 5 包的直接 import |
| agent-runtime 拆分影响 cron 任务 | 提供 CLI 兼容包, 旧命令路由不变 |
| 跨项目测试断裂 | 每步搬完后跑全量测试套件 |
| git 子仓库混乱 | 使用 `git subtree` 或直接 `cp` 方式搬代码 |

---

## 七、最终架构快照

```
L3 ──→ cockpit · ~12K (wksp CLI + hermes Web)
        │
I0 ──→ agora · ~15K (MCP Hub, 精简)
        │
L2 ──→ ┌ omo · ~17K (治理面, 合并 k-gov)
       ├ kairon · ~220K (知识引擎, 14包)
       ├ metaos · 7.8K (编排引擎)
       └ gbrain · 163K TS (知识数据库)
        │
L1 ──→ runtime · ~10K (注册表/健康/调度/沙箱)
        │
L0 ──→ ┌ protocols/ (16 YAML 协议)
       └ ecos · 6.3K (SSB 协议 + 涌现)

X1 ──→ KEI 审计 (runtime)
X2 ──→ freshness + autoheal (scheduler)
X3 ──→ cost tracking (omo cost estimate)

共: 9 项目 · ~460K 行 · 0 新增代码
```
