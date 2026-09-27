---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B3 — 服务注册现实收口（installed 枚举口径 / 所有权谓词 / 双向 registry==installed 门禁）
bet_id: BET-Y2Q4-T10-206
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
---

# B3 — 服务注册现实收口

> 上游契约：`ADR-0456`（code_root / state_root 双根，principal 2026-09-27 批准 ACCEPTED，
> `72c93f896`）。本 spec 是 B4（安装位 + 状态搬迁）的**前置门禁**：B4 的动作形状是
> `launchctl bootstrap` 换路径，前提是"每一个在跑的 launchd job 都能被注册表说出来"。
> 现状说不出。

## 1. 为什么必须先做这个（实测，2026-09-27，本机 + 本仓）

| 事实 | 实测值 |
|---|---|
| `~/Library/LaunchAgents/*.plist` | **56** |
| 其中字面引用 `/Users/xiamingxing/Workspace` | **43** |
| `launchctl print gui/501/<label>` 成功（实际 loaded） | **43 / 56**（Workspace 口径 31 / 43） |
| `.omo/_truth/registry/services.yaml` 服务条目 | **340**（**多文档 YAML**：`safe_load` 只返回第一段 ⇒ 必须 `safe_load_all`） |
| 声明了 `label:` 的服务 | **34**（其中 15 条磁盘上没有 plist） |
| installed-but-undeclared | 全集 **37** / owned 分区 **30** |
| declared-without-plist | **15**，其中 8 条 `generate: false` ⇒ 真缺口 7 = 2× `com.l4.*` + 5× `docker:*` |
| declared + `enabled: true` + 未 loaded | **6**：`com.cockpit.dashboard` + 5× `com.l4.*` |
| `bin/mof/gen-service-configs.py --check` | `drift_count 0`，但它是 **registry→plist 单向字节比较** ⇒ 结构性看不见"装了但没登记" |

**归属分区 × 是否字面引用 Workspace × 是否已声明** 的交叉表（同一批 56 条 plist，逐条实测，
`plutil` 口径）：

| | declared | undeclared | 合计 |
|---|---|---|---|
| owned ∩ ws | 16 | **26** | 42 |
| owned ∩ no-ws | 3 | **4** | 7 |
| unclassified ∩ ws | 0 | 1 | 1 |
| unclassified ∩ no-ws | 0 | 3 | 3 |
| external（全部 no-ws） | 0 | 3 | 3 |
| **合计** | **19** | **37** | **56** |

⇒ **四个数各自只回答一个问题，互相不能代理**：

| 数 | 谓词 | 回答的问题 |
|---|---|---|
| **37** | `installed − declared` | 注册表整体盲区有多大（计划文档里"37 个未登记 label"是这一口径） |
| **30** | `owned − declared`（= 26 + 4） | **C2 等式门禁要归零的面**（E2 现状缺口） |
| **27** | `undeclared ∩ 字面引用 Workspace` | 未登记面里有多少会被 B4 换路径打到 |
| **43** | `installed ∩ 字面引用 Workspace` | **B4 的真实爆炸半径**（含 19 条已登记的） |

**"loaded 集合 == Workspace 引用集合"是错的**（本 spec 早期版本的隐含假设，已实测推翻）：
Workspace 口径 43 条里只有 **31** 条 loaded；另有 **12** 条不引用 Workspace 的 job 在 loaded
（`com.aetherforge.gateway`、`com.lmstudio.server`、`com.omlxc.daemon`、`com.omlxc.ollama-env`、
`com.amazon.codewhisperer.launcher`、`com.macpaw.CleanMyMac5.Updater`、`com.lifeos.pulse`、
`com.local.decision-svc`、`com.local.phosphene`、`com.opencode.quota-monitor`、
`com.omostation.claims-observation-r0`、`com.omostation.zhixing-dashboard-refresh`）。
⇒ 运行态真值只能问 `launchctl`，"plist 里有本仓路径"既非必要也非充分。

