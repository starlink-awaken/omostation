---
type: report
status: completed
owner: governance-team
last-reviewed: 2026-10-20
bet_id: BET-Y2Q4-T10-261
title: BET-Y2Q4-T10-261 closeout — 跨安装位 import 错包的启动断言与检出钉面可观测化
---

# BET-Y2Q4-T10-261 closeout — 「这次跑的是哪份码」第一次成为一个能读出来的量

交付物：`docs/superpowers/specs/2026-10-20-import-root-startup-assertion.md`
（spec_version 1.0.0，content_digest `sha256:c3da49c055a5cb02ad3289b1c68506aa855d5e267407e926b585c2e17c4bf09e`
—— 与台账 `accepted_specifications[0]` 逐字节相同，本轮未改 spec 正文）
台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-261`
PR：#4835 —— squash 合并为 `79e2b99309f3d7026f5e45619d39a4863786fe79`
CI 终态：22 项检查 = 20 pass / 2 skipping（`Documents domain projects`、`doc-freshness` 按 `on.paths` 过滤）/ 0 fail
Run：交付腿 `20261020T062827Z-project-code-change-f36673d8`（workflow `project-code-change`，
work_packet_hash `sha256:9bed6fa0ad17f2e917f9b5fd5595b802367fd7dadfd7456969bab63c729c7a86`，已 `close --status ok`）；
本收口腿 `20261020T072009Z-project-doc-change-badd841c`（workflow `project-doc-change`，
work_packet_hash `sha256:b8c0f6ac8c01165d646002767616bb48437097fee1bf9a0af8a1a59208e595d1`）。
两 run 并存的原因：本腿把 `write_surfaces` 从 4 面补到 6 面（加 retro 与本 receipt），那是 packet **投影**字段，
旧 run 的 claim 一律 `WORK_PACKET_SOURCE_DRIFT`；`refresh-packet` 在本仓不可用（T10-259 已记），
所以按同一先例用新 run 承接。`status` / `done_at` / `completion_evidence` 不在投影里，故本腿照常回填。

## 1 基线 — 改之前是什么

| 量 | 基线读数（`origin/main@f13ef01c3`，即本分支的 base） |
|---|---|
| `bin/lib/repo_root.py` 里 `assert_import_root` / `import_root_report` 命中 | **0**（两条名字不存在，ADR-0456 Consequences `:246—247` 记的缓解未交付） |
| `bin/lib/repo_root.py` 行数 | 306 |
| 「这次跑的到底是哪个检出的码」 | 只能靠人肉 `python -c 'import omo; print(omo.__file__)'`；`roots_report()` 无此面 |
| 装置侧真实形状（本轮实测） | 39 条 `.pth` 分布在 14 个 venv，把导入根钉在 `/Users/xiamingxing/Workspace/…`；`omo.__file__` 从 `/tmp` 也解析到 canonical 检出；新 claim 的 worktree 里没有 `projects/omo/.venv` |

## 2 diff — 交付腿四个文件

| 文件 | numstat | 内容 |
|---|---|---|
| `bin/lib/repo_root.py` | `118/0` | `IMPORT_PROBE_ENV = "OMOSTATION_IMPORT_PROBE_MODULE"`（`:60`）、`class ImportRootMismatch(ValueError)`（`:129`）、`import_root_report()`（`:140`）、`assert_import_root()`（`:177`）、`_probe_module_file()`（`:202`）、`_import_root_observation()`（`:224`）、`roots_report()["import_root"]`（`:360` 起）、`__all__` +4 名。**`main()`（`:382`）函数体逐字未改** |
| `tests/unit/test_repo_root_import_root_assertion.py` | `372/0` | 17 个测试函数 / 24 条用例（参数化） |
| `docs/superpowers/specs/2026-10-20-import-root-startup-assertion.md` | `120/0` | C1—C4 契约、G1—G3 判据、§4 五条验收、§5 非目标 |
| `docs/plans/3y-bet-ledger.yaml` | `86/1` | 新条目 + spec binding + `total_bets: 554 → 555` |

合计 **696 insertions / 1 deletion**（`git show --numstat 79e2b9930` 累加实测）。分支内四个单 lane commit：
`bd6160068` docs(governance) → `33fa256bb` chore(ledger) → `2f662d7ae` feat(governance) → `1bb50a69c` fix(ledger)。

`1bb50a69c` 是**本轮唯一一处自纠**：`verify[0].cmd` 原写 `--with pytest --with pyyaml`，在最小 venv 下按字面跑不起来
—— 根 `pyproject.toml` 的 addopts 注入 `--timeout=300 --timeout-method=signal`，而该 venv 没有 pytest-timeout，
pytest 当场 `unrecognized arguments`。补 `--with pytest-timeout` 后按台账字面重跑（见 §3）。
AGENTS.md §7「验收条款先实证通道行为」的同族：**想象中的通道行为写进验收 = 埋假绿**（这条 cmd 从写下到被真正执行过，隔了一次交付）。

## 3 tests — 基线 → 终态，同一 worktree、同一装置

台账 `verify[0].cmd` 按字面执行（hermetic：`env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT HOME=/tmp/emptyhome`）：

```
uv run --no-project --with pytest --with pytest-timeout --with pyyaml python -m pytest
  tests/unit/test_repo_root_import_root_assertion.py tests/unit/test_repo_root_profile.py -q -p no:randomly
