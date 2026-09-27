---
schema: md/v1
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-27
type: report
bet_id: BET-Y2Q4-T10-207
title: BET-Y2Q4-T10-207 运行时代码安装位落位（ADR-0456 B4a） — closeout receipt
created: '2026-09-27'
run_id: 20260927T065628Z-project-code-change-1b82b22d
---

# BET-Y2Q4-T10-207 closeout receipt — ADR-0456 B4a

> 本文件是 ledger `completion_evidence` 指向的 receipt。所有数值为 closeout 撰写时点
> （2026-09-27T09:19Z）在**合并后的 main** 与**真实安装位目录**上重新实测，非复述交付期数字。
> 契约定义见 `docs/superpowers/specs/2026-09-27-runtime-install-root-landing.md`（`spec_version 1.0.1`）。
> 复盘见 `.omo/_knowledge/retros/BET-Y2Q4-T10-207.md`。
> 本轮边界：**只落位、不改道**。任何 plist / crontab / launchctl / ledger 数据搬迁都不在本轮，
> 属 B4b（见 §5）。

## 1. 交付物

| 项 | 值 |
|---|---|
| 主仓 PR | #4439（`state: MERGED`，`mergedAt 2026-09-27T09:15:16Z`） |
| 主仓 merge commit | `1b5f02cb35ef6bc27363bbaa9458b90c710f4157` |
| merge commit 触及文件 | **恰好 9 个**（`git show --name-only 1b5f02cb3`）：`bin/lib/repo_root.py`、`tests/unit/test_repo_root_profile.py`、`Makefile`、`bin/_registry/scripts/governance/repo_root.yaml`、`AGENTS.md`、`ARCHITECTURE.md`、`.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`、`docs/plans/3y-bet-ledger.yaml`、`docs/superpowers/specs/2026-09-27-runtime-install-root-landing.md` — 无生成态（`.omo/state/**`、`BRIEF.md`、`governance-data.json` 均未随 PR 走）、无子模块 gitlink |
| 行量 | `+573 / -21`（`git diff --numstat 1b5f02cb3^1 1b5f02cb3` 合计） |
| 分支 commit（按 change-lane 拆分） | `6ce96f61f` code（定位器 + `--json` CLI + `make runtime-install-root` + 守卫测试 + 脚本登记表）/ `f4979e930` docs（ADR + spec + AGENTS + ARCHITECTURE）/ `a2ecd7c6d` docs_data（台账绑定） |
| 契约 spec | `spec_version 1.0.1`，digest `sha256:b9b469f9cf8f75a7f709cfb94f8b8e44178c0c77b297742e9d9575a2fea462d6`；closeout 时点复核 `git show origin/main:<spec> \| shasum -a 256` == 台账 `BET-Y2Q4-T10-207.accepted_specifications[0].content_digest` == 工作树文件，**三者一致**（不写台账行号：派生计数与证据块会挪动它，本轮自身就是例证） |
| 代码安装位 | `~/.local/opt/omostation` —— 自有 `.git` 的**独立 clone**（`git worktree list` 不含它，`git -C …/.git` 是目录而非 gitfile），detached 在**记录在案**的 `1b5f02cb3`（即本轮 merge commit），工作树干净（`git status --short` 0 行），子模块未 init，**未写 `omostation.profile.toml`**（零消费者，与 `BET-Y2Q4-T10-203.md` 同一判定；它属 B4b） |
| 新增 API | `repo_root.install_root()`（缺席→`None`，不抛异常）、`repo_root.roots_report()`、`repo_root.main()` + `--json`；`INSTALL_ROOT_ENV = OMOSTATION_INSTALL_ROOT`、`INSTALL_ROOT_RELATIVE = .local/opt/omostation` |
| 入口 | `Makefile` `runtime-install-root`（`bin/` 有净新增脚本配额 ⇒ 入口加在 Makefile，非新脚本） |

## 2. done_when 实测（spec §4 七条，逐条，closeout 时点）

| # | 判据 | 实测 |
|---|---|---|
| D1 | 安装位存在且为独立 clone、detached 在记录 SHA | `HEAD = 1b5f02cb35ef6bc27363bbaa9458b90c710f4157`；`dirty=0` |
| D2 | 安装位内 `repo_root.py --json` 报 `code_root == install_root` 且 `canonical_root == ~/Workspace` | `code_root=/Users/xiamingxing/.local/opt/omostation`、`install_root=` 同值、`cwd_is_install_root=true`、`canonical_root=/Users/xiamingxing/Workspace` —— **两条同时成立**（本轮只读） |
| D3 | 守卫测试覆盖缺席→None / 落位不改解析 / 不污染 state_root / CLI 键 | `python3 -m pytest tests/unit/test_repo_root_profile.py -q` → **852 passed in 2.17s**；其中 `test_landing_an_install_root_does_not_move_any_existing_root` 直接钉 D2 的反面 |
| D4 | 清扫不可见性被钉住 | `worktree-hygiene-audit.py --json` 输出中 `.local/opt/omostation` 出现 **0 次**；`test_hygiene_sweep_cannot_select_the_install_root` 用 `ws-*` 样本断言"能看见 worktree、看不见安装位" |
| D5 | `make runtime-install-root` 存在且无需第二处入口 | 实测打印两段 JSON（worktree + 安装位自报）；合并前该目标显式打印「安装位落后于本轮」而不是把空输出当通过 |
| D6 | agent 感知更新 | `AGENTS.md` §1 第 9 条（三根并列 + 问根命令）、§7 新条（"它不是第三个可写的根"、旧路径作废、别当残留扫掉）、`ARCHITECTURE.md` SoT 映射新增一行、`bin/_registry/scripts/governance/repo_root.yaml` 描述改正（原写"库模块（非可执行入口）"，本轮之后不成立） |
| D7 | ADR-0456 同步修正 | 路径、"release tag"→"记录 SHA"、§5 防呆改判为守卫测试、B4 拆 B4a/B4b、标识冲突记录、`last-reviewed: 2026-09-27`；**`status` 仍为 PROPOSED**（见 §4） |

