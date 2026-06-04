# Safe Mesh / RBAC Deployment Roadmap

> 日期: 2026-05-30 | 版本: v1.0 | 状态: active
> 里程碑: M2.6 | 优先级: P2 | 风险级别: L0
> 依据: `.omo/standards/operation-levels.md`, `.omo/standards/agent-registry-heartbeat.md`
> 本文件定义 Safe Mesh 的全量部署路线图，包含 RBAC 模型设计及其与已有组件的集成点。

---

## 1. 什么是 Safe Mesh

Safe Mesh 是 Agora Service Mesh 的安全控制面，由四层相互咬合的组件构成：

```
┌─────────────────────────────────────────────────────────────────┐
│                     Safe Mesh 控制面                              │
│                                                                  │
│   ┌──────────────────────┐  ┌──────────────────────────────┐    │
│   │  L0-L3 Operation     │  │  Agent Registry Heartbeat    │    │
│   │  Levels              │  │  + Cache + Zombie Detection │    │
│   │                      │  │                              │    │
│   │  Read-Only           │  │  60s heartbeat interval     │    │
│   │  Low-Risk Write      │  │  3-miss → zombie            │    │
│   │  High-Risk Write     │  │  24h → dead / auto-dereg    │    │
│   │  Destructive         │  │  Local cache 15min max      │    │
│   └──────────┬───────────┘  └──────────────┬───────────────┘    │
│              │                              │                    │
│   ┌──────────▼──────────────────────────────▼───────────────┐   │
│   │              Identity Gate (Agent Identity Token)         │   │
│   │  JWT-signed: {agent_id, agent_type, role, capabilities}  │   │
│   │  24h expiry, HMAC anti-forgery, timestamp+nonce anti-replay│  │
│   └────────────────────────┬──────────────────────────────────┘  │
│                            │                                     │
│   ┌────────────────────────▼──────────────────────────────────┐  │
│   │  RBAC (Role-Based Access Control) ← NEW for this roadmap  │  │
│   │  Maps: agent_type/role → operation_level + domain + tool  │  │
│   └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**已有设计（M2.2 已完成）：**
- Operation Levels [operation-levels.md](.omo/standards/operation-levels.md)
- Agent Registry Heartbeat + Identity Gate [agent-registry-heartbeat.md](.omo/standards/agent-registry-heartbeat.md)

**本计划新增设计（M2.6）：**
- RBAC 模型定义（角色、权限、策略）
- RBAC 与现有组件的集成点
- 全量部署路线图（6 Wave）

---

## 2. 当前状态基线

| 组件 | 状态 | 交付物 |
|------|------|--------|
| L0-L3 Operation Levels | ✅ 设计完成，已合并 | `operation-levels.md` + `operation-level-rollout-plan.md` |
| First-wave candidate tools | ✅ 已识别 | 5 tools: search_knowledge(L0), run_indexer-incremental(L1), run_indexer-full(L2), delete_page(L2), db_vacuum(L3) |
| Deny Path 标准 | ✅ 已定义 | L2: `_confirmed:true`, L3: +24h cooldown |
| Audit Log Schema | ✅ 已定义 | YAML entry schema with timestamp/actor/tool/level/reason |
| Agent Registry Heartbeat | ✅ 设计完成 | 60s interval, 3-miss zombie, local cache 15min |
| Identity Token Schema | ✅ 已定义 | JWT: agent_id, agent_type, capabilities, issued_at, expires_at |
| Deadlock Detection | ✅ 已定义 | 30min timeout, heartbeat miss, duplicate task, circular dependency |
| Registry 不可达降级 | ✅ 已定义 | <5min cache write, 5-15min reject writes, >15min safe mode |
| **RBAC 模型** | ❌ 待定义 | **本计划的核心交付** |
| **Deny Path 代码实现** | ❌ 待实现 | 需在 Agora + agentmesh Gateway 中落地 |
| **Heartbeat 代码实现** | ❌ 待实现 | 需在 agentmesh Gateway + 各 Agent 中落地 |
| **Identity 签发流程** | ❌ 待实现 | Registry 签发、Agent 续期、吊销 |

---

## 3. RBAC 模型设计（NEW）

### 3.1 角色定义

| 角色 | 描述 | 最大 Op Level | 可操作域 | 需审批 |
|------|------|:-----------:|---------|:------:|
| `reader` | 只读查询 | L0 | 所有域 | 否 |
| `operator` | 常规运维操作 | L1 | 所有域 | 否（审计即可） |
| `curator` | 内容管理 | L2 | 指定域 | L2 需确认 |
| `admin` | 系统管理 | L3 | system 域 | L2+L3 需确认+冷静期 |
| `auditor` | 审计追踪 | L0 | audit 日志 | 否 |

### 3.2 默认角色映射

| Agent 类型 | 默认角色 | 说明 |
|-----------|:-------:|------|
| `research` | `reader` | 研究 Agent，仅需搜索和获取知识 |
| `indexer` | `operator` | 索引 Agent，需要增量同步、添加标签 |
| `gateway` | `operator` | 网关 Agent，需要转发请求和注册服务 |
| `orchestrator` | `curator` | 编排 Agent，需要管理内容和调度任务 |
| `system` | `admin` | 系统 Agent，需要维护和配置 |
| `human` | `admin` | 人类操作者，通过 CLI 或 UI |

### 3.3 Agent 类型 → 允许的 Tool 类别

```
research (reader):
  ✅ L0: search_knowledge, get_knowledge, get_page, list_pages,
          get_entity, get_relation, list_services, check_health
  ❌ L1+: all writes blocked

