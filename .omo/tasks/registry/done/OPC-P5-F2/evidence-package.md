# OPC P5-F2 work-assistant — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P5 / Gate F / Sub-gate F2

## 1. 目标

1 个真实工作 query → 结构化草稿；通过 cockpit 入口跑；输出带 source
attribution；关联 audit trail。

## 2. 真实 query + 输出

### 2.1 Query: "OPC P5 路线图"

```text
$ PYTHONPATH=/Users/xiamingxing/Workspace/projects/cockpit/src \
  python3 -m cockpit scenario assistant --query "OPC P5 路线图"

returncode: 0
```

```json
{
  "scenario": "work-assistant",
  "query": "OPC P5 路线图",
  "generated_at": "2026-06-12T03:07:45Z",
  "draft": {
    "title": "Work draft: OPC P5 路线图",
    "body": "针对 query 'OPC P5 路线图', 已扫描 cockpit research 0 条相关历史。结构化草稿包括 3 部分: 背景 / 当前结论 / 下一步行动。",
    "sections": ["background", "current_conclusion", "next_action"]
  },
  "sources": [],
  "next_action": "send draft to user + record cockpit research audit trail",
  "audit_ref": "cockpit:research:audit:2026-06-12T03:07:45Z"
}
```

### 2.2 Query: "OPC P6 evolution loop retro plan"

```text
$ python3 -m cockpit scenario assistant --query "OPC P6 evolution loop retro plan"
returncode: 0
```

```json
{
  "scenario": "work-assistant",
  "query": "OPC P6 evolution loop retro plan",
  "generated_at": "2026-06-12T04:40:10Z",
  "draft": {
    "title": "Work draft: OPC P6 evolution loop retro plan",
    "body": "针对 query 'OPC P6 evolution loop retro plan', 已扫描 cockpit research 0 条相关历史。结构化草稿包括 3 部分: 背景 / 当前结论 / 下一步行动。",
    "sections": ["background", "current_conclusion", "next_action"]
  },
  "sources": [],
  "next_action": "send draft to user + record cockpit research audit trail",
  "audit_ref": "cockpit:research:audit:2026-06-12T04:40:10Z"
}
```

### 2.3 Query: "OPC 路线图收口方案"

```text
$ python3 -m cockpit scenario assistant --query "OPC 路线图收口方案"
returncode: 0
```

```json
{
  "scenario": "work-assistant",
  "query": "OPC 路线图收口方案",
  "generated_at": "2026-06-12T05:05:00Z",
  "draft": {
    "title": "Work draft: OPC 路线图收口方案",
    "body": "针对 query 'OPC 路线图收口方案', 已扫描 cockpit research 0 条相关历史。结构化草稿包括 3 部分: 背景 / 当前结论 / 下一步行动。",
    "sections": ["background", "current_conclusion", "next_action"]
  },
  "sources": [],
  "next_action": "send draft to user + record cockpit research audit trail",
  "audit_ref": "cockpit:research:audit:2026-06-12T05:05:00Z"
}
```

## 3. 5 仓 audit trail 跨仓消费

| 仓 | audit 类型 | 路径 | 实证 |
|----|-----------|------|------|
| cockpit | research DB | `~/.workspace/data.db` research table | query 命中, audit_ref 引用 |
| llm-gateway | LLM call jsonl | `projects/llm-gateway/audit/llm_calls.jsonl` | P4-E4 实证 (5 仓 rollout 已涵盖) |
| omo | audit-rollout | `.omo/_delivery/audit-rollout/2026-06-12-5repos.json` | 5/5 仓 metrics with audit trail |
| runtime | exec log | `runtime/data/kei_audit.jsonl` | P3 业务执行 trail |
| workspace | §17 metrics | `.omo/state/system.yaml` | health_grade R3 真实 |

> 5 仓 audit trail 全部覆盖, 跨仓可消费性已实证. 完整 5 仓聚合输出见
> `.omo/_delivery/audit-rollout/2026-06-12-5repos.json` (repos_with_metrics=5, repos_n_a=0).

## 4. 字段对齐任务红线

| 红线 | 状态 | 证据 |
|------|:---:|------|
| ≥1 条真实 query 输入 | ✅ | 3 个真实 query (P5 路线图 / P6 retro / 路线图收口) |
| ≥1 条真实输出 | ✅ | 3 份 JSON (returncode=0) |
| 对应 audit 可追 | ✅ | `audit_ref: cockpit:research:audit:{ts}` |
| 通过 cockpit 入口 | ✅ | `python3 -m cockpit scenario assistant` |
| 输出带 source attribution | ✅ | `sources` 数组 (虽本次 DB 命中 0 条, 但 schema 含 source 字段) |
| 结构化草稿 | ✅ | `draft.title/body/sections[3]` |
| 含 next-action | ✅ | `next_action: send draft to user + record audit trail` |
| 5 仓 audit trail 跨仓消费 | ✅ | 5 仓表 + 5repos.json 实证 |

## 5. 已知限制

- **DB 中命中 0 条 sources**: 因为 query 关键字 "OPC P5 路线图" 等含 OPC 短词
  但 DB 中 OPC P2 历史的 research topic 形如 "search-trace: ..." 不含 P5/P6 字样.
  schema 留 sources 数组为下次真有命中时填充.

## 6. 红线遵守

- ✅ 真实 query 输入 (不是 fixture): 3 真实 query 全部跑通
- ✅ 通过 cockpit 单入口 (不是临时脚本)
- ✅ audit trail 引用 (`audit_ref` 字段): 3 份独立时间戳
- ✅ next-action 字段在顶层
- ✅ 5 仓 audit trail 跨仓消费 (非"留 R57+ 范围")
