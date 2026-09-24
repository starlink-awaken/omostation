---
schema: bet-retro/v1
bet_id: BET-Y2Q3-T10-OMLXC-01
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-24
type: ephemeral
completed_at: 2026-09-24
---

# Retro: BET-Y2Q3-T10-OMLXC-01 — omlxc P0 死引用 + inventory 诊断 + CLI 契约一致性

## Summary

**PR #4258 已合入主仓（merge commit `b66ac2624`）**，实现了 BET-Y2Q3-T10-OMLXC-01 的全部 done_when。本 retro 配套 closeout，evidence 全部指向 PR #4258 + 子仓 PR omostation-omlxc#87。

## done_when 验证

| # | 条件 | 落地 | 证据 |
|---|---|---|---|
| 1 | P0 三处死引用清零（gac-compute-onboard / nextgen-cognitive-mesh skill / cli_presenter） | ✅ | PR #4258 主仓代码 + `grep -rL` 三文件全无 dead-ref |
| 2 | doctor inventory 失败项清零或三问归因落档 | ✅ | `docs/reports/2026-09-23-omlxc-inventory-diagnosis.md`（三问结论已落档）+ `docs/reports/omlxc-baseline-*.json` 基线存档 |
| 3 | schema_version 类型统一为 int，benchmark 死桩移除 | ✅ | omostation-omlxc#87 squash `ec48f56` |
| 4 | fabric snapshot 非法 action 不再静默成功 | ✅ | omostation-omlxc#87（同 commit） |

## What went well

- **PR #4258 squash 一次到位**：14 文件 + 子仓 squash-merged PR #87，避免来回往返
- **三问归因**：inventory degraded 不直接动手，先诊断三问（mbp-omlx-app / lm-studio / conf 33 vs 可用 20 差）—— 找到根因"omlxc CLI 无法凭空创建 inventory"，决定不强行 reconcile 而是摘除 placement / 标 known-debt
- **基线存档**：`omlxc-baseline-{doctor,models,nodes,status}-20260923T132503Z.json` 在修复前固化了现场状态（防自愈时基线漂移）
- **verification 不被 grep 误导**：尽管 `verify[].cmd` 用 grep，工具仍识别"空 = 匹配成功"——done_when 1 实际通过（grep 输出空）

## What was learned

- **PITFALL-RES-004**: session resume 时第一件事应是"查 main 是否已含目标内容"而非重建 —— PR #4258 完整做了 P0 fix + 三问归因 + CLI hardening，BET closeout 才是剩余路径
- **PITFALL-RES-005**: `verify[].cmd` 用 `grep -rn`（无匹配 exit 1）会被工具误判 FAIL —— 应当用 `grep -rL` (反向) 或 `! grep` 才表达 "no match = pass"
- **PITFALL-RES-006**: `completion_evidence` 的 `merged_reachable_commit` 必须 40-lowercase-hex（短 hash 被 COMPLETION_GIT_REF_INVALID 拦）
- **PITFALL-RES-007**: `affected-graph.py --changed-projects` 必须显式包含 `workspace-root`，否则主仓文件 claim 会失败 "claimed projects missing from affected graph receipt: workspace-root"

## What to improve

- **done_when 表达统一**: 当前 done_when 用纯自然语言描述，缺少可机器验证签名（建议每条配 ≥ 1 条 `verify[].cmd` + 期望值）
- **inventory 三问模板化**: 把"诊断三问"抽成 `.omo/standards/inventory-three-questions.md`，其他子仓类似 case 可复用
- **三份 omlx 副本 deferred**: `circuit_breaker` 已明示"三份 omlx 副本只开票"，建议另开 BET-Y2Q4-T10-OMLXC-01（runtime 热路径，**不可在当前会话级别触碰**）

## Metrics

- 主仓 PR: #4258 (merged 2026-09-24)
- 子仓 PR: omostation-omlxc#87 (squash commit `ec48f56`)
- 主仓 +14 文件 / 子仓 +N 文件
- 1 baseline JSON 三件套 + 1 三问归因报告
- done_when 4/4 满足 (100%)
- 本 retro evidence: 8 处 receipt://（diff/rollback/tests/cleanup/fresh_receipt/live_canary/replay + merged_reachable_commit）

## 三问归因（引用 inventory-diagnosis.md）

Q1 mbp-omlx-app 3 placement 不服务：模型未注册进 omlx-app inventory，**omlxc 无法凭空创建**，需 omlx-app 注册或摘除
Q2 mbp-lm_studio 15/15 mismatch：baseline 45→1 stale placement，**待 reconcile**
Q3 conf 33 vs 可用 20：差 13 待 intentional disabled 审计，已建 ticket