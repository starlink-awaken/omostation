---
title: BET-Y1Q4-T1-02 复盘
owner: governance-team
created: 2026-09-04
lifecycle: history
last_updated: 2026-09-04
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