本 spec 之前我自己在不同处给出过 25 / 27 / 29 / 37 四个未登记数。25 来自**枚举工具选择错误**
（见 §2），27 来自**把 `ws` 谓词当成 `owned` 谓词**，29 来自一版**手工写的 owned 清单**
（漏了 `com.user.cron-service` 与 `com.lmstudio.server` 两条，又把 `com.local.phosphene` 留在
待定）。⇒ `owned` 分区最终由 §3 的前缀表在实现时**重算**，不沿用任何手算数字；实现落地后
`--reality-check` 报的 `owned_installed / e2_undeclared` 是唯一口径（49 / 30）。

**两个容易互相冒充的谓词**：`com.omostation.claims-observation-r0` 与
`com.omostation.zhixing-dashboard-refresh` 是本仓服务，但 plist 里没有 `/Users/xiamingxing/Workspace`
字面量（实测 `ProgramArguments` 指向 `~/.local/share/zhixing-dashboard/`）；
反之 `com.user.cron-service` 的 `ProgramArguments` 直接指进本仓
（`uv run --directory <WS>/projects/runtime -m runtime.cron_service.server`），而
`bin/svc/service_view.py:71-80` 的 `NON_WORKSPACE_SERVICES` 却把它列为"不归 Workspace 管"
—— 那份清单的自述判据是"ProgramArguments 指向 Workspace 之外"，它自己就违反了自己的判据。
⇒ `ws` 字面引用与 `owned` 归属是**两个不同的谓词**，C2 用前缀表判归属，`ws` 只用于回答
"B4 换路径会波及哪几条"；`NON_WORKSPACE_SERVICES` 作为第四份重复定义登记为遗留（§7.6），
本 bet 不改它 —— 它是 cockpit/ops 大屏的运行时消费者，改判会动生产视图。

## 2. 契约 C1：installed 枚举口径 = Apple 解析器，不是 Python 解析器

56 个 plist 里有 2 个用 `plistlib`（expat）**读不出来**：

- `com.omostation.expiry-radar.plist` — `ExpatError: line 11 col 18`
- `com.omostation.zhixing-host-drift.plist` — `ExpatError: line 7 col 36`

真因不是"文件坏了"：两者的**注释块内含 `--`**（`--strict`、`drwx------`），XML 1.0 禁止注释
内出现 `--`，但 `plutil -lint` 判 `OK`，且两个 job **都在 launchd 里 loaded、真在跑**。

⇒ 任何用 stdlib XML 枚举 installed 集合的工具，天生少 2 条**正在运行的服务**。
实测本仓现有踩在这条上的**两处**（`grep -rn plistlib bin/**/*.py`）：
`bin/gac/meta-doctor.py:365`（launchd 现实核对）与 `bin/gac/task-inventory.py:83`。
失效形态是**静默**而非报错：`bin/gac/meta-doctor.py:364-367` 的形状是
`try: plistlib.loads(...) / except Exception: continue` ⇒ 那 2 条真在跑的 job 在它的
launchd 路径核对里**不存在**。

`bin/mof/gen-service-configs.py` **不解析磁盘 plist**（`_plist_program_args()` 只用正则读它
**自己生成**的 XML），所以它既不是受害者、也不是检测器 —— E2 的 disk 侧枚举必须新造。

**规定**：
- 枚举/读取 plist 一律 `plutil -convert json -o - <path>`；
- `plistlib` / `xml.etree` 只允许出现在**严格良构检查**（C3-E3）里，且其结果只作
  lint 债报告，**不得作为过滤器**丢文件；
- 任何 installed 计数必须同时声明口径：`全集 56` 还是 `Workspace-scoped 43`。

## 3. 契约 C2：所有权谓词（否则"等值"是荒谬的）

37 条 undeclared 里含第三方软件自己的 job：`com.amazon.codewhisperer.launcher`、
`com.macpaw.CleanMyMac5.Updater`。要求把它们登记进本仓 `services.yaml` 是范畴错误。

