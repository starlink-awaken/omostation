---
schema_version: specification/v1
spec_version: 1.0.0
title: 门禁机制优化二期 — 文档 PR 风险分级 + spec-init 一键工具
bet_id: BET-Y1Q4-T10-135
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-07
---





# 门禁优化二期规格 (BET-Y1Q4-T10-135)

## 1. 文档 PR 风险分级 (建议 3)

ci-check-runner.py 新增 docs-only 检测: PR 变更文件 (git diff origin/main...HEAD)
全部命中文档面 (*.md / docs/** / .omo/_knowledge/** / *.yaml 且不含 bin//projects/)
时, 跳过 ci-surfaces 中标记 `skip_if_docs_only: true` 的重检查 (gatekeeper 全量类)。
ci-surfaces.yaml 的 governance-check.yml workflow 下 heavy check 补该字段。

## 2. spec-init 一键工具 (建议 4)

bet-ledger.py 新增子命令:
  bet-ledger.py spec-init <BET-ID> --spec <path>
功能: 规范化 spec frontmatter (schema_version/spec_version/title/bet_id/status/
lifecycle/last-reviewed 七件套补缺) + 计算 content_digest + 插入 ledger
accepted_specifications binding (幂等: 已有 binding 则校验并更新 digest)。
消灭 spec binding 五连报错的手工试错。

## done_when

- docs-only PR: 标记 check 被 SKIP (runner 输出可见), 非 docs PR 不跳过
- spec-init 对全新 BET 一次成功 (start 无 SPEC_* 报错)
- 幂等重跑不重复插入 binding
