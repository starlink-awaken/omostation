---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-12
type: closeout-receipt
bet_id: BET-Y2Q4-T10-245
title: BET-Y2Q4-T10-245 closeout receipt — tests/unit 13 处 host 锚点改由 registry / home 派生，3 处合法命中反向钉住
---

# BET-Y2Q4-T10-245 closeout receipt

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-245`
契约：`docs/superpowers/specs/2026-10-12-tests-unit-host-anchor-convergence.md`（spec_version 1.0.0，digest `sha256:97b6ce98…`，在 merged main 上逐字节对拍通过）
机器可读读数：`docs/reports/2026-10-12-bet-245-closeout-canary.json`
Retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-245.md`
交付：PR #4723 → squash `84d8b91e8`（2026-10-12，16 pass / 1 skipping / 0 fail，无 admin、无 `--no-verify`、无 `--force`）
性质：ADR-0456 **B4b 批次 2+ 的前置** —— 本轮不搬运行态，只把测试面从这台机器上解绑

## 1 交付

| 面 | 位置 |
|---|---|
| 13 处锚点改关系断言（期望值来自 registry 声明值 + `Path.home()` 组合 + `code_root()`） | `tests/unit/gac/test_meta_doctor.py`、`tests/unit/test_agent_cell_semantic_scheduler.py`、`tests/unit/test_reference_cell_direct_local_schedule.py` |
| 判据用例（5 个 test：检测器自证、命中面钉死、合法站点形状反向钉住、镜像用例「派生而非写死」、`str(HOME` 点数集合相等） | `tests/unit/test_tests_unit_host_anchors.py` |
| 契约与台账 | `docs/superpowers/specs/2026-10-12-tests-unit-host-anchor-convergence.md`、`docs/plans/3y-bet-ledger.yaml` |

零改动面：`projects/omo/**`（无 gitlink）、`runtime/cron/*.plist`（`generate: false`，是外部安装态镜像）、
`services.yaml` 本体的 host 字面量、§1 表两个非锚点文件、`gate-known-debt.yaml`。
尺：`/usr/bin/grep -rn`（**不用 `git grep -E`** —— 正则引擎不同读数不同，T10-231 实测）。

## 2 判据读数（全部在 merged 树或对照树上量，不在工作树推断）

- **ISC-1 同尺差分（一次扫描产两侧）**：改前 `386ff8b92` = **16 站点 / 5 文件**，改后 `84d8b91e8` = **3 站点 / 2 文件**。
  测量装置：`git archive <ref> tests/unit | tar -x` 造对照树后跑同一把尺。
  **差分目标是 3 而不是 0** —— 那 3 处是脱敏用例（`test_spine_diff_adaptation.py:35,42`，
  它的输入**必须**含真实用户名形状才能证 `<REDACTED_USER>` 生效）与一次环境伪影的 docstring 叙述
  （`test_service_interpreter_stability.py:11`，不参与断言）。
- **ISC-2 断言强度**：13 处一律改**关系断言**，`==` 无一条降级为 `in` / `is not None`。
- **ISC-3 非同源（变异对照，本轮重跑）**：`services.yaml` 两条 entry 的 `program.args` 各改 **1 字节**
  ⇒ `test_agent_cell_semantic_scheduler` `rc=1`（2 failed）、
  `test_reference_cell_direct_local_schedule` `rc=1`（2 failed, 1 passed）；
  还原后 `/usr/bin/shasum -a 256` = `ddfd5d0d…` 与改前逐字节相同、`git status` 该路径为空。
- **ISC-4 反向钉住（否证真跑过）**：删掉 `test_service_interpreter_stability.py:11` 那一处合法命中
  ⇒ `test_host_literals_are_confined_to_declared_legitimate_sites` 与
  `test_legitimate_sites_still_present_and_in_the_right_shape` **两条同时红**（rc=1），
  还原后 `eee1b04c…` 逐字节相同。⇒ 「顺手清理合法项」会被当场抓住，而不是让差分洗绿。
- **ISC-5 三环境读数**（尺：`uv run --with pyyaml --with pytest python -m pytest <四文件> -q`）：
  ① 未声明 profile = **25 passed / rc=0**；② `OMOSTATION_STATE_ROOT=/tmp/t10245-ambient-state` = **25 passed / rc=0**；
  ③ `HOME=/tmp/t10245-emptyhome` + `env -u OMOSTATION_ROOT` = **1 failed / 24 passed / rc=1**，
  红的只有 `test_reference_cell_smoke_plist_uses_fresh_main_and_attempt_evidence`
  —— 即 §2 第 2 类那 3 处 `str(HOME / …)` 组合面。
  **这不是回归**：基线（host 字面量烧进断言）在 ③ 反而全绿，那是假绿；
  去 host 的正确形状就是「只在声明的 host 组合面红」，且点数钉成
  `{agent-cell: 0, reference-cell: 3}`（`test_home_composition_is_confined_to_declared_sites`）。
