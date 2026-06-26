# AetherForge L0 M1 消费鸿沟审计 (TASK-13AD0B21)

> **日期**: 2026-06-26
> **审计范围**: ecos L0 M1 命名空间 vs AetherForge 实际消费
> **病根同构**: 与 [[bos-decl-exec-gap]] (BOS 声明/执行鸿沟) 同病 — 定义层丰富 / 执行层薄弱
> **结论**: M1 有 43 命名空间 / 1195 yaml, AetherForge 只消费 5 个 (3.3%), 38 个 (96.7%) 未接入

---

## 1. 执行摘要

AetherForge 作为 L0 集群引擎, 理应深度消费 ecos M1 SSOT (单一事实源), 但实测消费率仅 **3.3%** (5/43 命名空间). 高价值命名空间 (agent/protocol/mechanism/workflow/skill/decision) 全部未接入, 导致:

- **蜂群 worker** 硬编码, 不读 M1 `agent/` (22 个 worker 定义)
- **A2A/ACP 通信** 自实现, 不读 M1 `protocol/` (10 个协议定义)
- **调度策略** 硬编码, 不读 M1 `mechanism/` (66 个机制定义)

这是"定义层丰富 / 执行层薄弱"的典型 — 和 BOS 声明/执行鸿沟 (102:0) 同构. 治本: 扩 AetherForge M1 loader, 接入高价值命名空间.

---

## 2. M1 命名空间全景 (43 子目录 / 1195 yaml)

实测 `projects/ecos/src/ecos/ssot/mof/m1/` 全量统计 (按 yaml 数降序):

| 命名空间 | yaml 数 | 语义 | AetherForge 消费 |
|----------|:------:|------|:---------------:|
| lesson | 138 | 教训库 | ❌ |
| entity | 136 | 实体定义 | ❌ |
| specification | 122 | 规格定义 | ❌ |
| omo_layer | 101 | OMO 层 | ❌ |
| component | 88 | 组件 | ❌ |
| bosroute | 77 | BOS 路由 | ❌ |
| **mechanism** | **66** | **机制 (调度策略)** | **❌ P0** |
| mcptool | 62 | MCP 工具 | ❌ P1 |
| **skill** | **61** | **技能 (worker 能力)** | **❌ P1** |
| artifact | 61 | 制品 | ❌ |
| **workflow** | **29** | **工作流** | **❌ P0** |
| domain | 28 | 域 | ❌ |
| governance | 25 | 治理 | ❌ |
| **agent** | **22** | **Agent (蜂群 worker)** | **❌ P0** |
| process | 20 | 流程 | ❌ |
| **decision** | **15** | **决策 (仲裁者)** | **❌ P1** |
| **compute_engine** | **14** | **计算引擎 (endpoint)** | **✅** |
| service | 13 | 服务 | ❌ |
| **model** | **13** | **模型 (MODEL-BREW-*)** | **✅** |
| lifecycle | 11 | 生命周期 | ❌ |
| convention | 11 | 约定 | ❌ |
| trigger | 10 | 触发器 | ❌ |
| **protocol** | **10** | **协议 (A2A/ACP)** | **❌ P0** |
| pattern | 9 | 模式 | ❌ P2 |
| cognitive_framework | 6 | 认知框架 | ❌ |
| action | 6 | 动作 | ❌ |
| **network_zone** | **5** | **网络区** | **✅** |
| intent | 4 | 意图 | ❌ |
| **hardware_asset** | **4** | **硬件资产** | **✅** |
| **compute_node** | **4** | **计算节点** | **✅** |
| architecture | 4 | 架构 | ❌ |
| 其他 12 个 | 各 1-3 | (routing_policy/quota/outcome/...) | ❌ |

**消费汇总**: ✅ 5 个 (compute_engine + model + compute_node + hardware_asset + network_zone, 共 ~40 yaml, 3.3%) / ❌ 38 个 (96.7%)

---

## 3. AetherForge 当前消费路径 (已接入)

消费入口: `projects/aetherforge/packages/gateway/src/llm_gateway/ssot_loader.py`

```
ssot_loader.py 消费 M1 三层:
  1. compute_engine/  → "where" (endpoint, protocol) — 算力引擎定位
  2. model/           → "what" (MODEL-BREW-*.yaml, model_id/pricing/capabilities) — 模型规格
  3. CredentialsManager → "how" (API keys/base_url) — 凭证
```

合成: `SSOTProviderAdapter` 三层合一 → 统一 provider → `ModelScheduler` 调度.

**消费的命名空间** (5 个):
- `compute_engine/` (14) — endpoint 定义
- `model/` (13) — MODEL-BREW-* 模型规格
- `compute_node/` (4) — 节点
- `hardware_asset/` (4) — 硬件
- `network_zone/` (5) — 网络区

**消费方式**: `glob.glob(MODEL-BREW-*.yaml)` + `yaml.safe_load` (非 import ecos, 直接读 yaml 文件).

---

## 4. 高价值未接入命名空间 (推荐优先级)

### P0 — 蜂群/网关核心, 接入收益最高

| 命名空间 | yaml | AetherForge 对应 | 接入价值 |
|----------|:----:|------------------|----------|
| **agent** | 22 | swarm worker 定义 | 蜂群 worker 不再硬编码, 读 M1 agent/ 生成 worker 拓扑 |
| **protocol** | 10 | A2A/ACP 通信 | 通信协议 SSOT 化, 不再自实现 a2a_protocol.py |
| **mechanism** | 66 | 调度策略 (RouteScheduler) | 调度机制 SSOT 化, RouteScheduler 读 mechanism/ 配置 |
| **workflow** | 29 | 任务工作流 | 工作流定义 SSOT, lifecycle_manager 消费 |

