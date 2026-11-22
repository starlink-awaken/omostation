---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-22
type: report
bet_id: BET-Y2Q4-T10-347
title: BET-Y2Q4-T10-347 closeout — gac-bootstrap 层3/层4/层6 结构性空绿收口与 A 类谎报点名
---

# BET-Y2Q4-T10-347 收口收据

工程腿 = PR #5420 squash `aee01506c795b1772805c0e6604f87c8ed9d2901`（base `d67683a6c`，CI 16 pass / 2 skipping）。
准入腿 = PR #5291（`25fbb76ed` 入 main）：spec + 台账条目 + `accepted_specifications` 绑定。
主体判据（层3 普查 / 层4 全量路径 / 层6 平面覆盖 / B 类目录修正 / debt 条目）由并发会话的 #5297 `abaec3429`、
#5300 `3a9121809`（hook-runner 调用面）、#5305 `fb0ef6b06`（cron 已装机作业面）落地；本 BET 的增量是
**A 类判据 + 4 条变异钉 + 三处口径真实化**，不重发旧快照（旧快照覆盖上去会删掉两个已上线平面）。

本文件是 `completion-evidence-matrix/v1` 的 tests / diff / rollback / fresh_receipt / live_canary / cleanup 载体，
`replay` 载体是 `.omo/_knowledge/retros/BET-Y2Q4-T10-347.md`。

## 读数前置条件（不满足则整批读数无效）

| 条件 | 实测 |
|---|---|
| 检出形态 | 隔离 worktree `ws-t10347-leg2`，分支 base = `origin/main`，非共享主工作区 |
| runtime 平面来源 | `planes.runtime.policy_source = sgf`（需 `projects/ecos` 有真检出；只有 `.git` 时 `submodule update --init` 静默 no-op，要 `checkout --force HEAD -- .`） |
| 降级副本的后果 | `policy_source=default` 时五平面判定整批改口 `device_unavailable`，`violations` 不可当事实 |
| 取数 base | 下表全部在**合并后** main `aee01506c` 上重取；11-22 早段（base `e2c7d48bb`）的读数另行标注 |

## 实测读数

| 层 | 合并后 main `aee01506c` | 早段 base `e2c7d48bb` | 差值解释 |
|---|---|---|---|
| 层3 工具普查 | `total=326 alive=320 audited=326 instrument_dead=false` | 同 | 上游未动 `bin/gac/**` 普查面 |
| 层4 `source_ref` 存在性 | `rules=90 checked=75 missing_count=6 indexed_missing_count=0` | 同 | 缺席 6 条 = `CR-AGE-{BOS,POLICY,MEMORY,REPLAY,EVENT}-01` ×5 + `CR-L0-SSOT-PATH-NORM` |
| 层6 执行平面 | `surfaces=158 declared=148 reached=139 violations=9 dead_registered=1 manual_exempt=0 skipped=6` | `157/147/138/9/1/0/6` | 上游 #5417 新登记并接线 1 个 BOS 检查 ⇒ 三面各 +1，点名集不变 |
| 不变式 | `reached + violations == declared`（139+9=148）成立 | 成立 | 分母可读性 |
| `ok` | `true`、`blocking=false`、`advisory_gaps=true`、`rc=0` | 同 | 单点开关 = registry `CR-X2-GAC-BOOTSTRAP.enforcement`（当前 `advisory`，`review_before=2026-11-29`） |

层6 点名清单（9 条，`aee01506c`）：

```
declared_no_execution_plane ×8
  bin/gac/check-gate-detail-contract.py          ← 本 BET 立案的 A 类人证 1
  bin/gac/check-cron-interpreter-executability.py← 本 BET 立案的 A 类人证 2
  bin/gac/ci-local-fast.py
  bin/ssot/observability-events.py
  bin/gac/anomaly-detector.py                    ← cron 作业存在但 reality=declared_only
  bin/gac/alert-router.py                        ← 同上
  bin/gac/cross-domain-trend.py                  ← 同上
  bin/gac/predictive-governance.py               ← 同上
dead_tool_registered_as_executed ×1
  bin/gac/documents_domain_jobs.py               ← 层3 判死（无 __main__）但被平面文本提到
```

## done_when 逐条对账

