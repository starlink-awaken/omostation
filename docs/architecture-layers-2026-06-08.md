# eCOS v5 · L 层深度架构分析

**2026-06-08 · 架构师视角 · 自底向上**

---

## 一、层级逻辑模型

eCOS v5 使用 **5+1+1** 的层级编号体系（L0-L4 + I0 + X1-X4）：

```
L4 · 自我层     ← 数据面（人类意图）
L3 · 入口层     ← 交互面（用户/Agent 唯一界面）
I0 · 集成织层   ← 控制面（服务网格、路由、代理）
L2 · 引擎层     ← 能力面（知识、治理、决策）
L1 · 运行时     ← 执行面（注册、监控、沙箱）
L0 · 协议层     ← 定义面（模型、签名、根约束）
```

这并非传统的"上层依赖下层"的分层架构，而是一种**以 I0 为枢纽的星形拓扑**：L3 和 L2 都通过 I0 通信，L0 为所有层提供根定义，L1 为所有层提供运行保障。

---

## 二、逐层深度解剖

### L0 · 协议层 · ecos

**定位**: 认知地基 — 系统的根定义层。其他层不直接依赖 ecos 代码，但所有层的建模和约束都源于 ecos 的 MOF 模型。

```
结构:
  ecos/
  ├── ssot/mof/           ← 元模型工厂 (MOF)
  │   ├── m3.yaml         ← Meta-Meta-Model (Layer/Type/Relation 枚举)
  │   ├── ontology.yaml   ← 本体映射 (M3→M2 关系定义)
  │   ├── m2/             ← 类型层 (12 个 YAML: workflow/domain/architecture/...)
  │   └── m1/             ← 实例层 (130+ YAML: 具体域/流程/约束/制品...)
  │       ├── domain/     ← 19 个域定义 (L0-L4 全覆盖)
  │       ├── process/    ← 流程 (CARDS 7, Agent 启动...)
  │       ├── specification/ ← 治理约束 (12 CLAUDE 规范)
  │       ├── bosroute/   ← BOS URI 路由定义
  │       ├── artifact/   ← 24 个 L4 执行脚本
  │       ├── skill/      ← 30 个定时技能
  │       └── mechanism/  ← 执行机制
  │
  ├── core/               ← SSB 签名链
  ├── cli/                ← dashboard, scheduler
  └── services/           ← governance, integration, monitoring
```

**关键设计**:

| 概念 | 实现 | 说明 |
|------|------|------|
| M3 元元模型 | `m3.yaml` | 定义 Layer(0-4/I0)、Type(Skill/Process/Pattern...)、Relation(depends/contains/refines) |
| M2 类型定义 | `m2/*.yaml` | 为每种类型定义 schema + 示例，所有 M1 实例必须遵循 |
| M1 实例 | `m1/*.yaml` | 130+ 个具体化的 M2 实例，包含 id/layer/status/created 元数据 |
| M0 运行时 | `L0-registry.yaml` | M1 模型在运行时的投影（协议注册、端口分配） |

**层级流向**:

```
L0 MOF 模型
  ↓ 定义
L1 runtime protocols/    ← L0-registry, ecos-ontology
  ↓ 注册
I0 agora BOS resolver    ← bos:// 域→服务 映射表
  ↓ 路由
L2 kairon/omo/metaos     ← MCP tool → BOS URI 映射
  ↓ 调用
L3 cockpit               ← research/context 命令包装
  ↓ 展示
L4 CARDS/Vault           ← 数据消费
```

---

### L1 · 运行时底座 · runtime

**定位**: 系统的心跳和免疫系统。不产生业务价值，但保障所有服务可用。

```
runtime/
├── matrix.py             ← 服务注册 (YAML → ServiceEntry)
├── scheduler.py          ← 15s 心跳 + 自愈引擎
├── protocol.py           ← L0 协议投影
├── mcp_server.py         ← 7 MCP tools (runtime 对外接口)
├── kei.py/kei_sandbox.py ← Python C-level audit hook
├── cron_service/         ← 30 L4 定时技能调度
└── executor/             ← Agent DAG 编排引擎 (100+ files)
```

**核心机制**:

