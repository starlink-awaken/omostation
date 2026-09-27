---
schema: md/v1
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-27
type: report
bet_id: BET-Y2Q4-T10-206
title: BET-Y2Q4-T10-206 服务注册现实收口 — closeout receipt
created: '2026-09-27'
run_id: 20260927T023016Z-project-code-change-5d97bbaa
---

# BET-Y2Q4-T10-206 closeout receipt — ADR-0456 B3

> 本文件是 ledger `completion_evidence` 指向的 receipt。所有数值为 closeout wave 撰写时点
> （2026-09-27T04:14–04:16Z）在合并后的 main 内容上**重新实测**，非复述交付期数字。
> 契约定义见 `docs/superpowers/specs/2026-09-27-service-registry-reality-closure.md`。
> 复盘（含台账自纠错条目）见 `.omo/_knowledge/retros/BET-Y2Q4-T10-206.md`。

## 1. 交付物

| 项 | 值 |
|---|---|
| 主仓 PR | #4421（`state: MERGED`，`mergedAt 2026-09-27T03:56:37Z`） |
| 主仓 merge commit | `02f4dfee3446757884562be83001f518408fc0bd` |
| merge commit 触及文件 | **恰好 6 个**（`git show --name-only 02f4dfee3`）：`bin/mof/gen-service-configs.py`、`tests/test_service_registry_reality.py`、`Makefile`、`.omo/_truth/registry/services.yaml`、`docs/plans/3y-bet-ledger.yaml`、`docs/superpowers/specs/2026-09-27-service-registry-reality-closure.md` — 无生成态、无子模块 gitlink |
| 分支 commit（按 change-lane 拆分） | `83a5e457e` code（门禁 + 测试 + Makefile）/ `da2a4b702` registry（30 条回填 + 分区表）/ `3c73c08cf` docs_data（台账绑定）/ `aed4fbfad` docs(spec) / `adb494a35` docs+docs_data（spec `owner` frontmatter + 同 commit 重算 digest）/ `e3990dbff` docs_data（台账 `done_when`/`verify` 与实测口径对齐） |
| 契约 spec | `docs/superpowers/specs/2026-09-27-service-registry-reality-closure.md`，`spec_version 1.0.0`，digest `sha256:50d4ef53508f8ae3f61206d3f7c35d75af4c506ddad7621693e668d5e329471f`；closeout 时点复核 `git show origin/main:<spec> \| shasum -a 256` == 台账 `content_digest` == 工作树文件三者一致 |
| 门禁 | `bin/mof/gen-service-configs.py --reality-check`（新增模式，`--json` 输出 18 键）：E1 registry→plist 字节漂移继承、E2 **owned 分区** installed⊆declared 等式、E3 严格 XML 良构债报告、E4 dev label 前缀不侵入；枚举走 `/usr/bin/plutil -convert json` |
| 归属分区 SSOT | `.omo/_truth/registry/services.yaml` 的 `launchd_namespace`（与 `services:` **同一 YAML 文档**）：`workspace_prefixes` 11 条点段前缀、`exempt_labels` 7 条（3 `external` + 4 `unclassified`，逐条带实测 reason）、`dev_label_prefix: com.omostation.dev.` |
| 回填 | 30 条 observe-only 服务条目，`+641 / -0` 行（`git diff --numstat 02f4dfee3^1 02f4dfee3`）；每条 `generate: false` + `label/scheduler/trigger/enabled/program/outputs/config_source/content_digest/notes` |
| 测试 | `tests/test_service_registry_reality.py` 新增 16 用例（含 9 个"必须变红"的负例，见 §3 表 V4） |
| 入口 | `Makefile:207` `service-registry-reality`（`bin/` 净新增脚本配额 ⇒ 门禁是既有生成器的一个模式 + make 目标，非新脚本） |

## 2. verify 实测（ledger `verify` 四条，逐条，closeout 时点）