| # | 判据 | 实测 | 判定 |
|---|---|---|---|
| AC-01 | 零分母不再为绿（`tools.total>300`，glob 退回单目录时层3 用例当场红并记红条数） | `total=326 audited=326`；变异 ⇒ `3 failed, 14 passed`（`test_l3_census_is_a_real_population_not_zero` + 两条依赖死清单的用例） | ✅ |
| AC-02 | 层4 覆盖全部路径型 `source_ref`；B 类 2 条改对后可达，余 6 条交 debt | `checked=75`（90 条规则内）；`test_l4_god_module_refs_now_point_at_the_real_file` 绿；`missing_count=6` 与 debt 交叉引用一致 | ✅ |
| AC-03 | 层6 点名两条 A 类且理由写明「五平面全缺席」；换文本正则时该用例红 | 两条均在点名清单（reason 含「五平面全缺席」）；变异「runtime 平面换正则扫源码」⇒ `2 failed, 15 passed` | ✅ |
| AC-03b | 层3 判死仍声称执行者另判 `dead_tool_registered_as_executed`、不计 `reached`；拆层3→层6 接线时生产路径用例红 | `dead_registered=1` ⇒ `documents_domain_jobs.py`；`reached=139` 已剔除；变异拆接线 ⇒ `1 failed, 16 passed`（只有生产路径钉红） | ✅ |
| AC-04 | 加宽的层不扩权：advisory 期 `make gac-local-gate` 不因本层红；仪器类失效恒红 | `enforcement=advisory` ⇒ `ok=true rc=0`；`test_advisory_switch_is_read_from_the_registry_rule` 绿（脚本内无常量/开关）；CI `gac-gate` pass | ✅ |
| AC-05 | 零回归，`tests/unit/test_gac_bootstrap_layers.py` 读数入收据 | `17 passed in 4.58s`（合并后 main）；无 skip ⇒ sgf 依赖用例真实执行 | ✅ |
| AC-06 | debt 登记成立且读数与收据一致 | `.omo/debt/items/GAC-BOOTSTRAP-REGISTERED-NO-EXECUTION-PLANE.yaml` `last_reviewed_at=2026-11-22`；`debt-integrity-check.py` ⇒ ✅ 90 条在册；条目内读数与本收据早段列一致，点名集合本次未变 | ✅ |
| AC-07 | 两条固化条目落地并被本 BET 自己造的门禁验过 | `DEFAULT_POLICY 不是执行平面` / `判据口径要与契约名同源` 各在 `AGENTS.md` §7 ×1、`docs/pitfalls.md` 正文 ×1；`check-pitfalls-index.py` ⇒ `total=56 dead=5`，5 条 DEAD 全在 L271/L274 的他人条目，本 BET 三条短语字面可命中 | ✅（`dead=5` 属他条预存，`blocking=false`，`enforce_after=2026-12-12`） |

## 判读要点

1. **canary（收据必带）**：`RUNTIME_PLANES 91 False False` —— runtime `GATES_LIST` 有 91 条，
   `check-gate-detail-contract` 与 `check-cron-interpreter-executability` 都不在里面（早段 base 是 90，
   上游 #5417 加了一条 ⇒ `N` 会漂，**判据是两个 `False`**，台账 expect 已按此订正）。这条证伪了「登记面说
   `triggers: [gac_local_gate]` 就有人在跑」。
2. **A 类的机制根因**：登记 `trigger: [gac_local_gate, per_pr]` 而工具名只出现在 `gac-local-gate.py` 的
   `DEFAULT_POLICY` 字面量里；本机 `load_sgf_policy()` 成功时 `POLICY = load_sgf_policy() or DEFAULT_POLICY`
   永不走 `DEFAULT_POLICY` 分支 ⇒ 「提到」是死字面量。同份检出 `check-ci-surfaces.py` 因
   `_local_gate_tools()`（:99）把 sgf-policy 与「正则扫全文」（:123）并集，仍报 `ok=true wired_tools=143`；
   两套口径的差值就是本层价值。统一口径归 `CI-SURFACES-GATE-FIELD-UNDEFINED`（本 BET 不动那个文件）。
3. **本轮自踩并当场补钉的假绿**：A 类判定写完 + 2 条用例后，把 `run_bootstrap` 里的接线拆掉 ⇒ 16/16 仍绿，
   因为新用例都直接调 `check_plane_coverage(dead)`。第 3 条用例改走生产路径（`run_bootstrap(as_json=True)`
   读 JSON）后同变异必红（AC-03b 读数）。**「判据写在函数签名上」不等于「判据被执行」**。
4. **不覆盖上游扩面**：11-11 的本地快照与 main 的层6 有 2 个平面之差（hook-runner / cron），
   整文件替换即回退；只打 delta，diff 前后各测一次。

## rollback

- 单点回退：`git revert aee01506c795b1772805c0e6604f87c8ed9d2901`（含 A 类判定、3 条用例、三处口径订正）。
- 局部降级：把 `.omo/_truth/registry/governance-checks.yaml::CR-X2-GAC-BOOTSTRAP.enforcement` 保持 `advisory`
  即可让新层只点名不改退出码（当前即此态）；`dead_registered` 只影响层6 的 `violations`，不影响层3/层4 计数。
- 数据面无迁移、无删除：本 BET 未撤任何 `ci-surfaces.yaml` 登记、未删任何规则、未改 `DEFAULT_POLICY`。

## operational 轴

| 项 | 载体 |
|---|---|
| live_canary | 本文件「判读要点」第 1 条（`RUNTIME_PLANES 91 False False`）+ 层6 点名清单实机输出 |
| fresh_receipt | 本文件（读数全部在合并后 main `aee01506c` 的隔离 worktree 上重取，2026-11-22） |
| replay | `.omo/_knowledge/retros/BET-Y2Q4-T10-347.md`（含四组变异的装置侧成本与两次踩坑复现路径） |
| cleanup | `gac-worktree.sh release t10347-leg2` 释放工程腿 worktree；未 init 的 `projects/runtime`、`projects/knowledge/kairon` 已按 pin 补到 detached HEAD（pre-push `submodule-sync` 由 `failed=2` 转 skip）；无遗留 `.omo/_delivery/**` 之外的临时物（affected-graph 收据在 gitignore 面内） |

## value 轴（不宣称）

`value_indicator_policy: false`。本轮只证明「仪器能点名 + 分母可读」：9 条点名 + 1 条谎报**无人认领、未接线**，
`CR-X2-GAC-BOOTSTRAP` 仍 advisory，层3 判死 6 条里 `gac_severity.py` / `test_agent_clone.py` 之类究竟是库还是漏入口
也未裁定。价值需等 debt 收敛 + 转阻断后另案评估。
