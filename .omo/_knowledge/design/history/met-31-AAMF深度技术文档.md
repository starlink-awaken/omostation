---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# AAMF: Agent Architecture Meta-Framework — 深度技术文档

> **副标题**: 从架构审计到自我治理的 10 小时工程实践
> **作者**: AAMF Governance System (governance-system, EVOLVER, v1.0.0)
> **文档编号**: #31 | **时间**: 2026-05-28

---

## 摘要

本文详细阐述 AAMF（Agent Architecture Meta-Framework）的设计与实现——一个自指、可进化的架构治理体系。全文从时序、元模型、约束系统、状态机、工具链、视图层、自指机制七个维度展开，每个维度均包含设计决策、实现细节和关键复盘。

---

## 目录

1. [动机：为什么要治理架构](#1-动机为什么要治理架构)
2. [时序：10 小时的工程奇迹](#2-时序10-小时的工程奇迹)
3. [元模型：M2 层的 7 种类型与 10 种关系](#3-元模型m2-层的-7-种类型与-10-种关系)
4. [约束系统：26 条规则的代码化与执行](#4-约束系统26-条规则的代码化与执行)
5. [状态机：节点生命周期与热插拔协议](#5-状态机节点生命周期与热插拔协议)
6. [工具链：15 个 CLI 的完整架构](#6-工具链15-个-cli-的完整架构)
7. [视图层：C4 + Archimate + 仪表盘](#7-视图层c4--archimate--仪表盘)
8. [自指机制：治理系统管理自身](#8-自指机制治理系统管理自身)
9. [数据流：从 sniff 到 auto-fix 的闭环](#9-数据流从-sniff-到-auto-fix-的闭环)
10. [复盘：56x 偏差、设计缺陷、未解决的问题](#10-复盘56x-偏差设计缺陷未解决的问题)

---

## 1. 动机：为什么要治理架构

### 1.1 问题背景

在构建个人 AI 基础设施时（~30 个项目，覆盖编排引擎、MCP 网关、知识工程、数据设施、生态工具），一个典型的多项目架构面临的核心问题是：

> **30 个项目，30 套接口标准，0 个统一管控。**

具体表现为：

| 问题 | 表现 | 严重程度 |
|------|------|---------|
| 无统一架构宪法 | 每个项目有自己的 README 和设计文档，但没有任何文档定义"什么算一个架构节点" | 🔴 P0 |
| 元模型只有 12.5% 的使用率 | Eidos 元模型定义了 8×4 的类型关系矩阵，实际只有 1 个关系类型被项目使用 | 🔴 P0 |
| 无统一枚举契约 | 30 个项目各有协议定义（MCP stdio、HTTP REST、WebSocket、CLI stdio），但无一统一定义 | 🟡 P1 |
| 游离节点 | Agent Runtime 承担 LLM 推理但无明确架构角色定义 | 🟡 P1 |
| 各层实现参差不齐 | 持续进化层（S2）完全缺位，价值可视化层（X3）完全缺位 | 🟡 P1 |

### 1.2 为什么选择元模型驱动

两个候选方案：

| 方案 | 方式 | 评估 |
|------|------|------|
| **注册中心（Registry）** | 每个服务注册 endpoint + health check | 轻量但无语义，无法推导关系 |
| **元模型（Meta-Model）** | 定义类型/关系/约束，实例化为节点声明 | 重量但可推导、可验证 |

**选择元模型。** 原因：注册中心只能回答"有哪些服务在跑"，元模型能回答"这个节点是什么类型、依赖谁、提供什么接口、应该由谁管理"。后者是治理的基础。

### 1.3 三个层级的元模型

```
M3: ArchitectureObject         — "架构节点是什么"（元元模型）
     ↓ 实例化
M2: MetaType × MetaRelation    — 7 种类型 × 10 种关系（元模型）
     ↓ 实例化
M1: ArchitectureNode Schema    — 每个模块的 YAML 声明（模型层）
     ↓ 实例化
M0: agent-runtime / agora / kos — 运行中的具体组件（运行层）
```

### 复盘 1：Eidos 元模型的教训

**问题**: 初始体系使用了 Eidos 元模型（8 类型 × 4 关系），但实际只有 12.5% 的关系被使用。

**根因**: Eidos 元模型是通用的本体建模框架，而 AAMF 需要的是架构治理专用的元模型。通用框架的抽象层次过高，导致项目开发者不理解如何在具体场景中使用。

**决策**: AAMF 不重用 Eidos，而是从零构建自己的 M2 层（schema.py），专注于架构治理场景。Eidos 继续做它的本体建模工作，AAMF 独立运行。

**教训**: 通用框架在特定场景下的落地成本远高于专用框架。不要试图用一个元模型框架解决所有问题。

---

## 2. 时序：10 小时的工程奇迹

### 2.1 时间线

整个 AAMF 从 Phase 0 到 Phase 7 在 **10.5 小时** 内完成。

```
04:01  审计开始              → 发现 5 个核心问题
04:44  Phase 0 完成          → 确定迭代方案
07:54  Phase 1 完成          → 8 章宪法 + 18 约束落盘
08:53  Phase 2 完成          → 21 节点注册流水线
10:47  Phase 3 完成          → 依赖图 + drift + 周报
12:38  Phase 4 完成          → 进化引擎 + governance-system 自注册
14:22  Phase 5 完成          → 7 步热插拔协议
14:42  Phase 6 完成          → 依赖自动维护 + 视图
15:05  Phase 7 完成          → 宪法同步 + 自指热插拔
```

### 2.2 为什么这么快

| 因素 | 加速比 | 原因 |
|------|--------|------|
| LLM 代码生成 | 10-20x | 大部分 CLI 由 LLM 生成，人工只做设计决策和验证 |
| 共享基础设施 | 3-5x | schema.py 统一枚举 + 约束，脚本间相互调用 |
| 快速迭代 | 2-3x | 没有审批流程，设计→编码→测试在 15-45 分钟内完成 |
| 递归架构 | 2x | 治理系统本身就是 AAMF 的节点，自指设计减少重复工作 |

### 2.3 关键里程碑

| 事件 | 时间 | 发生了什么 |
|------|------|-----------|
| schema.py 创建 | +1h | 所有后续脚本共享的枚举定义（MetaType/Relation/DependencyLevel） |
| 第一个 cron | +2h | drift-check cron 的设置意味着治理体系开始"自我运行" |
| governance-system 自注册 | +8h | 治理体系开始管理自身——系统从"管理别人的工具"变为"管理系统的系统" |
| hotswap 自指测试 | +11h | 治理体系可以替换自身——终极闭环验证 |

### 复盘 2：计划 vs 实际偏差 56x

**原计划**: 10 周（70 天）
**实际**: 10.5 小时

**偏差根因**:

1. **工时估算模型错误** — 原方案按"人类开发者"估算（2-6h/任务），实际按"LLM 生成 + 人类设计"执行（15-45min/任务）。架构设计值钱，代码执行便宜。

2. **瀑布 vs 迭代** — 原方案是瀑布式大方案（每 Phase 2 周），实际是快速迭代（每 Phase 45min-2h）。每次迭代只解决当前最痛的问题，不超前设计。

3. **基础设施复用** — schema.py 一次编写四处使用。新 CLI 的平均代码量 ~200 LOC，其中 60% 是重复模式（log_governance、argparse、YAML 加载）。

4. **设计即实现** — 很多"设计决策"在编码过程中自然解决，不需要额外的设计文档。代码本身成为了设计文档。

**结论**: 对于 LLM 辅助开发的项目，工时估算至少应除以 10-20。更好的方法是：先做最小可行体系（MVP），然后按每小时一个增量功能迭代。

---

## 3. 元模型：M2 层的 7 种类型与 10 种关系

### 3.1 MetaType — 7 种架构角色

所有元模型定义在 `schema.py` 中，是 AAMF 的共享核心。

```python
class MetaType(str, Enum):
    PROCESSOR = "PROCESSOR"    # 任务处理引擎
    SERVICE = "SERVICE"        # 提供传输协议的服务
    GATEWAY = "GATEWAY"        # 路由/网关
    STORE = "STORE"            # 存储/查询
    AGENT = "AGENT"            # LLM-backed 决策
    TOOL = "TOOL"              # 原子功能
    EVOLVER = "EVOLVER"        # 进化分析（新增，Phase 4）
```

**类型选择的原则**：

每个类型对应一个"架构职责"，而非"技术实现"。具体：
- **PROCESSOR** 负责执行任务（agent-runtime 跑 task_definitions）
- **SERVICE** 提供网络服务（agora 提供 MCP 注册 API）
- **GATEWAY** 负责路由转发（agentmesh Gateway 做 SSE 推送）
- **STORE** 负责数据持久化（kos 做文档存储，ssot 做配置存储）
- **AGENT** 负责 LLM 推理决策（hermes-agent 做 IM 交互）
- **TOOL** 提供原子能力（Forge 提供 111 个工具的注册发现）
- **EVOLVER** 负责进化分析（governance-system 做熵趋势和宪法同步）

**为什么需要 EVOLVER 类型？**

Phase 4 的复盘中发现：现有的 6 种类型无法描述"治理系统自身"。如果 governance-system 是 AGENT（LLM 驱动），那么它的"决策能力"元模型约束（T5）会要求它有 chat/decide 能力——但 governance-system 是 engine 而非 actor，它接受指令而不是自主决策。

**engine/actor 分类**:

```python
META_TYPE_PRIORITY = {
    "engine": {"types": ["PROCESSOR", "GATEWAY", "EVOLVER"], "rule": "接受指令并按指令执行"},
    "actor": {"types": ["AGENT", "SERVICE"], "rule": "自主决策后再行动"},
}
```

Engine 类型包含 EVOLVER——治理系统是 engine，永不自主做决策。这是安全设计。

### 3.2 MetaRelation — 10 种架构关系

```python
class Relation(str, Enum):
    COMPOSE = "COMPOSE"        # 组成关系（整体-部分）
    DEPEND = "DEPEND"          # 依赖关系（消费者-提供者）
    DELEGATE = "DELEGATE"      # 委托关系（PROCESSOR → PROCESSOR）
    CONFIGURE = "CONFIGURE"    # 配置关系
    MONITOR = "MONITOR"        # 监控关系
    COMMUNICATE = "COMMUNICATE" # 通信关系（双向）
    REPLACE = "REPLACE"        # 替换关系（热插拔，Phase 5 新增）
    EVOLVE = "EVOLVE"          # 进化关系（Phase 4 新增）
    OBSERVE = "OBSERVE"        # 观察关系（EVOLVER→其他，Phase 4 新增）
    EVALUATE = "EVALUATE"      # 评估关系（EVOLVER→其他，Phase 4 新增）
```

**为什么 4 种带到 10 种？**

从 Phase 1 的 6 种关系到 Phase 4-5 的 10 种关系，每个新增关系对应一个功能扩展：

- **REPLACE** (Phase 5): 热插拔需要"替换"语义，描述节点 A 替换节点 B 的关系
- **EVOLVE** (Phase 4): 进化引擎需要"进化自"语义，描述新版本节点与旧版本的关系
- **OBSERVE** (Phase 4): drift-check 与嗅探需要"观察"语义，描述治理系统与被管节点的关系
- **EVALUATE** (Phase 4): self-report 需要"评估"语义，描述健康度评分

**禁止关系矩阵**:

```python
FORBIDDEN_RELATIONS = {
    ("TOOL", "COMPOSE"):       "TOOL 不可再分",
    ("TOOL", "DELEGATE"):      "TOOL 独立执行，不委托",
    ("TOOL", "REPLACE"):       "TOOL 不可热替换",
    ("AGENT", "REPLACE"):      "AGENT 替换需人类确认",
    ("SERVICE", "DELEGATE"):   "SERVICE 不委托任务",
    ("EVOLVER", "DELEGATE"):   "EVOLVER 不委托任务",
    ...
}
```

这个矩阵在 `arcnode-validate --strict` 中硬校验。违反者直接拒绝注册。

### 3.3 Interface Contract — 统一枚举契约

除了类型和关系，还需要统一的项目间通信协议定义：

```python
class TransportProtocol(str, Enum):
    INTERNAL_PYTHON = "internal:python"   # 同进程 Python import
    MCP_STDIO = "mcp:stdio"               # 标准输入输出 MCP
    MCP_SSE = "mcp:sse"                   # 服务端推送事件 MCP
    HTTP_REST = "http:rest"               # RESTful API
    HTTP_WEBHOOK = "http:webhook"         # Webhook 回调
    WS_STREAM = "ws:stream"               # WebSocket 流
    CLI_STDIO = "cli:stdio"               # CLI 子进程
    EVENT_PUBSUB = "event:pubsub"         # 事件发布/订阅
    FILE_PIPE = "file:pipe"               # 文件管道
    GRPC_STREAM = "grpc:stream"           # gRPC 流
```

每个 ARCH_NODE.yaml 的 `provides` 条目必须声明其接口协议。这是 R2/R3 检查的基础——HARD 依赖要求 provider 的 health_check 可达，接口兼容性要求 provides 的超集检查。

### 复盘 3：枚举设计的成本

**问题**: schema.py 维护 7 个枚举类（MetaType、Relation、DependencyLevel、TransportProtocol、Discovery、Role、LifecycleManager）。每次新增一个枚举值需要更新 schema.py + constraints.md + arcnode-validate。

**教训**: 枚举是"共享内核"模式的核心资产，但也是变更成本。在 Phase 1 就定义好所有枚举（哪怕有些初始不用）比 Phase 4-5 再追加更好。因为追加枚举意味着同时更新 schema.py、constraints.md、FORBIDDEN_RELATIONS、TYPE_CONSTRAINTS 四个地方。

**优化**: Phase 7 的 `arcnode-sync-constitution` 就是为了解决"四个地方不同步"的问题。

---

## 4. 约束系统：26 条规则的代码化与执行

### 4.1 约束分层

```
优先级: S (结构) > T (类型) > R (关系) > G (治理)
```

| 类型 | 数量 | 校验方式 | 代码位置 |
|------|------|---------|---------|
| S (Schema — 结构约束) | 8 | `arcnode-validate --strict` | schema.py + validate 脚本 |
| T (Type — 类型约束) | 7 | `arcnode-validate --strict` | schema.py TYPE_CONSTRAINTS |
| R (Runtime — 运行时约束) | 6 | 分散在多个 CLI | hotswap/sniff/evolve |
| G (Governance — 治理约束) | 5 | 流程强制 + cron | register/evolve/report |

### 4.2 约束的执行

每个约束的代码化方式不同：

**S 约束 (结构)**: 在 `arcnode-validate` 中统一校验。

```python
# 示例: S1 — meta_type 必填
if not node.get("meta_type"):
    errors.append("S1 FAIL: meta_type 为必填字段")
if node.get("meta_type") not in ARCH_META_TYPES:
    errors.append(f"S1 FAIL: meta_type 必须为 {ARCH_META_TYPES}")
```

**T 约束 (类型)**: 在 `arcnode-validate --strict` 中校验。

```python
TYPE_CONSTRAINTS = {
    "PROCESSOR": {
        "label": "T1",
        "check": lambda caps: any("task" in str(c).lower() for c in caps),
        "error": "PROCESSOR 必须提供 task-handling 能力",
    },
    ...
}
```

**R 约束 (运行时)**: 分散执行。

- **R2 (HARD 依赖可达)**: `agora-register-node` 的 Step 2b 中校验，通过 HTTP health_check 连通性
- **R3 (接口兼容)**: `agora-update-node` 中校验，通过 provides 集合的超集检查
- **R4 (REPLACE 门禁)**: `agora-hotswap` 的 Step 5 中校验，要求 R2+R3+R10 全部通过
- **R5 (OBSERVE 时效)**: `arcnode-evolve --auto-fix` 中校验，7 天未处理升级
- **R6 (EVALUATE 阈值)**: `arcnode-evolve --self-report` 中校验，< 0.3 触发告警

**G 约束 (治理)**: 流程强制。

- **G1 (双轨校验)**: register-node 的 7 步流水线强制 validate + reason
- **G2 (每日 drift)**: cron `0 5 * * *` 强制每日运行
- **G3 (每周审阅)**: cron `0 9 * * 1` 强制每周 unresolved 审查
- **G4 (自注册)**: `arcnode-evolve --self-report` 检查 governance-system 是否在治理日志中
- **G5 (自记录)**: 治理日志必须包含 governance-system 自身的操作

### 4.3 约束 vs LLM Reasoner 的分工

```
┌──────────────────────────────────────────────┐
│  arcnode-validate (代码硬校验)                │
│  S1-S8, T1-T4, T6-T7, R2-R3                  │
│  → 确定性规则，纯代码执行                      │
├──────────────────────────────────────────────┤
│  arcnode-reason (LLM 软推理)                  │
│  T5 (AGENT 语义检查), O1-O5 (本体论检查)      │
│  → 语义性规则，需要理解上下文                  │
├──────────────────────────────────────────────┤
│  arcnode-evolve (进化引擎)                     │
│  R5-R6 (时效/阈值), G4-G5 (自指)              │
│  → 数据驱动，需要积累 observation              │
└──────────────────────────────────────────────┘
```

这个分层设计的关键洞察是：**不是所有约束都需要代码硬校验**。语义性约束（如"AGENT 必须有 LLM 决策能力"）由 LLM 做软推理，代码只做关键串匹配。这样既保证了可靠性，又保留了灵活性。

### 复盘 4：约束代码化的节奏

**Phase 1**: 18 条约束全部在代码中实现。这是正确的决定——约束体系是治理的根基，延迟代码化意味着宪法与实现分离。

**Phase 4-5**: 追加 8 条约束 (S7-S8, T7, R4-R6, G4-G5)。约束代码化落后于功能实现——hotswap 实现了一周后，R4 才被代码化。这会带来宪法漂移风险。

**优化**: Phase 7 的 `arcnode-sync-constitution` 解决了文档同步问题，但约束代码化仍需要人工在 schema.py 中添加。可以考虑：constraints.md 作为权威源，generate schema.py 从它生成。但代价是增加了构建步骤，目前 26 约束的手动同步是可控的。

---

## 5. 状态机：节点生命周期与热插拔协议

### 5.1 节点状态定义

```
ACTIVE ──→ DRAINING ──→ STANDBY ──→ VERIFYING ──→ ACTIVE (new)
  │                                              │
  └──→ DECOMMISSIONED (old) ←────────────────────┘
```

| 状态 | 定义 | 占时比例 |
|------|------|---------|
| **ACTIVE** | 正常工作，接受请求 | 99% |
| **DRAINING** | 停止新请求，等待 in-flight 完成 | 几秒~30s |
| **STANDBY** | 旧进程暂停，新进程就绪 | 几秒 |
| **VERIFYING** | 运行 R2+R3+R10 验证 | 5~15s |
| **DECOMMISSIONED** | 旧节点标记为废弃 | 永久 |

### 5.2 7 步热插拔协议

`agora-hotswap` 实现了完整的 7 步协议：

```
Step 1: 标记 replacing        → governance log: status=draining
Step 2: 通知 HARD 依赖方      → governance log: dependents 列表
Step 3: 排空 (drain)           → health 端点监视 + startup_duration 超时
Step 4: 启动新进程             → launchd=automatic / manual=脚本输出
Step 5: 验证 (R2+R3+R10)      → 依赖可达 + 接口兼容 + 健康检查
Step 6: 切换路由               → YAML 替换 + git commit
Step 7: 清理旧进程             → governance log: status=decommissioned
```

### 5.3 降级链

```
auto (launchd) → semi-auto (systemd/supervisor) → manual (通知+脚本)
```

每种 lifecycle manager 对应不同的热插拔路径：

| 管理器 | 实现 | 回滚 |
|--------|------|------|
| **launchd** | `launchctl bootout` + `launchctl bootstrap` | KeepAlive 自动重启 |
| **manual** | 生成可执行脚本 + health 轮询验证 | 人工回滚 |
| **ephemeral** | 无需操作（下次自动重建） | 无 |

### 5.4 Drain 机制实现

Drain 不是简单的 `kill -9`，而是优雅排空：

```python
def drain_node(node, timeout_sec=30):
    """排空: 等待 in-flight 完成"""
    time.sleep(startup_duration)  # 给节点处理时间
    
    # 监视 health 端点
    while time.time() - start < timeout_sec:
        try:
            health_check()  # 仍然响应 → 还有 in-flight
        except ConnectionError:
            return True  # 不再响应 → drain 完成
    return False  # 超时 → 回滚
```

关键设计：**health 端点从可达变为不可达 = drain 完成**。这比"等待排空队列为空"更简单可靠（不需要节点支持 drain 统计）。

### 复盘 5：为什么不做连接数计数

**初始方案**: 记录 in-flight 连接数，等 count=0 才认为 drain 完成。

**问题**: 需要每个节点暴露 in-flight 统计 API，侵入性强。

**最终方案**: 等待 health 端点不可达。如果 30s 后 health 仍可达，回滚。

**trade-off**: 简单可靠，但不是"零停机"。如果节点在 30s 内处理不完 in-flight，会有中断。但考虑到所有节点都是内部工具（非用户面服务），30s 足够。

---

## 6. 工具链：15 个 CLI 的完整架构

### 6.1 CLI 全景

15 个脚本（13 个 `arcnode-*` + 2 个 `agora-*`），分布在 `~/.hermes/scripts/` 下，共享 `schema.py`。

```
                                            ┌─────────────┐
                                            │  schema.py  │
                                            │  核心枚举+约束│
                                            └──────┬──────┘
                                                   │
         ┌──────────┬──────────┬──────────┬─────────┴──────┬──────────┐
         │          │          │          │                │          │
    ┌────┴───┐ ┌───┴────┐ ┌──┴────┐ ┌───┴────┐     ┌─────┴─────┐ ┌──┴─────┐
    │validate│ │ reason │ │register│ │ update │ ... │  evolve   │ │  graph  │
    │ S1-S8  │ │ LLM    │ │ 7步    │ │ 4步    │     │ 熵+趋势    │ │ 8种格式 │
    │ T1-T7  │ │推理    │ │流水线  │ │更新    │     │ auto-fix  │ │ C4      │
    └────────┘ └────────┘ └────────┘ └────────┘     │ dashboard │ │Archimate│
                                                    └──────────┘ └─────────┘
```

### 6.2 核心脚本详解

#### schema.py（共享核心）

**大小**: 243 行 | 7 枚举类 | 24 约束定义

所有 `arcnode-*` CLI 的第一行导入：

```python
from arcnode.schema import (
    MetaType, Relation, DependencyLevel,
    TransportProtocol, Discovery, Role, LifecycleManager,
    ARCH_META_TYPES, RELATIONS, DEPENDENCY_LEVELS,
    META_TYPE_FEATURES, FORBIDDEN_RELATIONS, TYPE_CONSTRAINTS,
    is_valid_semver, get_interface_ids, detect_dep_cycle,
)
```

关键函数：
- `detect_dep_cycle(edges)`: Kahn 算法检测依赖环。所有注册操作必须通过此项检查（S3）。
- `get_interface_ids(provides)`: 提取接口 ID 集合。R3 兼容性检查的基础。
- `is_valid_semver(version)`: 语义化版本正则校验。

#### arcnode-validate（约束校验器）

**大小**: ~200 行 | 校验所有 24 约束

校验流程：

```python
def validate(yaml_data, strict=False):
    errors, warnings = [], []
    node = yaml_data.get("architecture_node", yaml_data)
    meta_type = node.get("meta_type")
    
    # S1: meta_type 必填
    if not meta_type or meta_type not in ARCH_META_TYPES:
        errors.append("S1 FAIL: meta_type ...")
    
    # S2: provides 非空
    if not node.get("provides"):
        errors.append("S2 FAIL: provides 不能为空")
    
    # T1-T7: 类型约束
    if strict and meta_type in TYPE_CONSTRAINTS:
        tc = TYPE_CONSTRAINTS[meta_type]
        if not tc["check"](...):
            errors.append(f"{tc['label']} FAIL: {tc['error']}")
    
    # 禁止关系
    for dep in node.get("depends_on", []):
        rel = dep.get("relation", "DEPEND")
        if (meta_type, rel) in FORBIDDEN_RELATIONS:
            errors.append(f"FR FAIL: {FORBIDDEN_RELATIONS[(meta_type, rel)]}")
    
    return errors, warnings
```

#### agora-register-node（7 步注册流水线）

**大小**: 342 行 | 功能：将节点注册到治理体系

```
Step 1: S6 节点唯一性检查       → governance log 中是否已有此 id
Step 2: arcnode-validate --strict  → 24 约束硬门禁
Step 3: S3 依赖环检测           → Kahn 算法
Step 4: R2 HARD 依赖连通性      → HTTP health_check
Step 5: arcnode-reason --json    → LLM 软推理
Step 6: 写入 governance log     → SHA256 链
Step 7: Agora 注册 + R10 健康检查 → 对外暴露
```

**为什么 7 步？** 每步对应一个约束或治理规则。跳过任何一步 = 违反宪法。

#### agora-hotswap（7 步热插拔协议）

**大小**: ~500 行 | 功能：热替换运行中的节点

实现要点：

```python
def hotswap(node_id, new_yaml=None, force=False, dry_run=False):
    # 0. 查找节点
    cur_node = find_registered(node_id)
    # 1. 标记 replacing
    log_governance(action="hotswap", status="draining")
    # 2. 通知依赖方
    dependents = scan_hard_dependents(node_id)
    # 3. Drain
    ok = drain_node(cur_node)
    # 4. 启动新进程 (launchd/manual)
    start_new_process(manager, new_node)
    # 5. 验证 (R2+R3+R10)
    check_r3(old_node, new_node) if not force
    check_r2(new_node)
    check_r10(new_node)
    # 6. 切换路由
    replace_yaml(old_yaml, new_yaml) + git commit
    # 7. 清理
    log_governance(action="hotswap", status="decommissioned")
```

#### arcnode-evolve（进化引擎）

**大小**: ~700 行 | 功能：熵计算、趋势追踪、auto-fix、仪表盘

核心数学模型：

```python
# 节点熵
e(node) = (src_missing * 3 + port_down * 2 + health_fail * 1 + gov_missing * 2) / 8

# 系统熵: 所有节点熵的平均值
E(system) = avg(e(node) for all registered nodes)

# 熵趋势: 当前 vs 首次记录/周数
ΔE/Δt = (latest_entropy - first_entropy) / weeks
```

触发阈值：

| E 范围 | 状态 | 动作 |
|--------|------|------|
| < 0.1 | 健康 | 记录基线 |
| 0.1-0.3 | 注意 | 写入 observation |
| 0.3-0.6 | 警告 | 触发根因分析 |
| ≥ 0.6 | 危机 | 冻结新注册 |

auto-fix 规则：

```python
# 观察置信度积累
same_observation连续3次 → auto-fix触发
confidence_decay = 7天   # 7天无新观察归零
escalation_delay = 14天  # 14天未解决 → 架构债务
```

### 6.3 治理日志：SHA256 链

每条治理日志写入时都会链接前一条的 hash：

```python
def log_governance(entry):
    entry["ts"] = now
    prev_hash = last_entry.get("hash", "")
    entry_str = json.dumps(entry, sort_keys=True)
    chain = f"{prev_hash}{entry_str}"
    entry["hash"] = sha256(chain.encode())[:16]
    append_to_file(entry)
```

这意味着：
- 日志不可篡改（修改任何一条 → 后续所有 hash 失效）
- 可溯源（从最近一条往前可验证全部历史）
- 轻量（16 字符 hash，JSONL 格式）

### 6.4 Cron 链：无人类干预的自维护

```
每日 5:00 drift-check        (no_agent)
每日 6:00 evolve             (agent)
每日 6:05 sniff              (no_agent)
每日 6:10 dep-aging          (no_agent)
每日 6:20 sync-constitution  (no_agent)

周一 7:00 graph (含C4)       (agent)
周一 9:00 resolve            (no_agent)
周一 9:30 report+dashboard   (agent)
```

**no_agent vs agent**: no_agent 脚本直接输出 stdout（零 token 成本），agent 脚本由 LLM 驱动（需要推理）但每次 ~2000 tokens。8 道 cron 中 5 道 no_agent = 每日运行成本 ~0.01 美元。

### 复盘 6：为什么不是单一 CLI

**问题**: 为什么 15 个 CLI 而不是一个 `aamf` 主命令？

**原因**:
1. 每个 CLI 专注一个职责（Unix 哲学）
2. 独立 cron：每个 cron 调用一个 CLI，不需要解析子命令
3. 独立调试：试错不影响其他功能
4. no_agent 支持：脚本可直接被 cron 调用

**成本**: 15 个文件 vs 1 个文件的维护成本确实更高。但每个文件平均 200-500 LOC，管理成本可接受。

---

## 7. 视图层：C4 + Archimate + 仪表盘

### 7.1 六种视图输出

```
arcnode-graph --format mermaid   → MD 文档嵌入图
arcnode-graph --format dot       → Graphviz 矢量图
arcnode-graph --format html      → vis.js 交互式图
arcnode-graph --format json      → 结构化数据

arcnode-graph --format c4        → C4 四层视图
  --level context                → 系统边界图
  --level container              → 节点拓扑图
  --level component              → 组件详情
  --level code                   → 声明级

arcnode-graph --format archimate → 三层分层视图

arcnode-evolve --dashboard       → 交互式健康仪表盘
```

### 7.2 C4 Context 视图

最简单的视图，只有 4 个元素：

```
👤 架构师 (人类) ←→ ⚙️ governance-system (EVOLVER)
                      ↓
                26 节点 (管理)
                      │
                外部依赖: eCOS/Minerva/Hermes
```

**设计要点**: 不显示所有节点，只显示系统边界。C4 Context 的目标是让新人 30 秒理解系统做什么。

### 7.3 C4 Container 视图

按 MetaType 分组的 26 节点拓扑：

```
EVOLVER (1)      PROCESSOR (8)     SERVICE (5)
governance-system agent-runtime     agora
                   kos              iris
                   minerva          agentmesh
                   ...              ...

依赖关系 (红色=HARD, 黄色=SOFT):
🔴 gateway → agora
🟡 agent-runtime → agora
🟡 kronos → kos
...
```

**实现**: 两栏布局，左侧按类型分组，右侧依赖列表。~13KB HTML，无外部依赖。

### 7.4 C4 Component 视图

每个节点的 provides/depends_on 详情卡片：

```
┌──────────────────────────────────────┐
│ agent-runtime (PROCESSOR v1.0.0)    │
│ provides:                            │
│  [runtime.run-task] [runtime.chat]   │
│  [runtime.health] [runtime.mcp-tools]│
│ depends_on:                          │
│  [deepseek-llm] [agora] [kos] [minerva]
└──────────────────────────────────────┘
```

**实现**: CSS grid 布局，每个节点一张卡片，类型颜色编码。

### 7.5 C4 Code 视图

每个节点的完整 ARCH_NODE.yaml JSON 声明。~36KB——最大的 HTML 文件。适合调试用。

### 7.6 Archimate 三层视图

```
🏛️ Business Layer         宪法修订 · 热插拔审批 · 审计 · 进化引擎
                            ↓ governance-system (EVOLVER)
📋 Application Layer       12 CLI 工具 (validate→reason→register→...)
                            ↓ 运行于
🖥️ Technology Layer        YAML · governance log · Git · launchd · Mac mini
```

**设计要点**: Archimate 标准定义了 3 层 + 关系矩阵（Assignment/Realization/Flow）。这里只用了 3 层分组，没有实现完整的 Archimate 关系——因为完整的 Archimate 模型需要专门的建模工具，纯 HTML 实现 30% 的关系就够用。

### 7.7 健康仪表盘

5 个 Plotly.js 交互式图表：

```
┌─ 统计卡片(4) ──────────────────────────────────┐
│ 架构熵: 0.0   处理速度: 0%   节点: 26   热插拔: 0 │
├──────────────────────┬─────────────────────────┤
│ 熵趋势(折线图)        │ 类型分布(饼图)            │
├──────────────────────┴─────────────────────────┤
│ 节点健康热力图 (26节点×4维度)                      │
├────────────────────────────────────────────────┤
│ 决策追溯时间线 (最近50条治理事件)                    │
└────────────────────────────────────────────────┘
```

**实现**: 纯 HTML + Plotly.js CDN。无后端依赖，浏览器直接打开。~15KB。

热力图的维度设计：

| 维度 | 含义 | 检测方式 |
|------|------|---------|
| 源代码 | 源代码路径是否存在 | `Path.exists()` |
| 端口 | 声明端口是否在监听 | `lsof -iTCP -sTCP:LISTEN` |
| 健康 | health_check 是否可达 | `HTTP GET` |
| 治理 | 是否在 governance log 中 | 日志扫描 |

4 个维度 × 3 种权重 = 熵值公式中的 `src_missing*3 + port_down*2 + health_fail*1 + gov_missing*2`。权重设计反映影响严重程度：源代码丢失最严重（整个节点没了），健康检查失败最轻（可能只是临时波动）。

### 复盘 7：视图层的价值

**问题**: 在命令行体系（15 CLI）已经能完全控制治理体系的情况下，为什么还需要 6 个 HTML 视图？

**答**: CLI 适合**运维**（日常巡检、注册、热插拔），HTML 视图适合**汇报**（周报、审计、新人入门）。

具体场景：
- 每天 5:00 drift-check 用 CLI（自动化）
- 每周一 9:30 report+dashboard 用 HTML（人类阅读）
- C4 Context 图用在架构文档中（解释性）
- C4 Code 图用在调试场景中（排查问题）

---

## 8. 自指机制：治理系统管理自身

### 8.1 问题

传统管理系统的架构通常是：

```
管理系统 → 管理 → 被管理系统
              ↑
         管理系统自身不受管理
```

这在架构上的问题是：**管理系统的架构变更不透明、不可追溯、不受约束。**

### 8.2 解决：governance-system 自注册

governance-system 注册为 EVOLVER 类型节点，受同一宪法约束：

```yaml
architecture_node:
  id: "governance-system"
  meta_type: EVOLVER
  provides:
    - id: "governance.validate"
    - id: "governance.drift-check"
    - id: "governance.evolve"
    - id: "governance.hotswap"
    - id: "governance.constitution"
  depends_on:
    - id: "agent-runtime"    # LLM Reasoner 依赖 (SOFT)
      dependency: SOFT
  lifecycle:
    manager: "manual"
  governance:
    audit_events: true
```

这意味着：
1. governance-system 的变更必须通过 `agora-update-node`（走 R3 兼容性检查）
2. governance-system 的漂移会被 `arcnode-drift-check` 检测
3. governance-system 可以被 `agora-hotswap` 替换（自指）
4. governance-system 的操作记录在 governance log 中（G5）

### 8.3 L4 自我层的三层能力

```
Level 1 — 自描述
  能力: 生成自身架构报告、依赖图包含自身节点
  验证: arcnode report 中包含 "governance-system" ✅

Level 2 — 自评价  
  能力: 评估自身治理有效性
  指标: 约束违反率、观察处理速度、治理时效性、往返时间、宪法年龄
  验证: arcnode-evolve --self-report ✅

Level 3 — 自进化
  能力: 宪法文档自动同步、宪法修订流水线、自指热插拔
  验证: 
    arcnode-sync-constitution --check ✅
    arcnode amend --proposal "R7" → 提议→确认→应用 ✅
    agora hotswap governance-system --dry-run ✅
```

### 8.4 自指热插拔的验证

```bash
agora hotswap governance-system --dry-run
```

输出 7 步骤，其中关键步骤：

```
Step 2: 通知 HARD 依赖方 → governance-system 无 HARD 依赖方
Step 4: 启动新进程 → manager=manual, 生成执行脚本
Step 5: 验证 → R2+R10 全部通过
```

**为什么自指热插拔可行？** 因为 `agora-hotswap` 是 CLI 工具，执行时不依赖 governance-system 的运行时状态。CLI 读取 YAML 文件、调用 launchctl、写入 governance log——所有这些操作都不需要 governance-system 进程在运行。

### 复盘 8：自指的哲学含义

**问题**: 一个系统管理自身是否会导致无限递归？

**答**: 不会。因为自指有三个层级，每层有明确的边界：
1. 自描述：读取自己的 YAML 文件（无递归）
2. 自评价：运行熵计算（无递归，熵计算不需要 governance-system 运行）
3. 自进化：热插拔 CLI 独立于 governance-system 进程（无递归）

关键是：**治理系统的运行时 ≠ 治理系统的代码。** 运行时可以替换，代码在 git 中。自指操作的是运行时，不涉及代码自身的修改。

---

## 9. 数据流：从 sniff 到 auto-fix 的闭环

### 9.1 完整数据流

```
lsof -iTCP
    ↓
arcnode-sniff-deps
    │
    ├── 检测未声明连接 → observation (status=missing_declaration)
    ├── 检测HARD dep离线 → observation (status=runtime_drift)
    │
    ↓ (每日6:05)
arcnode-sniff-deps --reconcile --auto-fix
    │
    ├── 连续3次 same observation → auto-fix触发
    │     ↓
    │   YAML追加 dependency
    │     ↓
    │   governance log: action=auto-fix
    │
    └── HARD dep offline → 只记录不修复（需人工确认）
    │
    ↓ (每日6:10)
arcnode-dep-aging
    │
    └── 7天无连接 → observation (status=idle-dep-warning)
    └── 30天无连接 → 自动降级 SOFT→OPTIONAL
```

### 9.2 observation 的数据结构

```json
{
  "action": "observation",
  "node_id": "agent-runtime",
  "description": "undeclared connection to agora:7430",
  "status": "missing_declaration",
  "ts": "2026-05-26T06:05:00+00:00",
  "hash": "a1b2c3d4"
}
```

每次 sniff 运行写入一条 observation。三次后 auto-fix 触发。

### 9.3 auto-fix 决策逻辑

```python
def auto_fix_observations():
    observations = group_by(node_id, description, status)
    
    for (nid, desc, status), entries in observations.items():
        count = len(entries)
        if count < 3:
            continue  # 置信度不足
        
        if "HARD dep offline" in desc:
            print(f"⚠️ 需人工确认: {nid} HARD dep offline")
            continue  # 不自动修复
            
        if "undeclared connection" in desc:
            target = parse_target(desc)
            yaml_file = find_yaml(nid)
            append_dependency(yaml_file, target, "SOFT")
            log_governance(action="auto-fix", ...)
            auto_fixed += 1
```

**为什么 HARD dep offline 不 auto-fix？** 因为 HARD 依赖离线可能有多种原因（服务宕机、网络中断、配置错误），自动追加依赖可能掩盖真正的问题。undeclared connection 是"有运行时连接但未声明"，100% 应该修复。

### 9.4 闭环的数学保证

```
auto_fix_threshold = 3     # 连续 3 次 observation → auto-fix
confidence_decay = 7 days  # 7 天无新 observation → 置信度归零
escalation_delay = 14 days # 14 天未解决 → 升级为架构债务
```

3 次 threshold 的设计：1 次可能是误报，2 次可能是巧合，3 次就是模式。

---

## 10. 复盘：56x 偏差、设计缺陷、未解决的问题

### 10.1 最大的偏差：56x 工时估算

| 维度 | 原计划 | 实际 |
|------|--------|------|
| 总 Phase | 7 | 7 |
| 总工时 | 10 周 | 10.5 小时 |
| CLI 数量 | ~10 | 15 |
| 约束数量 | 18 | 26 |
| 文档产出 | 7 | 11 |
| 每 Phase 平均 | ~10 天 | ~1.5 小时 |

**教训**: LLM 辅助开发时代，工时估算是伪命题。更好的做法是：列出 todos，逐个实现，不提前估算。

### 10.2 设计缺陷

#### 缺陷 1：宪法文档 vs 代码的双轨维护

Q4 之前，宪法文档（constraints.md）和代码（schema.py）由不同机制维护。文档是手动编辑，代码是手动编辑。两者不同步是常态。

**修复**: Phase 7 的 `arcnode-sync-constitution`。

**根本解决**: schema.py 应该是权威源，constraints.md 从它生成。但当前 26 约束的手动同步已足够。

#### 缺陷 2：枚举变更的成本

新增一个 MetaType（如 Phase 4 的 EVOLVER）需要同时修改：
1. `schema.py` — MetaType 枚举
2. `schema.py` — META_TYPE_FEATURES
3. `schema.py` — TYPE_CONSTRAINTS
4. `schema.py` — FORBIDDEN_RELATIONS
5. `constraints.md` — 对应 T 约束
6. `arcnode-validate` — 验证逻辑（如果需要）
7. 已有的 ARCH_NODE.yaml 文件（可能需要添加类型）

7 个地方。这是架构治理的成本。

#### 缺陷 3：没有回溯兼容性检查

R3 只检查升级（新 provides 必须包含旧 provides 的超集），但不检查降级。如果节点 v2.0.0 移除某个接口但 v1.0.0 有依赖方，`agora-hotswap` 的 `--force` 可以绕过。治理日志会记录但不会阻止。

**未修复**: 这是一个 conscious trade-off。紧急情况下 force 是必要的。

### 10.3 未解决的问题

#### Q1: 跨机器拓扑（X2 剩余 40%）

AAMF 目前运行在单台 Mac mini M4 上。实际有 MBP M5 Max（开发机）和 Y7000P 48GB（游戏机），但治理体系不感知跨机器拓扑。

**未来**: 如果需要，可以在 ARCH_NODE.yaml 中添加 `deployment.host` 字段，然后在 drift-check 中 SSH 到目标机器检查。

#### Q2: 架构模式识别（7.3）

等 3 个月数据积累。31 条治理日志不足以做模式识别。需要至少 200+ 条才能看出趋势。

#### Q3: LLM Reasoner 降级

`arcnode-reason` 调用 Agent Runtime 的 HTTP API，超时 30s。如果 Agent Runtime 不可用，注册跳过 reason 步骤（G1 降级）。但 G1 要求"必须经过 validate + reason"，降级是否违反宪法？

**当前**: 超时跳过 reason 但会记录 observation。这是一个未解决的紧张关系：G1 要求双轨校验，但运行时可用性无法 100% 保证。

### 10.4 什么是对的

**1. schema.py 作为共享核心** — 一个文件定义所有枚举和约束，所有 CLI 共享。这是整个体系的基础设施复用。

**2. SHA256 链式治理日志** — 不可篡改、可追溯、轻量。28 字节日志开销。

**3. engine/actor 分类** — EVOLVER 是 engine（接受指令），AGENT 是 actor（自主决策）。这个区分防止了治理系统自作主张。

**4. 3 次 observation 触发** — 平衡了灵敏度和可靠性。1 次是噪声，2 次是巧合，3 次是模式。

**5. no_agent cron** — 80% 的治理任务零 token 成本运行。只有需要 LLM 推理的任务（evolve/report）才消耗 tokens。

---

## 附录 A：代码量统计

```
~/.hermes/scripts/
├── schema.py                 243 LOC  (共享核心)
├── arcnode-validate          200 LOC  (约束校验)
├── arcnode-reason            150 LOC  (LLM 推理)
├── agora-register-node       342 LOC  (7 步注册)
├── agora-update-node         229 LOC  (4 步更新)
├── agora-hotswap             500 LOC  (7 步热插拔)
├── arcnode-graph             650 LOC  (8 种格式)
├── arcnode-graph-html        300 LOC  (vis.js 交互图)
├── arcnode-drift-check       292 LOC  (四维漂移)
├── arcnode-sniff-deps        450 LOC  (运行时嗅探)
├── arcnode-dep-aging         200 LOC  (依赖时效)
├── arcnode-resolve-review    150 LOC  (unresolved 审阅)
├── arcnode-report            350 LOC  (周报)
├── arcnode-evolve            700 LOC  (进化引擎+仪表盘)
├── arcnode-sync-constitution 250 LOC  (宪法同步)
└── arcnode-amend             200 LOC  (宪法修订)
───────────────────────────────────────
总计: ~4,800 LOC
```

## 附录 B：文档索引

```
~/Documents/学习进化/基建架构/
├── 18-深度架构审计-AAMF.md               Phase 0 审计
├── 19-Phase1-深度复盘+架构债务审计+红队分析.md  Phase 1
├── 22-Phase2-深度复盘+架构债务审计+红队分析.md  Phase 2
├── 23-Phase3-深度复盘+架构债务审计+红队分析.md  Phase 3
├── 24-AAMF-v2-全面架构补全方案.md         Phase 4-7 方案
├── 26-Phase5-深度复盘+热插拔协议审计.md       Phase 5
├── 27-Phase6-细化方案.md                  Phase 6 方案
├── 28-Phase6-深度复盘+依赖自动维护+视图审计.md Phase 6
├── 29-AAMF-全面复盘+Phase7修订方案.md     全体系复盘
├── 30-Phase7-深度复盘+AAMF最终审计.md     最终验收
└── 31-AAMF-深度技术文档.md                ← 本文
```

## 附录 C：治理登录

```
~/Documents/学习进化/基建架构/宪法/
├── constraints.md            26 条约束定义（宪法组成部分）
├── meta_types.md             元模型类型定义
├── interface_contract.md     接口契约枚举
├── WORKSPACE_ARCHITECTURE_CONSTITUTION.md 工作区宪法
└── project-review.md         项目审查

~/.hermes/architecture/
├── arch_nodes/               28 个 ARCH_NODE.yaml
├── governance_log/
│   ├── governance.jsonl      33 条 SHA256 链式治理日志
│   ├── entropy-trend.json    架构熵历史
│   ├── last-drift.json       漂移检测快照
│   ├── runtime-deps.json     运行时依赖快照
│   ├── dashboard.html        交互式健康仪表盘
│   ├── c4_context.html       C4 Context 视图
│   ├── c4_container.html     C4 Container 视图
│   ├── c4_component.html     C4 Component 视图
│   ├── c4_code.html          C4 Code 视图
│   └── archimate.html        Archimate 视图
├── hotswap_scripts/          热插拔执行脚本
└── ARCHITECTURE.md           Mermaid 依赖图
```

---

> **文档位置**: `~/Documents/学习进化/基建架构/31-AAMF-深度技术文档.md`
> **关联**: #18-#30 全系列文档
> **版本**: AAMF v2.0（治理体系最终版）
