---
type: ephemeral
created: 2026-09-03
---

# ECCP N1-N10 收尾 Handoff

> 创建: 2026-08-05 | 最后更新: 2026-08-05 (P0 完整闭环交付) | **14 PR MERGED + 3 零代码**
> 用法: 新 session 第一句「读 `/Users/xiamingxing/Workspace/ECCP-HANDOFF.md` 继续」→ 秒接 ECCP 剩余

---

## 1. 已交付 (14 PR MERGED + 3 零代码)

### 1.1 N1-N10 主线 (9 PR + 3 零代码)

| N | 内容 | PR |
|---|------|-----|
| N1 | document-review scene BOS URI + opportunity_window | #963 |
| N1 | catalog iris 断链修复 (跨项目扫 + health 适配 + capabilities id) | #961 |
| N2 | cockpit-ui (零代码已实现) | — |
| N3 | daemon (零代码已实现) | — |
| N4 | universal_private connector | #58 (kairon) |
| N5 | netease (zlib) + seeyon (CDP) list | #59 (kairon) |
| N6 | MCP 21 连接器 (零代码已实现) | — |
| N7 | 健康指标 | #944 |
| N8 | scene-card lineage (base64 修复) | #946 |
| N9 | P0 mesh-iris-executor (手动跑就位) | #969 |
| N10 | rss 退役 (entry_points 移除) | #60 (kairon) |
| — | 子模块指针 (#58 + #59) | #956 |

### 1.2 P0 完整闭环 (5 PR, 本轮交付)

| 块 | 内容 | PR |
|----|------|-----|
| 第一块 | `dispatch_admitted_workflow` iris 快速路径 (`_dispatch_iris_via_executor`) | #973 |
| 第二块 | packet 复用 (`workflow_run_id` + admission 一致性) | #977 |
| N9 工具 | `mesh-stale-analyze.py` (planned run 分析, 只读) | #981 |
| 第三块 | `consume_pending_workflow_requests` (mesh step → admit → dispatch 闭环) | #991 |
| 根因修复 | consume 排除 `agent-workflow` producer (268 stale run 根因) | #1003 |

**核心闭环**: `request_workflow_from_task` (声明 caps) → mesh store (planned) → `consume_pending_workflow_requests` (daemon auto-consume) → `preview/admit` → `_dispatch_iris_via_executor` (iris 快速路径) → mesh 6 事件链 + iris receipt. 全自动, 无需 launch agent.

---

## 2. P0 完整闭环架构 (本轮交付)

### 2.1 闭环数据流

```
代理 (task + required_capabilities)
  │ request_workflow_from_task (workflow_promotion.py:129)
  ▼
WorkflowRequested (mesh store, planned state, payload 带 caps)
  │ consume_pending_workflow_requests (workflow_dispatch.py, daemon tick)
  ▼
preview_requested_workflow → admit_workflow (gate: capability_health)
  │
  ▼
WorkflowAdmitted
  │ _dispatch_iris_via_executor (iris 快速路径) / dispatch_task (worker)
  ▼
StepDispatched → AgentWorkflowStarted → WorkflowSucceeded → EvidenceRecorded
```

### 2.2 关键组件

| 组件 | 文件 | 角色 |
|------|------|------|
| `request_workflow_from_task` | `workflow_promotion.py:129` | 代理仅创建 WorkflowRequested (声明 caps, 不 admit) |
| `consume_pending_workflow_requests` | `workflow_dispatch.py` | 扫 planned → preview → admit → dispatch (daemon tick) |
| `_dispatch_iris_via_executor` | `workflow_dispatch.py:540` | iris 快速路径, subprocess 调 `mesh-iris-executor` |
| `_run_auto_consume` | `omo_daemon.py` | daemon `run_once` 集成 (30min tick) |
| `_collect_iris_capability_health` | `omo_daemon.py` | iris entry_points → capability_health (subprocess) |
| `mesh-stale-analyze.py` | `bin/ssot/` | 只读分析 planned run (stale vs fresh 分类) |

### 2.3 根因修复 (PR #1003)

- **问题**: 268 个 planned run 永远不被 consume (无 `required_capabilities`)
- **根因**: `mesh_agent_events.py:177` 将 `AgentWorkflowStarted` → `WorkflowRequested` (producer=`agent-workflow`), 用于 agent 生命周期可视化 (阶段 1b/4/5 设计), 无 `task_id`/caps
- **修复**: `consume_pending_workflow_requests` 加 producer 过滤 (排除 `agent-workflow`), 不破坏阶段 1b/4/5 状态机链
- **验证**: `total_planned` 268 → 0 (mesh-stale-analyze 确认)

---

## 3. 剩余接力棒

### 3.1 P0 完整 — ✅ 全交付

第一块 (#973) + 第二块 (#977) + 第三块 (#991) + 根因修复 (#1003) 全 MERGED. 闭环跑通.

**剩余运维 (可选)**:
- 生产启用 `omo daemon start --auto-consume` (运维门, 非开发)

### 3.2 N1 activation (document-review lifecycle→active) — 业务门

- **当前**: `lifecycle: proposal_only`, `activation: forbidden` (`docs/scene-cards/document-review.yaml`)
- **业务门**: 需 operator grant + `permission_ref` + business confirmation (**fabric 红线, 不伪造**)
- **CDP 9222**: seeyon_oa 不可用 (需开 CDP), apple_mail/netease_mailmaster 可用 ✅
- **fabric 红线**: `lifecycle→active` 必须 succeeded/degraded evidence + operator grant

### 3.3 N9 全覆盖 (所有 iris connector 走 mesh receipt) — ✅ 工具就位

- **工具**: `mesh-stale-analyze.py` (#981) + `mesh-iris-executor.py` (#969) 支持任意 connector
- **静态契约**: ✅ 全兼容 (20 connector, rss 退役后)
- **动态**: 10 可用 connector 可走 mesh receipt, 10 不可用需 credentials/CDP
- **闭环验证**: P0 完整后, daemon auto-consume 自动触发 → 全覆盖

---

## 4. 下个 session 入口

```bash
# 1. 读本 handoff
cat /Users/xiamingxing/Workspace/ECCP-HANDOFF.md

# 2. P0 闭环验证 (可选, 生产启用前)
python3 bin/ssot/mesh-stale-analyze.py  # planned run 分析 (应 0 stale)
cd projects/omo && uv run --with pyyaml --with pytest python -m pytest tests/test_workflow_dispatch.py -k consume -v

# 3. N1 activation 业务门
cat docs/scene-cards/document-review.yaml  # lifecycle/activation 字段

# 4. 生产启用 daemon auto-consume (运维门)
cd projects/omo && uv run python -m omo.omo_daemon once --auto-consume  # dry run 验证
```

---

## 5. ECCP 顶层判断

- **技术交付完整**: 14 PR + 3 零代码 + P0 完整闭环 (5 PR) + 根因修复
- **P0 完整**: ✅ 全交付 (request → consume → admit → iris dispatch → receipt)
- **剩余**: N1 activation (业务门, 等 operator/CDP) + 可选 daemon 生产启用 (运维门)
- **建议**: ECCP 技术交付收尾. N1 等业务输入 (operator/permission + CDP 9222). 生产启用 daemon auto-consume 是运维决策, 非开发任务.

---

## 6. 关键文件路径

```
# P0 完整闭环 (本轮)
bin/ssot/mesh-iris-executor.py                      # iris connector 执行器 (#969)
bin/ssot/mesh-stale-analyze.py                      # planned run 分析 (只读, #981)
projects/omo/src/omo/workflow_promotion.py          # request_workflow_from_task (声明 caps)
projects/omo/src/omo/workflow_dispatch.py           # consume + iris 快速路径 + admit
projects/omo/src/omo/omo_daemon.py                  # daemon auto-consume 集成
projects/omo/src/omo/workflow/mesh_agent_events.py  # AgentWorkflowStarted→WorkflowRequested (根因)
projects/omo/tests/test_workflow_dispatch.py        # consume 单测 (iris fast path + skip non-planned)

# N1-N10 主线
bin/ssot/external-resource-catalog.py               # N1 catalog (跨项目扫 iris)
bin/ssot/gen-scene-card-lineage.py                  # N8 scene-card lineage
docs/scene-cards/document-review.yaml               # N1 scene (lifecycle: proposal_only)
projects/knowledge/kairon/packages/iris/src/iris/base.py      # BaseConnector 契约
projects/knowledge/kairon/packages/iris/src/iris/connectors/  # 20 connector (rss 退役)
.omo/standards/external-connection-fabric.md        # fabric 标准 (红线)
```
