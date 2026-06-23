---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# 红队审查修订补丁：全部 4 阶段任务规格书

> 日期: 2026-05-29 | 版本: v1.0→v1.1 | 审查: 红队 (shrill-teal-dragonfly)
> 适用: phase1/2/3/4-task-specs.md
> 本文档是历史红队修订补丁，保留当时对 phase1-4 任务规格书的修订意见与补丁建议，不是当前任务状态、当前工具计数或当前安全面 SSOT。
> 当前阶段、当前任务与当前实现状态请以 `/.omo/goals/current.yaml`、`/.omo/tasks/active/`、`/.omo/state/system.yaml` 和当前代码为准。

---

## 修订摘要

红队审查发现 **19 项 Critical + 20 项 Major** 问题。此补丁覆盖所有修订。修订原则：

1. **任务类别修正**: 19 个 "quick" → "unspecified-high" 或 "deep"
2. **HITL 超时机制**: 所有人工审核门控增加超时 + 默认拒绝
3. **memU 回退路径**: Phase 2 Plan B
4. **RBAC 凭证分发**: 角色绑定机制落地
5. **紧急停止**: Phase 4 增加 kill switch
6. **级联保护**: 自愈系统增加并发重启断路器
7. **Agora 注册缺口**: sharedbrain-bridge 注册到 Agora
8. **EU 价格锚定**: EU 定价表 + 外部参照
9. **安全测试**: 每 Phase 增加安全扫描

---

## 🔴 跨阶段修订 (X)

### X-1: 任务类别系统性修正

以下 19 个任务从 `category="quick"` 修正为适当类别：

| Phase | 任务 | 原类别 | 新类别 | 原因 |
|-------|------|:------:|:------:|------|
| 1 | T1.3-PRE | quick | **unspecified-high** | memU 兼容性分析需阅读 gbrain 74 tools 接口 |
| 1 | T2.1.4 | quick | **unspecified-high** | LiteLLM 适配器需理解 agentmesh Gateway 架构 |
| 1 | T2.3.4 | quick | **unspecified-high** | gbrain 兼容性测试需跨模块分析 |
| 2 | T2.1a | quick | **deep** | GitNexus→KOS 桥接需阅读 GitNexus API + KOS index 双架构 |
| 2 | T2.1b | quick | **deep** | Graphify→KOS 桥接同上 |
| 2 | T2.1d | quick | **unspecified-high** | 共识机制设计需分析投票算法 |
| 2 | T2.2a | quick | **deep** | UltraRAG 集成需替换 minerva 核心检索链 |
| 2 | T2.3a | quick | **deep** | MinerU 集成需部署 + API 理解 |
| 3 | T3.1a | quick | **deep** | nuwa-skill 蒸馏是博士级研究综合 |
| 3 | T3.1b | quick | **unspecified-high** | Schema 发现需分析 KOS 知识图谱 |
| 3 | T3.1c | quick | **unspecified-high** | Tool 发现需分析 agentmesh 执行日志 |
| 3 | T3.1d | quick | **unspecified-high** | Prompt 优化器是评估框架，非单次任务 |
| 3 | T3.2a | quick | **unspecified-high** | 扩展 entropy 监控需理解 10+ 服务接口 |
| 3 | T3.2b | quick | **unspecified-high** | 自愈规则扩展需跨系统协调 |
| 3 | T3.2c | quick | **unspecified-high** | 自愈学习需分析日志 + 模式识别 |
| 3 | T3.4a | quick | **unspecified-high** | pipeline v2 schema 是架构级定义 |
| 3 | T3.4b | quick | **unspecified-high** | 管线编排器是复杂执行引擎 |
| 4 | P4.1a | quick | **unspecified-high** | 自主度仪表盘需跨系统数据聚合 |
| 4 | P4.3b | quick | **unspecified-high** | 异常检测器需时间序列基线 |

### X-2: memU 兼容性失败 → Phase 2 "Plan B"

在 `phase2-task-specs.md` 开头增加：

