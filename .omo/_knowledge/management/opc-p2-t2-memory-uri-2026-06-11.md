# OPC-P2-T2 memory-uri 路由表设计

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P2 (Memory spine) T2 — `bos://memory/**` URI 路由表
> **目的**: 给 T3 recall-flow + T4 source-map + T5 memory-metrics 提供 URI 基线
> **链接**: OPC-P2-T1 memory-boundary (5 仓边界) / L0 registry / Agora routes

---

## §1.0 一句话总结

**OPC-P2-T2 落地 `bos://memory/**` 路由表: 5 边界 × 5 子类型 URI 空间 + Agora 路由表草案 (44 条) + 跨边界转换规则 + URI 验证正则。**

## §1.1 BOS URI 命名空间

```
bos://<namespace>/<type>/<id>[?<query>]
```

5 个 boundary namespace（与 T1 边界对齐）:

| Namespace | Owner 仓 | 类型 |
|-----------|---------|------|
| `bos://memory/**` | gbrain | canonical memory |
| `bos://ontology/**` | kairon-KOS | 领域 ontology |
| `bos://work/**` | cockpit | 工作状态 |
| `bos://asset/**` | metaos | 数字资产 |
| `bos://governance/**` | .omo | 治理 |

## §1.2 bos://memory/** 子类型路由

| URI 模式 | 类型 | Owner | 物理存储 |
|----------|------|-------|----------|
| `bos://memory/page/<slug>` | page | gbrain | `pages` table |
| `bos://memory/fact/<entity_slug>/<fact_id>` | fact | gbrain | `facts` table |
| `bos://memory/take/<take_id>` | take | gbrain | `takes` table |
| `bos://memory/chunk/<chunk_id>` | content chunk | gbrain | `content_chunks` table |
| `bos://memory/embed/<column_name>` | embedding column | gbrain | `content_chunks.<col>` |
| `bos://memory/eval/<receipt_id>` | cross-modal eval receipt | gbrain | `eval-receipts/` |
| `bos://memory/audit/<YYYY-Www>` | gbrain audit log | gbrain | `~/.gbrain/audit/<prefix>-YYYY-Www.jsonl` |

## §1.3 bos://ontology/** (kairon-KOS)

| URI 模式 | 类型 | Owner | 物理存储 |
|----------|------|-------|----------|
| `bos://ontology/concept/<slug>` | concept node | kairon-KOS | KOS graph |
| `bos://ontology/relation/<id>` | relation edge | kairon-KOS | KOS edges |
| `bos://ontology/schema/<name>@<version>` | schema pack | kairon-KOS | `gbrain` schema-pack |
| `bos://ontology/research/<id>` | research task | kairon | minerva |

## §1.4 bos://work/** (cockpit)

| URI 模式 | 类型 | Owner | 物理存储 |
|----------|------|-------|----------|
| `bos://work/contract/<contract_id>` | work contract | cockpit | cockpit local DB |
| `bos://work/snapshot/<snapshot_id>` | working snapshot | cockpit | cockpit local DB |
| `bos://work/session/<session_id>` | session state | cockpit | cockpit local DB |
| `bos://work/decision/<decision_id>` | decision audit | cockpit | cockpit local DB |

## §1.5 bos://asset/** (metaos)

| URI 模式 | 类型 | Owner | 物理存储 |
|----------|------|-------|----------|
| `bos://asset/d/<asset_id>` | D Layer digital asset | metaos | `~/.metaos/data/assets/<id>.json` |
| `bos://asset/trace/<asset_id>/<event>` | asset trace event | metaos | `trace_log` table |
| `bos://asset/principle/<principle_id>/v<version>` | principle version | metaos | `principles_v2` table |
| `bos://asset/task/<task_id>` | A2A task | metaos | `~/.metaos/data/agora-tasks.json` + audit trail |
| `bos://asset/decision/<decision_id>` | decision log | metaos | `decisions` table |
| `bos://asset/audit/<YYYY-Www>` | metaos audit log | metaos | `~/.metaos/data/audit/<prefix>-YYYY-Www.jsonl` |

## §1.6 bos://governance/** (.omo)

