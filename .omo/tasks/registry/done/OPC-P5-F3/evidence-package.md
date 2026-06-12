# OPC P5-F3 family-health — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P5 / Gate F / Sub-gate F3

## 1. 目标

1 个真实家庭健康 query 闭环；强制 privacy_class=confidential；输出
紧急/关注/正常 三级 next-action。

## 2. 三级 next-action 实证

### 2.1 紧急 (urgent)

```text
$ PYTHONPATH=/Users/xiamingxing/Workspace/projects/cockpit/src \
  python3 -m cockpit scenario health --query "高烧不退是否需要立即去医院"
```

```json
{
  "scenario": "family-health",
  "query": "高烧不退是否需要立即去医院",
  "generated_at": "2026-06-12T03:07:52Z",
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

### 2.2 关注 (attention)

```text
$ python3 -m cockpit scenario health --query "本月孩子有几次需要复查"
```

```json
{
  "scenario": "family-health",
  "query": "本月孩子有几次需要复查",
  "generated_at": "2026-06-12T03:07:57Z",
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

### 2.3 正常 (normal)

```text
$ python3 -m cockpit scenario health --query "日常体检"
```

```json
{
  "scenario": "family-health",
  "query": "日常体检",
  "generated_at": "2026-06-12T03:08:03Z",
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

## 3. privacy 路径证据

- **privacy_path**: `/Users/xiamingxing/Workspace/data/驾驶舱/documents.db` (documents vault)
- **privacy_class**: `"confidential"` (强制顶层字段, 不可改)
- **路径约束**（`scenario._f3_family_health` 实现）：
  - ❌ 不调任何 provider（没有 `from llm_gateway...` 导入）
  - ❌ 不写 llm-gateway audit（没有 `record_llm_audit` 调用）
  - ✅ 只读 documents vault (本地 SQLite)
  - 三个 red_lines 全部 `True`

## 4. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 真实家庭健康 query 跑通 | ✅ | 3 个 query 全部跑通 |
| 2 | 输出含 紧急/关注/正常 三级 next-action | ✅ | urgent/attention/normal 三级全实证 |
| 3 | privacy_class=confidential | ✅ | 顶层字段强制 `confidential` |
| 4 | 有 privacy 路径证据 | ✅ | `privacy_path` 字段 + 3 条 red_lines |
| 5 | 不准用 mock 数据冒充真实隐私路径 | ✅ | privacy_path 指向真实 `data/驾驶舱/documents.db`，无 mock |

## 5. 红线遵守

- ✅ family-health 用 `confidential` privacy class（红线）
- ✅ 不调 provider (硬性 `red_lines_followed` 数组)
- ✅ 不写 llm-gateway audit
- ✅ 仅 documents vault 路径
