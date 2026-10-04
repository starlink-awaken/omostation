---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-224 — launchd 任务登记实测双向纠偏 + tests/unit 去 13 处 host 字面量（B4b 批次 2 前置）
bet_id: BET-Y2Q4-T10-224
status: accepted
lifecycle: contract
last-reviewed: 2026-10-04
owner: governance-team
---

# 一处登记在说谎，另一个方向也在说谎，而用例用字面量把谎话钉成绿

> ADR-0456 B4b 批次 2 要把 43 个 plist / 40 条 cron 的根从 `~/Workspace` 改道。
> 本 BET 不碰改道本身（那是逐批授权的动作），只清除改道前必须先存在的两样东西：
> **可信的 launchd 现实登记**，和 **不会因为换根就变红的断言**。
> 基线：`origin/main@540783376`（2026-10-04 实测）。

## 1. 实测：登记 ↔ 机器，两个方向都失配

测量手段三条，互相独立，全部本地无网络：

| 探针 | 命令 |
|---|---|
| 是否被 launchd 加载 | `launchctl list`（23 条 `com.omostation.*` 标签，实测） |
| 是否装到用户域 | `ls ~/Library/LaunchAgents/`（23 个 `com.omostation.*` plist，实测） |
| 是否被仓库跟踪 | `ls runtime/cron/*.plist`（7 个，实测） |

`.omo/cron/registry.yaml` 实测 70 条 job，其中 `planes` 含 `launchd` 的 18 条。逐条对上表三条探针，本 BET 只处理**能证明**的 3 条：

| job | 登记 status/reality | 加载 | 装机 | 跟踪 | 判定 |
|---|---|---|---|---|---|
| `panorama-dashboard-refresh` | `proposed` / `pending` | ✅ | ✅ | ✅ | **低报**：应为 `active` / `installed` |
| `panorama-dashboard` | `proposed` / `pending` | ❌ | ❌ | ✅ | **误报为"待装"**：应为 `declared_only`（见下：它已退役，不是等着装） |
| `knowledge-foundry-6h` | `proposed` / `installed` | ❌ | ❌ | ✅ | **高报**：`installed` 无据，应为 `declared_only` |

`pending` 不是人手写上去的当前值，而是**重复键 last-wins 的产物**：那两条 panorama 记录各自带**两个** `reality` 键 —— `:605 reality: declared_only` 紧跟 `:607 reality: pending`、`:630 reality: installed` 紧跟 `:632 reality: pending`。PyYAML `safe_load` 对重复键**静默保留最后一个**，所以文件里同时印着"已装机"和"待装"，而所有读者只看见后者。全文件 dup-aware 扫描实测**恰好这 2 处**（其余 68 条干净）。这决定了修复形状：不是把 `pending` 改成 `installed`，而是**删掉被遮蔽的那一键**再写唯一真值 —— 只改其中一行，另一行仍会赢。同一条重复键因此必须成为可判定不变式（I3），否则下一次 reconciliation（`:607/:632` 正是 2026-09-30 复核留下的）会再制造一份。

关键判据：**修复方向不由"哪一侧能让 pytest 变绿"决定**。`tests/unit/test_panorama_runtime_scheduler.py:25` 断言 `panorama-dashboard` 的 `status == "active"` 是**用例错**；`:42` 断言 `panorama-dashboard-refresh` 是 `active` 是**登记错**（实测已加载且已装机）。两条同形（都是 `assert status == "active"`），若按绿灯收敛，第一条会把一个不存在的安装写进 SSOT。

`panorama-dashboard` 的真相在另一面：`services.yaml:5813` 记着 `disabled_reason` —— ":43910 已由 `com.omostation.sunset-redirector` 接管 (302 → 织星驾驶舱)，**panorama-serve 退役**"（TASK-F54F176A, 2026-09-28）。所以它既不是"运行中"，也不是"等着装"，而是**已退役、只剩一份仓库里的 plist 骨架**。但 `status` 词表实测只有 `{active, proposed}`（43/27），没有 `retired` 值，而 `reality` 词表里有语义正确的 `{installed, declared_only, pending}`（41/18/8）—— 于是退役在本文件里的合法表达是 `status: proposed` + `reality: declared_only` + `reconciliation_note` 指向 services.yaml 那条 `disabled_reason`。**扩词表不在本 BET 边界内**。两个字段的真实消费者是实测过的：`status` 被 `bin/scheduler-compile.py` 的三处编译/对账逻辑消费（`:46` crontab 只出 active、`:147` launchd 登记集只取 active、`:183` drift 只比 active），`reality` 被 `bin/panorama/panorama-collect.py` 消费（`:1603` 与 `:2802` 按 `== "installed"` 挑选、`:2810` 缺省回落 `declared_only`）。动枚举要同时改这两处，是另一件事。