indexer (operator):
  ✅ L0: all read tools
  ✅ L1: run_indexer(incremental), cross_domain_sync, add_tag,
          remove_tag, register_service (auto)
  ❌ L2+: delete, full reindex, unregister

orchestrator (curator):
  ✅ L0-L1: all above
  ✅ L2 (with _confirmed): run_indexer(full), delete_page,
          unregister_service, ontology_rebuild
  ❌ L3: db_vacuum, db_drop, registry_db_reset

system (admin):
  ✅ L0-L3: all tools, with deny path checks
```

### 3.4 RBAC 检查流程

```
Agent Request
  │
  ├─► 1. Decode identity_token (JWT)
  │     ├─ agent_id, agent_type, role
  │     └─ Verify HMAC signature
  │
  ├─► 2. Operation Level Check
  │     ├─ role.max_level ≥ tool.level? → continue
  │     └─ role.max_level < tool.level? → DENY
  │
  ├─► 3. Tool Allowlist Check
  │     ├─ role.allowed_tools contains tool? → continue
  │     └─ not allowed → DENY
  │
  ├─► 4. Domain Allowlist Check (if scoped)
  │     ├─ role.allowed_domains contains domain? → continue
  │     └─ not allowed → DENY
  │
  ├─► 5. Operation Level Deny Path
  │     ├─ L1: audit log (auto)
  │     ├─ L2: _confirmed:true required
  │     └─ L3: _confirmed:true + 24h cooldown

  └─► 6. Audit Log: result = allow|deny