**规定**：门禁断言的是**只在 owned 分区上的等式**

```
declared ∩ installed ∩ owned  ==  installed ∩ owned
```

即"每一个属本仓命名空间、且真在 `~/Library/LaunchAgents` 里的 job，都必须被注册表说出来"；
`external` 与 `unclassified` 分区不在断言范围内。等价说法：`installed ∩ owned − declared == ∅`，
实测基线 **30** 条缺口（49 owned − 19 owned∩declared）。

分区落在 `services.yaml` 里与 `services` **同文档**的 `launchd_namespace:` 段（键名即契约，
见 §5 的放置约束），三张表逐条带 `reason:`，不允许"猜测式默认归属"：

| 分类 | registry 键 | 判据 | 实测（installed 计数） |
|---|---|---|---|
| **owned** | `workspace_prefixes:`（点分段前缀） | 该命名空间下的 plist 由本仓作者写下并安装 | **49** = `com.omostation`(23) `com.l4`(14) `com.omlxc`(3) `com.ecos`(2) + `com.aetherforge` `com.agora` `com.cockpit` `com.kos` `com.lmstudio` `com.omo` `com.user` 各 1 |
| **external** | `exempt_labels[].classification: external` | 程序体是第三方 app 自带的 bundle / 由第三方安装器（pinokio）拉取，本仓不接管其生命周期 | **3** = `com.amazon.codewhisperer.launcher`(→`/Applications/Kiro CLI.app/…`) `com.macpaw.CleanMyMac5.Updater`(→CleanMyMac 更新器) `com.local.phosphene`(→`~/pinokio/api/phosphene.git`；aetherforge 有 `phosphene_adapter.py` 按**外部服务**适配它，同计划文档决策 5 给 zhixing-dashboard 的契约同一类) |
| **unclassified** | `exempt_labels[].classification: unclassified` | 本仓作者写的脚本，但活在检出之外的用户域，生命周期归属未经署名裁决 | **4** = `com.learningevolution.concept-weave.monthly`(→`/usr/bin/true` 空转占位，`WorkingDirectory ~/.local/state/omostation/accepted-20260904`) `com.lifeos.pulse`(→`~/.claude/LIFEOS/PULSE`) `com.local.decision-svc`(→`~/.local/share/decision-svc` 自带 venv) `com.opencode.quota-monitor`(→`~/.config/opencode/quota-monitor.py`) |

`com.lmstudio.server` 与 `com.user.cron-service` 是本表相对草案的两处改判，依据是实测
`ProgramArguments`：前者跑 `~/.lmstudio/bin/lms`（外部 app）但 **plist 由本仓作者安装、
且 registry 里已有它的 `generate: false` 条目**；后者 `uv run --directory <WS>/projects/runtime
-m runtime.cron_service.server` 指进本仓子模块。把已被注册表管理的 label 划到 owned 之外，
会让 `declared ⊄ owned`，等式左边失去意义。

**必须按点分段取前缀，不能做字符串前缀匹配**：`com.omo` 与 `com.omostation` 是两个命名空间，
`startswith("com.omo")` 会把 23 条 `com.omostation.*` 吞进 `com.omo.model-scheduler` 那一格
（实测 `com.omo.*` 只有 1 条）。

**只有 owned 可以用前缀通配，两个 exempt 分区必须逐条精确列 label。** 这不是排版偏好，
是 E4 的可失败性所在：豁免面若也写成前缀（如 `com.local.`），任何新装的
`com.local.<whatever>` job 都会**自动**落进豁免清单，等式当场退化为"本仓命名空间内成立"，
而 B4 期间真正会静默跑旧代码的恰恰是检出之外那些 job。精确列名的代价是多装一条就要改一次
registry —— 这个代价是设计意图（改 registry 就是"有人认领了这条 job"的凭证）。

