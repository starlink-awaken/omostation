---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-06
type: retro
title: BET-Y2Q4-T3-04 复盘（进行中）
created: 2026-10-06
---


# BET-Y2Q4-T3-04 复盘（进行中）

> 记录于交付前（2026-10-06）；closeout 前需按 Q1/Q2/Q4 补入实测值。
> 本文件是 T3-04 的 per-BET 记录，同时承载本 BET 唯一的 D3 纪律偏差存档。

## D3 越权偏差（2026-10-06 记录，human decision）

- **现象**：adversarial review 的 M1 blocker 要求修改 `bin/ssot/test-mcp-kos.py`
  （断言从遗留字符串 `"prohibited"` 改为真实保证：isError + 非读载荷 + 拒绝词汇，
  并新增 default-deny authorizer 子测试）。该文件**不在本 BET 的 write_surfaces 内**
  （本 BET 只覆盖 `bin/gac/mcp-server-kos.py`），`agent-workflow claim` 实测拒绝：
  `WORK_PACKET_SCOPE_MISMATCH: bin/ssot/test-mcp-kos.py is outside [...]`。
- **决策（human，2026-10-06）**：M1 是 registered gate 检查，在存在 `data/kos/` 的
  主机会把 gate 打红，必须修；但**不扩大本 BET 的 spec**（会破坏 accepted
  `content_digest` 的 sha256 绑定）。处置 = 在本复盘记录 D3 偏差 +
  另开 `BET-Y2Q4-T10-231`（写面正式覆盖 `bin/ssot/test-mcp-kos.py`），供后续
  claim/verify/close。
- **偏差范围**：仅 `bin/ssot/test-mcp-kos.py` 一个父仓文件；kairon 子模块内所有
  改动均在 `packages/**` 写面内且已 claim。未使用任何 gate waiver。
- **收口**：见 `BET-Y2Q4-T10-231`（本偏差的对账 bet）。

## Q1 实际耗时 vs appetite？

（待 closeout 补入。）

## Q2 done_when 是否全部通过？

（待 closeout 补入。）

## Q3 过程中发现的与 plan 不符的事实（打假）？

- `engine.py:714` 的「body 未分词」前提在 915fc76 上**不成立**：`_process_file:818`
  已在上游分词；真正缺陷是同一份分词文本同时写进 `documents.body`（内容被 jieba
  分段污染）。修复改为 `documents.body` 保留原文 + `documents_fts` 显式
  `fts_text(body)`（见 spec Item 4 与 `test_fts_body_tokenization.py`）。
- default-deny authorizer 起初按「精确 allow-list」把 `SQLITE_RECURSIVE(33)`
  也拒掉，human 判定过度收紧（递归 CTE 是知识库图查询的合法读），已加回（Task A）。

## Q4 净增减？

（待 closeout 补入 `bet-ledger.py surface` 读数。）

## Q5 下一个认领本 track 的 agent 需要知道什么？

- `bin/ssot/test-mcp-kos.py` 的改动属 `BET-Y2Q4-T10-231` 写面，不在本 BET 内。
- gate 的 test-mcp-kos 已拆分：default-deny authorizer 子测试**不需要** `data/kos/`
  恒运行；DB 相关协议检查在无 runtime DB 时 exit 78 软跳过。
- 先读 `BET-Y2Q4-T10-3-04`（本文件）的 D3 段与 `BET-Y2Q4-T10-231` 的 spec，
  再动 gate 工具链。