```

### 3.5 Identity Token 扩展

当前 `agent-registry-heartbeat.md` §4.1 的身份令牌 schema 需要扩展 `role` 字段：

```yaml
# Extended Agent Identity Token
agent_id: str                    # 唯一标识
agent_type: str                  # "research" | "indexer" | "gateway" | "orchestrator" | "system"
role: str                        # "reader" | "operator" | "curator" | "admin" | "auditor"
capabilities: [str]              # 向后兼容，由 role 派生
allowed_domains: [str] | null    # null = all domains
identity_token: str              # JWT or HMAC-signed
issued_at: ISO-8601
expires_at: ISO-8601             # 默认 24h
public_key: str                  # 用于签名验证
```

### 3.6 RBAC 集成点总结

| 集成点 | 组件 | 变更内容 |
|--------|------|----------|
| I1 | Agora Registry | 注册时接受 `role` 字段，签发时嵌入 JWT |
| I2 | agentmesh Gateway | 解码 JWT，执行 RBAC 检查（L2-L3 前） |
| I3 | KOS MCP | `operation_level` 注解已存在，需接入 Gateway 的 RBAC 决策 |
| I4 | gbrain MCP | 添加 `operation_level` 注解，接入 RBAC |
| I5 | SharedBrain MCP | 添加 `operation_level` 注解，高敏感度（默认 L2+） |
| I6 | Ops/Hermes | 审计日志记录 RBAC allow/deny 事件 |
| I7 | CLI / Dashboard | 人类操作者需绕过 RBAC 的机制（通过 identity_token） |

---

## 4. 部署路线图（6 Wave）

```
                            🚦 Governance Gate                    🚚 Delivery Track
                            ─────────────────                    ───────────────
Wave 1 (现在 · 治理门禁):    Wave 2 (M2.6 exec):                  Wave 3 (M2.6 exec):
  RBAC 模型评审               身份令牌扩展 + RBAC 实现              First-wave deny path
  Identity Token 扩展         (Agora Registry, agentmesh           (5 candidates: KOS +
  Audit Schema 对齐           Gateway ENFORCE)                     gbrain delete_page)

Wave 4 (M2.7 gate):          Wave 5 (M2.7 exec):                  Wave 6 (M2.8 gate):
  剩余 Tool 分类评审            全量 deny path 实现                 安全审计 + 敏感能力锁定
  敏感能力阻断确认              Heartbeat 代码实现                  退化回退策略
