# eCOS v5 · L0-L4 分层架构深度分析

**2026-06-08 · 内部架构全解剖 · L0 + L1 重点**

---

## 一、层级拓扑全景

```
                            L4 · 自我层 (12域数据)
                            CARDS(SQLite) + Vault(Obsidian)
                            不运行代码
                                  ↑ MCP 只读
                            L3 · 入口层
                            cockpit · CLI 23 + MCP 20
                                  ↑ bos://
                          ┌────── I0 · 集成织层 ──────┐
                          │  agora · 38 tools · 136路由  │
                          │  MCP Proxy · Circuit Breaker │
                          └───────┬──────────┬──────────┘
                                  │          │
                    ┌─────────────┼──────────┼──────────────┐
                    │             │          │              │
              ┌─────▼─────┐ ┌─────▼─────┐ ┌──▼────────┐    │
              │  L2·引擎  │ │ L2·引擎   │ │ L2·引擎   │    │
              │  kairon   │ │ omo       │ │ metaos    │    │
              │  16包·260 │ │ Phase·债务 │ │ Gate·免疫  │    │
              │  tools    │ │           │ │           │    │
              └─────┬─────┘ └─────┬─────┘ └───────────┘    │
                    │             │                         │
              ┌─────▼─────────────▼─────────────────────┐   │
              │            L1 · 运行时底座               │   │
              │  Matrix + Scheduler + KEI + Cron + Exec  │   │
              │  12 模块 · 30 MCP tools                 │   │
              └─────────────────┬───────────────────────┘   │
                                │                           │
              ┌─────────────────▼───────────────────────┐   │
              │          L0 · 协议层 (ecos)              │◄──┘
              │  M3→M2→M1→M0 模型驱动 · 884节点          │
              │  SSB签名链 · BOS URI · 治理服务           │
              └─────────────────────────────────────────┘
```

**关键洞察**: 这不是分层调用架构，而是以 **I0 agora 为枢纽的星形拓扑** + **L1 为底层运行保障** + **L0 为顶层模型驱动**。

---

## 二、L0 · 协议层 — 内部架构详解

### 2.1 模型驱动金字塔

```
              ┌─────────┐
              │   M3    │  1 YAML · 434行 · 19KB
              │ 元元模型  │  "定义'定义的方式'"
              └────┬────┘
                   │ 实例化
              ┌────▼────┐
              │   M2    │  28 YAML · 定义28种要素类型
              │  元模型   │  Domain/Entity/Workflow/Mechanism/...
              └────┬────┘
                   │ 实例化
              ┌────▼────┐
              │   M1    │  884 YAML · 32子目录
              │ 节点实例  │  136 Entity + 138 Lesson + 121 Spec
              └────┬────┘
                   │ 运行时投影
              ┌────▼────┐
              │   M0    │  1 YAML · 运行时快照
              │ 运行态   │  协议衰减 · Daemon状态 · 健康分
              └─────────┘
```

### 2.2 M3 元元模型 — 系统基因

M3 定义四类元素 + 四类关系：

| 元素类别 | 类型 | 用途 |
|---------|------|------|
| 结构元素 | Layer, Component, Entity, Artifact | 描述"是什么" |
| 行为元素 | Process, Mechanism, Protocol | 描述"做什么" |
| 治理元素 | Constraint, Policy, Pattern, Spec | 描述"怎么管" |
| 描述元素 | Model, Architecture, View | 描述"怎么理解" |

| 关系类别 | 类型 | 语义 |
|---------|------|------|
| 结构关系 | Contains, References | 组成与引用 |
| 行为关系 | Invokes, Triggers, DataFlow | 调用与触发 |
| 治理关系 | Constrains, Audits, Attributes | 约束与审计 |
| 语义关系 | EquivalentTo, Generalizes, Realizes | 等价与泛化 |

**自反性**: M3 自身结构也遵守 M3 规则 — 这是四层模型能形成闭环的关键。

### 2.3 M2 元模型 — 28 种类型

M2 定义 28 种要素类型，每种有 m3_parent 继承链：

```
M3 父类型                      M2 类型
─────────────────────────────────────────────
StructuralElement.Component → Domain, Component
StructuralElement.Entity     → Entity
StructuralElement.Artifact   → Artifact
BehavioralElement.Process    → Workflow, Process
BehavioralElement.Mechanism  → Mechanism
BehavioralElement.Protocol   → Protocol
GovernanceElement.Spec       → Specification
GovernanceElement.Pattern    → Pattern
DescriptiveElement.Architecture → Architecture
DescriptiveElement.Model     → Model
```

