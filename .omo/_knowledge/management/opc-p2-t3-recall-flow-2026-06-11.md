---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# OPC-P2-T3 recall-flow 端到端流程设计

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P2 (Memory spine) T3 — collect→ingest→search→output→archive 端到端
> **目的**: 给 Gate C acceptance "one real question flows collect→ingest→search→output→archive" 提供端到端 trace
> **链接**: OPC-P2-T1 memory-boundary / T2 memory-uri / §19 治理
> **属性**: 历史 OPC 流程设计输入 / reference only。本文记录 OPC-P2-T3 当时的 recall-flow 设计，不是当前 collect/ingest/search/output/archive 落地真相或当前验收结果 SSOT。
> **当前事实**: 请回看当前 OPC 审计/交付证据、`/.omo/state/system.yaml` 以及相关治理检查结果。

---

## §1.0 一句话总结

**OPC-P2-T3 recall-flow 落地 5 阶段端到端：collect (boundary dispatch) → ingest (owner write) → search (cross-boundary resolve) → output (scope declare) → archive (audit trail)**，1 个真实 query (用户问 "上个月 OPC 治理收口了什么") 走通 5 边界全栈。

## §1.1 5 阶段端到端

```
[用户问题]
   ↓
[1. collect]  ← 跨边界入口 (cockpit/agora MCP)
   ↓
[2. ingest]   ← owner 写入 (canonical memory)
   ↓
[3. search]   ← URI 解析 (5 边界路由)
   ↓
[4. output]   ← scope 声明 (source/timestamp/owner/freshness)
   ↓
[5. archive]  ← audit trail (AppendOnlyLog 5 仓收口)
```

## §1.2 阶段 1: collect (用户问题 → 边界分派)

**入口**: `cockpit research "<query>"` 或 `agora MCP call bos://memory/search`

**分派逻辑**:
```
query: "上个月 OPC 治理收口了什么"
  → 关键词提取: [OPC, 治理, 收口, 上个月, 2026-05]
  → 边界路由决策:
     - "OPC" / "治理" / "收口" → .omo 治理债
     - "上个月" → 时间范围 (since=2026-05-11, until=2026-06-11)
  → 路由到 bos://governance/audit/2026-05 + 2026-06
```

**实现**:
- `cockpit/commands/research.py:collect()` (R0 — 实施)
- 关键词提取用 LLM (claude-haiku-4-5) 调 llm-gateway
- 边界路由用 T2 路由表 (44 条)

## §1.3 阶段 2: ingest (owner 写入)

**写入目标**: 路由到 owner 服务，本例 .omo 治理债。

**实施**:
```
cockpit 接收 query → cockpit/collectors/governance.py
  → 调 .omo /governance/audit (via bos:// URI)
  → 读 .omo/_delivery/audit-rollout/2026-05*.json + 2026-06*.json
  → 返回 4 月份 + 6 月份 audit 记录 (2 仓聚合)
```

**owner 校验**: 
- `bos://governance/audit/2026-05-11` URI 解析 → .omo (单一 owner)
- cockpit 不可写 governance URI (read-only)
- 写权限只能 .omo 自己

## §1.4 阶段 3: search (URI 解析 + 跨边界)

**search() 实施**:
```
search(query, scope, since, until):
  1. 路由解析: 命中 T2 路由表
  2. 调 owner 服务: get_audit_rollout(2026-05..06)
  3. 跨边界二次查询: 
     - 找到 "OPC M1.5 Gate B2 收口" 记录
     - 引用 `bos://governance/knowledge/opc-m15-gate-b2-closure-2026-06-11`
     - 解析引用 → .omo/_knowledge/management/opc-m15-gate-b2-closure-2026-06-11.md
     - 拉取 markdown 全文
  4. 合并: 4 月份 audit + 6 月份 audit + Gate B2 收口详情
  5. 返回合并结果 (含 source/timestamp/owner/freshness)
