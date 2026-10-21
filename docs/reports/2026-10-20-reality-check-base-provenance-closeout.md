---
type: report
owner: governance-agent
bet_id: BET-Y2Q4-T10-262
last_updated: 2026-10-21
last-reviewed: 2026-10-21
lifecycle: record
status: completed
---

# BET-Y2Q4-T10-262 收口 receipt — `--reality-check` 自报测量基座

交付 = PR **#4847** squash-merge 为 **`00cc8bb35e33c48cd6fc2b7653fb6f45d5754b1f`**
(受控后继；前代 #4843 因 GitHub 冻结 merge ref 无法靠 rerun 复绿，已标 superseded 关闭)。
本轮全部读数在合并后的 `origin/main`(= `00cc8bb35`) 上于隔离检出
`/Users/xiamingxing/ws-t10-262-closeout` 复测。

## 1 · 交付面（4 文件，与台账 write_surfaces 逐字一致）

| 文件 | 变化 |
|---|---|
| `bin/mof/gen-service-configs.py` | `measured_base()` (`:466`) + `reality_check()` 接线 (`:540`) + 输出键 (`:648`) + `--reality-check` 呈现 (`:670`) |
| `tests/test_service_registry_reality.py` | +262 行，15 条新用例 (`:455`–`:663`) |
| `docs/superpowers/specs/2026-10-20-launchd-reality-check-base-provenance.md` | 契约与 6 项 done_when |
| `docs/plans/3y-bet-ledger.yaml` | 本 BET 条目定稿（+75/−1） |

`git diff --name-only origin/main..HEAD` 只含上述面；不含 `.omo/state/**`、`BRIEF.md`、子模块 gitlink。

## 2 · done_when → 证据映射（逐条有名字，不靠"全绿"概括）

| done_when | 钉住它的用例 | 本机实测 |
|---|---|---|
| 1 返回值含 `measured_base`，六字段齐 | `test_measured_base_has_exactly_the_six_contract_fields:455` | 实跑输出 `sorted(keys)` = `['base_state','behind_count','head','origin_main','registry_file','registry_sha256']` |
| 2 `base_state` 四值枚举；ref 不可解析一律 `unknown`，不折算成 `equal` | `:576` `:586` `:604` `:617` `:663` | 实跑 `base_state=equal`（head==origin_main==`00cc8bb35`）；不可证侧 `:663` 绿 |
| 3 零判定效应由同一次调用对照证明 | `test_measured_base_is_purely_observational:465` | 实跑 `findings_total=3`，其中提及 `measured_base` 的 = **0**；`ok` 只由 E1—E5 决定 |
| 4 假债可指认（少 N 条登记的旧注册表 vs 完整注册表） | `test_stale_base_and_full_base_are_distinguishable_from_output_alone:491` | 用例侧 `e2` 1 vs 0 且 `registry_sha256` 不同；本机侧见 §3 两条不同 sha |
| 5 非 git 测量根不抛 | `test_non_git_root_reports_nulls_not_an_error:548` | 绿；`head/origin_main/behind_count = null`，`base_state=unknown`，`ok` 不变 |
| 6 `registry_file` 相对呈现，输出面不含 `/Users/` | `test_registry_file_is_reported_relative_to_the_root:563` | 实跑 `'registry_file': '.omo/_truth/registry/services.yaml'`；`'/Users/' in output` = **False** |
| 7 变异对照：两侧注册表内容改成一致 ⇒ 该用例当场红 | 本轮现场执行 | `old_base = _write_registry(tmp_path, full, …)` 后 `1 failed` @ `:509`（`assert (0 == 1)`）；随即 `git checkout --` 还原并复跑 **32 passed** |

## 3 · 台账 verify 三条的原样读数

```
uv run --no-project --with pytest --with pyyaml --with pytest-timeout --with pytest-randomly \
  python -m pytest tests/test_service_registry_reality.py -q -p no:randomly
→ 32 passed in 3.08s

python3 bin/mof/gen-service-configs.py --reality-check --json
→ measured_base 六键齐; head=origin_main=00cc8bb35; base_state=equal; behind_count=0
→ registry_sha256=45f56048eb74…; e2_undeclared=0; owned_declared=47; owned_installed=47
→ findings=3 (E4 未分区 19 条 · E5 enabled-missing com.l4.omo.sync · E5 disabled-residual
  com.cockpit.dashboard); ok=False; rc=1
```

装置补记（不是改窄断言）：台账里原样 `--with pytest --with pyyaml` 在本机 `rc≠0`，因为
`pyproject.toml` 的 addopts 注入 `--timeout=300` 而最小 venv 无 `pytest-timeout` 插件；
补 `--with pytest-timeout --with pytest-randomly` 后为上述读数。

`ok=False` 的三条 finding 是 **改前既存的署名准入面**（E4 19 条见 BET-Y2Q4-T10-259 评审清单，
E5 2 条属 Principal 决策面），本轮按 non_goal 逐条未回填 —— 这正是 done_when-3 要证的
「基座字段对判定零贡献」：`measured_base` 换了值，finding 条数与 `ok` 一字不变。

## 4 · 一处必须留案的自我矛盾（non_goal 1 vs 收口链）

本条目 `non_goals` 第一条写着「不调 `bin/gac/sync-main.sh`、**不 fetch**、不 `reset --hard`」，
而立此条的动机是同段的「主工作区本地 main 落后是运维事实，处置权属 Principal」。但
`bin/plan/bet-ledger.py:1682` 要求 `engineering.merged_reachable_commit` 在**本地对象库可达**，
squash-merge 的对象只在服务端生成 ⇒ 收口链（bet-closeout-chain 步 4）本身就要求一次 fetch。

实际处置与其边界：只执行 `git fetch origin main`（隔离检出内，一次 `SSL_ERROR_SYSCALL` 后重试成功），
它写的是 object store 与 `refs/remotes/origin/main`；**没有任何检出被移动** ——
`/Users/xiamingxing/Workspace` 的 `main` 仍在 `fdb106c9f` 且逐字节未动，non_goal 想保护的那件事
（不替 Principal 同步规范工作区） intact。留案结论：这两条在本 BET 内**不可能同时满足**，
应把 non_goal 1 改写为「不动任何检出的工作树/HEAD」，而不是靠下次悄悄违反它。

## 5 · 判读要点：git 事实跟着注册表走，不跟着 `root` 走

`measured_base()` 的 docstring 与 `test_git_facts_follow_the_registry_tree_not_the_passed_root:640`
钉死了这个设计：HEAD 取 `git rev-parse --show-toplevel`（自 `registry_path.parent` 上溯），
不是取传入的 `root`。因由写在正文里 —— 在 worktree 里跑 CLI 时 `workspace()`/`canonical_root()`
解析到规范检出（本机 = `fdb106c9f`），拿它的 HEAD 去标注 worktree 的注册表就是**假证词**；
本轮实测两侧确实不同根（`canonical_root()` = `/Users/xiamingxing/Workspace`，
而 `measured_base.head` = `00cc8bb35` = 注册表所在检出），这恰好是 desired 行为而不是缺陷。
证不出树时给 `unknown`，不退回任何猜测的根（`:663`）。

## 6 · 未做（按 non_goals，逐条如实）

不宣布 ADR-0456 B1/B3/B4/B5 或整个 plan 完成；不动 launchd/plist/crontab/`~/Library/LaunchAgents`；
不改 `services.yaml` 任何条目与 `workspace_prefixes`/`exempt_labels`/E1—E5 判据本体；
不回填 E4 19 条与 E5 2 条；不把 `--reality-check` 注册进 `ci-surfaces.yaml`/`governance-checks.yaml`；
不动 `script_baseline`。