### 2.4 M1 节点 — 884 个实例

| 三大域 | 文件数 | 占比 |
|--------|--------|------|
| Entity (实体) | 136 | 15.4% |
| Lesson (经验) | 138 | 15.6% |
| Specification (规范) | 121 | 13.7% |
| **小计** | **395** | **44.7%** |

其他关键目录：
- BOSRoute: 73 个 BOS URI 路由定义
- Mechanism: 65 个执行机制
- Artifact: 61 个制品脚本
- Skill: 56 个技能 (含 30 个 Scheduled)
- MCPTool: 43 个工具定义
- Workflow: 26 个工作流

### 2.5 SSB 签名链

**双写架构**: SQLite (快速查询) + File (持久真源)

```
事件 → SSBClient
  ├─ SQLite → ~/.ecos/LADS/ssb/ecos.db (快查)
  ├─ File   → HANDOFF/LATEST.md + STATE.yaml + FAILURES/FAIL-*.md
  └─ HMAC   → SHA256签名 (16字符), 密钥 ~/.ecos/LADS/ssb/.ssb_key (600权限)
```

**防泛洪**: 60s 滑动窗口, 同类型事件 ≤ 10 条
**恢复**: recover_from_files() 可从文件重建 SQLite

### 2.6 MOF 工具链

```
mof bootstrap → M3 自反一致性校验
mof validate → M2→M1 结构校验 (575节点)
mof audit    → M1↔M0 漂移审计
mof events   → M0 异常→治理事件
mof enforce  → 层边界合规检查
mof pipeline → 全链路 (7阶段) 自动验证
```

---

## 三、L1 · 运行时底座 — 内部架构详解

### 3.1 六核心模块

```
┌─────────────────────────────────────────────────────────────┐
│                      L1 Runtime                              │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │  Matrix  │  │Scheduler │  │   KEI    │  │   Cron     │  │
│  │ 注册表    │  │ 健康监控  │  │  沙箱    │  │  调度      │  │
│  │          │  │          │  │          │  │            │  │
│  │Service   │  │15s心跳   │  │sys.add   │  │FastAPI     │  │
│  │Entry     │  │DAG扫描   │  │audithook │  │asyncio     │  │
│  │轻量YAML  │  │自愈引擎   │  │JSONL审计  │  │croniter    │  │
│  │解析      │  │指数退避   │  │          │  │30 L4 jobs  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
│       │              │             │               │        │
│  ┌────┴──────────────┴─────────────┴───────────────┴──────┐ │
│  │                    数据流总线                            │ │
│  │  Matrix → Scheduler → HealthPulse → OMO SSOT            │ │
│  │  Bus Consumer → Agora SSE → gbrain                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Executor    │  │  Protocol    │  │ MCP Server   │      │
│  │  Agent引擎   │  │  L0→L1投影   │  │  7 tools     │      │
│  │              │  │              │  │              │      │
│  │AgentRuntime  │  │7类协议注册   │  │health/matrix │      │
│  │LLM→工具编排  │  │dispatch      │  │protocol/onto │      │
│  │DAG 8 Phase   │  │validate      │  │brief/kv      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Matrix 服务注册表 (199行)

**核心设计**: 零外部依赖的轻量 YAML 解析器。

```python
ServiceEntry:
  name / type / status           # 标识
  port / launchd_label / docker  # 运行时检测点
  health_url                     # HTTP 健康检查
  depends_on: list[str]          # DAG 依赖图
```

**解析**: 按缩进层级 (2/4/6/8空格) 解析 matrix.yaml，`$VAR` 自动展开为环境变量。

### 3.3 Scheduler 健康监控 (414行)

**scan_once() 流程**:
```
1. 加载 matrix.yaml → 构建 DAG (TopologicalSorter)
2. 按依赖顺序扫描每个服务:
   ├─ 依赖不健康? → WAITING_FOR_DEPENDENCY
   ├─ 5分钟内重启>5次? → FROZEN_CRASH_LOOP
   ├─ launchd: launchctl list <label>
   ├─ Docker: docker ps --filter name=<container>
   ├─ 端口: lsof -iTCP:<port> -sTCP:LISTEN
   └─ HTTP: curl health_url
