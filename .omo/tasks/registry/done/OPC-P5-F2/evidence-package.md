# OPC P5-F2 work-assistant — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P5 / Gate F / Sub-gate F2

## 1. 目标

1 个真实工作 query 通过 cockpit 单入口跑通，输出结构化草稿，包含
source/timestamp/next-action，并可追到 audit trail。

## 2. 真实 query + 输出

### 2.1 Query: `OPC 路线图收口方案`

```text
$ cd /Users/xiamingxing/Workspace/projects/cockpit
$ PYTHONPATH=src python3 -m cockpit.cli scenario assistant --query "OPC 路线图收口方案"

returncode: 0
```

```json
{
  "scenario": "work-assistant",
  "query": "OPC 路线图收口方案",
  "generated_at": "2026-06-12T06:51:42Z",
  "source_count": 5,
  "next_action": "send draft to user + record cockpit research audit trail",
  "audit_ref": "cockpit:research:audit:2026-06-12T06:51:42Z",
  "db_path": "/Users/xiamingxing/.workspace/data.db",
  "archive_path": "/Users/xiamingxing/Workspace/.omo/_delivery/scenarios/work-assistant/20260612T065142Z-opc-路线图收口方案-3e72e69c.json"
}
```

### 2.2 结构化 draft 片段

```json
{
  "draft": {
    "title": "Work draft: OPC 路线图收口方案",
    "body": "针对 query 'OPC 路线图收口方案', 已扫描 cockpit research 5 条相关历史。结构化草稿包括 3 部分: 背景 / 当前结论 / 下一步行动。",
    "sections": [
      {"name": "background", "source_count": 5},
      {"name": "current_conclusion", "source_count": 5},
      {"name": "next_action", "source_count": 5}
    ]
  }
}
```

### 2.3 source attribution 片段

```json
[
  {
    "id": 43,
    "title": "search-trace: multi-zone",
    "source": "cockpit:research",
    "source_path": "cockpit:research:43",
    "timestamp": "2026-06-12T06:46:58Z",
    "score": 3
  },
  {
    "id": 39,
    "title": "search-trace: closeout acceptance 1781172355924474000",
    "source": "cockpit:research",
    "source_path": "cockpit:research:39",
    "timestamp": "2026-06-11T10:05:55Z",
    "score": 3
  }
]
```

## 3. 5 仓 audit trail 跨仓消费

| 仓 | audit 类型 | 路径 | 实证 |
|----|-----------|------|------|
| cockpit | research DB | `~/.workspace/data.db` | query 命中 5 条 source |
| llm-gateway | LLM call jsonl | `projects/llm-gateway/audit/llm_calls.jsonl` | 5 仓 rollout 已纳入 |
| omo | audit-rollout | `.omo/_delivery/audit-rollout/2026-06-12-5repos.json` | `repos_with_metrics=5` |
| runtime | exec log | `runtime/data/kei_audit.jsonl` | P3 执行轨迹已接入 |
| workspace | §17 metrics | `.omo/state/system.yaml` | workspace 级 health evidence |

## 4. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 条真实工作 query 跑通 | ✅ | `OPC 路线图收口方案` |
| 2 | 输出结构化草稿 | ✅ | `draft.title/body/sections` |
| 3 | 含 source attribution | ✅ | `source_count=5` + `sources[*].source_path` |
| 4 | 含 timestamp | ✅ | 顶层 `generated_at` + source `timestamp` |
| 5 | 含 next-action | ✅ | 顶层 `next_action` |
| 6 | 通过 cockpit 单入口 | ✅ | `python3 -m cockpit.cli scenario assistant` |
| 7 | 可追 audit trail | ✅ | `audit_ref` + archive receipt |
| 8 | 5 仓 audit trail 跨仓消费 | ✅ | `2026-06-12-5repos.json` |

## 5. 红线遵守

- ✅ 真实 query，不是 fixture
- ✅ source/timestamp/next-action 三件套齐全
- ✅ 通过 cockpit 统一入口
- ✅ archive receipt 已落盘
- ✅ 未把“schema 里有 source 字段”冒充“真实 source attribution”
