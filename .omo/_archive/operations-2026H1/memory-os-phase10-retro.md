---
status: active
lifecycle: history
owner: engineering-team
last-reviewed: 2026-08-05
related:
  - ./memory-os-epic-retro.md
  - ./memory-os-neo4j-local.md
  - ../architecture/memory-os.md
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ../../.omo/_truth/registry/memory-os.yaml
title: Memory OS Phase 10 — 能力加深复盘
type: doc
---

# Memory OS Phase 10 — 能力加深复盘

## 交付

| 项 | 结果 |
|----|------|
| Neo4j bi-temporal `as_of` | SEARCH_CYPHER + FakeDriver；CLI/cockpit `--as-of` |
| Live KOS | `MOS_LIVE_KOS=1` → HTTP `KOS_API_URL` |
| Live gbrain | `MOS_LIVE_GBRAIN=1` search；`MOS_LIVE_GBRAIN_WRITE=1` put |
| 文档 / help | architecture §6/§10 · ops · skill · mos README · cockpit `memory` help |
| kairon | `9ac7d761` · 56 mos tests |
| PR | #987 |

## 用法指针

见 `docs/architecture/memory-os.md` §10「操作入口」与 `.omo/standards/memory-os-ops.md` Phase 10。

## 诚实边界

- Live 默认 off；不可用时 degrade 到 fixture，不阻断主路径
- graphiti-core / Mem0 生产闭环仍未宣称

## 后续：六条意图路由的 CJK 缺陷已修（`2976f20`）

`routing.py` 有六个 pattern（`_CODE_RE` / `_PREF_RE` / `_ENTITY_RE` / `_TASK_RE` /
`_CARD_RE` / `_FILE_RE`）把整个 alternation 包进 `\b(...)\b`，含 CJK 分支。Python 的
`\b` 以 `[a-zA-Z0-9_]` 判定词字符，CJK 不在其中，故 CJK 分支两侧的边界永不成立 ——
这六条路由对中文查询等同关闭，全部落 `general`（换一套 backend 集合）。只有
`_TEMPORAL_RE` 合规，所以中文时间表达当时能用、另外六条不能。

**已修**（kairon 子模块 `2976f20`，branch `agent/mos-acl-fix`，本地未推送）：改为
ASCII 分支带 `\b`、OR 一个无边界 CJK 分支。关键字逐个机械核对零增删零改词；
探测集 12 条中 9 条改变分类；eval_harness 15 条分类零变化；
测试 56 → 89，修复前代码上新测试确实失败（防空绿）。

**仍未决**：`_TEMPORAL_RE` 排在 `_FILE_RE` / `_CARD_RE` 之前，年份相对词会压过文档 /
卡片 / 偏好名词。实测读数是含年份词的查询**修复前就已**在 TEMPORAL 短路，故
`去年写的文档在哪` 一类**分类未变** —— 也就是说这条优先级问题恰好落在最容易被误判为
「没问题」的那批查询上。本轮**未做任何重排**（重排需独立基线与人工签署）；
待决项见 `.omo/tasks/active/BET-Y2Q4-T10-TEMPORAL-PRECEDENCE.yaml`，
修复记录见 `.omo/tasks/active/BET-Y2Q4-T10-CJK-ROUTING.yaml`。