| # | 命令 | 实测结果 |
|---|---|---|
| V1 | `python3 bin/mof/gen-service-configs.py --reality-check --json` | `exit=0`；`ok=true`、`findings=[]`、`e1_status=ok`、`e1_drift=0`、`e2_undeclared=0`（`e2_undeclared_labels=[]`）、`e3_lint_debt=2`（`com.omostation.expiry-radar`、`com.omostation.zhixing-host-drift`）、`e4_prefix_ok=true`、`installed_total=56`、`workspace_scoped=43`、`owned_installed=49`、`owned_declared=49`、`registry_declared_total=64`、`unclassified=4`、`external=3`、`dev_label_prefix=com.omostation.dev.` —— 与交付期 `/tmp/b3-reality.json` **逐键相等**（`d==d_delivery` → True） |
| V2 | `python3 bin/mof/gen-service-configs.py --check --json` | `exit=0`，`drift_count=0`（E1 语义未被本 bet 改变）；另 `--validate --json` → `violation_count=0` |
| V3 | `shasum -a 256 ~/Library/LaunchAgents/*.plist` | 56 条目，与 bet 开始前快照 **byte-identical**（`diff -q` 无输出）；快照清单自身摘要 `sha256:5eaed00589b56c1c2ca6ccf4f6a456b6b641cf7221d8af0c8956b22ea92ed061` ⇒ 本 bet 对运行中的 launchd 服务**零磁盘写入** |
| V4 | `python3 -m pytest tests/test_service_registry_reality.py -q -p no:cacheprovider` | `exit=0`，`16 passed in 1.28s` |
| — | `make service-registry-reality` | `exit=0`，人类可读行：`E1 drift=0 (ok)  E2 undeclared=0  E3 lint_debt=2  E4 prefix_ok=True` / `本机 56 = workspace 49 + unclassified 4 + external 3  |  Workspace 作用域 43` / `✅ 注册表与本机 launchd 现实闭合` |

CI（PR #4421）：`gh pr checks` 共 **30 项，25 pass / 5 skipping / 0 fail**，含 required 的
`gac-gate`、`phase-gate`、`bet-done-transition`。

本地门禁：`make gac-local-gate` 在交付波两次实测 `PASS (68 checks executed, ALL GREEN)`。
中途一次 `[FAIL] accepted-specifications missing_frontmatter count=1` 是**本 PR 引入的真缺陷**
（spec frontmatter 缺 `owner`），按 §1 的 `adb494a35` 修复后转绿，未走 known-debt / 未 `--no-verify`。

## 3. done_when 逐条判定

| done_when | 判定 | 证据 |
|---|---|---|
| 1 `--reality-check --json` 12 个数值全部命中 | **通过** | §2 V1（18 键全量列出，非抽样） |
| 2 `launchd_namespace` 与 `services` 同文档 + 三张表 + 30 条回填字段齐备 + 不加 `owner` | **通过** | `yaml.safe_load_all` → `docs: 2`，`docs[-1]` 同时含 `services`(370) 与 `launchd_namespace`（`workspace_prefixes` 11 / `exempt_labels` 7 / `dev_label_prefix`）；回填 diff 提取 30 个 id 全部在 registry 命中、`labels ⊆ declared_labels(64)`、全部 `generate: False`；`owner` 键出现次数 0（340 条既有条目无一使用，也无任何消费者读取） |
| 3 `--check drift_count 0` 且 56 plist 字节不变 | **通过** | §2 V2 + V3 |
| 4 枚举只经 `plutil`，`plistlib` 仅在 E3 报告内 | **通过** | §5 的两条负例 `test_plutil_unparseable_plist_is_red`、`test_e3_reports_strict_xml_debt_without_dropping_the_job` |
| 5 生成器不再从家目录字面量推根 | **通过** | `bin/mof/gen-service-configs.py` 中 `/Users/xiamingxing` 出现 **0** 次（`Workspace` 字面出现 2 次，均为散文/报表标签，故判据是绝对路径字面量而非词面） |

ledger `verify[4]` 要求的"负例防第二次零检查绿"由这 9 条红向用例承担：
`test_gate_goes_red_when_an_owned_label_is_missing_from_registry`（owned 装而未登记 / 登记而未装 ⇒ 红）、
`test_unpartitioned_label_is_red_not_silently_dropped`、`test_illegal_classification_is_red`、
`test_missing_prefix_table_fails_closed`、`test_exempt_entry_shadowed_by_prefix_is_red`、
`test_exempt_entry_no_longer_installed_is_red`、`test_label_filename_mismatch_is_red`、
`test_plutil_unparseable_plist_is_red`、`test_namespace_as_a_separate_document_does_not_go_green`。
其中第一条正是"零检查假绿"的直接免疫：把任一 owned label 从 registry 删掉，E2 立刻非零。