| 机制 | 节奏 | 输入 | 输出 |
|------|------|------|------|
| 服务注册 | on-start | agora services | matrix.yaml |
| 健康心跳 | 15s | matrix.yaml | matrix_state.json |
| 自愈 | 按需 | 过期检测 | launchctl restart |
| KEI 沙箱 | 持续 | sys.addaudithook | JSONL 审计日志 |
| Cron 调度 | cron 表达 | l4_scheduled_jobs.yaml | cockpit skill run |

**架构评价**: 
- ✅ 心跳+自愈闭环完整
- ✅ KEI 沙箱粒度精细（fs/network/shell/env）
- ⚠️ executor 引擎 100+ 文件，是最复杂的子系统但实际使用频率最低
- ⚠️ Python 3.10+ 要求与 cockpit 一致，但与 kairon/agora 的 3.13+ 不一致

---

### I0 · 集成织层 · agora

**定位**: 系统的神经中枢。所有 L 层之间的通信都经过 agora。

```
agora/
├── server/mcp.py         ← FastMCP 主服务器 (38 tools)
├── mcp_registry/         ← 服务注册表 (agora-services.json)
├── mcp_proxy/            ← 动态代理 (Phase 2: 加载/卸载/超时)
├── auth/                 ← Bearer/JWT + tenant PBKDF2
├── mcp/                  ← BOS 解析器 + forge 加载器 + swarm
├── a2a/                  ← Agent-to-Agent 协议 (0.1)
├── bus/                  ← SSE 事件总线
└── metrics/              ← Prometheus 指标导出
```

**路由拓扑** (136 条路由):

```
bos://memory/kos/search     → kairon/kos
bos://analysis/minerva/research → kairon/minerva
bos://governance/metaos/gate → metaos
bos://forge/runtime/task    → runtime executor
bos://persona/sot-bridge/recall → kairon/sot-bridge
...
```

**架构评价**:
- ✅ 38 个原生 MCP tools + 136 条路由 + 代理转发 → 统一入口
- ✅ 动态加载/卸载 + idle timeout → 资源管理成熟
- ✅ PBKDF2 tenant 认证 + JWT auth → 安全体系完整
- ⚠️ 是单点枢纽 — 如果 agora 挂掉，所有跨服务通信中断
- ⚠️ bos_resolver 中的域名枚举硬编码 → 新增域需改代码

---

### L2 · 引擎层 · kairon/omo/metaos/gbrain

**定位**: 系统的业务逻辑面。四个引擎各司其职。

```
L2 引擎矩阵:
┌──────────────┬─────────────┬──────────────┬────────────┐
│    kairon    │    omo      │   metaos     │   gbrain   │
│   知识引擎    │  治理引擎    │  决策引擎     │  存储引擎   │
├──────────────┼─────────────┼──────────────┼────────────┤
│ 16 包        │ Phase/债务   │ Gate/Immune  │ 67 MCP     │
│ ~260 tools   │ 586 tests   │ 189 tests    │ TypeScript │
│ Python 3.13  │ Python 3.13 │ Python 3.13  │ Bun        │
└──────────────┴─────────────┴──────────────┴────────────┘
```

**数据流**:

```
Kairon 知识管线:
  kronos (摄取) → eidos (校验) → kos (索引) → gbrain (持久化)
                                              → minerva (研究)
                                              → ontoderive (推导)

OMO 治理管线:
  .omo/_truth → omo debt registry → cockpit context
              → omo phase track → X2 freshness check

MetaOS 决策管线:
  L4 CARDS → metaos cards_context → Agent planning prompt
           → metaos gate (红/黄/绿) → MLayer → Immune check
```

**架构评价**:
- ✅ 知识摄→存→研→推导 闭环完整
- ✅ 治理 X1-X4 全覆盖
- ⚠️ kairon 16 包中 core-models 被 8 包引用 → 耦合集中点
- ⚠️ gbrain 是唯一 TypeScript 项目 → 技术栈碎片

---

### L3 · 入口层 · cockpit

**定位**: 用户体验的门面。23 CLI + 20 MCP + Web Dashboard。

```
cockpit/
├── cli.py                ← argparse 路由 (23 子命令)
├── storage.py            ← IDataAccess Protocol + SQLite
├── commands/
│   ├── research.py       ← 核心 (1257 行, 最深模块)
│   ├── status.py         ← 健康概览
│   ├── l4bridge.py       ← L4 CARDS/Vault 桥接
│   └── quickstart.py     ← onboarding
├── scripts/
│   └── cockpit_mcp.py    ← MCP Server (13 tools)
└── dashboard_server.py   ← Web Dashboard (:8090)
```

