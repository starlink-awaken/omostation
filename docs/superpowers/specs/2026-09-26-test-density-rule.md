---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 测试密度规则化 — fix 类交付必带回归测试的门禁提示与度量
bet_id: BET-Y2Q4-T10-02
---

# BET-Y2Q4-T10-02 — 测试密度规则化

## 背景

近 30 天提交构成：feat 501 / fix 424 / **test 34**（test:feat ≈ 1:15）。
缺陷修复密度高但回归测试覆盖薄，同类问题有复发风险（如 #3282 回退 #3277 实录）。
治理路径：不做一次性大补测，把"fix 必带回归测试（或留痕豁免）"规则化进交付面。

## 目标

1. PR 模板（`.github/pull_request_template.md`）加回归测试检查项：
   fix 类 PR 必须声明"新增回归测试"或"豁免理由"；
2. 度量基线落档：`docs/reports/` 记录 test:feat = 34:501 基线与 30 天 ≥1:5 目标，
   附统计命令（可复算，D1）；
3. 豁免路径写明：纯文档/生成态/子模块指针类 fix 可豁免，理由留 PR body。

## 写面

`.github/**`（PR 模板）、`docs/reports/**`、`docs/plans/3y-bet-ledger.yaml`、
本 spec、retro。

## 验收（done_when 摘要）

1. PR 模板含回归测试检查项（fix 类强制声明）；
2. 基线报告含可复算统计命令与 30 天目标；
3. 豁免路径成文；retro 固化规则采纳理由与预期阻力（如历史 PR 无该声明）。

## 红线

- 不改 CI 强制门禁（先提示后收紧，观察期由后续 bet 决定）；
- 统计口径必须可复算（git log 过滤规则写进报告），禁止人工报数。

## verify

- `grep -A2 "回归测试" .github/pull_request_template.md` → 命中检查项
- 基线报告中的统计命令原样执行 → 输出与报告数字一致
- `python3 bin/plan/bet-ledger.py lint` → 不引入新错误
- `make gac-local-gate` → exit 0
