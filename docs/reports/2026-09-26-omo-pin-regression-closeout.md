---
schema: md/v1
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-26
type: report
title: BET-Y2Q4-T10-204 omo gitlink 回归恢复 — closeout receipt
bet_id: BET-Y2Q4-T10-204
created: '2026-09-26'
run_id: 20260926T154127Z-submodule-pointer-bump-8a82cfee
---

# BET-Y2Q4-T10-204 closeout receipt — omo pin 回归恢复

> 本文件是 `completion_evidence` 指向的 receipt。所有数值均为本 run 实测，非复述。
> 契约定义见 `docs/superpowers/specs/2026-09-26-submodule-gitlink-reachability.md`。

## 1. 交付物

| 项 | 值 |
|---|---|
| 子仓改动 | omo `e9252141d9c737c2d99edd76fb6bd1e12650a3ea`（PR omo#197，squash 合并进 omo `origin/main`） |
| 主仓 pin 变更 | `c91b203e15e68fe7ce087c3c5b688f9f3990cdf2` → `e9252141d9c737c2d99edd76fb6bd1e12650a3ea` |
| 生成方式 | `bin/ssot/submodule-pointer-transaction.sh --changed-from origin/main --message "…"`（非手工 `git add projects/omo`） |
| 主仓 PR | #4408 |
| 主仓 merge commit | `ba7b3787d8e2280ace4cbfa0599997260b9d235d` |
| 契约 spec | `docs/superpowers/specs/2026-09-26-submodule-gitlink-reachability.md`，digest `sha256:2d4fc9bb91f247dbde4c0cfc1e1158656f122c7b291fdd3759c50d2388d068ba` |

## 2. 回归的实测成因

`4be9125a0`（ADR-0456 B1，PR #4403）把根 pin 指向 `0790f897`。该 commit 只存在于 omo 侧
feature 分支 `agent/governance-agent/ws-devruntime-b1s2`，不在 omo `origin/main`。因此根侧
没有任何检查报错，PR #4403 照常合并。下一波 freshness 扫描 `28158b9bc`（PR #4405）把 pin
回退到子仓 main tip `c91b203e`，改动从 main 上消失，且**没有任何门禁报错**。回退 commit body
自带豁免声明：

```
[gitlink-regress: parent pin 0790f897 sits only on omo feature branch … not on omo
origin/main — freshness gate requires the pin to be the child main tip; c91b203e IS omo origin/main]
```

即：成因在交付侧（用 gitlink 当交付载体），不在 harness 侧。harness 侧另一处相关事实：
PR `4209`（`86b61b84e`，2026-09-22）从 `.github/workflows/gac-gate.yml` 的 reachability 步骤
移除了 `--require-main`，用于支持跨仓 PR 模式 —— 因此合并路径上没有任何检查会报告
「pin 可达但子分支未合并」。本 bet 未反转该决定（见 §6）。

内容等价性核验：`git diff --stat 0790f897 e925214` → `src/omo/omo_paths.py | 4 +---`（1 插 3 删）。
`0790f897` 仍可由 `remotes/origin/agent/governance-agent/ws-devruntime-b1s2` 到达，无孤儿对象。

## 3. verify 实测（ledger `verify` 四条，逐条）

在 `origin/main` 的检出点（`ba7b3787d`，worktree `/Users/xiamingxing/ws-ws-omo-pin-restore`）执行：

| # | 命令 | 实测结果 |
|---|---|---|
| V1 | `git -C projects/omo merge-base --is-ancestor "$(git rev-parse HEAD:projects/omo)" origin/main` | `exit=0`；`HEAD:projects/omo` == `e9252141d…` |
| V2 | `python3 bin/ssot/submodule-reachability-gate.py --source head --fetch --require-main` | `submodule-reachability: PASS (16 gitlinks, source=head)`，`exit=0`，34.8s |
| V3 | `git -C projects/omo show "$(git rev-parse HEAD:projects/omo):src/omo/omo_paths.py" \| grep -c STATE_ROOT` | `11` |
| V4 | `make gac-local-gate` | `GaC local gate: PASS (68 checks executed, ALL GREEN)`；6 项 known-unavailable 跳过；**两次独立执行 `exit=0`**（1:22.8 / 1:49.1）；运行后 `.omo/state/**`、`BRIEF.md` 零脏 |

CI（PR #4408）：`gh pr checks` 全部 `pass`（含 required 的 `phase-gate` /
`bet-done-transition` / `gac-gate`），无 `fail`。

## 4. live canary（双 profile，只读、零副作用）

命令形态：`[OMOSTATION_STATE_ROOT=…] PYTHONPATH=projects/omo/src python3 -c "import omo.omo_paths …"`，
加载的正是 pin 指向的子仓内容。

**C1 — 未设 profile（必须在 legacy 路径逐字节不变）**

```
WORKSPACE_ROOT /Users/xiamingxing/ws-ws-omo-pin-restore
STATE_ROOT     /Users/xiamingxing/ws-ws-omo-pin-restore
STATE_DIR      /Users/xiamingxing/ws-ws-omo-pin-restore/.omo/state
OMO_ROOT       /Users/xiamingxing/ws-ws-omo-pin-restore/.omo
TRUTH_DIR      /Users/xiamingxing/ws-ws-omo-pin-restore/.omo/_truth
projection system_health → .omo/state/runtime/system_health.yaml
projection health        → .omo/state/health.yaml      (legacy 命中)
projection brief         → BRIEF.md                    (legacy 命中)
```