```

### Wave 1 — RBAC 定义与治理审批（当前 Wave）

| 任务 | 产出物 | 状态 |
|------|--------|:----:|
| 1.1 完成 RBAC 模型设计 | 本文档 §3 | ✅ 已完成 |
| 1.2 评审角色/权限映射 | 审批记录 | ⏳ 等待 human review |
| 1.3 扩展 Identity Token schema | 更新 `agent-registry-heartbeat.md` | ⏳ Wave 2 执行 |
| 1.4 对齐 Audit Log schema | 确认字段覆盖 RBAC deny | ⏳ Wave 2 执行 |

**Gate 通过条件:** RBAC 模型获 human 批准，Identity Token schema 定稿。

### Wave 2 — 身份令牌扩展 + RBAC 强制执行

| 任务 | 组件 | 风险级别 | 操作级别 |
|------|------|:-------:|:--------:|
| 2.1 扩展 Agora Registry 注册 API，接受 `role` 字段 | `agora` | L1 | L1 |
| 2.2 Registry 签发 JWT 时嵌入 `role` + `allowed_domains` | `agora` | L2 | L2 |
| 2.3 agentmesh Gateway 解码 JWT，提取角色信息 | `agentmesh-gateway` | L2 | L2 |
| 2.4 Gateway 实现 RBAC 中间件（Level/Tool/Domain gate） | `agentmesh-gateway` | L2 | L2 |
| 2.5 Gateway RBAC deny 路径接入审计日志 | `ops/hermes` | L1 | L1 |

**Gate 通过条件:** RBAC 中间件在 agentmesh Gateway 中可用，可拦截越权调用。

### Wave 3 — First-Wave Deny Path 实现

| # | Tool | Target Level | 当前状态 | 实施组件 |
|:-:|------|:-----------:|:--------:|----------|
| 1 | `kos search_knowledge` | L0 | 无需 deny path | — |
| 2 | `kos run_indexer(incremental)` | L1 | 已有 L1 注解 (server.py:463) | 添加 audit log |
| 3 | `kos run_indexer(full)` | L2 | 已有 L2 注解 (server.py:398) | 验证 deny path 生效 |
| 4 | `gbrain delete_page` | L2 | 无注解 | 添加 L2 deny path |
| 5 | `kos db_vacuum` | L3 | 无注解 | 添加 L3 deny path + 24h cooldown |

**Gate 通过条件:** 5 个 first-wave tools 均对接 RBAC 中间件，L2/L3 拒绝路径可复现。

### Wave 4 — 剩余 Tool 分类 + 敏感能力阻断

| 任务 | 涉及 MCP Server | 风险级别 |
|------|----------------|:--------:|
| 4.1 Agora Registry tools 分类 | `agora` | L1 |
| 4.2 Eidos MCP tools 分类 | `eidos` | L1 |
| 4.3 agentmesh tools 分类 | `agentmesh` | L1 |
| 4.4 SharedBrain MCP tools 分类 | `sharedbrain` | ⚠️ L2 — 部分为敏感 |
| 4.5 敏感能力阻断确认 | 全部 | L2 |

**敏感能力清单（保持 blocked 直到独立 gate 通过）：**
- Apple 生态连接器（Calendar, Reminders, Notes）
- WeChat 消息/文件访问
- Family OS 调度器（成员档案、健康记录）
- SMB/NAS 文件操作
- Media 索引（照片、视频）
- 高自主自愈触发（>50% 自主操作）

**Gate 通过条件:** 全部工具的 operation_level 分类完成，敏感域标记为 L2+。

### Wave 5 — 全量 Deny Path + Heartbeat 代码实现

| 任务 | 组件 | 风险级别 |
|------|------|:--------:|
| 5.1 所有 MCP Server 添加 operation_level 注解 | 全部 | L2 |
| 5.2 所有 L2+ tools 对接 deny path | 全部 | L2 |
| 5.3 Agent 端 Heartbeat 实现（60s send） | `agentmesh` + `agora` | L2 |
| 5.4 Registry 端 Heartbeat 接收 + zombie 检测 | `agora` | L2 |
| 5.5 Registry 不可达降级 - 本地缓存 + safe mode | `agentmesh-gateway` | L2 |
| 5.6 Deadlock 检测实现 | `agentmesh` | L2 |

**Gate 通过条件:** 全量 deny path 可用，heartbeat 端到端通过测试。

### Wave 6 — 安全审计 + 敏感能力锁定 + 回退策略

| 任务 | 风险级别 |
|------|:--------:|
| 6.1 全量 RBAC 审计（模拟攻击场景） | L2 |
| 6.2 敏感能力独立 gate 锁定 | L2 |
| 6.3 退化回退策略（Safe Mesh 不可用时的降级路径） | L2 |
| 6.4 完成验收报告 | L0 |

**Gate 通过条件:** 安全审计通过，敏感能力锁死，回退策略文档化。

---

## 5. 交付 Track vs 治理 Gate 区分

| 方面 | 交付 Track (Waves 3, 4, 5) | 治理 Gate (Waves 1, 2, 6) |
|------|---------------------------|--------------------------|
| 本质 | 代码实现 + 部署 | 设计 + 评审 + 审计 |
| 执行者 | Agent (engineer role) | Human + Verifier |
| 产出物 | 代码提交 + 测试报告 | 设计文档 + 审批记录 + 审计报告 |
| 通过条件 | 测试通过 | Human 批准 |
| 失败后果 | 代码回滚 | 设计重审 |
| 交付速度 | 快（days） | 慢（hours to days） |
| 可并行 | 可（若 gate 已过） | 不可（序列化评审） |

**规则：** Waves 3, 4, 5 只能在 Waves 1, 2 的治理 Gate 通过后启动。Wave 6 是最终验收，可在 Wave 5 完成后立即启动。

---

## 6. RBAC 与现有组件的集成矩阵

| 组件 | Safe Mesh 角色 | RBAC 集成点 | 依赖 |
|------|--------------|-------------|------|
| **Agora Registry** | Identity 签发 + Service Catalog | 注册时接受 `role`，JWT 包含角色声明 | — |
| **agentmesh Gateway** | 执行点（enforcement point） | 解码 JWT → RBAC check → allow/deny | Agora Registry |
| **KOS MCP** | 被保护的工具面 | `operation_level` 注解，接入 Gateway 决策 | operation-levels.md |
| **gbrain MCP** | 被保护的工具面 | `operation_level` 注解 | 新增分类 |
| **SharedBrain MCP** | 敏感工具面 | 默认 L2+，需独立 gate | 敏感能力策略 |
| **Ops/Hermes** | 审计记录面 | 接收 allow/deny 事件，写入 audit log | audit schema |
| **CLI / Dashboard** | 人类入口 | 绕过 RBAC（human token），但留存审计 | identity proof |

---

## 7. 验收场景

### 7.1 RBAC 场景

| 场景 | 输入 | 预期输出 | 验证 |
|------|------|----------|:----:|
| reader 执行 L0 工具 | `search_knowledge("test")` with reader token | 成功返回结果 | ✅ |
| reader 执行 L1 工具 | `add_tag("hello", "test")` with reader token | **拒绝**: role reader 无写入权限 | ✅ |
| operator 执行 L2 工具 | `delete_page("hello")` with operator token + no confirm | **拒绝**: L2 需确认 | ✅ |
| curator 执行 L2 工具 + 确认 | `delete_page("hello", {_confirmed: true})` with curator token | 成功，有审计 | ✅ |
| research agent 越权删除 | `delete_page("hello")` with research/research token | **拒绝**: role reader 越权 | ✅ |
| 伪造 agent_id 被拒 | 伪造 JWT 请求 | HMAC 验证失败，拒绝 | ✅ |

### 7.2 全量 Safe Mesh 端到端场景

| 场景 | 输入 | 预期输出 |
|------|------|----------|
| 正常 heartbeat → 正常路由 | Agent 每 60s heartbeat | Registry `renewed` |
| Heartbeat 超时 → zombie | 停止 180s | 取消路由，通知管理员 |
| Registry 宕机 15min → safe mode | 断开 | Agent 只读 |
| L3 操作 + 确认 + 24h | `db_vacuum(confirmed, cooldown=24)` | 成功，审计 |
| L3 操作未确认 | `db_vacuum()` | 拒绝: PermissionError |

---

## 8. 依赖与前置条件

| 前置条件 | 依赖任务 | 状态 |
|----------|---------|:----:|
| M2.0 治理收敛关闭 | M2.0-phase1-governance-close.yaml | ⚡ 同时进行 |
| M2.1 KOS baseline 恢复 | M2.1-kos-index-diagnosis.yaml, M2.1-kos-repair-plan.yaml | ⚡ 同时进行 |
| M2.2 操作级别分类完成 | operation-levels.md | ✅ 已完成 |
| M2.2 Agent Registry Heartbeat 设计 | agent-registry-heartbeat.md | ✅ 已完成 |
| Human 批准 RBAC 模型 | 本 roadmap Wave 1 | ⏳ 待审批 |

---

## 9. 风险登记

| 风险 | 可能性 | 影响 | 缓解 |
|------|:-----:|:----:|------|
| RBAC 过于细粒度导致性能下降 | 中 | 中 | 先实现粗粒度（role→level），后续优化 |
| 已有 MCP Server 注解与 RBAC 中间件冲突 | 中 | 高 | Wave 2 先做 Gateway 层，不修改各 MCP Server 内部 |
| Agent 升级期间新旧 token 不兼容 | 低 | 中 | Token 包含 version 字段，支持 24h 滚动窗口 |
| Identity 签发流程成为新单点故障 | 中 | 高 | 本地缓存 + 离线 token（预签发 + 冷启动） |

---

> **本文件已写入 `.omo/plans/`**  
> **下一个动作:** Human 评审 RBAC 模型 → 审批通过后进入 Wave 2 执行阶段
