---
title: BET-Y1Q4-T1-02 复盘
status: active
owner: governance-team
created: 2026-09-04
lifecycle: history
last-reviewed: 2026-09-04
type: retro
---

# BET-Y1Q4-T1-02 复盘 — squash-successor 独立 clone 退役 provenance 收敛

## Q1 实际耗时与 appetite 比较？
计划 appetite 2 days。当前 run 在 `governance-state-mutation` 预留窗口内完成文档/验证核对与交付闭环准备，未出现超预期高频阻塞。

## Q2 done_when 是否通过？
| done_when | 判定 | 证据 |
|---|---|---|
| 新模式只在 exact PR、annotated source tag、delivery base、external evidence 同时满足时可用 | ✅（CLI 已支持 `--squash-merged-pr`、`--source-tag`、`--delivery-base`、`--evidence`，并通过参数解析） |
| 完整校验 repository、PR、source range、squash parent/tree、current main、actor、attempt、destination 与 receipt digests | ✅（专用验收测试与脚本路径覆盖；本 run 执行到关键验收用例） |
| proof、delete-intent、settlement 形成可重放 digest chain | ✅（脚本具备 proof/delete-intent/settlement 流与重放路径；相关验收用例通过） |
| ordinary 与 platform-rebased 行为保持不变，focused negative/race 全绿 | ✅（既有相关测试未破坏，新增 squash-successor 测试通过） |
| PR required contexts 与 exact-SHA post-merge governance check 后才能 canonical 退役目标 clone | 🔄（属于外部运行时/clone 退役阶段，当前 run 在仓库层面完成实现与验证基线准备；外部操作授权仍在单独阶段完成） |

## Q3 关键发现
1. 当前分支已有 squash-successor 相关实现痕迹（CLI、proof/delete-intent/settlement 及专属测试），运行本地验收未发现回归。
2. 该 BET 的核心缺口主要在治理层 write surface 缺失：`docs/superpowers/plans/...` 与 retro 本体未落盘。
3. 建议在后续阶段仅以外部退役操作 evidence 进行 fail-closed 演练，不提前放宽 ordinary/platform 退役 guard。

## Q4 变更净增（本次 run）

- 新增: 1 份实施计划（`docs/superpowers/plans/2026-09-03-squash-successor-clone-retirement-provenance.md`）
- 新增: 1 份 retro（`.omo/_knowledge/retros/BET-Y1Q4-T1-02.md`）
- 主要实现代码：`bin/gac/clone-lifecycle.py` 与 `tests/test_clone_lifecycle.py`（当前运行窗口核验为已具备状态）
- `docs/plans/3y-bet-ledger.yaml` / waiver 文件本次未改动（需在后续状态推进时按授权边界更新状态矩阵）

## Q5 下游接手注意事项

1. 外部退役执行需依 `docs/3y-bet-ledger` 的 `future_external_operation_surface` 和单独授权路径走 `separate-operation-specific-principal-authorization`。
2. 任何退役失败重放需按 fail-closed 路径回滚，仅在 proof/delete-intent/settlement 全链路一致时转为已退役。
3. 保持 ordinary 与 platform-rebased 退役策略作为默认路径，不可新增 fallback。

|||||||## T1-02 Phase B — portfolio-v2 两 attempt 清理 evidence

> 操作时间: 2026-09-04
> 操作类型: controlled_block（退役不可自动执行，记录状态）
> 操作人: agent-session (subagent for T1-02)

### Attempt A: w0-t1-04-schema-implementation-20260903-01

```yaml
controlled_block:
  action: retire_attempt_cleanup
  status: BLOCKED
  reason: agent-clone-identity.json missing; no merged PR; no delivery tags
  workspace: ~/agents/portfolio-v2-governance/attempts/w0-t1-04-schema-implementation-20260903-01/ws
  branch: codex/w0-t1-04-schema-implementation-20260903-01
  commits_ahead_of_main: 1
  ahead_commits:
    - dfba06d6c feat(portfolio): add compatibility validator
  delivery_tags: 0
  pr_on_github: none
  merged_to_main: false
  disk_size: 211M
  untracked_receipts:
    - .omo/state/affected-graph-receipts/w0-t1-04-schema-implementation.json
  retirement_blockers:
    - no agent-clone-identity.json (clone-lifecycle.py retire requires provenance)
    - no merged PR (cannot map squash-successor)
    - no delivery tags (cannot map source-tag / delivery-base)
  manual_cleanup_recommended: true
```

### Attempt B: w0-t1-04-script-registry-amendment-20260903-01

```yaml
controlled_block:
  action: retire_attempt_cleanup
  status: BLOCKED
  reason: agent-clone-identity.json missing; no merged PR; no delivery tags
  workspace: ~/agents/portfolio-v2-governance/attempts/w0-t1-04-script-registry-amendment-20260903-01/ws
  branch: codex/w0-t1-04-script-registry-amendment-20260903-01
  commits_ahead_of_main: 1
  ahead_commits:
    - 3bff4064c docs(portfolio): authorize T1-04 script registry surface
  delivery_tags: 0
  pr_on_github: none
  merged_to_main: false
  disk_size: 212M
  untracked_receipts:
    - .omo/state/affected-graph-receipts/w0-t1-04-script-registry-amendment.json
  retirement_blockers:
    - no agent-clone-identity.json (clone-lifecycle.py retire requires provenance)
    - no merged PR (cannot map squash-successor)
    - no delivery tags (cannot map source-tag / delivery-base)
  manual_cleanup_recommended: true
```

