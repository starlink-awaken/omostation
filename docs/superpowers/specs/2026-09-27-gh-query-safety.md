---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: gh 查询安全层 — 重试 + 空保护共享助手（GRAPHQL-FLAKY 处置）
bet_id: BET-Y2Q4-T10-08
---

# BET-Y2Q4-T10-08 — gh 查询安全层

## 授权链

TOOL-GRAPHQL-FLAKY-EMPTY-MEANS-UNKNOWN 的 decision_needed（"给常用 gh 查询包一层
重试+空保护（失败/空时 abort 而不是继续删东西）"）——本单实现该处置。

## 目标

1. **bin/lib/gh_query.py 共享助手**（lib 模块，非 CLI 脚本）：
   - `gh_json(*args, retries=3, treat_empty_as_unknown=False)`：重试瞬态失败
     （EOF/timeout/network 字样、非零 rc），成功但输出空时——
     `treat_empty_as_unknown=True` 抛 `GhQueryUnknown`（调用方必须显式选择
     "空=合法"，破坏性调用方默认拒绝空）；
   - `GhQueryUnknown` 异常携带原始 stdout 供 UNKNOWN 上抛。
2. **clone-lifecycle.py integrate 接线**：PR 列表查询换用助手——空列表重试 ×3 后
   仍空 → `reject("integrate", "pr_query_unknown", ...)`（拒绝自动建 PR，消除
   网络抖动造重复 PR 的模式——原始事故同款）。
3. **prune-ci-runs.py 去重**：内联 gh_api 换用共享助手（行为不变：rc 非零抛
   RuntimeError）。
4. gen-real-evalset.py 不动（非破坏性、设计即优雅降级，retro 记录理由）。

## 红线

- 不改变既有成功路径的输出语义（JSON 解析结果一致）；
- clone-lifecycle 的空列表处置从"静默建 PR"变为"重试后拒绝"是**行为变更**，
  以测试钉住并在 retro 说明理由（debt 规则明令"空时 abort"）；
- bin/lib 模块遵循 repo_root.py 先例，不新增 CLI 脚本。

## 验收

1. 新助手 + 两处接线落地，hermetic 测试覆盖（瞬态重试/空→UNKNOWN/成功透传）；
2. `make gac-local-gate` PASS；lint 0 新增；
3. retro 固化（含 gen-real-evalset 不接线的理由）。
