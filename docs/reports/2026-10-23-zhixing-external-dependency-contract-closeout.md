---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-23
bet_id: BET-Y2Q4-T10-267
---

# BET-Y2Q4-T10-267 收口 receipt — Zhixing 外部依赖契约三件套成型

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-267`
规格：`docs/superpowers/specs/2026-10-23-zhixing-external-dependency-contract.md`（spec_version 1.0.0，
digest `sha256:97d888760ac344c062dfad2dcd6171a6220996398c240009e8dd59a19011bd1a`；在合并 commit
`51c9ed62e` 上 `git show 51c9ed62e:<path> | shasum -a 256` 复算，与台账
`accepted_specifications[0].content_digest` 逐字一致）
run：`20261023T081416Z-project-code-change-4387ba78`（workflow `project-code-change`）
交付：**工程腿** PR #4879 squash 为 `51c9ed62e8dde955e73f9158df380a6411650439`
（GitHub `mergedAt 2026-10-23T09:40:50Z`；25 条检查 0 失败；push 前 L3 深度安全评审 `findings_count 0`）

## 1 这一轮改了什么（一句话）

ADR-0456 决策 5 承诺的三件套（registry 条目锁 repo+SHA、`ZHIXING_DASHBOARD_ROOT`、`check-signals`
的 `/health` 探针）从四处散文变成**有代码消费点、有登记表字段、有守卫用例**的对象，并且判定路径
按构造拿不到 `pinned_sha`。

三个 lane / 三个 commit：

| Lane | 文件 | 内容 |
|------|------|------|
| docs | spec + `docs/plans/3y-bet-ledger.yaml` | 契约条目 + 台账（含 spec 绑定；`done_when` / `verify` 两处按实测改写） |
| governance_state | `.omo/_truth/registry/external-write-roots.yaml` | zhixing 条目 +5 个 **optional** 键（`repo` / `pinned_sha` / `root_env` / `health.env` / `health.path`），其余条目零破坏 |
| code | `bin/lib/repo_root.py` + `bin/ops/cli.py` + `tests/unit/test_zhixing_external_root_contract.py` | `external_root(id)` 定位器 + observe-only `/health` 分类面 + 28 例守卫 |

## 2 done_when 六条的实测读数

| # | 条款 | 读数 |
|---|------|------|
| 1 | registry 四键齐 + `health.env` 在 port-registry 反查存在 | verify-2 `['health', 'pinned_sha', 'repo']`；`test_healthy_env_names_are_registered_in_port_registry` 断言 `used` 非空且 `used ⊆ env_vars.values()` |
| 2 | `external_root()` 三条解析序各一条断言 | `test_external_root_prefers_env_named_by_the_registry` / `test_external_root_expands_tilde_from_registry` / `test_external_root_returns_none_when_not_placed`；本机实调 `external_root('zhixing-dashboard') → /Users/xiamingxing/.local/share/zhixing-dashboard`，且同进程 `'yaml' in sys.modules` 为 **False**（本模块不得 import yaml 的约束未被破坏） |
| 3 | `check-signals --json` 含 `health_checks` 且 zhixing 分类 `ok` | verify-1 `drifts 0 health [('zhixing-dashboard', 'ok')]`；真实 `/health` 同步读数 `code_drift=False`、`projection_status=BOUND_FRESH`、`dashboard_code_oid=e021642b37cac2f6784d1d207b36dba62a66a2ee` |
| 4 | 缺省声明下 drifts 与 exit code 与改前逐字节等价 | 改前（主区 `3f65a7a11`，无 health 面）`drifts 0` rc=0；改后 `drifts 0` rc=0；真实 registry 里没有任何条目声明 `require_health`（`test_real_registry_zhixing_entry_carries_the_three_contract_keys` 断言 `"require_health" not in entry`）；`test_default_readings_keep_drift_plane_empty` 三面（ok / unreachable / 无 env）均 `_health_drifts(...) == []` |
| 5 | `pinned_sha` 不进判定路径（两台装置 + 变异） | 见 §3、§4 |
| 6 | 28 例全绿 + hermetic 复跑全绿 | 正常面 28 passed；hermetic（`HOME=<空目录>` + `uv run --no-project --python 3.12 --with pytest --with pytest-timeout --with pyyaml`）28 passed；探针只断言 `fake_urlopen` 记录的 `url`/`timeout`，`test_probe_folds_any_exception_into_undetermined` 保证任何异常都折成 `undetermined` 而不外逃 |

## 3 两处验收装置按实测改写（不是放宽判据）

**（a）done_when-5 原措辞不可达。** 原文写「`git grep -w pinned_sha -- bin/` 除 registry 校验语境外零判定
读取点」。实测 `bin/` 有 **13 处 / 4 个文件**读 `pinned_sha`：`bin/gac/agent-clone.py`、`bin/gac/clone-lifecycle.py`、
`bin/gac/test_agent_clone.py`、`bin/_archive/obsolete_tests/test_agent_clone.py`（上一行的归档副本）
—— 读的是**子模块 gitlink** 概念，与本契约无关。零命中这条判据在原措辞下**按构造不可能满足**，而把它
悄悄删掉就是放宽。

交付的是两台**不共享失效模式**的装置：

1. `test_no_registry_consumer_reads_pinned_sha`：消费者面由 registry 自己的**文件名**（`external-write-roots`）
   导出，扫 `bin/` + `projects/omo/src/`，AST 判 `Constant == "pinned_sha"` 或 `Attribute .attr == "pinned_sha"`；
   同一用例先断言消费者集合**确实含** `bin/lib/repo_root.py` 与 `bin/ops/cli.py`（防「面为空所以绿」），
   再断言零命中。
2. `test_repo_wide_pinned_sha_sites_are_the_reviewed_gitlink_list`：全 `bin/` 读 `pinned_sha` 的**文件集合**与
   被评审的 4 个 gitlink 站点 `frozenset` **集合相等**，且断言这 4 个文件都不引用该 registry。
3. `test_pinned_sha_detector_is_not_a_no_op`：合成违规（真比较）必须命中行 `[3]`；只在 docstring / 注释里
   出现字面量必须不命中；旁观文件必须不命中（AGENTS.md §7② 「检测器必须自证」）。

**（b）verify-1 原措辞不可复现。** 原命令假设 `ZHIXING_OBSERVATORY_PORT` 已被导出。实测全机没有任何
rc 文件、`.githooks`、`bin/` 脚本或 `runtime/cron` 导出它，裸跑只会得 `undetermined` —— 那是**装置没搭对**，
不是服务不健康。端口改由 `protocols/port-registry.yaml` 的 `env_vars` 反查。

第二个坑是解释器：`bash -lc` 下裸 `python3` = `/usr/bin/python3` **3.9.6**，而 `bin/ops/cli.py:21` 是
`from datetime import UTC, datetime, timezone`，3.9 下当场 `ImportError`；同一命令在 zsh 交互下是
homebrew **3.15**，绿。这是 AGENTS.md §7「同一判据换装置读数不同 ⇒ 判据要写明用哪个二进制」的又一实例。
verify-1 现用 `uv run --no-project --python 3.12`（实测 `bash -lc` 下解析为 3.12.13，与登录 shell 无关）。
三条 verify 现在都在**最坏那个 shell**（`bash -lc`）里 rc=0。

## 4 变异对照（按改法分别记读数，不合并成一个数字）

基线：28 passed，rc=0。每例改一处实现 → 跑同一文件 → 逐字节还原并校验 sha 相等（`restored: True`）。

| 变异 | 改法 | failed | 点名用例 |
|------|------|--------|----------|
| M-a1 | `external_root` 丢掉 env 覆盖，只走 registry path | **2** | `test_external_root_prefers_env_named_by_the_registry`、`test_env_override_worthless_when_target_absent` |
| M-a2 | `external_root` 去掉 `is_dir()` 判在 | **2** | `test_env_override_worthless_when_target_absent`、`test_external_root_returns_none_when_not_placed` |
| M-b | 缩进手解放宽到任意缩进 | **3** | `test_health_path_is_not_parsed_as_root_path`、`test_indent_parser_is_not_a_no_op`、`test_real_registry_zhixing_entry_carries_the_three_contract_keys` |
| M-c | `_health_drifts` 丢掉 `required` 过滤 | **3** | `test_probe_self_reported_code_drift`、`test_default_readings_keep_drift_plane_empty`、`test_probe_folds_any_exception_into_undetermined` |
| M-d | 探针不再拒非布尔 `require_health` | **1** | `test_probe_require_health_validation_shapes` |
| M-e | 探针不再校验端口 env 已声明且为数字 | **3** | `test_probe_absent_port_env_is_undetermined`、`test_probe_non_numeric_port_env_is_undetermined`、`test_default_readings_keep_drift_plane_empty` |

`pinned_sha` 那条由 suite 内的正面变异钉住：`test_pinned_sha_mutation_leaves_classification_untouched`
注入两个不同 `pinned_sha`（含全零 `"0"*40`），探针分类逐字节相同。

## 5 本地门禁与已知噪声

- `make gac-local-gate`：`GaC local gate: FAIL | 2 SOFT WARN`（rc=2，**零 hard error**）。两条都与本 diff 无关：
  1. `current-state-coherence :: missing input: <worktree>/.omo/state/system.yaml` —— T10-235 摘库后
     「干净检出里没有这份文件」是**常态而不是回归**（AGENTS.md §7）。
  2. `governance-semantic: agent-workflow-status: active_runs=1` —— 本 run 在 closeout 前必然 active。
- `bin-quota-diff --base origin/main` PASS（未新增 `bin/` 脚本）。
- 邻近套件（本轮改动真正可能被影响的面：`test_repo_root_profile.py` / `test_projection_reader_resolution.py`
  / `test_system_yaml_write_plane.py` / `test_system_yaml_consumer_inputs.py` + 本契约 28 例）在同一最小
  venv 下 **955 passed / 0 failed**。
- `tests/unit/test_b1_ledger_call_time.py` 读 **43 passed / 1 failed**（`test_measure_value_truth_run_uses_the_db_declared_after_import`，
  断言 `report["status"] == "not_ready"`，实得 `{'status': 'unprovable', 'reason': 'observer_unavailable'}`）。
  **判为预存且属装置面**，两条证据：① 同一命令在未含本轮改动的 `3f65a7a11` 上是**同一行、同一读数**；
  ② 补 `--with pydantic` + `PYTHONPATH=projects/omo/src:projects/ecos/src` 后 44 全绿 —— 即红的是最小 venv 的
  **依赖面**，不是被测代码；`north_star_meter_v2` 把自己的观测器 import 失败折成了 `unprovable`（AGENTS.md §7⑨
  的同形：把「坏了」折叠成另一种状态，于是两种原因在输出里分不开）。**本轮未修它**，因为它与 T267 无关且
  修它要改的是 meter 的折叠语义 —— 那属于另一次准入。
- `tests/unit/**` 不在 `governance-check.yml:118-127` 的 pytest 白名单里 ⇒ 这 28 例的**本地运行是唯一证据**，
  CI 绿不构成它们的证据。

## 6 回滚

单 PR squash commit，回滚 = `git revert 51c9ed62e`（registry 的 5 个键全 optional，缺 `health` 的条目不进
探针面；`external_root()` 是新符号，无既有调用者；`check-signals` 的 health 面是附加键，`drifts` 与
exit code 语义未变）。无机器侧动作 —— 本轮**没有**改 plist、launchd、crontab 或 `services.yaml`。

## 7 边界（不在本轮，逐批授权）

- `services.yaml` 里那 12 处直指 `~/.local/share/zhixing-dashboard` 的字面量收口 —— 属 B4b 批次 2+（任务 #91）。
- 生产 UI 脱离 vite（任务 #86）、G8 morning-brief 装机（任务 #97）、安装位追平（任务 #143）都未被本轮触碰。
- 本契约只把「外部依赖有没有健康声明」变成可见对象，**没有**把 zhixing 的服务纳入本仓调度，也不构成
  ADR-0456 任何阶段（B1/B3/B4/B4b/B5）的完成宣告。