```markdown
## ⚠️ Phase 2 前置条件 + Plan B

Phase 2 启动前必须确认 Phase 1 memU 兼容性结果:

| memU 兼容性 | Phase 2 行为 |
|:-----------:|-------------|
| ≥ 60/74 tools | 🟢 **GO**: gbrain memU 后端就绪。P2.1-P2.5 全部执行 |
| 40-59/74 | 🟡 **Plan B**: gbrain 保留 SQLite 后端。P2.1-P2.4 执行，P2.4c (gbrain EU 计价) 改为适应 SQLite。T3.2 自愈规则调整 |
| < 40/74 | 🔴 **NO-GO**: memU 集成放弃。Phase 2 目标降级为"知识管线深化（无 gbrain 升级）"。创建 Plan B 决策日志 → .omo/decisions/memu-no-go.md |
```

### X-3: 安全扫描任务（每 Phase）

在每个 Phase 的验收检查清单中增加：

```
□ Sn: 安全扫描 — 依赖漏洞审计 (安全扫描工具) + 密钥泄露扫描 (密钥扫描工具) → 0 CRITICAL/HIGH
```

### X-4: HITL 超时 + 默认拒绝（全局）

所有 Human-in-the-Loop 门控必须增加以下行为：

```
HITL Gate 行为:
1. 推荐 → 通知人类 → 等待 N 分钟
2. 超时未响应 → 自动拒绝 (safe default)
3. 拒绝 → 推荐退回，可重新提交
4. 批准 → 执行，记录审计日志（不可变）
```

- Phase 2 辅助研究模式: 超时 30 分钟
- Phase 3 KOS self 推荐: 超时 24 小时（可以批量审查）
- Phase 4 异常通知: 超时 15 分钟（HIGH 严重性），超时后降级为自动处理

---

## 🔴 Phase 1 修订

### P1-1: memU 兼容性任务类别修正
- T1.3-PRE2: `category="quick"` → `category="unspecified-high"`
- 增加: 预检结果必须写入 `.omo/decisions/memu-compat-result.md`

### P1-2: LiteLLM API 密钥
T2.1.1 增加步骤:
```
0. 收集 LLM API 密钥 (至少 1 个: OpenAI / Anthropic / Google)
   - 写入 .env 文件或环境变量
   - LiteLLM config 引用这些密钥
   - 如果无密钥: 标记 T2.1.1 为 NO-GO，跳过 agentmesh 适配器
```

### P1-3: sharedbrain-bridge Agora 注册
新增任务 **T1.2.6b**:
```
task(category="quick", description="T1.2.6b: Register sb-bridge MCP tools to Agora", prompt='''
Register the 5 sharedbrain-bridge MCP tools to Agora registry.

1. Read the sb-bridge package to identify 5 MCP tools:
   - sb_bridge_eu_check — EU balance check
   - sb_bridge_eu_consume — EU consumption
   - sb_bridge_immune_audit — Immune audit
   - sb_bridge_organ_sync — Batch organ sync
   - sb_bridge_organ_status — Organ status query

2. Add them to /Users/xiamingxing/Workspace/projects/kairon/packages/agora/src/agora/registry.yaml
   - URI prefix: wksp://sharedbrain-bridge/
   - Endpoint: mcp://sharedbrain-bridge:8760

3. Verify: grep sharedbrain-bridge registry.yaml returns 5 entries
4. Report: "sb-bridge tools registered: 5/5"
''')
```

### P1-4: 架构合规检查过滤
T3.2.3 架构合规检查命令改为:
```bash
# 排除 test 文件和注释的误报
grep -r "class Entity\|class Relation\|class KnowledgeGraph" \
  projects/ --include="*.py" | grep -v "test" | grep -v "adapter" | grep -v "stub"
```

---

## 🔴 Phase 2 修订

### P2-1: EU 路由顺序依赖修正
Sprint 3 W5 内部执行顺序修正:
```
W5 串行执行:
1. T2.4a (Agora EU 路由) → 部署上线
2. T2.4b (agentmesh EU 计价) + T2.4c (gbrain EU 计价) → 并行
3. T2.4d (免疫审计扩展) → 并行
```
原 Sprint 3 时间从 2 周 → 2.5 周（增加 3 天串行等待）

