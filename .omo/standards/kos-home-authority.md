---
schema: md/v1
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-28
type: ssot
---


# KOS Home Authority Contract — 双库权威源契约

> Status: MANDATORY | Effective: 2026-09-28（ADR-0460 首批默认项 a，principal 批准）
> Authority: KOS-HOME-DUAL-AUTHORITY 债务关单决议

## 1. 权威源判定

| 库 | 角色 | 消费者 |
|---|---|---|
| **`<workspace>/data/kos/kos-index.sqlite`** | **权威源**（workspace 级唯一权威） | generate-brief 知识复用指标（T1-04 口径）、kos-mcp 挂载目标（待挂）、治理语料摄入目标 |
| `~/.kos/kos-index.sqlite` | 用户级索引（kairon ingest 默认通道落点） | 个人语料检索；**非 workspace 权威**，不作为治理知识的查询源 |

## 2. 强制规则

1. **工作区上下文的摄入与查询一律显式设置** `KOS_HOME=<workspace>/data/kos`
   （`kos-cli ingest/search/context` 均受 KOS_HOME 解析约束——2026-09-27 实证：
   缺省时写入 `~/.kos`，1,038 篇治理语料落错库）。
2. generate-brief 的知识复用指标只读 data/kos（T1-04 契约不变）。
3. kos-mcp 挂载时（config 层决策后）其数据源必须指向 data/kos。
4. `~/.kos` 的定位：principal 个人语料（12,553 篇基线）+ 治理语料的**副本**；
   定期同步或废弃由 kairon kos 包后续版本决定，不阻塞本契约。

## 3. 摄入规范（增量）

- 对象：`.omo/_knowledge/{decisions,retros,patterns,pitfalls}` 等治理知识目录；
- 通道：`KOS_HOME=<workspace>/data/kos python3 projects/knowledge/kairon/packages/kos/kos-cli.py ingest <dir>`；
- 已知局限（ingest 提案，另案）：canonical_path 不保留目录溯源（`kos::default::<文件名>`）、
  子目录不递归（pitfalls 仅顶层 6/47）。

## 4. 基线

- 2026-09-27：12,553 → **13,588**（治理语料 1,038 篇入双库）
- 2026-10-06：13,588 → **13,782**（Documents 域扩展：规自委 45 + 国转中心 38 + @公共 16 + 合同法规 76 + entities 52 = 227 篇，去重净增 194）；
- 备份：`data/kos/kos-index.sqlite.bak-20260927、.bak-20261006`。

## 5. 违约即假绿

不设 KOS_HOME 的摄入 = 写错库 = "指标不动但 indexed=N"——正是 T3-03 暴露的
双库漂移。任何消费端（指标/检索/挂载）发现库计数与权威源不符，先查 KOS_HOME。