→ 895 passed
```

四文件同装置扩面读数：`957 passed / 6 failed`。那 6 条**不是本轮引入**，用同装置换被测对象证明：
把 `bin/lib/repo_root.py` 换成基线版本（sha256 前 16 位 `37c5b27469394c68`，即 `f13ef01c3` 那份）单跑那两个邻居文件
⇒ `6 failed, 62 passed`，**失败函数名逐字相同**（`test_measure_value_truth_run_uses_the_db_declared_after_import`、
`test_scan_loads_the_real_omo_surface`、`test_state_reached_families_are_the_declared_set`、
`test_resident_inline_bare_writers_are_the_deferred_list`、`test_exact_root_split_pairs_are_the_reviewed_list`、
`test_caller_class_anchors_are_checkout_anchored`）。随后 `git checkout --` 还原，还原后 sha256
`a79c6165e02ca035` 与换出前逐字节相同。

装置纪律（AGENTS.md §7 hermetic 条）：这条复跑**不能**用宿主解释器 —— `HOME=<空>` 会同时摘掉装在 user-site 的
pytest；依赖面由 `uv run --no-project --with …` 供给。基线/终态两次读数都在同一 venv 形状下产生。

## 4 判据逐条对照

| 判据 | 读数 | 出处 |
|---|---|---|
| G1 ① 正向 | 返回解析后的 root 且不抛，`report["under"] is True` | `test_g1_positive_returns_the_confirmed_root`（`:58`） |
| G1 ② 反向 | 抛 `ImportRootMismatch`，消息同时含两侧绝对路径与 `.pth` 提示 | `:66` |
| G1 ③ 判不了 | 空串 / 空白 / 相对路径 ⇒ 一律抛且消息含「无从判定」；`report` 面 `under is None` | `:79` |
| G1 ③′ C1/C2 不对称 | `assert_import_root(None)` **抛**（无隐式探针对象），`import_root_report(None)` **自探 `repo_root.__file__` 并给布尔** —— 这是 spec C2 的措辞，不是缺陷 | `:93` |
| G1 ④-a 变异对照 | 把 `try/relative_to` 折成 `under = True` ⇒ 反向用例当场失守；用例先断言 `mutated != source`（装置没命中就不算证据） | `:115` |
| G1 ④-b 变异对照 | 撤掉两条输入守卫并折成 `return base` ⇒ 边界用例 ③ 当场失守；先断言 `source.count(guards) == 1` | `:134` |
| G1 ④-c 变异对照 | 把「判不了」的 `under: None` 改成 `False` ⇒ 折叠面用例当场失守（「判不了」与「判了且没问题」必须可分） | `:163` |
| G2 两面同批 | 跨根对（M2 形状）与同根对（M4 形状）由同一次扫描产出，键集相等 `{expected_root, module_file, under, ok}` | `:182` |
| G2 自探 | `import_root_report()`（不带参）`under is True` 且 `module_file == repo_root.__file__` | `:195` |
| C3 未设探针 | `roots_report()["import_root"]["probed"] is False` 且 `ok is not True`、`under is None` —— **缺席不等于 OK** | `:205` |
| C3 设探针 | CLI `--json` 下 `probed=true` 且 `ok` 为布尔；根内 ⇒ `under=true`，根外 ⇒ `under=false` | `:217` |
| C3 不可解析探针 | 模块名既不是文件也不是可定位 spec ⇒ `under=None`、`ok=False`，不得报 `ok=True` | `:241` |
| C4 观测不改退出码 | 三种探针（未设 / 根外 / 不可解析）下 `repo_root.py --json` 恒 rc=0；`main()` 恒 `return 0`；函数体与 `origin/main` **逐字节相等** | `:253` |
| G3 不被误认成根解析器 | 零参哨兵探测：`{state_root, event_ledger_path} ⊆ resolvers`、两条新名 `∩ resolvers = ∅`、`assert_import_root()` 必填参数 ⇒ `TypeError` | `:314` |
| G3 不被误认成检出定位器 | AST 重算定位器五谓词 ⇒ 通过集仍 `{"canonical_root"}` | `:324` |
| G3 诊断面不抛 | `HOME=<空>` + 剥三个 profile env 的子进程里，空/None/相对三种输入的 `import_root_report` 全部返回而不抛 | `:354` |

真机 M2 捕获（不是合成树）：canonical venv 的 `omo.__file__` 对**本 worktree root** ⇒ `under=false`；
对 **canonical root** ⇒ `under=true`。同一条判据两侧都过，才算 M2/M4 两面同批。

## 5 运行面零效应 — 正向读数，不是「我没执行写操作」的意图

| 量 | 改前 = 改后 |
|---|---|
| `crontab -l` 内容 | 67 行，sha256 前 16 位 `cbf14ddc2fdd972a` |
| `~/Library/LaunchAgents/*.plist` 总数 | 77 |
| 其中含 `import-root` 的 label | 0 |

台账 `verify[3]` 的那条 python heredoc 即为此而写（本机 `ls`/`grep` 是别名、零匹配会断链）。
本轮 `git diff --name-only origin/main..HEAD` 不含 `.omo/state/**`、`BRIEF.md`、子模块 gitlink。

## 6 安全审查

交付腿（三 commit）与本腿前置的单 commit 各过一次 L3 深度安全审查，`findings_count: 0`。

## 7 未做与遗留（不在本轮范围内，逐条写明归属）

1. **硬断言未接进任何常驻入口**。`assert_import_root()` 目前只有调用方测试与被 `roots_report()` 消费的观测面。
   接线的前置顺序与理由记在 spec §1：常驻入口一旦 crash-loop，就把 B4b 批次 2 的改道变成了保险丝，
   而改道是逐批授权面（task #91）。**接线轮不属于这一轮。**
2. **39 条 `.pth` 检出钉一条未修**。它们是各 venv 的 editable 安装产物；重建属运维动作，且
   「谁该指向哪棵树」取决于 B4b 的最终拓扑（spec §5 非目标）。本轮只让这件事**可观测**。
3. **`tests/unit/**` 不在 CI 的 pytest 白名单**（`.github/workflows/governance-check.yml:118` 起是显式文件白名单）。
   ⇒ 本文件那 24 条用例的绿**只有本地证据**，「CI 绿」不构成它们的证据。扩白名单是独立问题，不在本 BET 内动。
4. **6 条邻居用例预存红**（§3 已证明与本轮无关），其中 5 条属 resident write-plane 判据清单，另 1 条属 ledger 调用时刻探针。
5. **不宣布 ADR-0456 B1/B3/B4/B5 或整个 plan 完成。** 台账 `done` 只代表这条缝交付完。

## 8 回滚

单 squash commit，回滚面干净：`git revert 79e2b99309f3d7026f5e45619d39a4863786fe79`
= 删两条新文件（用例 + spec）、`repo_root.py` 回到 306 行、台账条目移除。
`main()` 与 `roots_report()` 其余键逐字未动 ⇒ 现有调用方零行为变化；运行面无任何依赖本轮产物的对象
（无新 env 被 plist/cron 读取，探针 env 未设时观测面固定 `probed=false`）。

## 9 清理

- affected-graph receipt 落 `runtime/affected/`（真实目录，不落 symlink 桥），用后即删、不进 commit。
- 交付腿 worktree `ws-t10-261-import-root-assert` 与 13 个 PASW 子 worktree 由 `gac-worktree.sh merge` 释放；
  本腿 worktree 在第二个 PR 合并后释放。
- `/tmp/emptyhome`、`/tmp/t261-*` 为一次性装置，不在仓内。