`unclassified` 这 4 条在本 bet 里**只登记事实与倾向，不代 principal 签字**，门禁**不**对它们
断言等式（否则 B3 的完成条件里凭空多出一个"必须 principal 先签字"的前置，直接撞 §10 中止判据）。
principal 改判 = 把某条的 `classification` 删掉、或把命名空间加进 `workspace_prefixes`，
等式自动把它纳入约束，**不动代码**。实测另有一条既有事实值得记住：草案把
`com.lmstudio.server` 记为"同时 foreign 且 declared"，这正是全量
`declared == installed` 会在第一天就因外部 app 而红的原因。

## 4. 契约 C3：双向门禁（四条独立可诊断断言）

| ID | 断言 | 现状 | 本 bet 目标 |
|---|---|---|---|
| **E1** | registry→plist 字节一致（现有 `--check` 语义，逐字不改） | `drift_count 0` | 保持 0 |
| **E2** | disk→registry：`installed ∩ owned − declared == ∅` | **30** 条缺口 | **0** |
| **E3** | 每个 plist 通过**严格 XML 良构**检查 | 2 条违反 | 报告项（不阻塞），因为修复要改在跑的 plist ⇒ 属 B4/运行时效应 |
| **E4** | 分区完整性（7 条子断言，任一违反即红）：① `workspace_prefixes` 非空且无重复；② `exempt_labels` 无重复、`classification ∈ {external, unclassified}`；③ 没有任何 exempt label 被 owned 前缀遮蔽（遮蔽 = 死数据）；④ 每条 installed label 恰好落进一个分区，落不进去即 `unmanaged_unknown` 红；⑤ `Label` 与文件名一致、Label 不重复；⑥ plutil 解不开的 plist 即红（连归属都无从判断）；⑦ exempt 项若本机已不存在该 plist → 登记陈旧即红 | 无分区数据 | 分区可证且**不可被扩大豁免面绕过** |

E4 ② 附带一条实现约束：**分类拼错的 label 落到分区外（`unmanaged_unknown` 红），不默认当成
`external`**。写成 `classification: externel` 若被宽容解释，等于一条本仓服务静默退出等式 ——
拼写错误把门禁面缩小，是这个 bet 最不该复现的失效形态。单元测试钉住这条（§8）。

E2 是"B4 安全网"的核心：B4 换安装位后，**漏改的 plist 会静默跑旧代码**；只有
`registry == installed` 成立时，"集合相等"才能当检测器用。

E4 今天在 dev 侧是空的（本机零个 dev-profile job，`dev_label_prefix` 无对象可断言），
所以它的**可失败性必须落在分区上**：49 条 owned installed label 各自要匹配**恰好一条**前缀，
且豁免面只能逐条精确列名（§3）。有人加一条与 `com.omostation.` 重叠的 `com.omos.` 前缀、
漏配一个新前缀的 label、或把 `com.local.` 整段划进 exempt，E4 立即红。否则 E4 就是本 spec
§8 反例条款所要防的"第二个零检查的绿"。

**实现位置（不是新脚本）**：E2/E3/E4 作为 `bin/mof/gen-service-configs.py --reality-check --json`
落地，Makefile 入口 `make service-registry-reality`。理由：`bin/**` 受净新增脚本配额约束
（`bin/gac/check-bin-quota-diff.py:26` 统计 `bin/*.py` / `bin/**/*.py` 的新增 vs 删除，净增即拦），
而放宽配额要动 `governance-checks.yaml` 的 `script_baseline` —— 那是别的 bet 的治理面，不在本 bet
授权内。E1 与 E2 共用同一个 registry 加载器（`load_services()` 已经必须 `safe_load_all`），
放在同一文件里也避免第二套 registry 解析口径。`--reality-check` 分支**不得**调用任何写盘函数。

## 5. 契约 C4：回填条目形状 = observe-only