- **ISC-6 门禁差分**：`make gac-local-gate` 在 merged 树 exit 2，硬失败集合
  = {`service-config-drift`, `check-work-landed`} = **基线集合，新增 0 条**。
  预存指认：`check-work-landed` 的 `blocking=2` 报的是 2026-10-04 两条**别的会话**的 run
  （`missing_landing`，本地浅检出下可达性判据无语义），在**主工作区 `origin/main` 检出**跑同一把尺
  输出逐字节相同。两条都在 `done_when` 里明令：**不得为它们登记债或改窄判据**。
- **相关治理面**：spec-binding / ledger 校验、doc-governance、`bin-quota-diff`、`test-collection` 等在
  PR #4723 的 CI 里 16 pass / 1 skipping / 0 fail。

## 3 台账结构与两轮顺序（WorkPacket 投影的正面证据）

| 轮 | run | claim | packet 面数 | packet hash |
|---|---|---|---|---|
| 1 声明 | `20261012T023831Z-project-doc-change-b2567131` | 仅 `docs/plans/3y-bet-ledger.yaml` | 6 | `sha256:3126663f…` |
| 2 落盘 | `20261012T023948Z-project-doc-change-a5416a9b` | 台账 + retro + receipt + canary | 9 | `sha256:f73cfc80…` |

`scope.write_surfaces` 由台账在 `start` 时投影、并在每次 `claim` 从活台账重导比对
（`bin/plan/bet-ledger.py:2333-2337`），所以「声明 closeout 面」与「写那三面」不能共用一个 run。
两轮 hash 不同、第二轮 9 面含三件新声明，就是投影生效的证据。
台账合并态结构契约（在 merged blob 上直跑，非看 rc）：`len(bets)=543 == meta.total_bets`、id 唯一、
上游 T10-241 块逐字节等值、两侧条目 `lost: [] / altered: []`。

## 4 冲突处置（本轮的形状与 T10-239 不同）

上游 #4722 改了 **`meta.total_bets` 这一条标量行（542）**，我方正插同一位置（543）。
内容预置（换上游字节为底 + 逐字重放我的条目，commit `aca8be193`）后
`git merge-tree --write-tree --name-only origin/main HEAD` **仍 rc=1** ——
**双方重写同一标量，文本层面没有写法能同时是 542 又是 543**。
`rebase` 被 `pre-rebase` hook 拒绝并指明授权通道是 merge/PR 合流，于是走 `git merge origin/main`
（`fe5b53af1`），解完对 merged blob 跑 §3 的结构契约才报干净。未用 `SWARM_ESCAPE_ID`。

## 5 rollback

- 交付面是纯测试侧派生化：回滚 = revert `84d8b91e8` 那一个 squash commit。
  它不碰 `projects/omo`、不碰 plist/cron/registry 本体、不碰 `bin/**` 与 `bin/lib/repo_root.py` 解析序，
  ⇒ 回滚不牵动 B1/B5 其他门，也不改变任何现役进程的路径解析。
- 收尾轮（retro + receipt + canary + 台账 `write_surfaces` / `completion_evidence` / `status`）可单独 revert，
  不影响交付面。
- 反向依赖：B4b 批次 2+（43 个 plist 改道）落地后，这三条用例不再因路径变化而红 —— 那是本轮的存在理由，
  所以回滚本轮会让那批授权批次重新踩测试面假红。

## 6 清理与安全

- 主工作区 `/Users/xiamingxing/Workspace` 全程只读；未替并发会话切分支、stash 或删锁。
- 暂存一律显式列路径；生成态不入库（`runtime/affected/**` 用完即删、`.omo/_delivery/**` 未跟踪）。
  本轮 gate 复跑后 `git status` 只剩我的未跟踪交付物，无 `.omo/state/system.yaml` 时间戳漂移。
- 交付 run `20261012T014050Z-project-code-change-555ad7ae` 与两轮收尾 run 均以 `--status ok` closeout；
  `missing_retro` 的真实含义本轮再证实一次：retro 必须在**执行 closeout 的那个检出**里存在
  （`bin/plan/chain_bind.py:42` 的 workspace = `__file__` 上两级；只有 `.omo/_delivery/agent-workflows/` 是 symlink 桥）。
- push 前按授权跑 L3 深度安全审查，`findings_count: 0`；提交集每次变化重新征询，不在未授权时推送。

## 7 遗留（登记，不用改窄判据换绿）

| 项 | 为什么不本轮修 |
|---|---|
| `service-config-drift` 1 条偏差（与 T10-239 同一条） | 修复要 `gen-service-configs.py --write` + LaunchAgent 重载 = 机器级需授权；该检查 `ci_skip` ⇒ 不阻断 CI |
| `check-work-landed` 预存 `blocking=2` | 报的是别的会话的 run；本地浅检出下可达性判据无语义；ISC-6 明令不得为此登记债 |
| 3 处合法 host 字面量 | 改动 = 收窄脱敏用例的断言；已由反向钉住挡住 |
| `services.yaml` 里 B4b 本体的 host 字面量 + 43 个 plist / crontab | **机器级需逐批授权**，本轮只拆测试面 |
| registry 无 PATH/EnvironmentVariables 键 | 补 env 声明属 B4b 本体；本轮据此把测试的 host 组合面收敛到 3 处并钉死点数 |