### P2-2: RBAC 凭证分发
新增任务 **T2.5c**:
```
task(category="unspecified-high", description="T2.5c: RBAC credential distribution", prompt='''
Implement role credential distribution for RBAC.

Design and implement:

1. Agent role binding: agentmesh agents get role via:
   - identity_bridge → AgentRole → RBAC role mapping
   - Agent creation: assign minimum role (Agent by default)
   - Admin override: Admin can promote agent to User role

2. Service role binding: kairon services get role via environment variable:
   - BOS_ROLE=admin (SharedBrain)
   - BOS_ROLE=user (kairon services)
   - BOS_ROLE=agent (agentmesh)
   - BOS_ROLE=readonly (external clients)

3. Role escalation prevention:
   - X-Role header cannot be set by caller (Agora strips and ignores it)
   - Role is determined server-side from: identity_bridge query (agents) or env var (services)
   - No default fallback → unknown callers get ReadOnly

4. Test: verify agent cannot set X-Role: Admin → still treated as Agent role
5. Report: "RBAC credential distribution: role binding mechanism documented and tested"
''')
```

### P2-3: Admin EU 豁免限制
T2.4a EU 路由中间件修改:
```python
# Admin role: EU check still runs (for audit), but never blocks
# Admin can see "you would be blocked if not admin" in logs
# This prevents silent EU bypass while preserving admin override
```

### P2-4: Agent 最小权限拆分
P2.5 RBAC 权限矩阵拆分:
```yaml
agentmesh/tools/search: Agent ✅
agentmesh/tools/run: Agent ✅  
agentmesh/tools/delete: Agent ❌ → User ✅  # 需要提升权限
agentmesh/tools/create: Agent ✅
agentmesh/tools/deploy: Agent ❌ → User ✅   # 需要提升权限
```

### P2-5: EU 价格锚定
T2.4a EU 路由中间件增加:
```
EU 定价表（外部锚定）:
  minerva_research: 10 EU ≈ GPT-4o 一次 API 调用 (~$0.015)
  ontoderive_engine: 5 EU ≈ GPT-4o-mini 一次 (~$0.001)
  kos_index: 3 EU ≈ 一次向量搜索 (~$0.0001)
  kronos_ingest: 1 EU ≈ 一次网页抓取 (~$0.0005)

定价表文档 → .omo/eu-pricing-table.md
每季度重新锚定（真实 API 价格变动）
```

### P2-6: 向量数据库部署
新增任务 **T2.3c-impl**:
```
task(category="unspecified-high", description="T2.3c: Deploy vector database", prompt='''
Deploy and configure LanceDB (lightweight, no external service needed) for kronos pipeline artifacts.

1. Add LanceDB dependency to kronos
2. Initialize LanceDB at kairon/packages/kronos/data/vectordb/
3. Index pipeline artifacts (embeddings of ingested documents)
4. Expose search: "kronos_vector_search" MCP tool
5. Benchmark: vector search latency
6. Report: "LanceDB deployed: <N> vectors indexed, search latency: <X>ms"
''')
```

---

## 🔴 Phase 3 修订

### P3-1: HITL 超时机制（全局）
所有 HITL 门控 (T3.1a/b/c/d, T3.2b/c, T3.4b) 增加:

```python
# 在每个 HITL gate 实现中：
HITL_TIMEOUT = 86400  # 24h default, adjustable per-gate

def human_review(recommendation, timeout=HITL_TIMEOUT):
    notify_human(recommendation)
    try:
        response = wait_for_human_response(timeout=timeout)
        if response == "approve":
            apply(recommendation)
            log_audit("approved", recommendation)  # immutable
        else:
            log_audit("rejected", recommendation)
            return REJECTED
    except TimeoutError:
        # Safe default: auto-reject
        log_audit("auto-rejected (timeout)", recommendation)
        recommendation.status = "timeout_rejected"
        return AUTO_REJECTED
```

### P3-2: 自愈级联保护
T3.2b 增加:
```
级联保护规则:
  if 3+ services alert simultaneously:
    → STOP all auto-restarts
    → Notify human (CRITICAL)
    → Wait for human diagnosis before any restart
    → Reason: simultaneous failures likely indicate shared root cause
  
  Concurrent restart limit: max 2 services simultaneously
  Restart cooldown: 60s between any two restarts
```

