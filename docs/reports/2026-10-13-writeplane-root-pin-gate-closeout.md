---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-13
type: closeout-receipt
bet_id: BET-Y2Q4-T10-250
title: BET-Y2Q4-T10-250 closeout receipt — 写面根钉死门禁（bin/ 154 处 __file__ 检出根拼法收成 shrink_only 基线）
---

# BET-Y2Q4-T10-250 closeout receipt

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-250`
契约：`docs/superpowers/specs/2026-10-13-writeplane-root-pin-gate.md`（spec_version 1.0.0）
Retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-250.md`
交付：PR #4749 → squash `cdee6ca3fe05b034cca2e5a5c7bba265d1932b27`（2026-10-13，**28 pass / 2 skipping / 0 fail**；无 admin merge、无 `--no-verify`、无 `--force`、无 rebase/merge 吸收上游）
性质：ADR-0456 §「写目标跟随 profile 根」在 `bin/` 的**覆盖面门禁**。本轮零运行时效应 —— 95 个在账文件一个字节未动，改道仍属 B4b 批次 2+ 的逐批授权面

## 1 交付

| 文件 | 增删 | 内容 |
|---|---|---|
| `tests/unit/test_writeplane_root_pin.py` | +422 | 门禁本体：8 件用例 |
| `.github/workflows/governance-check.yml` | +8 | 显式 pytest 白名单第五件（不加则「CI 绿」不是这批用例的证据） |
| `docs/superpowers/specs/2026-10-13-writeplane-root-pin-gate.md` | +118 | 契约（`schema_version: specification/v1` / `lifecycle: contract`） |
| `.omo/_knowledge/retros/BET-Y2Q4-T10-250.md` | +91 | Retro |
| `docs/plans/3y-bet-ledger.yaml` | +109 / −1 | T250 条目 + `meta.total_bets` 绝对派生 |

合计 5 文件、+748 / −1，**零 `D` 行**（三点尺与两点尺读数一致，因 branch point 即当时的 `origin/main`）。

## 2 六条 ISC 的逐条读数

| ISC | 判据 | 实测 |
|---|---|---|
| 1 覆盖性 | 一次扫描同时产出「改前 = N」与「新增 = 0」 | `test_one_scan_reproduces_the_spec_readings` → **154 站点 / 144 对 / 95 文件**，且六类 marker 读数逐项相等（`.omo/_truth` 160 / `.omo/state` 103 / `.omo/_delivery` 82 / `runtime` 51 / `.omo/_knowledge` 62 / `kos` 2） |
| 2 自证 | 三条命中形状被点名 | ① 名字派生 + ② 内联派生 由 `test_detector_fires_on_both_pinned_shapes` 点名；③ 分段拼法（`W / ".omo" / "state" / "history.json"`）由 `test_detector_renders_the_whole_chain_not_just_its_first_segment` 断言**整条渲染**为 `.omo/state/history.json` |
| 3 反过宽 | 三条不该命中，且读面「可见但不计」 | `test_detector_does_not_fire_on_seam_or_read_plane`：经 `state_root()` 取根不进集合；`.omo/_truth` 与 `.omo/_knowledge` 由**同一次扫描**分类出来（`{s[2]} == {".omo/_truth", ".omo/_knowledge"}`）但 `gated_pairs() == frozenset()` |
| 4 shrink_only | 基线与实测**双向相等** | `test_gated_pairs_are_exactly_the_reviewed_baseline` + `test_new_pinned_site_breaks_the_baseline_equality`；另 `test_marker_table_is_load_bearing` 钉 marker 表承重 |
| 5 零运行时效应 | 在账 95 文件不得出现 | `git diff --name-only origin/main...HEAD`（三点）= 5 个文件，`grep -E "^bin/"` 计数 **0** |
| 6 CI 可见 | 进显式白名单 | CI `interface-check` job 的日志**打印了实际执行的 pytest 命令行**，其中第 471 行为 `../../tests/unit/test_writeplane_root_pin.py`；同一步以 `382 passed, 9 skipped in 121.76s` 收口 —— 本门禁的 8 件在其中 |

本地/装置面：**8 passed**；hermetic 复跑（`HOME=<空目录>` + `env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB -u OMO_PATH_ACL_PROFILE`，依赖由最小 venv 供给）**8 passed**。
`bet-ledger.py lint` → `OK -- 547 bets, 16 tracks, no errors`（27 warning，`not ancestor` 计数 27 / 其余 0 —— 全为 squash-merge 语义）。
`doc-ssot-lint.py --json` → `ok: true`；`check-doc-freshness-gate.py` → 全部在 90 天内。

## 3 变异对照，以及本轮唯一一次自伤

两次独立变异，**每次先证变异落地**（`git diff --numstat` 非空）再取读数：

- 从基线删一行 → **1 failed**（`test_gated_pairs_are_exactly_the_reviewed_baseline`）
- `GATED_MARKERS` 剥掉 `.omo/state` → **3 failed**（同源读数件 + 双向相等件 + 新增破基线件）
- 复原后 `git diff` 空 → 回到 8 passed

**作废记录**：第一版那段改基线的脚本自身 `NameError` 当场崩、文件逐字节未改，而我把「pytest 跑过了」读成了「变异跑过了」，于是写下「删一行 → 2 failed」。这句假读数同时进了 workflow 注释、retro 与台账 `verify[0]` 三处，三处都按实测改写并保留作废措辞（不悄悄换）。
教训：**变异对照的前置断言是「改动确实落地」，不是「测试跑完了」** —— 变异脚本可以静默死掉，之后那次运行测量的是未变异的工件。

## 4 受控后继：为什么换了分支

#4745 恒 `CONFLICTING / DIRTY` 且**零 checks 排队**。逐行验过它不是内容冲突：`71a958e6e:docs/plans/3y-bet-ledger.yaml` = `origin/main` 的台账 + 两个 hunk（T250 插入、`total_bets: 546 → 547`），没删 main 任何一行；但 merge-base 仍是旧分支点 `b59797e6d`，两侧都「改了」同一段台账 ⇒ 位置性冲突。

按 `bin/gac/gac-worktree.sh:942`（WP1 Wave B2：禁止 rebase/merge/pull 吸收上游，base 前进时发 `MANAGED_SUCCESSOR_REQUIRED`），正解是在当前 `origin/main` 上造一个独立受控后继重放同一交付面，而不是往 #4745 合上游。#4749 即该后继；#4745 已附完整说明后关闭。

## 5 rollback

单条 revert 即回全轮：`git revert cdee6ca3f`（删除门禁文件 + 摘掉白名单第五件 + 撤回台账条目，无运行时副作用 —— 本轮没有任何写目标改道，95 个在账文件逐字节未动）。

## 6 未做（按授权边界）

- 未改任何真实写目标（`.omo/state/**` / `runtime/**` 的落点仍按现状）—— 改道属 B4b 批次 2+，逐批授权。
- 未动 launchd plist / crontab / `services.yaml` / 权威 ledger 翻转。
- 本轮不碰 `bin/` 脚本登记面：交付的 5 个文件里没有 `.omo/_truth/registry/governance-checks.yaml`，
  也没有新增 `bin/` 脚本 ⇒ 脚本配额基线（`720 → 721`，属 #4746 / T248 那轮的具名准入）本轮零变动。
