---
schema_version: specification/v1
spec_version: 1.0.0
title: bin-quota 口径修复与配额迭代升级
bet_id: BET-Y1Q4-T6-02
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-04
last_updated: 2026-09-04
type: ssot
last_updated: 2026-09-04
---

# bin-quota 口径修复与配额迭代升级（BET-Y1Q4-T6-02）

## 背景（Context）

`bin/gac/check-bin-quota-diff.py` 的 `BIN_PATTERNS = ("bin/*.py", "bin/*.sh")`
在 git pathspec 语义下只匹配 `bin/` 顶层，不匹配 `bin/gac/*`、`bin/ops/*`、
`bin/ssot/*` 等子目录脚本——子目录新增脚本成为配额盲点。同时 #3044 引入的
2 个 `bin/ops/*-stub.py` 只同步了 +1 配额（570→571），欠账 +1。

## 目标（Goal）

1. 修复 `BIN_PATTERNS` 子目录盲点：支持 `**` 跨目录匹配（或显式增补
   `bin/ops/*` 等子目录口径），并用新旧口径输出对照验证。
2. 配额迭代升级：`script_baseline` 571→573，注释注明 2 个 stub 增量
  （`lighthouse-stub.py`、`nfr-stub.py`，见 #3044）。

## 非目标（Non-Goals）

- 不改业务逻辑：只修配额统计口径与基线数字，不碰脚本功能。
- 不做全量基线重盘点：历史漂移超出 2 个 stub 的部分不在本 bet 范围。
- 不归档脚本：本次选配额同步路径，不走 orphan 归档路径。

## 完成标准（Done When）

1. `check-bin-quota-diff.py` 新口径覆盖 `bin/ops/` 等子目录脚本（新旧口径输出对照留证）。
2. `governance-checks.yaml` 中 `script_baseline: 573` 且注释注明 stub 增量。
3. `bin/plan/bet-ledger.py lint` 通过，BET-Y1Q4-T6-02 结构合法。
4. 本 spec 的 binding（spec_ref / spec_version / content_digest /
   decision_ref）与 ledger 记录一致，digest 与文件 sha256 一致。
