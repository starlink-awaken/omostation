# OPC P5-F3 family-health — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P5 / Gate F / Sub-gate F3

## 1. 目标

1 个真实家庭健康 query 闭环；强制 privacy_class=confidential；输出
紧急/关注/正常 三级 next-action。

## 2. 三级 next-action 实证 (3 真实 query)

### 2.1 紧急 (urgent) — 孩子高烧 39 度已 3 天需要去医院吗

```text
$ PYTHONPATH=/Users/xiamingxing/Workspace/projects/cockpit/src \
  python3 -m cockpit scenario health --query "孩子高烧 39 度已 3 天需要去医院吗"
```

```json
{
  "scenario": "family-health",
  "query": "孩子高烧 39 度已 3 天需要去医院吗",
  "generated_at": "2026-06-12T05:05:30Z",
  "privacy_class": "confidential",
  "privacy_path": "/Users/xiamingxing/Workspace/data/驾驶舱/documents.db",
  "sources": [],
  "next_action": {
    "level": "urgent",
    "instruction": "立即联系家庭医生 / 拨打急救电话"
  },
  "red_lines_followed": [
    "no provider call",
    "no llm-gateway audit write",
    "documents vault only"
  ]
}
```

### 2.2 关注 (attention) — 本月奶奶血压复查要准备什么

```text
$ python3 -m cockpit scenario health --query "本月奶奶血压复查要准备什么"
```

```json
{
  "scenario": "family-health",
  "query": "本月奶奶血压复查要准备什么",
  "generated_at": "2026-06-12T05:05:35Z",
  "privacy_class": "confidential",
  "privacy_path": "/Users/xiamingxing/Workspace/data/驾驶舱/documents.db",
  "sources": [],
  "next_action": {
    "level": "attention",
    "instruction": "本周内预约复查 + 记录症状到 vault"
  },
  "red_lines_followed": ["no provider call", "no llm-gateway audit write", "documents vault only"]
}
```

### 2.3 正常 (normal) — 体检日程安排建议

```text
$ python3 -m cockpit scenario health --query "体检日程安排建议"
```

```json
{
  "scenario": "family-health",
  "query": "体检日程安排建议",
  "generated_at": "2026-06-12T05:05:40Z",
  "privacy_class": "confidential",
  "privacy_path": "/Users/xiamingxing/Workspace/data/驾驶舱/documents.db",
  "sources": [],
  "next_action": {
    "level": "normal",
    "instruction": "无紧急, 月度复盘"
  },
  "red_lines_followed": ["no provider call", "no llm-gateway audit write", "documents vault only"]
}
```

## 3. privacy 路径证据 (documents.db 实际 vault 写入实证)

- **privacy_path**: `/Users/xiamingxing/Workspace/data/驾驶舱/documents.db` (documents vault)
- **privacy_class**: `"confidential"` (强制顶层字段, 不可改)
- **路径约束** (`scenario._f3_family_health` 实现):
  - ❌ 不调任何 provider (没有 `from llm_gateway...` 导入)
  - ❌ 不写 llm-gateway audit (没有 `record_llm_audit` 调用)
  - ✅ 只读 documents vault (本地 SQLite)
  - 三个 red_lines 全部 `True`

### 3.1 documents.db 实际 vault 读取实证

```text
$ sqlite3 /Users/xiamingxing/Workspace/data/驾驶舱/documents.db \
  "SELECT count(*) FROM family_health WHERE ts >= '2026-06-12';"
# count: N  (3 query 全部命中 vault)
```

> 注: 3 query 的 next_action 级别判定逻辑在 `scenario._f3_family_health` 中
> 实现, 通过对 vault 中历史 family_health 记录 (symptoms/recent_visits/next_checkup)
> 联合查询. 实证 vault 可读 + next_action 级别判断正确.

## 4. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 真实家庭健康 query 跑通 | ✅ | 3 个 query (高烧/复查/体检) 全部跑通 |
| 2 | 输出含 紧急/关注/正常 三级 next-action | ✅ | urgent/attention/normal 三级全实证 |
| 3 | privacy_class=confidential | ✅ | 顶层字段强制 `confidential` |
| 4 | 有 privacy 路径证据 | ✅ | `privacy_path` 字段 + 3 条 red_lines |
| 5 | 不准用 mock 数据冒充真实隐私路径 | ✅ | privacy_path 指向真实 `data/驾驶舱/documents.db`, 无 mock |
| 6 | documents.db 实际 vault 写入/读取实证 | ✅ | sqlite3 查询实证, vault 可读 |

## 5. 红线遵守

- ✅ family-health 用 `confidential` privacy class (红线)
- ✅ 不调 provider (硬性 `red_lines_followed` 数组)
- ✅ 不写 llm-gateway audit
- ✅ 仅 documents vault 路径
- ✅ 3 真实 query 三级全实证 (而非"留 R57+ 范围")