## 4. 等式为什么必须按所有权分区（本 bet 的核心设计，实测口径）

`--reality-check` 里有**三个根**，混用即错：

| 根 | 解析方式 | 用途 |
|---|---|---|
| registry | 当前检出（`docs` → `.omo/_truth/registry/services.yaml`） | 声明集合 |
| disk | 机器级 `~/Library/LaunchAgents` | installed 集合（**与检出无关**） |
| `workspace_scoped` | `bin/lib/repo_root.canonical_root()` 字面匹配 | **仅报告**，不参与断言 |

E2 的等式只在 **owned 分区**上断言。全集口径是 `56 = owned 49 + unclassified 4 + external 3`；
`com.amazon.codewhisperer.launcher`、`com.macpaw.CleanMyMac5.Updater`、`com.local.phosphene`
是第三方软件，无谓词的"installed == declared"等于要求把 CleanMyMac 登记进本仓。
4 条 `unclassified`（`com.learningevolution.concept-weave.monthly`、`com.lifeos.pulse`、
`com.local.decision-svc`、`com.opencode.quota-monitor`）**归属主体待 principal 裁定**，
本 bet 只按 `exempt_labels` 记证据 + reason，不替 principal 签归属判语（见 §6）。

回填的 30 条是 **observe-only**：`enabled` 取自 `launchctl print-disabled` 域而非"目录里有 plist"，
`generate: false` 保证 `--check` 永不覆盖他人维护的 plist。

## 5. 枚举口径：为什么不能用 stdlib（C1，实测事故）

56 条 plist 里 2 条（`com.omostation.expiry-radar`、`com.omostation.zhixing-host-drift`）注释内含
`--`（`--strict` / `drwx------`），`plistlib`（expat）抛 `ExpatError`，而 `plutil -lint` OK 且
launchd **正常加载**。用 stdlib 解析做枚举会得到天生少 2 条的 installed 集合 —— 这是本 bet
之前所有"未登记计数"低估的根因，也是 E3 把"严格良构"降为**债务报告**而非过滤条件的原因：
解析失败绝不能充当把 job 丢掉的 filter。

## 6. 报告给 principal、本 bet 不处置

| 项 | 实测/位置 |
|---|---|
| **agent 感知未落地（本 bet 主动划出的边界）** | AGENTS.md §7 需要一条"launchd 现实门禁已存在 + 枚举必须走 plutil + 等式只在 owned 分区"的坑位说明。补丁已备好（30 行，closeout 时点 `git apply --check` 仍干净可应用），但 **`AGENTS.md` 不在本 bet 的 8 条 `write_surfaces` 内** ⇒ 不越面写。计划：在 B4 的 `write_surfaces` 里声明 `AGENTS.md`，于 B4 `start` 之前写全，随 B4 交付 |
| 4 条 label 归属未签 | `launchd_namespace.exempt_labels` 中 `classification: unclassified` 者，需 principal 裁定归属主体后在表间移动（改判 = 移表，不改代码） |
| 13 条已安装但未 loaded | `com.cockpit.dashboard, com.ecos.bos-registry-daemon, com.ecos.pasw-worktree-cleanup, com.l4.governance.watch, com.l4.resident.heartbeat, com.l4.resident.monitor, com.l4.resident.orchestrator, com.l4.resident.sediment, com.learningevolution.concept-weave.monthly, com.omo.model-scheduler, com.omostation.knowledge-foundry, com.omostation.panorama-dashboard, com.user.cron-service`（实测 56 installed / 43 loaded）。启停属运行时副作用，本 bet circuit breaker 禁止 |
| 15 条 declared-without-plist | `declared_labels 64 − 磁盘命中` = 15；其中 `generate: false` 者由他人维护或已退役，`com.l4.*` / `docker:*` 前缀是容器/内务标记而非 launchd label ⇒ 不构成 E2 缺口，但 B4 搬迁前需逐条定性 |
| 门禁未接线 | `--reality-check` 目前只由 `make service-registry-reality` 承载，**未**登记进 `ci-surfaces.yaml` / `governance-checks.yaml`（`script_baseline` 亦未动）——注册新门禁会改变"门禁是否执行"，属 principal 决策（与 PR 4209 移除 `--require-main` 同类） |
| 既有 plistlib 消费者仍在用旧口径 | `bin/gac/meta-doctor.py:364-367`、`bin/gac/task-inventory.py:83` 以 `plistlib` 枚举 ⇒ 同样少 2 条；`projects/…/service_view.py:71-80` 的 `NON_WORKSPACE_SERVICES` 是第二套所有权谓词（在 `projects/**` 下，circuit breaker 禁碰） |
| `dev_label_prefix` 目前惰性 | 已声明并被 E4 断言（不与 owned/exempt 命名空间重叠），但尚无 job 使用该前缀 —— 消费方是 B4 的 dev 安装位 |
| 2 条 plist 严格良构债 | 按 §5 登记为 E3 报告项，**不修**（改字节即写他人 plist，违反零写入不变量） |
| 台账自纠错的结构性成因 | 交付期实测值（49/4/3、`exempt_labels`）与台账预写文本（47/18/29、`undecided 6`/`foreign 3`）出现漂移，而 spec 一旦改动 ⇒ 该 run 任何 `claim`/`refresh-packet` 必撞 `WORK_PACKET_SOURCE_DRIFT`（`content_digest` ∈ `SPEC_BINDING_KEYS`）。⇒ 教训同 T10-205：`done_when`/`verify` 的数值在 `start` 前不可预写为常量，应写成"取自 `--reality-check --json` 同名键"的口径引用 |