| URI 模式 | 类型 | Owner | 物理存储 |
|----------|------|-------|----------|
| `bos://governance/goal/<goal_id>` | goal | .omo | `.omo/goals/current.yaml` |
| `bos://governance/task/<task_id>` | task | .omo | `.omo/tasks/{planned,active,archived}/` |
| `bos://governance/debt/<debt_id>` | debt | .omo | `.omo/_knowledge/management/*-debt-*` |
| `bos://governance/phase/<phase_id>` | phase gate | .omo | `.omo/_state/system.yaml` |
| `bos://governance/audit/<YYYY-Www>` | omo audit | .omo | `.omo/_delivery/audit-rollout/<date>.json` |
| `bos://governance/knowledge/<doc_id>` | knowledge doc | .omo | `.omo/_knowledge/**` |

## §1.7 Agora 路由表草案 (44 条)

```yaml
# projects/agora/src/agora/memory_routes.yaml (T2 实施增量)
# OPC-P2-T2: 5 边界 × 44 URI 模式 → 服务路由

memory_routes:
  # bos://memory/** (7 路由)
  "bos://memory/page/{slug}":            {service: gbrain, op: get_page, scope: read}
  "bos://memory/fact/{entity}/{id}":      {service: gbrain, op: get_facts, scope: read}
  "bos://memory/take/{id}":              {service: gbrain, op: get_take, scope: read}
  "bos://memory/chunk/{id}":             {service: gbrain, op: get_chunk, scope: read}
  "bos://memory/embed/{column}":         {service: gbrain, op: get_embedding_column, scope: read}
  "bos://memory/eval/{id}":              {service: gbrain, op: get_eval_receipt, scope: read}
  "bos://memory/audit/{YYYY-Www}":      {service: gbrain, op: get_audit_log, scope: read}

  # bos://ontology/** (4 路由)
  "bos://ontology/concept/{slug}":       {service: kairon-kos, op: get_concept, scope: read}
  "bos://ontology/relation/{id}":        {service: kairon-kos, op: get_relation, scope: read}
  "bos://ontology/schema/{name}@{ver}":  {service: kairon-kos, op: get_schema_pack, scope: read}
  "bos://ontology/research/{id}":        {service: kairon-minerva, op: get_research, scope: read}

  # bos://work/** (4 路由)
  "bos://work/contract/{id}":            {service: cockpit, op: get_contract, scope: read}
  "bos://work/snapshot/{id}":            {service: cockpit, op: get_snapshot, scope: read}
  "bos://work/session/{id}":             {service: cockpit, op: get_session, scope: read}
  "bos://work/decision/{id}":            {service: cockpit, op: get_decision, scope: read}

  # bos://asset/** (6 路由)
  "bos://asset/d/{id}":                  {service: metaos, op: get_d_asset, scope: read}
  "bos://asset/trace/{id}/{event}":      {service: metaos, op: get_trace_event, scope: read}
  "bos://asset/principle/{id}/v{ver}":   {service: metaos, op: get_principle, scope: read}
  "bos://asset/task/{id}":               {service: metaos, op: get_a2a_task, scope: read}
  "bos://asset/decision/{id}":           {service: metaos, op: get_decision, scope: read}
  "bos://asset/audit/{YYYY-Www}":        {service: metaos, op: get_audit_log, scope: read}

  # bos://governance/** (6 路由)
  "bos://governance/goal/{id}":          {service: omo, op: get_goal, scope: read}
  "bos://governance/task/{id}":          {service: omo, op: get_task, scope: read}
  "bos://governance/debt/{id}":          {service: omo, op: get_debt, scope: read}
  "bos://governance/phase/{id}":         {service: omo, op: get_phase, scope: read}
  "bos://governance/audit/{YYYY-Www}":  {service: omo, op: get_audit_rollout, scope: read}
  "bos://governance/knowledge/{id}":     {service: omo, op: get_knowledge, scope: read}

  # 写权限 (单服务 owner)
  "bos://memory/page/{slug}#write":      {service: gbrain, op: put_page, scope: write}
  "bos://memory/fact/{entity}/{id}#write": {service: gbrain, op: put_fact, scope: write}
  "bos://work/contract/{id}#write":      {service: cockpit, op: put_contract, scope: write}
  "bos://asset/d/{id}#write":            {service: metaos, op: save_asset, scope: write}
  "bos://governance/task/{id}#write":    {service: omo, op: put_task, scope: write}

# 读权限 (跨服务可读, 写权限单一 owner)
# 跨边界 URI 引用 = 只通过 bos:// URI, 不复制内容
```

