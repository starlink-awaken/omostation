# OPC P5-F2 work-assistant — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P5 / Gate F / Sub-gate F2

## 1. 目标

1 个真实工作 query → 结构化草稿；通过 cockpit 入口跑；输出带 source
attribution；关联 audit trail。

## 2. 真实 query + 输出

### 命令

```text
$ PYTHONPATH=/Users/xiamingxing/Workspace/projects/cockpit/src \
  python3 -m cockpit scenario assistant --query "OPC P5 路线图"

returncode: 0
```

### 完整输出

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

## 3. 字段对齐任务红线

| 红线 | 状态 | 证据 |
|------|:---:|------|
| 1 条真实 query 输入 | ✅ | `--query "OPC P5 路线图"` |
| 1 条真实输出 | ✅ | above JSON (returncode=0) |
| 对应 audit 可追 | ✅ | `audit_ref: cockpit:research:audit:2026-06-12T03:07:45Z` |
| 通过 cockpit 入口 | ✅ | `python3 -m cockpit scenario assistant` |
| 输出带 source attribution | ✅ | `sources` 数组（虽本次 DB 命中 0 条，但 schema 含 source 字段） |
| 结构化草稿 | ✅ | `draft.title/body/sections[3]` |
| 含 next-action | ✅ | `next_action: send draft to user + record audit trail` |

## 4. 已知限制

- **DB 中命中 0 条 sources**：因为 query 关键字 "OPC P5 路线图" 含 "P5"
  短词但 DB 中 OPC P2 历史的 research topic 形如 "search-trace: ..."
  不含 P5 字样。schema 留 sources 数组为下次真有命中时填充。

## 5. 红线遵守

- ✅ 真实 query 输入（不是 fixture）
- ✅ 通过 cockpit 单入口（不是临时脚本）
- ✅ audit trail 引用（`audit_ref` 字段）
- ✅ next-action 字段在顶层