### P1 — 蜂群辅助, 中等收益

| 命名空间 | yaml | AetherForge 对应 | 接入价值 |
|----------|:----:|------------------|----------|
| **skill** | 61 | worker 能力声明 | worker 技能 SSOT, 匹配任务-skill |
| **decision** | 15 | 仲裁者 (arbiter) | 决策规则 SSOT, 拍卖仲裁读 decision/ |
| **mcptool** | 62 | gateway 工具暴露 | MCP 工具 SSOT, gateway 自动注册 |

### P2 — 长尾, 按需接入

pattern(9) / service(13) / component(88) / entity(136) — 与蜂群关联弱, 按需.

---

## 5. 接入方式建议 (仿 ssot_loader 模式)

### 模式: 每命名空间一个 loader (SRP)

```python
# projects/aetherforge/packages/gateway/src/llm_gateway/m1_agent_loader.py (新建)
"""M1 agent/ loader — 消费 agent/ yaml 生成蜂群 worker 拓扑.

仿 ssot_loader.py 模式: glob + yaml.safe_load + 合成.
"""
def load_agent_topology(m1_agent_dir: str) -> dict[str, AgentDescriptor]:
    """读 AGENT-AGENTS-*.yaml → worker 拓扑 (替代硬编码 worker 定义)."""
    ...
```

### 接入点 (AetherForge 现有架构)

| AetherForge 模块 | 当前硬编码 | 接入 M1 后 |
|------------------|-----------|-----------|
| `swarm/worker_dispatcher.py` | 硬编码 worker | 读 `agent/` |
| `swarm/a2a_protocol.py` | 自实现协议 | 读 `protocol/` |
| `gateway/route_scheduler.py` (TASK-02788FE2 P0) | 硬编码策略 | 读 `mechanism/` |
| `swarm/lifecycle/lifecycle_manager.py` | 硬编码流程 | 读 `workflow/` |

---

## 6. 风险与前置条件

| 风险 | 影响 | 缓解 |
|------|------|------|
| AetherForge 并发 agent 活跃 (ARCH 清理 + 拆分) | 接入改动冲突 | 用 AdvisoryLock ([[concurrent-agent-contention]]) 保护, 或等并发停 |
| M1 schema 漂移影响 AetherForge | 接入后 M1 变化 break aetherforge | 接入加 schema 校验 (仿 ssot_loader 的 try/except 容错) |
| 接入增加 L0 → L2 耦合 | aetherforge 强依赖 ecos M1 | 已有 (_paths.py M1 dir 定位), 接入是深化非新增 |

### 前置条件
- RouteScheduler (TASK-02788FE2 P0) 实现后, mechanism/ 接入才有消费者
- AdvisoryLock 已落地 (TASK-94BB9C70), 接入改动可用锁保护

---

## 7. 价值评估 (Meadows 杠杆点)

接入 M1 命名空间 = **杠杆点 2 (范式)** + **杠杆点 7 (规则)**:
- 范式: 从"硬编码 worker/协议/策略"转向"SSOT 驱动" (同 BOS 鸿沟治本)
- 规则: M1 成为唯一事实源, AetherForge 执行层消费它 (声明/执行收口)

**预期收益**:
- 蜂群 worker 拓扑可配置 (改 M1 agent/ 即调整, 不改代码)
- 调度策略 SSOT (mechanism/ 驱动 RouteScheduler)
- 与 eCOS 其他子系统 (omo/metaos) 共享 M1 定义, 消除重复

---

## 8. 下一步 (可操作)

| 步骤 | 范围 | 前置 |
|------|------|------|
| 1. agent/ 接入 (P0) | 新建 m1_agent_loader.py + worker_dispatcher 消费 | AdvisoryLock 保护, aetherforge 无并发 |
| 2. protocol/ 接入 (P0) | a2a_protocol 读 protocol/ | 同上 |
| 3. mechanism/ 接入 (P0) | RouteScheduler (TASK-02788FE2) 实现后接入 | RouteScheduler done |
| 4. workflow/ 接入 (P0) | lifecycle_manager 消费 | 同上 |
| 5. skill/decision/mcptool (P1) | 蜂群辅助 | P0 接入稳定后 |

**本审计完成 TASK-13AD0B21 deliverable (分析基础)**. 实际接入 (提升消费率 3.3%→目标 30%+) 需 aetherforge 专项 session + RouteScheduler 前置.

---

## 附录: 实测命令

```bash
# M1 命名空间统计
find projects/ecos/src/ecos/ssot/mof/m1 -name "*.yaml" -not -name "*snapshot*" | wc -l  # 1195
for d in projects/ecos/src/ecos/ssot/mof/m1/*/; do echo "$(find $d -name *.yaml | wc -l) $(basename $d)"; done | sort -rn

# AetherForge 消费入口
rg -l "load_ssot_models|compute_engine|MODEL-BREW" projects/aetherforge/packages/gateway/src/  # ssot_loader.py
```

---

*审计者: 老王 · 2026-06-26 · TASK-13AD0B21 分析 deliverable · 纯只读, 未改 aetherforge 代码*