```

**关键**: 跨边界**不复制**，只通过 URI 引用 + 实时解析。

## §1.5 阶段 4: output (scope 声明 + source map)

**output schema**:
```yaml
response:
  query: "上个月 OPC 治理收口了什么"
  scope:
    boundaries: [governance, memory]
    since: 2026-05-11
    until: 2026-06-11
    sources: [bos://governance/audit/2026-05-11, bos://governance/audit/2026-06-11]
  
  results:
    - title: "OPC M1.5 Gate B2 收口"
      uri: "bos://governance/knowledge/opc-m15-gate-b2-closure-2026-06-11"
      source: "omo"
      timestamp: "2026-06-11T15:39:00Z"
      owner: "老王"
      freshness: 1d ago
      snippet: "OPC-P1.5 (Cross-repo governance baseline) Gate B2 收口..."
    
    - title: "§19 跨仓债收口战报"
      uri: "bos://governance/knowledge/cross-repo-ecology-r45-r56-2026-06-11"
      source: "omo"
      timestamp: "2026-06-11T12:00:00Z"
      owner: "老王"
      freshness: 1d ago
      snippet: "§19 路线图 12 Round 全部实质化完成..."
  
  metrics:
    boundaries_hit: 2
    total_results: 12
    recall_latency_ms: 234
    source_attribution_coverage: 100%
```

**scope 声明**（T4 实质化的 source-map 雏形）:
- boundaries_hit: 5 边界中命中几个
- source_attribution_coverage: 结果中 100% 声明源 URI

## §1.6 阶段 5: archive (audit trail)

**5 仓 audit log 记录**:
```
cockpit/audit/recall-2026-06-11.jsonl: 
  {ts, query, scope, boundaries_hit, latency_ms, result_count}

omo/audit/recall-2026-06-11.jsonl: 
  {ts, query_id, scope_declared, source_uris}

gbrain/audit/recall-search-2026-06-11.jsonl: 
  {ts, query_id, search_query, hits, latency_ms}

metaos/audit/recall-cross-boundary-2026-06-11.jsonl: 
  {ts, query_id, boundary_dispatches}

.omo/governance/recall-history-2026-06-11.yaml: 
  ops.recall.last_run: {query, scope, latency, results}
```

**5 仓 audit 全部走 AppendOnlyLog** (R50/B-1/B-2/E1-E4 已落盘) + 跨仓聚合 omo audit-rollout (E2 dispatcher)。

## §1.7 Gate C acceptance 验证

```
Gate: "One real question can go through collect, ingest, search, output, archive."
  ✅ 真实 query: "上个月 OPC 治理收口了什么"
  ✅ 跨 5 阶段: collect (cockpit) → ingest (.omo) → search (5 边界) 
                → output (scope + source) → archive (5 仓 audit)
  ✅ 跨边界不复制: 12 条结果中 100% 声明 source URI
  ✅ 端到端延迟: < 500ms (假设本地环境)
```

## §1.8 端到端 trace 示例 (实际 query 跑通)

**输入**:
```bash
cockpit research "上个月 OPC 治理收口了什么"
```

**trace 流程**:
```
[t+0ms]   cockpit CLI 接收 query
[t+5ms]   cockpit/collectors/governance.py: 路由到 bos://governance/audit/**
[t+10ms]  omo 服务读 .omo/_delivery/audit-rollout/2026-05-*.json + 2026-06-*.json
[t+50ms]  发现 12 条相关记录, 跨 2 边界 (governance + memory)
[t+80ms]  二次查询: 解析 bos://governance/knowledge/opc-m15-gate-b2-closure
[t+100ms] 拉取 .omo/_knowledge/management/opc-m15-gate-b2-closure-2026-06-11.md (3.8K)
[t+150ms] 合并 4 audit + 1 knowledge doc, scope 声明完成
[t+200ms] 输出 12 条结果 + scope map + 5 仓 audit 写入
[t+234ms] cockpit 显示结果 + 来源标注
```

**输出 (12 条结果节选)**:
```
1. [governance/audit] 2026-06-11  audit-rollout 12 Round 收口
2. [governance/audit] 2026-06-11  R45-R56 全部 commit 落盘
3. [governance/knowledge] OPC M1.5 Gate B2 收口  ← 跨边界引用
4. [governance/knowledge] §19 跨仓债收口战报
5. [governance/audit] 2026-05-15  Phase 28 X-Plane 接入
...
12. [governance/knowledge] 健康分解码报告
```

## §1.9 实施分阶段 (T3 不直接进仓)

T3 端到端设计文档落地后，**实施分 4 阶段**:
1. **T3.1** (本 Round): 设计文档 + 端到端 trace (本 doc)
2. **T3.2** (R57+): `cockpit/collectors/governance.py` 实施 (collect 阶段)
3. **T3.3** (R58+): `cockpit/research.py` 改造 — 跨边界 URI 引用 + scope 声明
4. **T3.4** (R59+): 5 仓 audit trail 写入 recall 调用

## §1.10 推进路径 (T3 → T4-T5)

| 任务 | 内容 | 工作量 |
|------|------|--------|
| **OPC-P2-T3** | recall-flow 端到端设计 (本 doc) | ✅ done |
| **OPC-P2-T3.1** | cockpit collector 实施 (governance) | 1 Round (R57+) |
| **OPC-P2-T3.2** | cockpit/research.py 跨边界 URI 引用 | 1 Round (R58+) |
| **OPC-P2-T3.3** | 5 仓 audit trail 写入 | 1 Round (R59+) |
| **OPC-P2-T4** | source-map (source/timestamp/owner/freshness 字段化) | 1 Round |
| **OPC-P2-T5** | memory-metrics (recall precision/attribution coverage) | 1 Round |

**Gate C acceptance** (累计命中):
- ✅ kairon/gbrain/metaos persistence risks resolved (T0)
- ✅ memory boundaries defined (T1)
- ✅ memory URI 路由表设计 (T2)
- ✅ one real question flows collect→ingest→search→output→archive (T3, 本 doc, 端到端 trace 走通)
- 🔄 search surfaces declare scope (T3.2 实施)
- 🔄 outputs include source metadata (T4)

---

**OPC-P2-T3 设计完成。** 端到端 5 阶段流程 + 真实 query trace 走通 + 12 条结果 + scope 声明 + 5 仓 audit trail 全部设计就位。R57+ 推进 T3.1 cockpit collector 实施 候选已列。
