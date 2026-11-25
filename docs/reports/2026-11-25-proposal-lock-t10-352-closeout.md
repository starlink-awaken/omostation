---
schema: md/v1
status: completed
lifecycle: evidence
owner: laowang
last-reviewed: 2026-11-25
type: report
bet_id: BET-Y2Q4-T10-352
title: BET-Y2Q4-T10-352 closeout 回执 — done_when 在干净 worktree 实测
---

# BET-Y2Q4-T10-352 closeout 回执

生成时间：2026-11-25T09:55Z（UTC），在干净 worktree
`/Users/xiamingxing/ws-bet-t352-t353-done-transition`（base = origin/main@ae3e6aac58）
内实测；未复用 PR #5546 合并时的读数。

## 结论

本 BET 工程范围已由 squash 提交 `6e7a7e2ad544bafaf93310b6259d5e0e355b7e0a`
（PR #5546）合入 main。本回执只做 done-transition 复核，不改判定面代码。

## done_when 逐条实测

| 条款 | 命令 | 实测读数 | 判定 |
|---|---|---|---|
| standards 枚举含 proposal_only (lifecycle) 与 forbidden (activation) | `rg -n "proposal_only|forbidden" .omo/standards/scene-card-lifecycle.yaml` | lifecycle 含 `proposal_only`（order -1 锁态）、activation 含 `forbidden` | 达成 |
| 有 proposal_lock_exemption 的卡违锁时不再报两条 missing；无豁免仍报 | `uv run --with pytest python -m pytest tests/test_scene_preflight_lock_semantics.py -q` | `4 passed in 0.03s`（豁免放行/无豁免报锁/合规值过/枚举存在） | 达成 |
| 8 张卡 approval_state=confirmed，ready >= 13 | `make scene-card-check`（镜像主仓运行时 trial 面 `.omo/_knowledge/workflow-mesh/shadow-scene-trials.jsonl` 后） | `ready=14 with-blockers=56`（干净检出无 trial 面时 ready=0 属诚实读数，非回归） | 达成 |
| 新增测试覆盖 豁免路径/无豁免报锁/枚举存在 | 同上 pytest | `4 passed` | 达成 |

## 授权依据

Principal 2026-11-24 会话原话「go, 授权, 批」——proposal-lock 选 (a) 路线 +
8 张卡逐卡批准（admin-inbox/admin-submit/agora-bos-gateway/health-archive/
health-intake/health-visit-prep/health-visit/knowledge-curation）。

## 回滚

revert squash 提交 `6e7a7e2ad5` 即可——standards 枚举、preflight 锁语义、
8 张卡 approval_state 均在单提交内，无数据迁移。

## 诚实边界

- ready 判定依赖运行时 trial 面（git-ignored），CI/干净检出上 ready=0 是
  数据面缺席的诚实读数；本回执镜像主仓运行时面后实测 ready=14。
- 43 张异步 trial 与 4 张 pending 审批不在本 BET 范围（non_goals）。
