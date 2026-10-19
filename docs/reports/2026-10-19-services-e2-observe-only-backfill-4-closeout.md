---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-19
type: closeout-receipt
bet_id: BET-Y2Q4-T10-253
title: BET-Y2Q4-T10-253 closeout receipt — 4 条 B4b 期间新装而未登记的 Workspace 命名空间服务登记为 observe-only（E2 4→0，owned 集合相等成立）
---

# BET-Y2Q4-T10-253 closeout receipt

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-253`
契约：`docs/superpowers/specs/2026-10-19-services-e2-observe-only-backfill-4.md`（spec_version 1.0.0，digest `sha256:b19b1fec0e1cd7c7de9f44839e3ffbe4690586348cf8945d0573cc51ea638ff9`）
Retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-253.md`
交付：分支 `agent/governance-agent/t10-253-e2-backfill`（base `fdb106c9f`）→ squash 合并 SHA 记于台账
`completion_evidence.axes.engineering.merged_reachable_commit` 与本 run 的 closeout evidence
性质：ADR-0456 **B3 收口** —— 本轮不动本机 launchd，只让「已装 label 集合 == 注册表集合」这条
中止判据在本检出可证。

## 1 交付

| 面 | 位置 | 内容 |
|---|---|---|
| 注册表 | `.omo/_truth/registry/services.yaml` | +4 条 `generate: false` observe-only 条目（services 373 → 377） |
| 规格 | `docs/superpowers/specs/2026-10-19-services-e2-observe-only-backfill-4.md` | 新档，含 §5 逐条归属与 §7 non-goals |
| 台账 | `docs/plans/3y-bet-ledger.yaml` | 新条目 `BET-Y2Q4-T10-253`，bets 549 → 550 |

登记的 4 条（全部落在 `com.omostation.*` 命名空间、`launchctl` 状态 active、本仓注册表零生成）：

| label | 安装者归属 | 触发面 | plist sha256（前 8） | 键面里生成器不发射的键 |
|---|---|---|---|---|
| `com.omostation.resident-agent` | `projects/omo/src/omo/resident/service_ctl.py:27`（`PLIST_LABEL`） | keepalive + RunAtLoad | `12482c70` | `WorkingDirectory`；且 interpreter 含 `/.venv/bin` → `resolve_interpreter` 直接 `ValueError` |
| `com.omostation.resident-web` | 未归属（本检出按 label 全仓 grep 无写者） | keepalive + RunAtLoad | `3e8eb76a` | `WorkingDirectory` |
| `com.omostation.mbp-night-patrol` | 未归属（同上） | calendar 02:30 | `6a8bf32e` | `WorkingDirectory` |
| `com.omostation.panorama-compact-observation` | 未归属（只命中脚本登记 `bin/_registry/scripts/governance/compact-observation.yaml`） | interval 240s + RunAtLoad | `55b300ca` | 无（键面可表达，本轮仍不接管内容） |

归属方法：对每条 label 在 `bin/ projects/omo/src tests/ .github/ Makefile` 全量 grep
`com.omostation.<label>`，命中者才写进 `notes`；未命中的三条如实记「安装者未归属（不编造来源）」。

## 2 验收读数（ISC-1 … ISC-7）

同一条命令、同一台机器、两棵注册表树并测（这是本轮唯一能区分「我改的」与「机器变的」的装置）：

| 字段 | `origin/main` 树（无我的改动） | 本检出树（含 4 条） | 判据 |
|---|---|---|---|
| `e2_undeclared` | 4 | **0** | ISC-1 ✓ |
| `owned_declared` / `owned_installed` | 42 / 46 | **46 / 46** | ISC-1 ✓ 集合相等在 B3 作用域内成立 |
| `e1_drift` | 0 | 0 | ISC-2 ✓ |
| `e3_lint_debt` | 0 | 0 | ISC-2 ✓ |
| `e4_prefix_ok` | False（16 条未分区） | False（同一 16 条） | ISC-2 ✓ 未新增分类问题 |
| `e5_enabled_missing` / `e5_disabled_residual` | 1 / 1 | 1 / 1 | ISC-2 ✓ |
| `registry_declared_total` | 70 | 74 | 恰好 +4（只动声明面） |
| `installed_total` | 73 | 73 | 见 §3 —— 基线时的 71 是机器侧数字，非本轮变量 |
| `workspace_scoped` | 37 | 37 | ✓ 两条新装的 label 不在本仓命名空间 |

