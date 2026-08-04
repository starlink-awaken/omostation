# ECCP N1-N10 收尾 Handoff

> 创建: 2026-08-05 | 上个 session 接力 | **9 PR MERGED + 3 零代码**
> 用法: 新 session 第一句「读 `/Users/xiamingxing/Workspace/ECCP-HANDOFF.md` 继续」→ 秒接 ECCP 剩余

---

## 1. 已交付 (9 PR MERGED + 3 零代码)

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

**核心交付**: `bin/ssot/mesh-iris-executor.py` (#969) — mesh worker 执行 iris connector 自动化，固化 mesh 状态机 6 事件链 (Requested→Admitted→Dispatched→Started→Succeeded→EvidenceRecorded) + iris receipt。

---

## 2. 这轮诊断 (2026-08-05)

### 2.1 N9 全覆盖矩阵 (mesh-iris-executor 兼容性)

**静态契约**: 21 connector (rss 退役后 20) **全兼容 mesh-iris-executor** ✅
- `BaseConnector(ABC)` 无 `__init__` (base.py:37) → `ep.load()()` 无参构造 OK
- `list_items(limit, cursor, tag, folder, subdir, chat_id)` 全可选 (base.py:56) → `inst.list_items(limit=N)` 兼容
- `KnowledgeArtifact.id/.title` 就位

**动态可用性** (`iris --json status`): **10/20 可用**

| 状态 | 连接器 |
|------|--------|
| ✅ 可用 (10) | apple_mail, applenotes, cua_browser, github, local_files, netease_mailmaster, universal_private, wechat, wpsnote, zhihu |
| ❌ 不可用 (10) | dingtalk, feishu, notebooklm, obsidian, openhuman, pocket, polar, **seeyon_oa**, telegram, wxread |

⚠️ **seeyon_oa 不可用** (需 CDP 9222) — N1 activation 的公文源之一。

### 2.2 P0 完整评估 (dispatch_task 集成点)

`dispatch_task` 是**通用 task→worker model** (`projects/omo/src/omo/omo_worker_dispatch.py:151`):
- 创建 dispatch/envelope/prompt 文件 + 发 mesh 事件 (`_bridge_dispatch_to_mesh:30`)
- `launch=True` 时 `subprocess.run(_build_launch_argv)` 跑 **worker process** (`workers.yaml` 注册的 CLI/agent)
- worker process 跑 **task prompt**, **不直接执行 iris connector**

**P0 完整** = mesh workflow step 自动触发 iris 执行. 两个切入点:
1. **注册 `iris-executor` worker** (`workers.yaml`), command 调 `mesh-iris-executor`
2. **`dispatch_task` 加 iris 快速路径** (`capability_refs` 含 `iris:` → 直接调 executor, 不 launch agent)

⚠️ **omo submodule 深度改动** (改 omo 代码 + 子模块指针 + 用户授权 + closeout)

---

## 3. 剩余三块接力棒

### 3.1 P0 完整 (mesh worker 自动执行 iris) — 第一块已落地 ✅
- **基础**: `mesh-iris-executor` (#969 MERGED) + `dispatch_admitted_workflow` iris 快速路径 (本 session)
- **第一块 (本 session 落地)**: `projects/omo/src/omo/workflow_dispatch.py` 加 `_dispatch_iris_via_executor` + `dispatch_admitted_workflow` iris 分支. `capability_refs` 含 `iris:xxx` → subprocess 调 `mesh-iris-executor` (不 launch agent). **功能验证通过**: apple_mail 5 items + mesh 6 事件链 + WorkflowSucceeded + EvidenceRecorded.
- **缺口 (下一步)**:
  1. mesh workflow step 自动触发 `dispatch_admitted_workflow` (candidate→proposal→active 触发链)
  2. packet 复用 (方案 B): 当前 executor 自 seed 新 run_id, 应复用 packet 的 workflow_run_id + admission (mesh 状态机一致性)
  3. omo submodule commit + 子模块指针 bump (待用户授权)
- **Pyright**: 2 个 diagnostic (Line 40/242) 是 pre-existing (`_parse_health` / `preview_requested_workflow`), 非本改动引入

### 3.2 N1 activation (document-review lifecycle→active) — 业务门
- **当前**: `lifecycle: proposal_only`, `activation: forbidden` (`docs/scene-cards/document-review.yaml`)
- **业务门**: 需 operator grant + `permission_ref` + business confirmation (**fabric 红线, 不伪造**)
- **CDP 9222**: seeyon_oa 不可用 (需开 CDP), apple_mail/netease_mailmaster 可用 ✅
- **fabric 红线**: `lifecycle→active` 必须 succeeded/degraded evidence + operator grant

### 3.3 N9 全覆盖 (所有 iris connector 走 mesh receipt) — P0 完整后顺势
- **基础**: `mesh-iris-executor` (#969) 支持任意 connector
- **静态契约**: ✅ 全兼容 (2.1)
- **动态**: 10 可用 connector 可立即走 mesh receipt, 10 不可用需 credentials/CDP
- **顺势**: P0 完整后, mesh workflow 自动触发 → 全覆盖

---

## 4. 下个 session 入口

```bash
# 1. 读本 handoff
cat /Users/xiamingxing/Workspace/ECCP-HANDOFF.md

# 2. P0 完整评估切入点
rg "def dispatch_task|def _bridge_dispatch_to_mesh" projects/omo/src/omo/omo_worker_dispatch.py
rg "iris-executor|capability_refs" projects/omo/src/omo/
cat projects/omo/.omo/_truth/registry/workers.yaml 2>/dev/null || find projects/omo -name "workers.yaml"

# 3. N9 全覆盖验证
cd projects/kairon && uv run --package iris iris --json status
cd /Users/xiamingxing/Workspace && python3 bin/ssot/mesh-iris-executor.py --connector apple_mail --dry-run

# 4. N1 activation 业务门
cat docs/scene-cards/document-review.yaml  # lifecycle/activation 字段
```

---

## 5. ECCP 顶层判断

- **技术交付完整**: 9 PR + 3 零代码 + P0 第一块 + 完整第一块 (`mesh-iris-executor`)
- **剩余**: P0 完整 (omo 深度, 独立 session) + N1 activation (业务门) + N9 全覆盖 (P0 完整后顺势)
- **建议**: 开新 session 啃 P0 完整 (worker 自动), 解锁 N9 全覆盖; N1 activation 等业务输入 (operator/permission + CDP 9222)

---

## 6. 关键文件路径

```
bin/ssot/mesh-iris-executor.py                          # N9 P0 核心 (手动跑就位)
bin/ssot/external-resource-catalog.py                   # N1 catalog (跨项目扫 iris)
bin/ssot/gen-scene-card-lineage.py                      # N8 scene-card lineage
docs/scene-cards/document-review.yaml                   # N1 scene (lifecycle: proposal_only)
projects/kairon/packages/iris/src/iris/base.py          # BaseConnector 契约
projects/kairon/packages/iris/src/iris/connectors/      # 20 connector (rss 退役)
projects/omo/src/omo/omo_worker_dispatch.py             # P0 完整集成点 (dispatch_task:151)
projects/omo/src/omo/workflow_mesh.py                   # mesh 状态机
projects/omo/src/omo/omo_external_receipt.py            # record_external_receipt (:142)
.omo/standards/external-connection-fabric.md            # fabric 标准 (红线)
```
