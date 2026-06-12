# OPC P5-F3 family-health — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P5 / Gate F / Sub-gate F3

## 1. 目标

真实家庭健康 query 闭环；强制 `privacy_class=confidential`；输出
urgent/attention/normal 三级 next-action；隐私路径限定在本地家庭 confidential store。

## 2. 三级 next-action 实证

### 2.1 urgent

```text
$ cd /Users/xiamingxing/Workspace/projects/cockpit
$ PYTHONPATH=src python3 -m cockpit.cli scenario health --query "孩子高烧39度已3天"
```

```json
{
  "generated_at": "2026-06-12T06:51:42Z",
  "privacy_class": "confidential",
  "privacy_path": "/Users/xiamingxing/Workspace/data/cards/cards.db",
  "source_count": 5,
  "next_action": {"level": "urgent", "instruction": "立即联系家庭医生 / 拨打急救电话"},
  "archive_path": "/Users/xiamingxing/Workspace/.omo/_delivery/scenarios/family-health/20260612T065142Z-孩子高烧39度已3天-04998f4b.json"
}
```

### 2.2 attention

```text
$ PYTHONPATH=src python3 -m cockpit.cli scenario health --query "奶奶血压复查要准备什么"
```

```json
{
  "generated_at": "2026-06-12T06:51:42Z",
  "privacy_class": "confidential",
  "privacy_path": "/Users/xiamingxing/Workspace/data/cards/cards.db",
  "source_count": 5,
  "next_action": {"level": "attention", "instruction": "本周内预约复查 + 记录症状到 vault"},
  "archive_path": "/Users/xiamingxing/Workspace/.omo/_delivery/scenarios/family-health/20260612T065142Z-奶奶血压复查要准备什么-3c565da3.json"
}
```

### 2.3 normal

```text
$ PYTHONPATH=src python3 -m cockpit.cli scenario health --query "本周体检安排建议"
```

```json
{
  "generated_at": "2026-06-12T06:51:42Z",
  "privacy_class": "confidential",
  "privacy_path": "/Users/xiamingxing/Workspace/data/cards/cards.db",
  "source_count": 5,
  "next_action": {"level": "normal", "instruction": "无紧急, 月度复盘"},
  "archive_path": "/Users/xiamingxing/Workspace/.omo/_delivery/scenarios/family-health/20260612T065142Z-本周体检安排建议-e1643744.json"
}
```

## 3. 隐私路径与红线

### 3.1 本地 confidential store

- `privacy_path`: `/Users/xiamingxing/Workspace/data/cards/cards.db`
- `privacy_class`: `confidential`
- `source`: `cards:family`

### 3.2 red_lines_followed

```json
[
  "no provider call",
  "no llm-gateway audit write",
  "confidential local family store only"
]
```

### 3.3 source attribution 片段

```json
[
  {
    "id": "DEBT-2026-06-05-004",
    "source": "cards:family",
    "source_path": "/Users/xiamingxing/Workspace/data/cards/cards.db#DEBT-2026-06-05-004",
    "privacy_class": "confidential"
  },
  {
    "id": "TASK-2026-06-05-006",
    "source": "cards:family",
    "source_path": "/Users/xiamingxing/Workspace/data/cards/cards.db#TASK-2026-06-05-006",
    "privacy_class": "confidential"
  }
]
```

## 4. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 真实家庭健康 query 跑通 | ✅ | 3 个 query 均运行成功 |
| 2 | 输出含 urgent/attention/normal | ✅ | 三级全实证 |
| 3 | privacy_class=confidential | ✅ | 顶层字段固定 |
| 4 | 有 privacy 路径实证 | ✅ | `privacy_path=data/cards/cards.db` |
| 5 | source attribution 存在 | ✅ | `source_count=5` + `cards:family` |
| 6 | 不调用 provider / 不写 llm-gateway audit | ✅ | `red_lines_followed` |
| 7 | archive receipt 落盘 | ✅ | 3 个 scenario receipt |

## 5. 红线遵守

- ✅ 不把 `documents.db` 旧描述继续拿来冒充当前隐私路径
- ✅ family-health 始终 `confidential`
- ✅ 只读本地家庭存储，不走 provider
- ✅ 三级 next-action 用真实 query 跑出，不靠静态样例