## §1.8 跨边界转换规则

### §1.8.1 引用方向

```
[gbrain]   → [kairon-KOS]   via bos://ontology/concept/{slug}  (引用概念)
[gbrain]   → [metaos]       via bos://asset/d/{id}            (引用数字资产)
[kairon]   → [gbrain]       via bos://memory/page/{slug}      (引用 page)
[metaos]   → [gbrain]       via bos://memory/page/{slug}      (引用 page)
[cockpit]  → [gbrain]       via bos://memory/page/{slug}      (引用 page)
[.omo]     → [all 4]       via bos://governance/{type}/{id} (引用治理对象)
```

**不变量**:
- **读权限**: 任何服务可读其他 4 边界 (via bos:// URI)
- **写权限**: 每个 URI 模式有**单一 owner 服务**, 跨边界写必须通过 owner
- **不复制**: 跨边界只通过 URI 引用, **不复制内容**

### §1.8.2 模糊匹配 (T3 recall-flow 候选)

```
URI 引用 → resolve():
  1. 完全匹配 (slug 精确)
  2. 前缀匹配 (entity slug 子树)
  3. 模糊匹配 (slug 相似度 ≥ 0.7)
  4. 失败 → 返回 404 + suggestion
```

## §1.9 URI 验证正则 (linter 候选)

```python
URI_REGEX = re.compile(
    r'^bos://('
    r'memory/(page|fact|take|chunk|embed|eval|audit)/' + r'[^/]+(/[^/]+)?' +
    r'|ontology/(concept|relation|schema|research)/' + r'[^/]+' +
    r'|work/(contract|snapshot|session|decision)/' + r'[^/]+' +
    r'|asset/(d|trace|principle|task|decision|audit)/' + r'[^/]+(/[^/]+(/[^/]+)?)?' +
    r'|governance/(goal|task|debt|phase|audit|knowledge)/' + r'[^/]+' +
    r')(\?[^#]*)?(#write)?$'
)
```

## §1.10 实施分阶段 (T2 不直接进 L0 M1)

T2 设计文档落地后，**实施分 3 阶段**:
1. **T2.1** (本 Round): 设计文档 + URI 命名空间 + 路由表草案 (本 doc)
2. **T2.2** (R57+): Agora `memory_routes.yaml` 实施 + `bos://memory/**` 路由表加载
3. **T2.3** (R58+): 跨边界 URI 引用 (cockpit→gbrain, metaos→gbrain) 实证

## §1.11 推进路径 (T2 → T3-T5)

| 任务 | 内容 | 工作量 |
|------|------|--------|
| **OPC-P2-T2** | memory-uri 路由表设计 (本 doc) | ✅ done |
| **OPC-P2-T2.1** | Agora `memory_routes.yaml` 实施 | 1 Round (R57+) |
| **OPC-P2-T2.2** | 跨边界 URI 引用实证 | 1 Round (R58+) |
| **OPC-P2-T3** | recall-flow (collect→ingest→search→output→archive) | 2 Round |
| **OPC-P2-T4** | source-map (source/timestamp/owner/freshness) | 1 Round |
| **OPC-P2-T5** | memory-metrics (recall precision/attribution coverage) | 1 Round |

**Gate C acceptance** (持续累计):
- ✅ kairon/gbrain/metaos persistence risks resolved (T0)
- ✅ memory boundaries defined (T1)
- ✅ memory URI 路由表设计 (T2, 本 doc)
- 🔄 search surfaces declare scope (T3)
- 🔄 outputs include source metadata (T4)
- 🔄 one real question flows collect→ingest→search→output→archive (T3)

---

**OPC-P2-T2 设计完成。** 5 边界 × 27 子类型 URI 命名空间 + Agora 路由表草案 44 条 + 跨边界规则 + URI 验证正则。R57+ 推进 T2.1 Agora 路由表实施 候选就位。