ISC-3 `--validate --json`：`ok true / violation_count 0`。
ISC-7 `--check`：`exit 0`、`0 drift (68 launchd services)`。
ISC-4 本机 launchd 零改动：4 份 plist 的 sha256 与 size 逐字节等于
`/tmp/pre253-plist-baseline.json`；`launchctl` state 全为 `active`；pid 对 3 条不变，
`panorama-compact-observation` 的 pid 由 `44438` 变 `93421` —— 它是 `StartInterval 240` 的一次性
轮次进程，pid 天然轮换，不构成改动信号。
ISC-5 登记内容与 `plistlib` 转出的实况逐项一致：对每条比对 `label`、
`[interpreter, entrypoint, *args] == ProgramArguments`、`content_digest == sha256(plist)`、
`run_at_load`、`KeepAlive ↔ resilience.keepalive`、`environment`（逐键值）、`outputs`、
`trigger` ↔ `StartInterval`/`StartCalendarInterval`，4 条全 OK。
ISC-6 `make gac-local-gate`：检查项**全部 [PASS]、硬失败集合为空**（相对基线零新增），
收尾为 `FAIL | 2 SOFT WARN`，两条 soft warn 是机器共享面的状态读数
（`agent-workflow-status: stale_locks=8, active_runs=15` 与 `governance-evolution-packages: release_ready=false`），
与本轮改动无因果 —— 本轮只改注册表与台账。

## 3 基线在交付窗口内被机器自己移动了

预交付基线（`captured_at` 2026-10-19T01:39:12Z）记的是 `installed_total 71 / E4 未分区 14 条`。
交付时实测 `73 / 16`。差额两条都是 `com.localbrain.*`：
`com.localbrain.monitor.plist` mtime 本地 09:39、`com.localbrain.backup-sync.plist` 本地 09:52，
即基线拍下后 13 分钟内由别的线装上。二者不在 `workspace_prefixes`（`workspace_scoped` 仍 37、
`owned_installed` 仍 46），所以对 E2 与「owned 集合相等」这条判据零影响。

判据因此按 §2 的两棵树并测来出：`installed_total` 是**机器读数**，不能当本轮验收项；
本轮真正能动的是声明面的 4 个字段。台账 done_when 里把 71 写进 ISC-2 的措辞，据 §2 表
逐字段判定为「除 installed_total 外全部逐字相同」，并把 installed_total 的漂移归因如实记在这里。

## 4 未做（按 spec §7 与台账 non_goals）

- 不回写 `com.cockpit.dashboard` 的 `enabled`（E5 disabled_residual 那条）—— 署名裁定面。
- 不补装 `com.l4.omo.sync`（E5 enabled_missing 那条）—— 署名裁定面。
- 不动 `exempt_labels` / `workspace_prefixes` / `--reality-check` 判据本体（E4 那 16 条未分区）。
- 不做 plist/cron 改道（B4b 批次 2+，逐批授权）。
- 不收口那 4 个往 `~/Library/LaunchAgents` 写而不登记的 installer
  （`service_ctl.py:27`、`bin/svc/service_view.py:281,487`、`bin/gac/install-watch-agent.py:26`、
  `bin/gac/documents-jobs-scheduler.py`）—— 那是让集合相等「按构造重新破掉」的源头，需要单独一轮。
- **不宣布 ADR-0456 B1/B3/B4/B5 或整个 plan 完成**。本轮交付的是 B3 中止判据变得可验，
  不是 B3 全部范围（B3 还含 label 的 profile 前缀与双 profile `--check`）。