因此本 BET 的三条纠偏**不是纯文档动作**，各自有下游效应，必须在改前改后各测一次：`panorama-dashboard-refresh` 由 `proposed` → `active` 会让它进入 `:147` 的 launchd 登记集，基线实测 `registered_count=12`，预期 13；`knowledge-foundry-6h` 由 `installed` → `declared_only` 会让它从驾驶舱的 `installed_declared` 名单里消失（那正是它的真实状态）。

这条判据对 B4b 批次 2 有直接后果：那份 `runtime/cron/com.omostation.panorama-dashboard.plist` 是**退役服务的残留**，不该跟着改道。

## 2. 不变式：可判定、当前有违规、修完归零

登记面加三条互斥约束，对全部 70 条 job 生效，**不查机器**（查机器即破坏 hermeticity）：

- **I1** `status == "active"` ⇒ `reality ∈ {installed, crontab_installed}`。基线违规 **0** 条。
- **I2** `reality ∈ {installed, crontab_installed}` ⇒ `status == "active"`。基线违规 **1** 条（`knowledge-foundry-6h`）。
- **I3** 每条 job 的映射内**不得有重复键**。基线违规 **2** 条（`:599`/`:623` 的 `reality`）。

I1 在基线上已经绿，所以它单独不构成证据；它必须和 I2 同时立，因为 I2 的违规方向正是"proposed 却声称 installed"这一类。纠偏后三条同时归零。

I3 无法用 `yaml.safe_load` 判定 —— 它在解析阶段就把重复键折叠了（这正是 §1 里那个 bug 能活到今天的原因）。检测器必须用 dup-aware 的 mapping constructor 自己重放解析。按 #4606 的教训，这类"扫文件的检测器"必须**拿合成违规样本自证**：变异用例注入一条带两个 `reality` 的记录，I3 必须点名它，否则"绿"只说明检测器没命中。

为什么不复用现成的 `bin/scheduler-compile.py::check_drift()`：它实测确实给出同一方向的结论（`launchd.installed_count=37`、`registered_count=12`、`undeclared_installed_count=25`），但它**直接读本机 launchctl 与 `~/Library/LaunchAgents`**，且返回体只有计数加 15 条样本、没有逐 job 判定。把它塞进 `tests/unit/` 就是把一条用例的绿/红交给机器状态 —— 正是 BET-Y2Q4-T10-222 刚清掉的那一类。所以本 BET 的 gate 只做**文件内部一致性**，`check_drift()` 的数字只作为 spec 里的实测引证。

## 3. 断言面：13 处字面量换成派生 + 变异对照自证

`tests/unit/test_panorama_runtime_scheduler.py` 8 处、`tests/unit/test_agent_cell_scheduler.py` 5 处 `"/Users/xiamingxing"` 字面量。**这些用例今天是绿的，且绿的原因正是它们逐字复述了 plist 里的 host 根** —— 这叫 green-by-literal：它不检测任何东西，只在 B4b 批次 2 改道那天准时变红。所以删除它们不是美化，是拆地雷。

替换成从 plist **自身**派生的根，三条闭合：

1. **仓库根 R** 取自 `payload["WorkingDirectory"]`，不写死。派生断言：`EnvironmentVariables["PYTHONPATH"] == R + "/projects/omo/src"`；`StandardOutPath` / `StandardErrorPath` 均以 R 为前缀。
2. **非 R 绝对路径**全部落在**同一个**第二根 D 族（部署数据域），且 D 与 R 互不包含；`ProgramArguments` 里的脚本路径、`PANORAMA_CODE_ROOT`、registry `command` 中的脚本路径三者字符串**逐字相等**（跨源一致，替代 5 处 host 字面量）。
3. `PATH` 里的用户本地 bin 由 `Path.home()/".local"/"bin"` 派生，而非 `/Users/xiamingxing/.local/bin` 字面量。