30 条回填一律 `generate: false`（registry 声明事实，**不**由 `gen-service-configs.py`
生成/覆盖磁盘上真实在跑的手写 plist），并带：`label` / `scheduler: launchd` /
`trigger`（按 plist 里 `WatchPaths`→`KeepAlive`→`StartCalendarInterval`→`StartInterval`→
`RunAtLoad` 优先级实测推导）/ `enabled`（按 `launchctl print-disabled gui/<uid>` 的**持久禁用域**
取值，不是按目录存在，也不是按"当前 loaded"）/ `config_source:` 指向该 plist +
`content_digest`（该 plist 字节的 `sha256`）/ `program`（原样记 `ProgramArguments` 的头三段）/
`outputs` / `notes` / `depends_on: []`。

**不加 `owner:` 键** —— 草案里写过它，但实测 `services.yaml` 340 条条目从未用过 `owner`
（键全集只有 `id/enabled/generate/config_source/scheduler/trigger/label/program/outputs/notes/…`），
且没有任何消费者读它。给一个无读者的键等于再造一份"没人维护的归属"：本 bet 要收的就是这类东西。

`config_source` 不是新造的键 —— 现有 `generate: false` 条目已经在用它
（实测 `com.lmstudio.server` → `config_source: ~/Library/LaunchAgents/com.lmstudio.server.plist`，
`com.omlxc.daemon` → `config_source: projects/omlxc/launchd/com.omlxc.daemon.plist`）。
回填复用同一条目形状，避免 registry 里出现第二种"源头在哪"的写法。
（实测 `config_source` 当前**零个代码读者**，它是给人看的指针；`generate: false` 才是
生成器实际尊重的开关。这一点如实记录，不假称它被校验。）

`content_digest` 同样**不参与 `ok` 判定**，只作为可见的变化指示器：这些 plist 的字节源头在
本仓之外（手改 / 外部安装器），若让摘要失配即红，门禁会经常红在**没人该为此负责**的地方，
而一个常红的门禁最终教会 agent 的是绕过它（本仓 §7 已有此类教训）。需要持续成立的等式是
**label 集合**，不是字节。

理由：本 bet 的 circuit breaker 禁止启停任何 job；若回填把 `generate` 留成默认，
下一次 `gen-service-configs.py`（不带 `--check`）会**重写 30 个正在跑的 plist**。

实测登记时的运行态（写进各条 `notes`，不进 registry 结构化键，避免又一份无人维护的实时状态）：
56 条 plist 里 **43** 条在 launchd 里可见（loaded），13 条不在；这 13 条中有
`com.l4.governance.watch`（B3 依赖的 watch agent 本身没 bootstrap）与 `com.user.cron-service`。
`print-disabled` 域里被显式 `disabled` 的 owned job 只有 `com.l4.resident.orchestrator`，
它本来就已在注册表里 ⇒ 30 条回填全部 `enabled: true`。

## 6. 契约 C5：根解析只有一份（收掉第三处分叉）

`bin/mof/gen-service-configs.py:26-43` 的 `_canonical_workspace()` 自己实现了
`$OMOSTATION_ROOT → ~/Workspace → __file__` 三级解析，把 `$HOME/Workspace` **写死**在源码里，
并在两者都不存在时**退回 `Path(__file__).resolve().parents[2]`**。这与
`bin/lib/repo_root.py:canonical_root()` 是同一逻辑的两份副本，差别恰在致命处：
`canonical_root()` 在定位不到规范检出时 **raise**，并写明理由 ——
"写机器级配置的工具不能退回 `__file__` 反推 —— 那会把 worktree 路径写死进配置"
（`bin/lib/repo_root.py:44-47`）。那个退回分支正是本文件 docstring 记录的 2026-08-08 事故形状
（7 个 plist 的程序路径被写成 `ws-mass-deletion-gate`、`ws-observability-impl` 等临时 worktree）。

⇒ 收敛方向是 `canonical_root()`，**不是** `code_root()`：`code_root()` 跟随当前检出，
是**读**平面的口径；本工具写的是机器级配置，必须锚定规范安装位（B4 之后由
`OMOSTATION_ROOT` 指向 `~/Runtime/omostation`）。

