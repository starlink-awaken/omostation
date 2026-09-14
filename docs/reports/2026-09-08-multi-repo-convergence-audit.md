# 多仓收敛盘点报告 (Multi-Repo Convergence Audit)

- date: 2026-09-08
- scope: BET-Y1Q3-T6-16 第一阶段 (只读盘点; human_gate 动作不在本报告执行)
- method: T10-140 cleanup-guard 分类 + git submodule status + gh pr list
- principle: 零破坏 — 不 reset / 不强推 / 不 clean / 不 stash 任何未知工作

## 1. 根仓分支分类 (lib/cleanup-guard 三维判定)

| 分支 | guard 判定 | 处置建议 |
|---|---|---|
| agent/governance-agent/bet-y2q4-t7-01 | 🛡 open-pr (#3424) | 等并行 PR 合并 |
| work/kos-ingest-bump | 🛡 open-pr (#3406) | 等并行 PR 合并 |
| agent/governance-agent/mof-l4-advance | 🛡 unpushed | 并行方未推工作 — **勿删** (T10-140 已系统防护) |
| fix/resident-jobs-adr0435 | 🛡 unpushed | 老王混战期分支, 内容已 squash 进 #3416 — 可人工确认后删 |
| auto/kos-ingest-bump | 🛡 unpushed | 并行方自动分支 — 勿删 |
| chore/t10-139-closeout | 🛡 unpushed | 内容已 squash 进 #3409 — 可人工确认后删 |
| work/t10-139-claim-broadcast | 🛡 unpushed | v2 的前身, 内容已在 #3405 — 可人工确认后删 |
| agent/governance-agent/t7-07 | 🛡 unpushed | 并行方 T7-07 域 — 勿删 |
| agent/governance-agent/agent-os-control-plane-foundation | 🛡 unpushed | 并行方 AGE-v2 域 — 勿删 |
| tmp-check | ✅ DELETABLE | 临时分支, 无未推无 PR |
| work/kos-ingest-bump2 | ✅ DELETABLE | kos bump 迭代残留 (#3406 用的是无 2 版) |
| work/kos-entity-ingest | ✅ DELETABLE | 已并入 ecos main (f56303d) |

**净结论**: 11 分支中 9 受保护 (T10-140 guard 全覆盖), 3 可删 (其中 2 个需并行方
确认 kos 域不再需要)。

## 2. 根仓 dirty surface 归因 (T6-16 done_when ①)

| 类别 | 文件面 | 归因 | 处置 |
|---|---|---|---|
| generated | `.omo/_knowledge/retros/resident/*.md` (约 20 个) | resident 系统 2026-09-08 修复后首次全量 tick 的正当写面 | 定期 sync 入库 (模式同 #3423) |
| generated | `.omo/_control/governance-data.json` | resident governance 写面 | 同上 |
| generated | `.omo/tasks/planned/*.yaml` (Y1Q1-T1 系列) | 计划投影生成 | 确认生成器后入库或 ignore |

**无 unknown owner 的 dirty 文件** — 全部可归因。

## 3. 子仓 gitlink 一致性

17 个子模块 `git submodule status` **零漂移** (无 + 前缀) — 根仓登记与实际
checkout 完全一致。

## 4. 子仓内部状态

| 子仓 | 当前 | 非 main 分支数 | dirty | 备注 |
|---|---|---|---|---|
| projects/omo | main | 30 | 0 | 大量历史 feat/fix/test 分支 (resident 系列交付遗产) |
| projects/ecos | main | 3 | 0 | kos-relations-ingest 已合并可清 |
| projects/agora | main | 2 | 0 | documents-facade 域并行中 |
| projects/cockpit | ⚠️ detached (0473060) | 1 | 0 | **detached HEAD** — 需并行方确认意图 |

## 5. 开放 PR

| PR | head | 归属 | 状态 |
|---|---|---|---|
| #3424 | agent/governance-agent/bet-y2q4-t7-01 | 并行 (research pipeline) | 等 review |
| #3406 | work/kos-ingest-bump | 并行 (kos bump, 注意与已合的 #3422 内容交叠) | 需确认是否 stale |

## 6. 建议收敛序列 (人类把关项)

1. **自动可做** (T10-140 防护下零风险): `tmp-check` 分支删除
2. **人工确认后删**: fix/resident-jobs-adr0435 / chore/t10-139-closeout /
   work/t10-139-claim-broadcast (老王交付链历史分支, 内容全部已 squash)
3. **并行方到场确认**: kos 域两分支 (bump2/entity-ingest) + omo 30 历史分支批量
   清理 (建议子仓跑 branch-ttl-gate --submodules --enforce, guard 会自动跳过
   未推分支)
4. **#3406 处置**: 与 #3422 (ecos f56303d) 内容交叠, review 时确认避免双 bump
5. **cockpit detached HEAD**: 并行方确认后归位 main
6. **resident 写面定期 sync**: 建立 cron 化 state-sync (模式已有 #3423 先例)

## 工具联动

本报告的全部分类由 T10-140 `lib/cleanup-guard.py` 产出 — 清理器防护与盘点
审计共用同一判定内核 (DRY)。