**变异对照**（#4606 的教训：扫源码的检测器必须自证，否则"绿"可能只是根本没命中）：

- 复制真实 payload，把其中一个 R 族值改写到另一个根下 → 派生检查**必须**报不一致；
- 复制真实 job 字典，`reality=installed` 且 `status=proposed` → I2 **必须**拦下；
- 拿真实 registry 文本的一处 job 块，复制其 `reality` 行改写取值 → I3 **必须**点名该重复键（同时反证 `safe_load` 看不见它）。

三个变异用例都从真实文件构造基例再注入违规，因此它们不可能"因基例缺失而空绿"。

**反字面量自锁**：三个测试文件（两个既有的 + 新增的不变式文件）各自断言自己的源码里不出现 `"/Users/"` 字符串。这是"地雷已拆"的持久判据 —— 任何人（含未来的我）再塞回 host 字面量，当场红。

## 4. 基线读数与边界：本 BET 不做什么

基线实跑（本机、未改动前）：

- 两个目标文件：`2 failed, 5 passed`（两条失败都是 `assert job["status"] == "active"` 拿到 `proposed`）。
- 加上邻域 5 个同读 registry 的文件（`tests/test_cron_registry_contract.py`、`test_panorama_launchd_health.py`、`test_scheduler_compile_launchd_plane.py`、`test_agent_cell_semantic_scheduler.py`、`test_reference_cell_direct_local_schedule.py`）：**`3 failed, 18 passed`**。

第 3 条失败**不是本 BET 引入的，也不是本 BET 要修的**：`test_scheduler_compile_launchd_plane.py::test_shadow_segment_never_blocks_the_gate` 在未改动代码上即红，`check_drift()` 返回 `ok=False / drift_count=0 / orphan_count=1`，而该用例断言 crontab 口径必须 `ok is True`。它自己就是 §2 说的"用例直接读本机调度面"的那一类，修它需要独立决定（补 `known_orphans` 还是把它做成 hermetic），**登记为后续 BET，不静默修、不静默 skip**。因此本 BET 的验收只点名选中的用例集，绝不断言"`tests/unit/` 全绿"。

边界：

- **不改 `runtime/cron/**` 任何一个 plist**。改道是 B4b 批次 2，需逐批授权；本 BET 完成后那些 plist 里的 host 根一个不少。
- **不跨面合并登记**。`zhixing-projection-republisher` 实测已加载已装机，`.omo/cron/registry.yaml` 里没有它，而 `services.yaml:6000` 有它（`label` / `entrypoint` / `stdout` 齐全）—— 这不是"漏登记一条"，而是**两个 SSOT 面都在定义 launchd 对象**。实测规模：按 label 数 `services.yaml` 有 27 条 `com.omostation.*`，其中 20 条在 cron registry 里按名找不到对应行；编译器口径的 `undeclared_installed_count` 是 25。裁定归属（哪面是源、哪面是投影）是架构决定，且会覆盖 BET-Y2Q4-T10-223 刚合入的设计 —— 另立 BET。**对 B4b 批次 2 的直接影响必须先说清：只按一个面枚举 plist/cron 对象，会漏掉 20~25 条活着的 job**，那个批次的"43 plist"基线数因此是下界而非真值。
- 不做 18 条 launchd-plane job 的全量逐条审计（只处理上表 3 条能证明的）。其余 `proposed`/`pending` 记录维持原样。
- 不扩 `status`/`reality` 枚举（`bin/scheduler-compile.py` 消费它们）。
- 不新增门禁脚本、不动 `.github/workflows/**`。`tests/unit/**` 不在 CI 白名单（`governance-check.yml:118-127`）里，所以本 BET 的绿**不能**以"CI 绿"为证据，必须以本地 `pytest` 实跑为证据。
- 不装、不卸、不 `launchctl` 任何 job：registry 向实测靠拢，不是实测向 registry 靠拢。