## 3. 零运行时效应（本轮的核心不变量）

| 探针 | 实测 |
|---|---|
| `gen-service-configs.py --reality-check --json` | `ok=true`、`e1_drift=0`、**`e2_undeclared=0`**、`installed_total=56`、`workspace_scoped=43`、`owned_installed=49 == owned_declared=49` —— 与 B3 收口时点逐键一致，即本轮**没有**新增/改动任何 plist |
| `~/.local/opt/omostation` 被 plist 引用 | `/usr/bin/grep -rl "\.local/opt/omostation" ~/Library/LaunchAgents` → **0 个文件** |
| `~/Library/LaunchAgents` 引用 Workspace | **51 个 plist**（`grep -rl "/Users/xiamingxing/Workspace"`，含并发 agent 新增服务；reality-check 的 `workspace_scoped=43` 是"归属本工作区命名空间"的口径，两者不是同一计数，均照实记录）—— 一个都没动 |
| crontab | 64 行，`opt/omostation` 命中 **0** 次 —— 未 `crontab -w`、未启停任何 job |

## 4. 与 plan 不符的实测事实（打假）

1. **`~/Runtime/omostation` 作废**：大小写不敏感卷上 `~/Runtime` 与 `~/runtime` 是**同一 inode（146632641）**，而该目录是 `projects/runtime` 的 Tier-1 运行时数据域（`matrix.yaml` / `matrix_state.json` / `scheduler_state.json` / `taskobject_envelopes.jsonl`，其 `CLAUDE.md` 写"读自由 / 写需确认"），且 `projects/runtime/scripts/service-ctl.sh:10` 已把 `$HOME/runtime` 当 `RUNTIME_HOME` 缺省。principal 于 2026-09-27 选定 `~/.local/opt/omostation`。
2. **没有可用的 release-tag 序列**：481 个 tag，`v*` 最后一个是 `v2026-06-15-r1`（落后 main 三个多月）。版本锚点改为**记录在案的 `origin/main` SHA**，一致性比对由 `git describe` 改为 `git rev-parse HEAD`。
3. **主仓是 shallow**：`git clone --local` 打印 `source repository is shallow, ignoring --local`，183 MB 对象是**复制**而非硬链接 —— plan 的"磁盘成本约等于零"改判为"约 250 MB，仍可接受"。**故意不跑 `--unshallow`**（对共享仓的大流量网络写不是零效应动作）。
4. **排除清单是空动作**：`worktree-hygiene-audit.py` 的 `_candidate_dirs()` 只 glob `$HOME/ws-*` / `$HOME/workspace-*` + 已登记 worktree；`gac-branch-prune.sh` 删分支不删目录。plan 的"加排除清单"改判为**守卫测试钉住边界**。
5. **spec 自身有两处契约缺陷**（实现时暴露，已在本 PR 修 spec 到 1.0.1）：done_when #5 写的是 `make install-root-check`（实际交付 `runtime-install-root`，与邻居 `service-registry-reality` 同族）；done_when #2 在 PR 时点**不可满足**（clone 早于 CLI，必须先合并、再把 clone 重新 detach 到新 main SHA 才能验）。
6. **交付烧掉两个分支代际**：#4438（base `49d1d68cd`）被 GitHub 判 `CONFLICTING` —— 唯一冲突是台账派生行 `meta.total_bets`（两侧都把 488→489 之后 main 又 minted 到 491）；`Makefile` 经 `git merge-tree` 验证是可自动合并（upstream #4430 重构与本轮 hunk 不同区）。#4439 重建在 `7f430b422`，台账经 `ledger-safe-insert.py` 重插得 `bets now 492`、`total_bets: 492`。这与 `BET-Y2Q4-T10-203.md` Q1 记录的"合并窗口赛跑"同因，本轮不新增解法。
7. **`ADR-0456` 标识冲突（只报告，不处置）**：`origin/main` 上有两个文件同时声明 `id: ADR-0456`，其中被记为 ACCEPTED（PR 4413）的那条属于另一个决定。因此本 ADR **不改 status**，引用本契约必须写文件名 `0456-dev-runtime-profile-root.md`。处置权在 principal。

## 5. 本轮刻意不发（留给 B4b）

`omostation.profile.toml`、`canonical_root()` 改道、plist/cron 分批切换、ledger `.backup` 迁移到
`~/.local/state/omostation/{prod,dev}`、安装位子模块 init、`--unshallow`、`make worktree-prune`。
台账条目的 `circuit_breaker` 已逐条封禁这些动作，越界需另立 bet 并逐批授权。

## 6. rollback

单 commit 粒度可回滚：revert `1b5f02cb3` 即移除定位器 / CLI / make 目标 / 守卫测试 / 文档与台账绑定；
安装位目录 `~/.local/opt/omostation` 是**仓外**产物，revert 不影响任何在跑服务（本轮无人引用它，
§3 的 plist 与 crontab 命中数均为 0），删除该目录即完全撤销落位本身。
