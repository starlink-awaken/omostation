---
type: report
status: completed
owner: governance-team
last-reviewed: 2026-10-21
bet_id: BET-Y2Q4-T10-263
title: BET-Y2Q4-T10-263 closeout — B4b 批次 2 的 cron 侧改道预检（前置条件表，非改道本体）
---

# BET-Y2Q4-T10-263 closeout — cron 侧改道预检

交付物：`docs/superpowers/specs/2026-10-21-b4b-cron-cutover-preflight.md`
（spec_version 1.0.0，content_digest `sha256:b82f0bc6b09f09f49cb8c1c6a3e62c89a23ca48e7fe83f8e4c3c03c5ddbfc7f6`）
台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-263`
PR：#4853 —— squash 合并为 `e5823c0ac99d4e4986b6310a2186ab1af135a9b9`
（CI 终态 22 项 = 19 pass / 1 fail / 2 skipping；三项 required checks
`phase-gate` / `bet-done-transition` / `gac-gate` 全绿，唯一红项 `interface-check` 是基线自带，见 §2b）
Run：工程腿 `20261021T073157Z-project-doc-change-658a0c3d`（`close --status ok`，锁已释放）
→ 收口腿 `20261021T082339Z-project-doc-change-5b22f819`（workflow `project-doc-change`，profile `governance-agent`）

## 1 diff

工程腿（PR #4853，2 个 commit）：

| 文件 | 动作 |
|---|---|
| `docs/superpowers/specs/2026-10-21-b4b-cron-cutover-preflight.md` | 新建（§1 结论 / §2 七行测量装置 / §3 cron 精确 diff / §4 安装位可执行性 / §5 P1—P5 / §6 中止判据 / §7 non_goals） |
| `docs/plans/3y-bet-ledger.yaml` | 新增 `BET-Y2Q4-T10-263` 条目（557 → 558 条），`status: in_progress` + `accepted_specifications` 绑定 |

其中第二个 commit（`e561794f9`）是对同一 spec 的**自我否证订正**：初稿 §3 断言「这十个角色的常驻权当前在 launchd 侧」，
实测后改为「`services.yaml` 声明 13 / 实装 9 / 声明未装 4；9 条 cron 作业里 6 条有已装 twin、3 条无 twin」，
digest 由 `sha256:757235ed…` 变为 `sha256:b82f0bc6…`，台账 `content_digest` 同步重算。

收口腿（本 PR）：retro 落 canonical 位 + 本 receipt + 台账条目 `in_progress → done` 与 evidence matrix。

## 2 tests（台账 `verify:` 四条 + `done_when:` 五条，收口时复跑）

台账 `verify:` 读数（收口腿 worktree，HEAD = `e5823c0ac` = `origin/main`）：

| # | 判据 | 实测 |
|---|---|---|
| 0 | 恰好 1 条且 `status` 为 `in_progress`（关闭后 `done`） | 交付时 `n=1 status=in_progress overall=evaluating`；本腿翻 `done` |
| 1 | spec 文件 sha256 与 `content_digest` 后缀逐字节一致 | `b82f0bc6b09f09f49cb8c1c6a3e62c89a23ca48e7fe83f8e4c3c03c5ddbfc7f6` ✅（对 `origin/main` 上的字节取，非本地工作树） |
| 2 | `crontab -l \| /usr/bin/grep -c 'omo\.cli resident'` = 0，前后不变 | 交付前 `0`、收口时 `0` ✅ |
| 3 | `git diff --name-only origin/main..HEAD` 只含本轮交付面 | 工程腿只含 spec + 台账两个文件；无 `.omo/state/**`、无 `BRIEF.md`、无子模块 gitlink ✅ |

spec §2 七行装置读数，收口时**全部逐条复现**（不是引用交付时的快照）：

```
crontab -l | /usr/bin/grep -c .                    → 67      （非空行数；物理行数 80，注释 21）
crontab -l | /usr/bin/grep -c Workspace            → 25
crontab -l | /usr/bin/grep -c resident-agent-schedule → 1    （孤儿标记）
crontab -l | /usr/bin/grep -c 'omo\.cli resident'  → 0
安装位 5 个写目录                                    → 5 × MISS
安装位 import 探针（PYTHONPATH=<opt>/projects/omo/src）→ ModuleNotFoundError: No module named 'omo'
              （对照同一探针在 ~/Workspace rc=0）
<opt>/projects/omo 目录条目数                        → 0（子模块 16/16 未初始化）
launchctl 里 resident 类 label 数                    → 9（与 spec §3 归属行一致，未增未减）
```

本地门禁：`make gac-local-gate` 在工程腿跑出 `[FAIL] check-work-landed`。该 FAIL **不是本 BET 引入**：
在零改动的 canonical Workspace 上逐字节复现同一条失败，13 条 blocking 项全部属于其他 agent 的 run
（闲置 7.4—16.5 天）。我一开始把这次门禁读成「全 PASS + 2 SOFT WARN」，是错的——`tail` 截掉了那行 FAIL，
已在工程腿交付前当面纠正。

## 2b 唯一红项 `interface-check` 的归因（基线自带，非本 PR）

`governance surfaces` 退出非 0，JSON 里 `missing_registered_roots: ["_control"]`。链条：

1. `projects/omo/src/omo/omo_governance_surfaces_report.py:121` 判据是 `(omo_dir / top).exists()`；
2. `.omo/_truth/registry/omo-governance-surfaces.yaml:113`（`write_targets`）与 `:143`（`OMO-CONTROL` 的 `ref`）仍声明 `.omo/_control/`；
3. `#4852`（`5519773d6`，2026-10-21 07:36Z）把 `.omo/_control/debt-dashboard/current.yaml` 摘库并 gitignore，
   该目录在干净检出里不再存在 ⇒ `origin/main` 上 `git ls-tree -r .omo/_control` 计数 **0**；
4. 本机 `.omo/_control` 目录仍在（未跟踪但存在）⇒ **本地绿 / CI 干净检出红**。

即 #4852 只做了摘库半边，未同步 surfaces registry。它不是 required check，因此不阻断合并；
修法（给 `OMO-CONTROL` 加 `runtime: true`，与已绿的 `OMO-DELIVERY`/`OMO-LOCKS`/`OMO-WORKERS`/`OMO-LOG`/
`OMO-CAPABILITIES` 同形）会**改动门禁的判定面**，属另一条 lane 的署名决策，本 BET 不夹带。
`git diff --name-only` 证明本 PR 只碰 2 个文件，与 `.omo/_control`、该 registry 均无交集。

**追加（2026-10-22 收口腿推送前实测）**：上游 `#4854`（`3a1f5617e`）把 `.omo/_control/README.md`
纳入跟踪 —— `git ls-tree -r --name-only origin/main .omo/_control/` 计数由 **0 → 1**，
`(omo_dir / "_control").exists()` 在干净检出里重新成立 ⇒ 该非 required 检查按构造自然转绿。
反向确认了第 3 节的归因：红是基线造成的，本 BET 没有为此改动任何门禁判定面。

## 3 live canary（运行面零效应的正向证据）

- 真实 crontab 全程未动：`crontab -l` 快照落 `/tmp/crontab.baseline`，收口时与新读数字节相同
  （`sha256[:16] = d2677b3321a39568`，全值 `d2677b3321a3956895423e56612f1d0f371fb05f43af4ea47ac26059eaa13614`，
  `IDENTICAL to now: True`）。
- installer 只以 shim 方式 dry-run（`PATH=/tmp/drybin:$PATH`，shim 拦 `crontab -l` / `crontab -`），
  生成 88 行文本但零次真 `crontab` 调用。
- launchd 一律未动：不 bootout / bootstrap / kickstart，不写 `~/Library/LaunchAgents`，9 条 resident label 原样。
- 未初始化任何子模块、未在安装位建目录、未写 `services.yaml`。
- 推送前第三次复测（2026-10-22 01:51Z，跨日）：`crontab -l | shasum -a 256` 仍是同一全值
  `d2677b3321a3956895423e56612f1d0f371fb05f43af4ea47ac26059eaa13614`，
  `crontab -l | /usr/bin/grep -c 'omo\.cli resident'` 仍是 `0` ⇒ 零运行面效应不是交付那一刻的快照断言。

⇒ 本 BET 的写面严格限于文档与台账；它产出的是**授权问题**，不是授权执行。

## 4 replay

复现顺序（不动运行面）：

1. `crontab -l > /tmp/ct.now; shasum -a 256 /tmp/ct.now` —— 取基线。
2. `PATH=/tmp/drybin:$PATH bash bin/ssot/install-resident-cron.sh` —— shim dry-run，看 88 行输出与 §3 的
   「2 条路径换 + 9 条净新增」分类。
3. 再取一次 crontab sha —— 必须与第 1 步逐字节相同。
4. `git show origin/main:docs/superpowers/specs/2026-10-21-b4b-cron-cutover-preflight.md | shasum -a 256`
   —— 必须 = `b82f0bc6…`（台账绑定即成立）。
5. retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-263.md`（四问 + 4 条 lessons）。

## 5 rollback

- 台账与 spec 的回退 = `git revert e5823c0ac`（一条 squash commit，无子模块 gitlink、无运行态）。
- 运行面无需回退（本轮没有写它）；`flock`、installer、plist、crontab 逐字节未变。

## 6 cleanup

- 工程腿 worktree `ws-b4b-cron-preflight-263`：合并时 `merge` 拒绝释放（两项 untracked：retro 与 `runtime/affected/`），
  retro 已迁入收口腿，剩余 scratch 在收口腿交付后一并清理。
- `runtime/affected/t263.json` / `t263c.json` 为 claim 前置 receipt，用完即删、不进 commit。
- 分支由 GitHub squash-merge 自动删除（`agent/governance-agent/b4b-cron-preflight-263`）；不再手工 `branch -D`。

## 7 scope 边界（本 BET 明确未做的事）

- 不改道任何 cron 行、不重装 installer、不判定 9 条 resident 作业里哪条「该活」。
- 不把权威 ledger 翻到安装位；不动 `services.yaml`、launchd、crontab。
- 不预先把 surfaces registry 的 `OMO-CONTROL` 加 `runtime: true`（§2b 的修法属另一 lane）。
- **不宣布 ADR-0456 B4b 或整个 plan 完成**：本 BET 只把批次 2 的 cron 侧变成一次可答复的授权。
