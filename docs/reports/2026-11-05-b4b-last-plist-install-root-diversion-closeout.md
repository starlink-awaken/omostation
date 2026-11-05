---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-05
type: report
bet_id: BET-Y2Q4-T10-286
title: BET-Y2Q4-T10-286 closeout — 最后一条指向检出根的常驻 plist 改道安装位
---

# BET-Y2Q4-T10-286 收口收据

工程腿 = PR #5049 squash `dd50f60975acf5664a73a938036c128f5ddb2e66`（`2026-11-05T05:35:37Z` 入 main，5 件：
`bin/ops/launchd/com.omostation.test-archive-purge-7d.plist`、`.omo/_truth/registry/services.yaml`、
`.omo/cron/registry.yaml`、`docs/superpowers/specs/2026-11-05-b4b-last-plist-install-root-diversion.md`、
`tests/unit/test_gen_service_runtime_root.py`）。准入与工程同批交付 —— 本 BET 在 #5049 之前不在台账上
（`origin/main:docs/plans/3y-bet-ledger.yaml` 命中 0），因为台账径被并发活锁持有，见「残留」第 1 条。
机器侧改道（仅本 label 的 `bootout` + `bootstrap`）于合入后执行，principal 授权范围即此一步。
本文件是 completion-evidence-matrix/v1 的 diff / rollback / tests / fresh_receipt / live_canary / cleanup 六项载体。

## 交付

| 件 | 内容 |
|---|---|
| `bin/ops/launchd/com.omostation.test-archive-purge-7d.plist` | `ProgramArguments[2]` 的 `cd` 目标与 `WorkingDirectory` → `~/.local/opt/omostation`；删除 argv 内 `>> runtime/cron/purge-test-archive.log` 重定向；`StandardOut/ErrorPath` → `~/.local/log/com.omostation.test-archive-purge-7d.log`；新增 `EnvironmentVariables.OMOSTATION_STATE_ROOT`；注释块「为什么从检出根跑」整段替换为 spec §0.2 的否证结论 |
| `.omo/_truth/registry/services.yaml` | 该条 `program.args` / `outputs` / `content_digest` 重算，新增 `runtime_root: install`（`generate` 保持 `false`），notes 追加改道段与否证出处 |
| `.omo/cron/registry.yaml` | 同一句被否证理由的第三份副本订正；`command` 改到安装位，`planes: [launchd]`、`reality: installed` |
| `tests/unit/test_gen_service_runtime_root.py` | `INSTALL_ROOT_SERVICES` 漂移钉 28 → 29 登记本 label（CI 首跑拦住后才登记，不是先放宽判据） |
| 机器侧 | `~/Library/LaunchAgents/com.omostation.test-archive-purge-7d.plist` 换成仓内镜像副本，`launchctl bootout gui/$(id -u)/<label>`（rc 0）+ `bootstrap gui/$(id -u) <plist>`（rc 0） |

## done_when 逐条对账

全部读数出自 base `dd50f6097`，量具为 `bin/mof/gen-service-configs.py`（工程腿与收口腿同 base，尺未换）。

| # | 判据 | 实测 |
|---|---|---|
| AC-01 | 镜像 plist `plistlib` 可解析，且三处不含 `/Users/xiamingxing/Workspace` 字面量 | `git show origin/main:<plist>` 解析通过；`ProgramArguments[2]` / `WorkingDirectory` / `StandardOutPath`（外加 `StandardErrorPath`）命中 **0**（四 site 全测，spec 只要求三处） |
| AC-02 | 三方同源：仓内镜像 == 已安装副本 == registry `content_digest` | 三者均 `sha256:b36857f0444ce996e1c1c0ae0cf851056274d56799207b87a495803a83781d10`（registry 侧经 `load_services()` 读出，非正则截取） |
| AC-03 | `workspace_scoped_labels` 改后为 `['ai.hermes.gateway']`，`e1_drift` / `e2_undeclared` / `e3_malformed` / `e7_checkout` 保持 0 | 真机 `--reality-check --json`：`workspace_scoped=1` 且只剩 `ai.hermes.gateway`；`e1_drift=0`、`e1_status=ok`、`e2_undeclared=0`、`e3_malformed=0`、`e3_lint_debt=0`、`e7_checkout=0`、`e7_undeclared=0`、`e7_profile=29`、`e7_non_ok=0`、`installed_total=87` |
| AC-03b | `e6_non_ok` 5 → 6，新增那条是本 label（`state=undetermined`、`script=null`），`e6_blocking=0` | 真机读数 `e6_non_ok=6` / `e6_blocking=0`，本 label 条目 `{"declared_root":"install","script":null,"state":"undetermined"}` ⇒ 归因缺陷 #173（E6 认不出 `/bin/bash -c` 内联载荷），如实入账不隐去 |
| AC-04 | 反证：argv 的 `cd` 目标改回检出根，AC-01 计数必须变非 0 | 两面都做了。**文本面**：同一 blob 内 `~/.local/opt/omostation → Workspace` 替换后仍 `plistlib` 可解析，检出根字面量命中 **2**（argv + `WorkingDirectory`），判别力成立。**尺面**（同一装置倒着用）：87 份已装 plist 复制到临时目录、仅本 label 换回改道前旧副本，`reality_check(registry, <tmp>)` 读回 `workspace_scoped=2` 且点名 `com.omostation.test-archive-purge-7d`，同时 `e7_undeclared` 0 → 1、`e7_profile` 29 → 28 ⇒ AC-03 的位移确由本条改道贡献，不是别的噪声 |
| AC-05 | `launchctl print` 该 label `state` 可读；无参数（只读 `status()`）路径不产生任何删除 | print 可读：`state = not running`、`working directory = /Users/xiamingxing/.local/opt/omostation`、`stdout/stderr path = ~/.local/log/com.omostation.test-archive-purge-7d.log`、argv 为安装位。只读实跑（安装位、无参数）：cards 0 / dispatches 0 / Total 0 / Due 0。**未跑** `--auto` / `--purge`。零删除佐证：检出根旧日志 sha256 前 12 位 `0f0e7a035783` 与 9 行内容逐字节未变（mtime `Nov 5 02:07:05`），`dispatches_test_archive` 在三个候选根全部 ABSENT，`crontab -l` 无本作业行 |