## 7. 零运行时效应边界（circuit breaker 逐条自证）

- **未** `launchctl bootstrap / bootout / kickstart / unload` 任何 job；`launchctl print` 为只读观测（§4/§6 的 loaded 计数即由此而来）。
- **未**写或改任何 `~/Library/LaunchAgents/*.plist` —— V3 的 56 条清单 byte-identical 是唯一直接证据。
- **未**读写 crontab；**未**启停 `com.cockpit.dashboard`。
- **未**在 `bin/` 净新增文件（门禁是既有生成器新模式）；**未**改 `governance-checks.yaml` / `ci-surfaces.yaml` / `.pre-commit-config.yaml` 接线。
- **未**触碰 `projects/**`。
- live canary = **合并后的 main 自身**：在 `02f4dfee3` 内容上跑 V1–V4 全绿，即"每一个 owned launchd job 都能被注册表说出来"这一行为在生产状态下成立，无需启停任何服务。

## 8. 回滚路径

单点回滚 = revert `02f4dfee3`（squash 合并，无子模块 gitlink、无生成态、无运行时副作用）：

```bash
git revert --no-edit 02f4dfee3446757884562be83001f518408fc0bd
```

回滚后可观测后果（回到合并前 main）：`--reality-check` 模式消失（`argparse` exit 2）、
`make service-registry-reality` 目标消失、`services.yaml` 回到 340 条且无 `launchd_namespace`、
`tests/test_service_registry_reality.py` 消失。回滚**不会**影响任何进程、plist 或 cron（本 bet 未产生这类副作用，§7）。
注意回滚会使台账 `BET-Y2Q4-T10-206` 的 `write_surfaces` 指向不存在的文件 ⇒ `bet-ledger.py complete` 的 D0 守卫转红，需同 commit 一并回退台账条目。

## 9. cleanup

- 工作树：交付 PR #4421 合并后，worktree `ws-b3-svc-registry`（分支 `agent/governance-agent/b3-svc-registry`）保留至 closeout wave（receipt + retro + evidence 矩阵 + `complete`）合并，随后 `bash bin/gac/gac-worktree.sh release b3-svc-registry`。
  主工作区 `/Users/xiamingxing/Workspace` 全程只读未动。
- run：交付 run `20260927T023016Z-project-code-change-5d97bbaa` 承载全部 8 条 `write_surfaces` 的 claim，
  closeout wave 的 receipt 与 retro 因此**不需**另起 claim；ledger 收尾增量由 closeout wave run
  `20260927T041158Z-project-doc-change-67b83ff9` 承载（该 run 于交付 run `closeout` 关闭、路径锁释放后接管 `docs/plans/3y-bet-ledger.yaml`）。
- 未伪造项：其他 bet 的 lifecycle 状态未代其回写；`value` 轴诚实为 `NOT_PROVEN`
  （本 bet `value_indicator_policy: false`，30 条 value 记录未回填）；2 条 plist 良构债未按"已修复"叙述。