**C2 — 声明 state root（写侧改挂，读侧回退）**

```
STATE_ROOT  /tmp/t10204-canary-state
STATE_DIR   /tmp/t10204-canary-state/.omo/state
OMO_ROOT    /Users/xiamingxing/ws-ws-omo-pin-restore/.omo   ← 仍留在 code root
projection system_health → /tmp/t10204-canary-state/.omo/state/runtime/system_health.yaml
projection brief         → /Users/xiamingxing/ws-ws-omo-pin-restore/BRIEF.md  ← 仍读已提交 legacy
```

即 code_root/state_root 双根分离在 pin 上实际生效，且 C2 的读回退就是 B5「dev 能读最后一次
提交快照」的行为前提。

**C3 — cleanup 证明**：`ls -d /tmp/t10204-canary-state` → 不存在（canary 只解析路径，不创建目录）；
`git status --short .omo BRIEF.md` 仅剩两份本地 affected-graph receipt，`.omo/state/**` 无改动。

**replay 证明**：同一组路径解析在两次独立执行中输出的公共行完全一致（第一次把 projection 名
写成 `system.yaml` 触发 `KeyError` —— 注册表实际键为
`system_health`/`health`/`governance_data`/`brief`；按注册表键重跑后通过）。

## 5. diff 与回滚路径

**diff（本次交付的净效应，实测）**

```
$ git diff --name-status ba7b3787d^..ba7b3787d
M       docs/plans/3y-bet-ledger.yaml
A       docs/superpowers/specs/2026-09-26-submodule-gitlink-reachability.md
M       projects/omo
```

即 3 个文件、无删除、除 gitlink 外全是文档。gitlink 单侧移动，且子仓 delta 恰好一个 commit：

```
$ git diff ba7b3787d^..ba7b3787d -- projects/omo
Submodule projects/omo c91b203e1..e9252141d:
  > feat(paths): ADR-0456 code/state 双根分离 — B1 内核侧 (BET-Y2Q4-T10-203) (#197)
```

**回滚路径（未执行，可执行性由上式证明）**

```
git revert --no-edit ba7b3787d
```

回滚把根 pin 还原为 `c91b203e`（该 commit 仍在 omo 对象库与 main 祖先链上），**不会**撤销
omo#197 —— 子仓改动独立落在 omo `origin/main`。副作用清单：无（本次交付未碰
`.githooks/**`、`.github/workflows/**`、`governance-checks.yaml`、cron/plist、`.omo/state/**`）。

**为什么这次不会被下一波 freshness 扫描再吃掉**（实测）：

```
$ git -C projects/omo rev-parse origin/main
e9252141d9c737c2d99edd76fb6bd1e12650a3ea      ← 与根 pin 相同
```

pin **等于** 子仓 main tip，正是 freshness gate 所要求的稳态；因此不需要 `[gitlink-regress:]`
豁免，也不会被对齐到别处。反过来说，上面的回滚**不是稳态**（`c91b203e` 已非 child main tip），
下一波扫描会把它再推回 `e925214`。这一点是"子仓先合、根指针后动"顺序的直接后果。

## 6. 未处置项（报告，不自作主张）

1. `tests/test_gac_gate_workflow_purity.py::test_reachability_and_generators_are_check_only`
   断言 CI 步骤含 `--require-main`，而 PR `4209` 已删之 → **main 上自 2026-09-22 起为红**
   （实测 `1 failed, 6 passed`）。修测试或恢复 CI 步骤都属 principal 决定，本 bet 两条都不做。
2. 同 SHA 上 `cascading_test` 一次红一次绿：
   `projects/omo/tests/unit/test_resident_status.py::test_one_hundred_concurrent_full_snapshots_are_bounded_and_side_effect_free`
   失败值 `assert 1277162 == 0`。该用例 monkeypatch **全局** `status.time.sleep` 并断言
   `sleep_count == 0`，负载相关。判据链：omo 自身 CI 在 `e925214` 绿、根 main 绿、pin 只差一个
   commit 且 env 未设时路径逐字节相同、`gh run rerun --failed` 同 SHA 转绿。本 bet 未加
   `--no-verify`、未登记豁免、未改测试。
3. `refs/remotes/upstream/main`（`6330e8202`）残留但无 `upstream` remote，会让
   `submodule-pointer-transaction.sh` 的增量 base 误判为 `.gitmodules` 变更；本次用
   `--changed-from origin/main` 规避。建议清理该陈旧 ref。
4. pre-push reachability 实测 34.8s（`--fetch` 全子仓），历史观测 52–161s，建议下沉 CI。

## 7. 与 BET-Y2Q4-T10-203 的关系

T10-203 的根侧交付被 `28158b9bc` 回退，其 `completion_evidence` 未随之更新。本 receipt
**不为其补写证据**：T10-203 的 ledger 状态由该回归的公开事实描述（spec §2 + 本节）承载，
重开或改写属 principal 决定。