**解析必须惰性**（`workspace()` / `services_yaml_path()` 两个访问器 + 一份缓存，取代原
`WORKSPACE` / `REGISTRY` 模块常量）。直接理由：`canonical_root()` 的 raise 是规定行为，
但本文件不止被命令行用 —— `bin/ops/cli.py:33-37` 用 `exec_module` 加载它只为取
`_stable_python3`，`tests/test_gen_service_configs.py` 同样按文件路径加载。把解析放在
import 期，等于让"本机没有规范检出"这件事把**纯函数消费者**一起判死（GHA 上必红）。
惰性之后契约仍然成立：真要落笔/比对机器级配置的那条路径（生成 plist、`--check`、
`--reality-check` 的根作用域统计）一调用就 raise，一次也不会退回 `__file__`。
这条由 §8 的 `test_import_does_not_eagerly_resolve_the_root` 钉住。

**不假装这条已经收敛完**。实测 `bin/**`（排除 `_archive`）里仍自带工作副本字面量
（`Path.home()/"Workspace"` / `expanduser("~/Workspace")` / `"$HOME/Workspace"` /
`/Users/<name>/Workspace`）的文件共 **13** 个，其中 `bin/lib/repo_root.py` 是规定的那一份
⇒ 还剩 **12** 份重复解析（`bin/svc/service_view.py:41`、`bin/gac/agent-clone.py:133,4161`、
`bin/gac/test_agent_clone.py:1036`、`bin/gac/codex-worker-adapter.py:245`、
`bin/gac/workspace-wip-guard.py`、`bin/scheduler-compile.py:116`，以及
`bin/gac/{corrosion-pipeline-connector,kernel-bridge,l4-memory-bridge,model-ecos-bridge,probe-heartbeat-monitor,repo-health-metrics}.py`）。
本 bet 消掉的是 `gen-service-configs.py` **这一份**，理由不是"顺手"：它是这批里唯一会
**写机器级配置**的，也就是 2026-08-08 事故的成因。其余 12 份是 B4 的收敛队列
（逐条列出，不合并成"以后再说是"）。

门禁的三个根口径**各自只有一个来源**，逐条写清，免得日后被当成同一件事：

| 量 | 取哪个根 | 为什么 |
|---|---|---|
| registry 侧读取（`--reality-check` 默认） | **当前检出**（`Path(__file__).parents[2]`，`--registry` 可覆盖） | 门禁要在合并前评**这份**分支的 `services.yaml`；评主仓那份等于自欺 |
| disk 侧枚举 | `~/Library/LaunchAgents`（机器级，与检出无关） | 现实只有一份，`launchctl` 不认 worktree |
| `workspace_scoped` 报告项 | `canonical_root()` 字面量匹配 | 回答"B4 换路径波及哪几条"（§1），**不参与任何 E2/E4 断言** |

E1 维持 `--check` 原语义（子进程不改环境、不改根）。**这条不对称如实记录**：
`run_e1_drift()` 跑的是**当前检出的代码** × **规范检出的 registry**（因为 `--check` 的
registry 走 `canonical_root()`，与 C5 之前逐字节相同）。回填的 30 条全是 `generate: false`
⇒ 对本 bet 无影响；但未来若在分支里改一条**会生成 plist** 的服务，E1 在分支上仍会绿
（它评的是主仓那份 registry）。那不是本 bet 引入的缺陷，是 E1 的既有口径；改它等于改
`--check` 的语义，违反 §4"逐字不改"，留给 B4（安装位收口时 registry 与检出重新合一）。

## 7. done_when

1. `plutil` 口径下 installed 集合 == 56（Workspace-scoped 43），且枚举实现**不出现**
   `plistlib.loads` 作为过滤器：`grep -c 'plistlib\.' bin/mof/gen-service-configs.py` == **1**，
   且那一处是 E3 的严格良构检查（`plist_strict_well_formed`），不丢文件、只计数。