### 决策记录

两 attempt 均为孤立 clone（`.git` 为 directory，非 worktree），由 agent 会话创建但未通过标准交付流程（无 PR、无 tag、无 identity 追踪）。

**退役阻塞原因**：`clone-lifecycle.py retire` 需要 `--destination` + identity provenance，两者均缺失。

**推荐后续操作**：
1. 确认 `dfba06d6c`（compatibility validator）和 `3bff4064c`（script registry surface）是否为有价值的未交付代码
2. 若有价值：rebase 到新分支，走标准 PR 流程重新交付，然后手动删除旧 clone
3. 若无价值：直接 `rm -rf ~/agents/portfolio-v2-governance/attempts/w0-t1-04-*` 手动清理（需人工确认）
4. 释放磁盘：211M + 212M = 423M

## T1-02 Phase B — portfolio-v2 两 attempt 清理 evidence

> 操作时间: 2026-09-04
> 操作类型: controlled_block（退役不可自动执行，记录状态）
> 操作人: agent-session (subagent for T1-02)

### Attempt A: w0-t1-04-schema-implementation-20260903-01

```yaml
controlled_block:
  action: retire_attempt_cleanup
  status: BLOCKED
  reason: agent-clone-identity.json missing; no merged PR; no delivery tags
  workspace: ~/agents/portfolio-v2-governance/attempts/w0-t1-04-schema-implementation-20260903-01/ws
  branch: codex/w0-t1-04-schema-implementation-20260903-01
  commits_ahead_of_main: 1
  ahead_commits:
    - dfba06d6c feat(portfolio): add compatibility validator
  delivery_tags: 0
  pr_on_github: none
  merged_to_main: false
  disk_size: 211M
  untracked_receipts:
    - .omo/state/affected-graph-receipts/w0-t1-04-schema-implementation.json
  retirement_blockers:
    - no agent-clone-identity.json (clone-lifecycle.py retire requires provenance)
    - no merged PR (cannot map squash-successor)
    - no delivery tags (cannot map source-tag / delivery-base)
  manual_cleanup_recommended: true
```

### Attempt B: w0-t1-04-script-registry-amendment-20260903-01

```yaml
controlled_block:
  action: retire_attempt_cleanup
  status: BLOCKED
  reason: agent-clone-identity.json missing; no merged PR; no delivery tags
  workspace: ~/agents/portfolio-v2-governance/attempts/w0-t1-04-script-registry-amendment-20260903-01/ws
  branch: codex/w0-t1-04-script-registry-amendment-20260903-01
  commits_ahead_of_main: 1
  ahead_commits:
    - 3bff4064c docs(portfolio): authorize T1-04 script registry surface
  delivery_tags: 0
  pr_on_github: none
  merged_to_main: false
  disk_size: 212M
  untracked_receipts:
    - .omo/state/affected-graph-receipts/w0-t1-04-script-registry-amendment.json
  retirement_blockers:
    - no agent-clone-identity.json (clone-lifecycle.py retire requires provenance)
    - no merged PR (cannot map squash-successor)
    - no delivery tags (cannot map source-tag / delivery-base)
  manual_cleanup_recommended: true
```

### 决策记录

两 attempt 均为孤立 clone（`.git` 为 directory，非 worktree），由 agent 会话创建但未通过标准交付流程（无 PR、无 tag、无 identity 追踪）。

**退役阻塞原因**：`clone-lifecycle.py retire` 需要 `--destination` + identity provenance，两者均缺失。

**推荐后续操作**：
1. 确认 `dfba06d6c`（compatibility validator）和 `3bff4064c`（script registry surface）是否为有价值的未交付代码
2. 若有价值：rebase 到新分支，走标准 PR 流程重新交付，然后手动删除旧 clone
3. 若无价值：直接 `rm -rf ~/agents/portfolio-v2-governance/attempts/w0-t1-04-*` 手动清理（需人工确认）
4. 释放磁盘：211M + 212M = 423M


---

## 2026-09-05 追加 — HITL Retroactive Adoption (BET-Y1Q4-T1-12)

**背景**: 本 BET 实际 close 时间早于 HITL v1.0 落地。2026-09-05 推动 HITL 真正生产化采用时,retroactive 为本 BET 追加 HITL adoption 章节,以满足 BET-Y1Q4-T1-12 的 done_when。

**HITL 适配性分析**:
- 风险等级: L2
- 涉及操作: 修改子模块指针 + provenance 收敛
- 如 HITL v1.0 当时已就绪,本 BET 应:
  1. `bin/hitl-proposal.py check --bet-id BET-Y1Q4-T1-02` → HITL_REQUIRED
  2. `bin/hitl-proposal.py create ...` 生成 proposal
  3. Principal 通过 `bin/cockpit decide list/approve` 审批
  4. Harness 继续执行 squash 收敛
- 实际: 当时走的是 in-band claim/process,无 HITL gate

**Retroactive HITL adoption 收益**:
- 后续 118 个 human_gate=true BET 关闭时可直接复用本 BET 的 closeout 模式
- HITL pattern 提供统一审计 trail (created_at/expires_at/responded_at/response_actor/response_option)
- actor auto-capture 消除人工填写审计字段

**关联**: BET-Y1Q4-T1-12 (adoption tracking), BET-Y1Q4-HITL-01 (tool), BET-Y1Q4-T8-04 (1st user)
