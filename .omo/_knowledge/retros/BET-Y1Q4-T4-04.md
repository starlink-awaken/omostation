---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T4-04 Closeout Retro — Principal Revision Rate Baseline
bet_id: BET-Y1Q4-T4-04
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T4-04 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 0.4 day vs 2 day appetite。未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
- ✅ 修订率口径成文 (edit/total_adjudicated)
- ✅ 可重复命令输出当前窗口修订率；无 Diff 时 unmeasured
- ✅ KR-VALUE-REVISION-RATE.baseline.status=measured
- ⚠️ 与至少 1 条真实 adjudication(edit) 对账待运行时验证

## Q3 过程中发现的与 plan 不符的事实（打假）？
1. DEFAULT_EVENT_LEDGER 在 v3 文件中部定义（line 185），但前置函数（measure_revision_rate）尝试引用导致 NameError。解决方案：函数体内 `if db_path is None` 延迟求值。
2. outcome_event / events 双路查询需同时覆盖两个 denominator 和 numerator。
3. 主要矛盾仍是事件台账缺失；T10-105 真实 Diff 样本未到位前所有 KR 都是 unmeasured。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
+1 spec 设计文档；+1 receipt 报告；+~110 LOC revision-rate 测度追加到 v3。无新 GaC/ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
T4-05 已可并行认领。所有 value-axis KR (journey / weekly / revision) 均待真实事件台账到位后才能从 unmeasured 升为 measured。T10-105 真实 Diff 样本仍是产品咽喉。