**命令树**:

```
cockpit
├── research [topic] [--stream] [--batch]   ← 研究+流式+批量
├── health --full                            ← 一键全栈体检
├── workspace context/cards/vault/domains    ← L4 桥接
├── status                                  ← 服务健康
├── quickstart                              ← onboarding
├── contracts                               ← 契约管理
├── data                                    ← 数据索引
├── dashboard                               ← Web
└── governance/daily/brief/events/...       ← 治理工具
```

**架构评价**:
- ✅ 23 命令 + 13 MCP tools + streaming → 功能密度高
- ✅ IDataAccess Protocol → 后端可替换
- ⚠️ `workspace` 和 `cockpit` 双入口 → 命令碎片化
- ⚠️ 无配置中心 → 硬编码路径/env var 分散在各文件

---

### L4 · 自我层 · 12 域数据

**定位**: 人类的意图层。不运行代码，通过 cockpit MCP 被动消费。

```
L4 12 域:
  cockpit (驾驶舱/CARDS), vault (@学习进化), personal (@个人)
  family, shared, sharedwork, shareddisk
  work-weijian, work-guozhuan
  ai-config, obsidian-vault, icloud-sharedconf
```

**数据流**:

```
L4 数据源
  ↓ 只读
L3 cockpit (workspace context, cards_status, vault_search)
  ↓ MCP
L2 metaos (cards_context → Agent prompt 注入)
  ↓ 写入
minerva VaultSink → @学习进化 自动归档
```

**架构评价**:
- ✅ 数据面与执行面完全解耦
- ✅ 多域扩展性好 (2→12 域仅需 dockit_mcp.py 一行)
- ⚠️ 无版本控制 — CARDS 修改无历史追溯 (SQLite 无 git)
- ⚠️ 跨设备共享 — 12 域都是本地 ~/Documents，无云同步

---

## 三、跨层通信矩阵

| 调用方 → 被调方 | L0 ecos | L1 runtime | I0 agora | L2 kairon | L2 omo | L2 metaos | L3 cockpit | L4 data |
|-----------------|---------|-----------|----------|-----------|--------|-----------|-----------|---------|
| L0 ecos | — | — | bos:// | — | — | — | — | — |
| L1 runtime | L0-registry | — | SSE/health | — | 写入 OMO | — | — | — |
| I0 agora | — | — | — | MCP proxy | MCP proxy | MCP proxy | MCP proxy | 路由表 |
| L2 kairon | MOF 定义 | — | MCP client | — | — | — | — | 写入 Vault |
| L2 omo | — | — | MCP client | — | — | — | — | — |
| L2 metaos | — | — | MCP client | — | — | — | — | 读取 CARDS |
| L3 cockpit | — | executor | MCP client | subprocess | — | — | — | 读取全部 |
| L4 data | — | — | — | — | — | — | cockpit MCP | — |

---

## 四、架构债务清单

| 类型 | 问题 | 影响层 | 严重度 |
|------|------|--------|--------|
| 耦合 | agora 是单点枢纽 | I0→全层 | 🔴 |
| 一致 | Python 3.10/3.13 版本分裂 | L0/L1/L3 vs L2/I0 | 🟡 |
| 一致 | `workspace` vs `cockpit` 双入口 | L3 用户面 | 🟡 |
| 碎片 | gbrain TypeScript 独立技术栈 | L2 | 🟡 |
| 规模 | kairon core-models 8 包耦合 | L2 内部 | 🟡 |
| 规模 | executor 引擎 100+ 文件低频使用 | L1 | 🟢 |
| 安全 | CARDS 无 git 历史 | L4 | 🟢 |
| 体验 | Web Dashboard 未完成 | L3 交互面 | 🟡 |

---

## 五、演进路线建议

| 优先级 | 方向 | 说明 |
|--------|------|------|
| P0 | 统一 cockpit 入口 (workspace→cockpit) | 消除命令碎片化 |
| P0 | agora 高可用 (备用实例/健康降级) | 单点故障保护 |
| P1 | Python 版本统一至 3.13 | 减少维护成本 |
| P1 | cockpit 配置中心 (`~/.config/cockpit/config.yaml`) | 消除硬编码路径 |
| P2 | Web Dashboard MVP | 交互可视化 |
| P2 | CARDS SQLite → git 同步 | 版本追溯 |