2. E2 门禁在本机绿：`installed ∩ owned − declared == ∅`，即 30 条已回填，且
   `services.yaml` 的 `launchd_namespace:` 三段（`workspace_prefixes` / `exempt_labels` 的
   `external` + `unclassified` / `dev_label_prefix`）逐条有 `reason:`。
3. `gen-service-configs.py --check` 仍 `drift_count 0`，且**新加的 E2/E3/E4 不改变
   E1 语义**（不重写任何磁盘 plist：回填前后 `shasum` 对 56 个文件逐字节相等）。
4. 根解析只剩一份且惰性：模块常量 `WORKSPACE` / `REGISTRY` 与 `Path(__file__)` 推断根全部
   消失，改为 `workspace()` / `services_yaml_path()` 走 `repo_root.canonical_root()`；
   `grep -c '/Users/xiamingxing' bin/mof/gen-service-configs.py` == **0**
   （口径是**绝对路径字面量**归零，不是 `Workspace` 这个词归零 —— 散文里解释事故、
   以及 `--reality-check` 输出里的"Workspace 作用域"标签都不算违规）。
5. 4 条 unclassified / 3 条 external 判定表落 registry，E3 的 2 条非法 XML 作为**已知债**
   在门禁输出里逐条具名（`e3_malformed_labels`）并写进 closeout，不当成不存在。
6. 遗留（**如实报告、不在本 bet 处置**）：① `bin/gac/meta-doctor.py:364-367` 与
   `bin/gac/task-inventory.py:83` 仍用 `plistlib` 枚举 ⇒ 各自少 2 条在跑的 job（§2 的 C1
   规定的剩余受害者）；② `bin/svc/service_view.py:71-80` 的 `NON_WORKSPACE_SERVICES` 是
   第四份归属判断，且自身违反其自述判据（§1）；③ E4 的 `dev_label_prefix` 目前无对象可断言，
   真正生效在 B4（dev profile 装 job 之后）。三者都不在本 bet 的 claim 面内（改 ①② 会动
   cockpit/health 的运行时消费者），另立 bet；④ **`AGENTS.md` §7 增一条 C1/plutil 与
   `make service-registry-reality` 的感知条目** —— 草案里写过并实现过，但它不在本 bet 的
   `write_surfaces` 里，而 WorkPacket 契约禁止 run 内扩面：`claim AGENTS.md` 先撞
   `SPEC_DIGEST_MISMATCH`，刷新 digest 后撞 `WORK_PACKET_SOURCE_DRIFT`
   （`bin/plan/bet-ledger.py:2334`），唯一重绑动词 `refresh-packet` 又要求 `spec_binding`
   未变（`bin/agent-workflow.py:849`）⇒ spec 内容一改就不可用。这是 BET-Y2Q4-T10-205
   closeout 已记录的同一道墙（"write_surfaces 必须在 start 前写全"），本 bet 再次实证并
   **拒绝绕**：改动已落成 patch 交下一个 doc-only run 走，不塞进本 PR。理由不是形式主义 ——
   C1/C2 若只活在 spec 里，下一个写 launchd 探测的 agent 仍会踩同一块（`meta-doctor` 已踩），
   所以这条感知交付是**必需**的，只是不属于这个 run 的作用域。

## 8. verify

- `python3 bin/mof/gen-service-configs.py --reality-check --json` → `exit 0` 且
  `e1_drift==0 && e1_status=="ok" && e2_undeclared==0 && e4_prefix_ok==true && ok==true`；
  计数 `installed_total==56`、`workspace_scoped==43`、`owned_installed==49`、
  `owned_declared==49`、`e3_lint_debt==2`、`undecided==4`、`foreign==3`、
  `registry_declared_total==64`（= 34 原有 + 30 回填）
  （报告键与 registry 里 `classification` 的取值同名：`unclassified` / `external`，
  §1/§3 散文里的"需署名裁决 / foreign"是同一批东西的叙述名）