## 改道前后（同一 label，`launchctl print`）

| 面 | 改道前（实测） | 改道后（实测） |
|---|---|---|
| `cd` 目标 / `WorkingDirectory` | `/Users/xiamingxing/Workspace` | `/Users/xiamingxing/.local/opt/omostation` |
| argv 尾部 | `… --auto --retention-days 7 >> runtime/cron/purge-test-archive.log 2>&1` | `… --auto --retention-days 7`（重定向交给 launchd） |
| `StandardOut/ErrorPath` | `/Users/xiamingxing/Workspace/runtime/cron/purge-test-archive.log` | `/Users/xiamingxing/.local/log/com.omostation.test-archive-purge-7d.log` |
| `EnvironmentVariables` | `[PATH]` | `[OMOSTATION_STATE_ROOT=/Users/xiamingxing/.local/state/omostation/prod, PATH]` |
| `state` / `runs` / `last exit code` | not running / 0 / never exited | not running / 0 / never exited |

`runs=0` 是预期而非缺陷：`RunAtLoad=false`、`StartCalendarInterval={Hour:2,Minute:7}`，重装发生在本地时间 13:37，
改道后尚无一次触发。**首条 canary 待 2026-11-06 02:07**，判据为 `launchctl print` 的 `runs` 增长 +
`last exit code = 0` + `~/.local/log/com.omostation.test-archive-purge-7d.log` 出现（该文件当前不存在）。
顺带一条量具观察：改道前的 print 也是 `runs = 0 / job state = uninitialized`，而检出根日志当天 02:07 确有写入
⇒ `runs` 不跨 bootstrap 代次累计，不能当历史记录用。

## 验证

- `python3 bin/mof/gen-service-configs.py --validate --json` → `ok: true / violation_count: 0`。
- `make gac-local-gate`（base `dd50f6097`，本 worktree）→ **PASS，69 checks executed，2 SOFT WARN**
  （`current-state-coherence` WARN + KOS 库缺席 exit 78 = skipped 而非 passed），6 件 known-unavailable 跳过；
  未使用 `--no-verify`。
- `--reality-check` 的注册表侧固定读 `canonical_root()`，因此 AC-03 一列以 `--registry <origin/main 的 services.yaml 快照>` 复算，
  避免「本地检出落后」把读数读歪（`gen-service-configs.py:58 services_yaml_path()`）。
- 工程腿 squash 内容等价：`git diff 48130a4e6 dd50f6097 -- <五件路径>` 为空 ⇒ 合并未引入分支外内容。

## 回滚

按 spec §4：`git revert -n dd50f60975acf5664a73a938036c128f5ddb2e66`，再把 `~/Library/LaunchAgents/` 副本换成回滚后的镜像并重新
`bootout` + `bootstrap`（改道前副本已存档）。§0.3 与 AC-05 证明改根不改变任何删除语义（两侧 Total=0），
回滚不需要数据恢复步骤。回滚会把这条常驻作业重新钉回「从检出根启动 + 写检出根日志」，而后者正是 ADR-0456 决策 1 要消灭的形状。

## 残留与读侧须知

1. **台账腿被并发活锁推后**。起手实测 `A2A Path Lock Collision: path 'docs/plans/3y-bet-ledger.yaml'
   overlaps with active claim 'docs/plans/3y-bet-ledger.yaml' in run
   20261104T115230Z-project-code-change-d825f60f`（actor `claude-lead`，BET-Y2Q4-T10-285）。对方 `expires_at`
   未到 ⇒ 不是僵尸锁，未 `--force-lock`、未 `prune-locks`。本收口腿只 claim 无主的 retro 与收据两径；
   `status: done` / `done_at` / `completion_evidence` 三轴由后续 run 落，条目正文（含 spec 摘要
   `sha256:d8afab8eb2a0e822c96060848362d80183725af82e6018e6f94dae96c3e9455d`）已在 worktree 内备好。
   ⇒ 在台账腿落地前，「BET-Y2Q4-T10-286 在 main 上存在」这一条不成立，别按台账检索这项交付。
2. **入口改了，码面没跟**。安装位 `~/.local/opt/omostation` 是独立 clone，停在 `3b85250d1`，落后 `origin/main`
   ⇒ 本 label 实际执行的 Python 码面不是最新提交。这正是 ADR-0456 B4b「入口改到安装位 ≠ 码面改到安装位」
   的原样复现，属 E6/#173 那一批待办，不在本 BET 判据内（AC 全部只要求入口、写面、env 三面离开检出根）。
3. **`ai.hermes.gateway` 那条假阳仍在**（#194，`gen-service-configs.py:729` 整 blob 子串命中），AC-03 因此显式期望长度 1 而非 0。
4. **E4 未分区 22 条异主 label 未动**（署名裁定 #147）；`--reality-check` 退出码 1 只由这一条 finding 造成，改道前后同形。
5. **本 worktree 有 2 个子模块检出仍空**（`projects/l4-kernel`：`restore --source=HEAD` 报 `could not resolve 'HEAD'`；
   `projects/omlxc`：需联网 fetch）。收口腿是纯文档，两者不参与本腿判据；若在复现别人读数时看到子模块类失败，先量这两处。