3. 自愈:
   ├─ launchd: launchctl stop + start
   ├─ Docker: docker restart
   └─ 指数退避: 5 * (2 ^ restart_count) 秒
4. 状态哈希 → 仅变化时写入 OMO
5. 健康告警: healthy → unreachable 跃迁通知
```

### 3.4 KEI 沙箱 (238行)

**双层模型**:
1. **权限声明** (kei.py): KEIManifest — fs_read/fs_write/network_hosts/shell_exec/env_vars
2. **运行时拦截** (kei_sandbox.py): `sys.addaudithook()` — 拦截 subprocess.Popen / socket.connect / open

**审计日志**: JSONL, 仅记录 fail/blocked, 使用 os.open/write 避免递归

### 3.5 Cron Service

**架构**: FastAPI (HTTP) + asyncio (调度) + ThreadPoolExecutor (执行)
- 30 个 L4 定时技能通过 `l4_scheduled_jobs.yaml` 注册
- 三种表达式: cron / "every 5m" / "*/15 * * * *"
- 新任务保护: 创建后 60s 内不执行

### 3.6 Executor AgentRuntime (302行)

**无状态单次任务引擎**:
1. System prompt (中文, `[SILENT]` 标记)
2. LLM 调用 (llm_gateway auto-detect)
3. 工具编排 (最多 30 轮)
4. 返回 `{result, tool_calls, turns, usage}`

### 3.7 L0→L1 协议投影

**ProtocolEntry** — L0 协议在 L1 的运行时投影:
- 7 类协议: agent-communication / model-access / service-discovery / state-sync / identity-auth / data-exchange / orchestration
- dispatch/validate/status 运行时语义

---

## 四、L0 ↔ L1 协同机制

```
L0 (ecos)                      L1 (runtime)
─────────────────────────────────────────────────
M3 元元模型  ──定义──→  protocol.py ProtocolEntry
M2 元模型    ──约束──→  kei.py SandboxPermissions
M1 节点      ──注册──→  matrix.py ServiceEntry
M0 快照      ──投影──→  scheduler.py HealthPulse

SSB 签名链   ──写入──→  bus_consumer.py (SSE→gbrain)
BOS URI      ──路由──→  agora bos_resolver
MOF 工具链   ──调用──→  mcp_server.py (protocol_get)
```

**关键设计原则**: L1 不重新定义 L0 的内容，而是将 L0 的模型**投影**到运行时语义中。ProtocolEntry 不是协议的"副本"，是协议的"运行时视图"。

---

## 五、L0-L1 架构评估

### L0 优势
- ✅ M3→M2→M1→M0 四级闭环，理论完整
- ✅ 884 个 M1 节点覆盖全栈建模
- ✅ 自反性保证体系自举
- ✅ SSB 双写 + HMAC 防篡改
- ✅ MOF 工具链 7 阶段全链路验证

### L0 弱点
- ⚠️ 884 个 M1 节点中 44.7% 集中在 Entity+Lesson+Spec → 其他域建模密度不均
- ⚠️ M2 28 种类型中有部分 (compute_engine, hardware_asset, network_zone) 使用频率极低
- ⚠️ M0 运行时快照仅 1 个 YAML → 与 M1 的漂移检测依赖手动审计

### L1 优势
- ✅ 6 核心模块职责清晰、边界明确
- ✅ 零外部依赖的 YAML 解析 → 健壮
- ✅ DAG 依赖图 + 指数退避自愈 → 成熟
- ✅ KEI sys.addaudithook → C 级拦截不可绕过
- ✅ Cron 30 个 L4 定时技能已注册

### L1 弱点
- ⚠️ Matrix 自研 YAML 解析器 → 不支持数组/嵌套，扩展性受限
- ⚠️ Scheduler 自愈依赖 launchctl → Linux 不兼容
- ⚠️ Executor 100+ 文件 → 最复杂但实际使用频率最低
- ⚠️ Python 3.14 运行但声明 3.13 → 已修复

### L0+L1 协同优势
- ✅ 协议定义与运行时投影分离 → L0 改模型不影响 L1 运行
- ✅ SSB→SSE→gbrain 事件管道完整
- ✅ BOS URI 统一寻址跨越 L0→L1 边界