- `python3 bin/mof/gen-service-configs.py --validate --json` → `violation_count==0`
  （新增 30 条 `generate: false` 条目不得把注册自洽面弄红）
- `python3 -c` 断言 `services.yaml` 用 `safe_load_all` 读到的 label 集合 ⊇ 回填的 30 条，
  且 `launchd_namespace` 与 `services` 在**同一个** YAML 文档里（`len(docs)==2`，
  `docs[-1]` 同时含两键）—— 这条防的是 §5 注明的"独立文档 ⇒ services 解析为空 ⇒ 假绿"
- `shasum -a 256 ~/Library/LaunchAgents/*.plist` 在 bet 前后逐字节相等（无磁盘写效应）
- `python3 -m pytest tests/test_service_registry_reality.py -q` 全绿。每条断言都要有配对的
  红/绿用例（不写"只数绿灯"的测试）：
  **反例条款**（§8 存在的理由）= 给门禁一条本机在跑、注册表没说的 owned label ⇒ 必须红；
  分区表为空 ⇒ 红；label 落不进任何表 ⇒ 红；`classification` 拼错 ⇒ 红且不被当成 external；
  exempt 被前缀遮蔽 / exempt 已不在本机 / `Label` 与文件名不一致 / plutil 解不开 ⇒ 各自红；
  E1 注入 `drift` ⇒ 进 findings；E3 的 `--` 注释文件 ⇒ 计数但不掉出 installed；
  namespace 独立成文档 ⇒ `load_services()` 空 **且** 门禁红（假绿被拦）；
  `workspace_scoped` 只报告不断言；import 期不解析根（C5 惰性）
- 门禁的测试**不碰本机 `~/Library/LaunchAgents`**（AGENTS.md §7 hermetic 泄漏条款）：
  fixture 用 `tmp_path` 造 plist + 造 registry，本机现实由 monkeypatch 注入的枚举器提供，
  E1 由注入的 dict 提供，不 shell out —— 因此在没有 `plutil` 的 GHA 上同样可跑

## 9. circuit_breaker（本 bet 绝不触碰）

任何 `launchctl bootstrap/bootout/kickstart`；任何对 `~/Library/LaunchAgents/*.plist`
或 crontab 的写；`com.cockpit.dashboard` 的启停（那是 B2-B，principal 明确押后）；
`.omo/_truth/registry/governance-checks.yaml` 与 `ci-surfaces.yaml` 的接线语义与配额基线；
`bin/**` 净新增脚本（配额见 §4）；`projects/**`。E3 的 2 条非法 XML 只登记不修复
（修复 = 改在跑的 plist）。

**因此本门禁不进 CI**（不接 `ci-surfaces.yaml`），入口只有 `make service-registry-reality`。
这不是遗漏，是两件事共同决定的：① 接线要动 `ci-surfaces.yaml`，在 breaker 内；
② E2/E3/E4 的现实侧是**本机 `~/Library/LaunchAgents`**，GHA 上那个目录不存在，
接线只会造出一个在 CI 里恒真/恒假的检查（本仓 §7 "hermetic 测试泄漏 host 状态"同一类）。
可进 CI 的部分已经进去了：`--validate`（注册自洽，不依赖本机）与
`tests/test_service_registry_reality.py`（fixture 化，不碰本机目录）。

## 10. 中止判据（正面继承计划文档）

若 E2 无法在**不写任何磁盘 plist** 的前提下达到 0（例如某条 label 只能在单一命名空间
下工作），**停在 B4 之前**并报告 —— 带着无人管理的 plist 做半程切换严格比现状更糟。
把等式限定在 owned 分区（§3）正是为了让这个判据**不因 principal 未签字而提前触发**：
30 条回填全部可观测、无需裁决。按 §1/§3 实测，该判据目前**不触发**（实现后本机
`--reality-check` exit 0，且 `shasum` 清单 56 条与 bet 前一致）。