### P3-3: 72h 验证增加吞吐量检查
T3.4c 验收标准修改:
```
原: "ZERO unplanned failures in 72h"
新: "ZERO unplanned failures AND ≥ 1 pipeline completion through HITL gate in 72h"
    → 需要至少 1 个人工审批通过 = 系统不只是挂着等
```

### P3-4: KOS self 工具 RBAC 限制
所有 KOS self 工具 (T3.1a/b/c/d) 增加:
```
RBAC 限制:
  kos_self_distill_skill: 仅 Admin 可触发
  kos_self_discover_schema: 仅 Admin 可触发
  kos_self_discover_tool: 仅 Admin 可触发
  kos_self_optimize_prompt: 仅 Admin 可触发
  原因: 这些工具改变系统能力边界，必须最高权限
```

### P3-5: HITL 审计追踪防篡改
T3.5 验收条件修改:
```
原: "ALL autonomous decisions have audit trail"
新: "ALL autonomous decisions have IMMUTABLE audit trail (append-only JSONL + SHA-256 chain)"
```

---

## 🔴 Phase 4 修订

### P4-1: 紧急停止
新增任务 **P4.0**:
```
task(category="unspecified-high", description="P4.0: Emergency stop mechanism", prompt='''
Implement a global emergency stop (kill switch) for all autonomous operations.

1. Create /Users/xiamingxing/Workspace/.omo/emergency_stop
   - File exists → ALL autonomous operations PAUSE
   - File deleted → resume normal operations

2. Integration:
   - Agora middleware: check emergency_stop before routing any autonomous call
   - KOS self: check before proposing new skill/schema/tool
   - D-Genesis: check before any self-healing action
   - Pipeline: check before starting new pipeline run

3. Human interface:
   - CLI: wksp emergency-stop [on|off|status]
   - Dashboard: big red STOP button in Agora

4. Test:
   - echo "stop" → verify autonomous operations halt
   - rm stop file → verify autonomous operations resume
5. Report: "Emergency stop: operational, test: PASS"
''')
```

### P4-2: 异常分类方案
P4.3b 增加分类:
```
异常分类:
  LOW:   服务慢 > 2× 基线, 但仍在服务中 → auto-heal (restart)
  MEDIUM: 服务超时/崩溃, 隔离的服务 → notify + auto-heal (restart)
  HIGH:   3+ 服务同时告警, 关键路径中断 → notify + WAIT for human
  CRITICAL: 安全相关, EU 余额耗尽, 数据损坏 → notify + STOP all autonomous ops + wait

分类依据:
  - 受影响服务数
  - 是否为关键路径 (agora, eu-pricing, identity_bridge)
  - 是否为安全相关
  - 历史重复次数
```

### P4-3: 自主操作角色绑定
新增:
```
自主操作角色:
  系统自主操作 (pipeline, self-healing, KOS self) 以 "System" 角色运行
  System 角色权限:
    - 读取: ALL (监控需要)
    - 执行: 有限 (仅操作自身管理的服务)
    - 修改: 禁止 (不能修改配置、SKILL、Schema、Tool — 只能推荐)
    - 推荐 → 人类 (Admin) 确认 → 以 Admin 身份执行

  这防止自主操作绕过 RBAC 权限检查。
```

### P4-4: 自主权分级过渡
原 Q2 50% → Q3 70% → Q4 80% 改为:
```
Q2 2027: 影子模式 (30%)
  - KOS 推荐但不执行 → 日志记录推荐内容 → 人类事后审核
  - 自愈: 仅 restart 类操作自动，其余通知

Q3 2027: 辅助模式 (50%)
  - KOS 推荐 → 人类确认 → 执行
  - 自愈: MEDIUM 以下自动，HIGH 通知

Q4 2027: 高自主模式 (70%)
  - KOS 推荐 → 超时默认批准 (已有信心)
  - 自愈: HIGH 以下自动，CRITICAL 通知

2028 Q1+: 评估是否 > 80%
```

### P4-5: 自主决策速率限制
新增:
```
速率限制:
  - Skill 推荐: 最多 1/天
  - Schema 推荐: 最多 3/天
  - Tool 推荐: 最多 2/天
  - 自愈操作: 最多 10/小时 (已由级联保护覆盖)
  - 超限 → 进入队列 → 下一天/小时再处理
```
