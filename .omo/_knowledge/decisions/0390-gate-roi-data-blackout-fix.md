---
id: ADR-0390
title: M5 数据黑障修复 — omo_daemon governance-history checks 丢失
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-08
type: ssot
---

# ADR-0390 Decision: M5 数据黑障修复 + 减法治理 Phase 2

> 承接 ADR-0389 (M5 gate ROI 报告). ROI 报告首份 (2026-08) 暴露:
> 7 gates 全 warn-only, agora-health / task-consistency / doc-lifecycle
> 30d 归零被标 PRUNE → 但 ROI 报告本身基于 693 events 冻结在 7-31 的数据.
> 归零根因 = **数据采集断层**, 非 gate 失效. 治本: 修 omo_daemon 写入 + 回归测试.

## 一、根因 (实测, 不靠猜)

| 现象 | 数据 |
|------|------|
| governance-history 7-31 后事件 | 4 条 (vs 8 月前平均 8-15/天) |
| 这些事件的 `checks` 字段 | **全部为空数组** `[]` |
| 7 个 gate fires/fail 计数 | 冻结在 7-31 的最后一条 |
| 7-31 前事件 schema | `{checks: [7 项], grade, timestamp, ...}` |
| 7-31 后事件 schema | `{grade, source: "omo_daemon", checks: []}` |

**根因**: `omo_daemon.py:202` 的 `append_entry` payload 只写
`{total_score, grade, watchlist_count, source}` — **漏写 checks 数组**!

7-31 前后, omo_daemon 接管了 governance-history 写入（替代 omo_audit
governance_history_main 的调用路径），但 omo_audit 写 checks 而
omo_daemon 不写，导致从那一刻起所有 gate counts 冻结 → ROI 报告
看到的"3 个 gate 30d 归零"是**采集断层假象**，非 gate 真失效。

## 二、决策

### 决策 1: 修 omo_daemon.run_once 写 checks

`projects/omo/src/omo/omo_daemon.py:202` — append_entry payload 补
`checks: [{name, category, score, severity} for c in report.checks]`，
格式与 `omo_audit.governance_history_main:947` 字节级一致。

### 决策 2: 回归测试 `test_omo_daemon_history_checks.py`

- test_run_once_appends_checks_to_history: 验证 append 的 record 含
  checks 列表 + 每个字段 schema (name/category/score/severity ∈ {ok,warn,fail})
- test_daemon_history_appended_flag_honors_audit_failure: 验证 audit
  失败时 history_appended=False (防止写空 record)

### 决策 3: ADR-0389 数据黑障声明

ADR-0389 §一 的 "693 events / 7 gates / 2026-06-06→08-06" 表格有
**采集断层偏差**: 7-31→8-06 数据不可信. 真实 gate 行为以修复后
下个季度报告为准. 本 ADR 标注此偏差.

### 决策 4: 暂缓"归零 gate 降级处置"与"NOISY warn 降级"

原计划处置 3 个归零 gate (PRUNE/降频) + 2 个 NOISY gate (warn 降级)
的数据**不可信**. 等 daemon 下次 tick (修复已 merge 后) 重新积累
至少 7 天数据, 再跑 ROI 报告, 然后做处置判断.

避免"基于冻结数据做减法决策"——这正是 ADR-0389 想治的病.

## 三、与 ADR-0389 / -0384 关系

- ADR-0384 D3: gate-effectiveness 首测 (5/7 gates WEAK) — 同样基于
  governance-history, 同样被本次黑障污染. 数据可靠性重审.
- ADR-0389: M5 ROI 报告的"减法建议"全部暂缓, 等新数据.
- ADR-0391 (下一轮): 重跑 ROI + 重新评估 7 gates, 数据基础 = 本 ADR 修复后.

## 四、验证

```bash
# omo 子模块: 22 测试通过 (含 2 新增回归测试)
cd projects/omo && uv run python -m pytest \
  tests/test_omo_daemon_publish_e2e.py \
  tests/test_append_only_log_schemas.py \
  tests/test_omo_lint_schemas.py \
  tests/test_omo_daemon_history_checks.py -q

# 数据恢复: 等 daemon 下次 tick 后, governance-history 新增 events 应含 checks
python3 bin/_archive/2026-08-conv3/gate-roi-report.py --json | jq '.gates[].fire_rate_30d'
```

## 五、教训 (P73 真理驱动)

| 陷阱 | 症状 | 实证 |
|------|------|------|
| **D1 单源依赖** | ROI 报告基于 governance-history 单源;该源 7-31 起黑障 → 整份报告失真 | 7 gates 全归零/全增长 一致性异常 |
| **D2 无 schema 守卫** | append_entry payload 不强校验, daemon 可静默漏写字段 | 测试无 checks 字段 assert |
| **D3 数据连续性假设** | 默认"数据在涨=业务在涨" → 实测黑障混淆为业务稳态 | 7-31→08-06 4 events vs 8 月前 8-15/天 |

固化:
- 测试 (test_omo_daemon_history_checks.py)
- D0 三段式 tag (round-0390-omo-fix)
- ADR-0389 数据可靠性标注