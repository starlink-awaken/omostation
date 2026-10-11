---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 残留（omo 侧）— src/ 32 处仓根字面量折进单一缝
bet_id: BET-Y2Q4-T10-239
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-10
---

# ADR-0456 残留（omo 侧）— `src/` 32 处仓根字面量折进单一缝

## 1 问题：bin/ 侧折完别名之后，omo 侧成了另一半

BET-Y2Q4-T10-217 把 `bin/` 侧的四个仓根私有别名（`OMOSTATION_WORKSPACE_ROOT` /
`OMO_WORKSPACE_ROOT` / `WORKSPACE_ROOT`×2）折进 ADR-0456 规范名，并把 12 个 import-time
常量改调用时刻解析。该 BET 的扫描范围是 `bin`，判据 `ALIAS-SURVIVORS-3` 也只约束 `bin`。
**`projects/omo/src/**` 从未进入那一轮**，于是两仓现在对同一个概念用两套名字。

实测基线（`origin/main` = omo `d8ca1a2`，2026-10-10 用
`git grep -En 'Path\.home\(\)[[:space:]]*/[[:space:]]*"Workspace"' origin/main -- 'src/**'`
产出，空白不敏感、`git grep` 引擎）：

| 读数 | 值 |
|---|---|
| 仓根字面量站点（行尺） | **32** |
| 涉及文件 | **18** |
| 形状 = 模块级常量（import 时求值） | **10** |
| 形状 = 函数内求值 | **22** |
| 有 env 缝读 `WORKSPACE_ROOT` | **21**（含 `enforcement.py` 的别名调用 `os_environ()`） |
| 读 `OMO_DIR` | **1**（`omo_dashboard.py`） |
| **无任何 env 缝**（纯字面量） | **10** |
| **AST 尺**（行尺 + 行尺结构性漏认的两形） | **34** |

行尺是 `Path\.home\(\)[ \t]*/[ \t]*"Workspace"`，它**按构造看不见两种写法**（实施时实测）：
`omo_observability.py` 的**跨行** home 拼接（一行结尾、下一行接 `/` 操作数），和 `omo_self_healing.py`
的**合并字符串** `Path.home() / "Workspace/projects/omo"`。所以判据用 AST 尺（`BinOp(Div)` 一侧含
`.home()`/`.expanduser()` 锚点、另一侧是 `is_host_literal` 常量；外加 `get/getenv` 的第二实参是 host
字面量或含 home 锚点），**34 → 0**，两把行尺 32 → 0 / 21 → 0 同时断言。

那条 env 缝在本机是**illusory 的**，这是本 BET 的定性依据（三条实测都是 0）：

```
crontab -l | grep -c WORKSPACE_ROOT            → 0
grep -rl WORKSPACE_ROOT ~/Library/LaunchAgents → 0 个文件
python3 -c "'WORKSPACE_ROOT' in os.environ"    → False
```

⇒ 那 21 处 `os.environ.get("WORKSPACE_ROOT", str(Path.home()/"Workspace"))` 在生产里**恒取
host 字面量兜底**；而在 CI 干净检出与非本机安装位（`~/.local/opt/omostation`）上，该兜底指向
一个**不存在的路径**。两类后果各自独立存在：缝名不对（profile 声明不进来），兜底值不对（钉死本机）。

别名面的完整读数（`git grep -c 'WORKSPACE_ROOT"'` on `src/**` = **28**）比字面量面宽，
其中 4 个定义点已经正确、**不在本 BET 射程**：`omo_paths.py:29`（`parents[3]`，即本 BET 要
扩用的锚）、`omo_scene_cli.py:22`（`parents[4]`，已是 `__file__` 反推）、
`mcp_server.py:21-25`（读 env 但兜底走 `_default_workspace_root()`，且 `WORKSPACE_ROOT` 是
对外部 MCP host 的**已发布契约名**）、`omo_audit.py:258`（局部变量赋值，不是 env 读）。
⇒ 判据落在**「读 `WORKSPACE_ROOT` 且默认值是 host 字面量」这一组合 = 21 → 0**，而不是
「全仓禁止 `WORKSPACE_ROOT` 这个名字」。禁止名字会砸掉外部 host 契约，且不解决任何站点。

`omo_paths.py` 已经 ADR-0456 感知 —— `WORKSPACE_ROOT = _MODULE_DIR.parents[3]`（跟随当前检出）、
`STATE_ROOT` / `state_root()`（读 `OMOSTATION_STATE_ROOT`）、`event_ledger_path()`
（`OMO_EVENT_LEDGER_DB` > `state_root()/runtime/omo/...`）、`OMO_ROOT`（检出内 `.omo` 锚）。
**缺的只是没人用它**：这 32 处各自手拼，且没有 `code_root()` 这个与 `state_root()` 对称的调用时刻入口。

## 2 理想状态（可独立证伪的六条）

- **ISC-1 缝存在**：`omo_paths` 暴露 `code_root()`，与 `bin/lib/repo_root.py:code_root()`
  **同语义** —— 跟随当前检出（`__file__` 反推），**不**读 `OMOSTATION_ROOT`。
  *证伪*：若让它读 `OMOSTATION_ROOT`，则与 `repo_root.code_root()` 分叉，且违反 ADR-0456
  「读跟随检出」；`canonical_root()` 才是读 `OMOSTATION_ROOT` 的那个，本 BET 不接它。
  未声明任何 profile env 时 `code_root() == WORKSPACE_ROOT`，逐字节复现历史路径。
- **ISC-2 字面量清零**：三把尺在 `src/**` 上「改前 N / 改后 0」由**同一次扫描**同时产出并断言
  —— 行尺 32 → 0、假缝尺 21 → 0、AST 尺 34 → 0。改前一侧不读 git（PASW 子树可能只有 1 个
  commit，`git show` 不可移植），而由 `tests/unit/omo_src_root_literal_baseline.json` 这份
  自足语料重算。
  *证伪*：只断言 0 → 少认一种形状 + 多认一处合法也能凑绿（AGENTS.md §7⑤）。
- **ISC-3 假缝清零**：`src/**` 里「读 `WORKSPACE_ROOT` **且**默认值含 `Path.home()`」的组合
  由 21 → 0，同一次扫描产出改前/改后两个数；`mcp_server.py:21` 这类「读同名 env 但兜底已是
  `__file__`」的合法形态**不计入**（它没有 host 字面量，判据按组合命中而不是按名字命中）。
  *证伪*：只按名字 `WORKSPACE_ROOT` 计数会把 4 个已正确的定义点也算成缺陷，改后永远到不了 0，
  或逼人为了凑 0 去砸外部 host 契约。
  `OMO_DIR`（`omo_dashboard.py:18`）同理：**保留**它作为显式覆盖名，被禁止的只是它的
  host 字面量默认值 —— 区分「env 名」与「默认值」这两件事。
- **ISC-4 逐字节无效应**：未声明 profile 时，32 个站点的**解析结果**与改前逐字节相同（本机）。
  *证伪*：把某个 `.omo/_knowledge/**` 写者错挂到 `code_root()`、或把读源码的站点错挂到
  `state_root()`，都会在这条上现形 —— 它是唯一能抓「挂错根」的判据，光看绿测试抓不到。
- **ISC-5 正向落点**：声明 `OMOSTATION_STATE_ROOT=<tmp>` 后，被收敛的**写面**站点
  （`omo_trail` / `omo_event` / `omo_sync` / `omo_alert` / `omo_bos_metrics` 的默认路径与
  a2a inbox）解析到 `<tmp>` 之下；`sovereignty/enforcement._default_db_path()` 与
  `event_ledger/surface._default_db_path()` 等于 `omo_paths.event_ledger_path()`。
  *证伪*：只断言「检出不含旧路径」是否定式验收，AGENTS.md §7 明确要求配正向落点断言。
  **ISC-4 对 code/state 互换是盲的**（未声明 profile 时两根相等），所以 ISC-5 不是加分项而是
  承重墙 —— 这一点由变异对照实测钉住（见 §6 第 6 项），不是修辞。
- **ISC-6 检测器自证 + 双 profile 相对基线无回归**：新扫描用例注入合成违规样本必点名它（no-op 反证），
  且 omo 测试面在「未声明 profile」与「声明 dev profile」两种 env 下各跑一遍，
  **相对基线 `d8ca1a2` 无新增失败**；根仓 `make gac-local-gate` **无新增硬失败**。
  *措辞订正*：本条原写「全绿」是动笔前的预期，不是判据 —— 台账 `done_when` 一直是
  「相对基线无回归 / 无新增硬失败」。判据必须比测量装置强，否则一次存量红就把 BET 变成假失败，
  而把断言改窄来迁就装置就是 AGENTS.md §7 禁止的那类「修绿」。读数见 §6 第 3 项。

## 3 站点定性：判据是它拼出什么，不是它在读还是在写

按变量实际用法逐站点判（32 处全列）。下表是**实施后的定案**，站点以符号名指认而不是行号 ——
`ruff format` 与迁移本身都会挪行，行号指针会陈旧（AGENTS.md §7⑥）：

| 目标根 | 站点 | 依据 |
|---|---|---|
| `state_root()` | `omo_trail.default_trail_path()`、`omo_event.default_event_log_path()`、`omo_sync.default_sync_log_path()`、`omo_logs.knowledge_dir()`、`omo_observability.knowledge_dir()`、`omo_alert.alert_log_path()`、`omo_bos_metrics.default_metrics_path()`、`omo_phase16.external_docs()` 的 `workspace` 前缀、`omo_agent_host` 的 `root_state`（a2a inbox / journey-states / MOSBeliefManager） | 拼 `.omo/_knowledge/*.jsonl` 与 `.omo/state/**`（追加写运行态与日志） |
| `code_root()` | `omo_alert.notify_script()`（`projects/runtime/scripts/notify-alerts.sh`）、`omo_bos.kairon_packages_src()` + `omo_bos.default_registry_path()`、`omo_self_healing`（`projects/` 枚举、`cwd=`、`rglob`、`healing_config_path()`）、`omo_state.py` 的 `runtime_root`、`omo_cards.layer_index`（`LAYER-INDEX.md`）、`omo_observability._execution_log_path()`、`omo_agent_host` 的 `root_code`（`projects/omo/src`） | 读检出内源码/脚本/仓根文件；`bos-registry.json` 虽落在 `.omo/_knowledge/` 下，但它**已跟踪 + 由 `bin/ssot/sync-bos-registry.py` 再生 + 被 CI 校验**，属读面不属运行态 |
| `event_ledger_path()` | `sovereignty/enforcement._default_db_path()`、`event_ledger/surface._default_db_path()` | 两处 `runtime/omo/event-ledger.sqlite3` 字面分叉，`omo_paths` 已有同名缝（`OMO_EVENT_LEDGER_DB` 优先） |
| 拆成两个局部 | `omo_agent_host.py` 原先的 6 处单一 `workspace` | 同一个变量同时喂 `.omo/state/a2a-messages.jsonl`（state）与 `projects/omo/src`（code）；一处变量两属 = 必拆，现拆为 `root_state` / `root_code` |
| 经既有 helper / 保留对外 env 名 | `cli.py` 两处（`WORKSPACE_ROOT` 名保留，**默认值**换成 `code_root()`）、`omo_dashboard.OMO_DIR`（env 名保留，默认换成 `OMO_ROOT`）、`omo_self_healing.omo_project_root()`（`OMO_ROOT` 名保留）、`omo_agent_host` 的 `system_health.yaml` → `projection_path()`、`omo_cards` 的检出内 `.omo` 治理锚 → `OMO_ROOT`、`omo_state` → `find_omo_dir()` | 已登记的投影/锚点由 helper 决定落在哪个根；手拼会绕过 `system_yaml_read()` 与 `projection_path()` 的 canonical/legacy 双语义 |
| 不经本轮三根 | `workflow/delivery_anchor.py` 的 `MARKER` 探针 | 该站点不折进 `code_root()`：实施改为从 `ws/.git` 的 **`gitdir:` 指针** + `MARKER` 校验推出**拥有该 worktree 的检出根**，因此 worktree/子树布局下都成立，而不假设「omo 目录往上第 N 层就是仓根」 |

**两处与 §3 初稿的定性差（实施时按证据改判，记录在此而不是悄悄偏离）**：
① `omo_bos.py` 的两个站点初稿都挂在 `state_root()`，实测一个读 kairon 源码、一个读**已跟踪且由
sync 再生**的 registry，两个都归 `code_root()`；② `omo_observability.py` 初稿当一个站点，实际是
两个动作 —— `knowledge_dir()` 写面走 state，`_execution_log_path()` 读面走 code。

**混合面是本 BET 的真实风险**：`omo_logs.knowledge_dir()` / `omo_observability.knowledge_dir()`
既读已跟踪内容（`_knowledge/decisions/**`）又被追加写日志；`omo_cards` 的两处 `.omo` 是
**检出内已跟踪治理面**（ADR、retro 都从这里读），不是运行态。判据：**按每个消费者的实际动作
分别挂根**，不为「目录名统一」而统一 —— 把读已跟踪内容的站点挂到 state 根，会让 dev profile
读到一个空目录，而且**没有任何测试会红**（BET-Y2Q4-T10-238 第 9 条同族：绿不等于对）。

## 4 测试侧缝的连带面（实测 16 处，逐处判归属）

探测（`git grep -nE '"WORKSPACE_ROOT"' origin/main -- 'tests/**'`）命中 **16** 处，
另加 `setattr(…, "_WORKSPACE", …)` **1** 处（`tests/test_omo_logs_baseline.py:40`）。
逐处对表，不整体替换。⚠️ 下表行号是**改前基线 `d8ca1a2` 的坐标**，不是现值 —— 迁完之后
用符号名（模块 + 用例名）定位（AGENTS.md §7⑥）：

| 归属 | 处数 | 位置 | 处置 |
|---|---|---|---|
| 模块**自有** `WORKSPACE_ROOT` 常量，不在 32 站点内 | **10** | `test_mcp_server.py:20,26,44`、`test_mos_closed_loop.py:450`、`test_omo_capability_registry.py:52,101,150,153`、`test_omo_doctor_path_acl.py:21,34` | 不动。`mcp_server.py` / `omo_capability` / `omo_phase14` / `omo_doctor` 自己定义该属性，本 BET 不改它们的 env 名 |
| 注入到**本轮要迁走的站点** | **5** | `test_event_ledger_jsonl.py:398`、`test_event_ledger_snapshot.py:383`、`test_event_ledger_surface.py:44`（→ `event_ledger/surface.py:41`）、`test_omo_agent_host.py:178`（→ a2a inbox）、`test_sovereignty_replay.py:40`（→ `enforcement.py:119`） | 换规范通道：台账面改 `OMO_EVENT_LEDGER_DB`，a2a inbox 改 `OMOSTATION_STATE_ROOT`。**这不是可选优化** —— 迁走 env 读之后仍注入旧名，测试会静默回到 host 兜底，那正是「假绿」的形状 |
| setattr 缝锚在模块级常量上 | **1** | `test_omo_logs_baseline.py:40` | 站点改调用时刻后 `_WORKSPACE` 不再是取值入口；改 patch 缝函数或声明 `OMOSTATION_STATE_ROOT` |
| 语义是「清屏」不是「注入」 | **1** | `test_workflow_claims_authority_bridge.py:308`（parametrize 名字列表含 `WORKSPACE_ROOT`） | 保留该名字在剔除列表里即可，无需改动 |

判据：对每个动过的模块跑「模块级赋值名 vs 模块内 Load 名」差集，并与 `origin/main` 逐条对拍
（AGENTS.md §7「把常量改成函数会打断测试侧的 setattr 缝」）。

## 5 范围边界（明确不做）

- 不改 `bin/**`（T10-217 已收）；不改 `repo_root.py` 的解析序。
- **不**在本轮声明任何 profile、**不**启停服务、**不**动 plist/cron（那是 B4b，逐批授权）。
  本 BET 只交机制：未声明 profile 时对今天的运行态无效应（ISC-4 钉住）。
- **不**把 `WORKSPACE_ROOT` env 从 ecos 侧删掉（`ecos-ci.yml:48,59` 仍为 `projects/ecos` 注入它，
  那是另一个仓的公开 env 面）。omo 侧停止读它 ≠ 全仓禁止它。
- 不动 `RUNTIME_HOME` / `USER` 的 5+4 处 env 读 —— 它们不是仓根锚点，纳入**写面改道**会稀释判据。
  （它们中的 `RUNTIME_HOME` 只进「测试隔离名单」`PROFILE_ENVS`：fixture 把它 delenv 是为了
  读数不受 host 影响，**不改**它的落点，也不把它挂到三根上。）

### 5.1 实施后仍存在的邻近面（逐条实测在册，不在本轮修，也不假装为 0）

| 残余项 | 实测位置 | 为什么不在本轮 |
|---|---|---|
| **另一种 host 锚**：`account_home / "Workspace"` ×**2** | `workflow/claims_authority.py` 与 `workflow/lifecycle.py` 各一处；`account_home = Path(pwd.getpwuid(os.getuid()).pw_dir)` | **这是三把尺都结构性看不见的一类形状** —— AST 尺的锚点判据是「操作数子树含 `.home()`/`.expanduser()` Call」，而这里的 host 锚是 `pwd.getpwuid().pw_dir`。它是权威 broker 的机器级路径，改动面属 claims-authority 那一轮；本轮把它记为检测器的已知盲区，不记为「已清零」 |
| **import-time 派生常量**仍在 | `omo_paths.py` 的 `STATE_ROOT`、`RUNTIME_OMO_ROOT = STATE_ROOT / "runtime" / "omo"`（其下再派生 `RUNTIME_DELIVERY_DIR` / `_CONTROL_DIR` / `CHANGE_LOG_DIR`）；`projection_path()` 的 canonical 侧按 docstring 落在 `STATE_ROOT` | 与 BET-Y2Q4-T10-232 同族（写路径应在调用时刻解析）。本轮只新增 `code_root()` 并迁 32 处字面量；把这些常量函数化会打断 `monkeypatch.setattr` 侧的测试缝，属独立一轮 |
| 模块自有同名常量作默认值 | `omo_belief.MOSBeliefManager.__init__` 的 `root or WORKSPACE_ROOT`（`bin/ssot/` 4 处 `MOSBeliefManager(root=ROOT)` 是消费侧） | 平面归属本就正确（`WORKSPACE_ROOT` 是 `__file__` 反推，不是 host 字面量），只是时间冻结；`bin/**` 属 T10-217 射程之外 |
| 测试侧固定深度反推仓根 | `tests/conftest.py:28` / `tests/test_mcp_server.py:13`（PASW 布局下解析到 `.subtrees`，非仓根）与 `tests/integration/conftest.py:15` / `test_real_scenario.py:23-24`（同一 `parents[3]` 在此布局下恰好解析到 omo 仓根，而在 `projects/omo` 布局下不是） | 实测：同一个「parents[3]」在不同文件深度与不同检出布局下含义不同。它们不产 host 字面量，所以不命中三把尺；属独立一轮（改为经 `omo_paths` 的 resolver 取根） |
| 检出内 `.omo/_delivery` 锚 | `omo_sse_daemon.py` 的 `DAEMON_PID_FILE` / `DAEMON_LOG_FILE` | 不是缺陷：`_delivery` 是全机共享的 symlink 协调面（AGENTS.md §7），落在检出侧正是它的语义 |
| **单例重置打空**：四处 `bridge._MANAGER = None` 改的是 facade 的**再导出别名**，真单例在别处 | `tests/integration/test_bos_4uri_concurrent.py:49/:75/:96` 与 `test_bos_40_uri_smoke.py:180`；真单例是 `omo_agora_pool.py:23` 的模块级 `_MANAGER`（`acquire()` 在 `:174` 取它的 `asyncio.Lock`），而 `omo_llm_bos_bridge.py:45` 是 `from … import _MANAGER` 的**值绑定** ⇒ 这四个赋值按构造不可能命中被测路径 | 实测（子树面 `.subtrees/omo`，同一棵树 `5befe6ad`、同一 env 未声明 profile，全量跑 3 次）：一次 0 红、两次各 1 红且**红的是不同用例**（`test_4uri_serial_vs_concurrent_speedup` / `test_engineering_delivery_consumer.py::test_query_only_shadow_observer_rejects_a_fifo_without_blocking_or_writing`）；单跑 4uri 文件 1 passed / 2 skipped（6.79s），smoke+4uri 配对 4 passed / 2 skipped（308s）⇒ 泄漏来自更大 session 上下文的 teardown，不是这两个文件互相污染，也不是确定性的仓根缺陷。修它要动别人名下的集成用例且**当前没有最小复现**，无复现的修复无法验证 ⇒ 记为独立一轮，本轮不据此声称「子树面全绿」 |
| **隔离名单 14 名中有 7 名是哨兵探针抽样不到的** | `RUNTIME_HOME`（5 处）、`AGORA_METRICS_DB`、`OMO_EXTERNAL_ROOT`、`EXECUTION_LOG`、`OMO_PATH_ACL_PROFILE`、`WORKSPACE_CODE_ROOT`、`OMOSTATION_ROOT` —— 逐站点见 `omo_paths.PROFILE_ENVS` 的行内注释 | 探针只能喂它抽样到的 28 个解析器，于是 `EXECUTION_LOG`（`omo_observability.py:46`）与 `RUNTIME_HOME` 那 5 处读数都是「不动」，实际形状都是 `Path(os.environ.get(...))`。AST 判据（§6 第 9 条）比抽样宽，名单随之从 4 名 → 14 名。注意这 7 名的**落点**不在本轮改道范围内，进名单只为了 fixture 清得干净 |

## 6 完成判据（可执行）

1. ISC-2/ISC-3 的扫描用例在 `projects/omo/tests/` 落地且首跑必绿（不靠豁免清单凑 0）。
2. ISC-4/ISC-5 两条各有一个用例：前者逐字节比对改前/改后解析值，后者正向断言 `<tmp>` 落点。
3. omo 测试面双 profile **相对基线无新增失败**；根仓 `make gac-local-gate` **无新增硬失败**。
   实测（同一目录 `projects/omo`、同一命令 `uv run --no-sync pytest tests/ -q`、串行跑避免互相污染）：
   基线 `d8ca1a2` 未声明 profile ⇒ **0 failed**（3009 passed / 216 skipped / 678.07s）；
   终态 `5befe6ad` 未声明 profile ⇒ **0 failed**（3045 passed / 216 skipped / 560.26s）；
   终态 `5befe6ad` 声明 dev profile（`OMOSTATION_STATE_ROOT=~/.local/state/omostation/dev`）
   ⇒ **0 failed**（3045 / 216 / 536.39s）。采集数 +36 是本轮新增用例，两个 profile 下都不构成失败。
   另一面同样在册：子树面 `.subtrees/omo` 基线是 **10 failed**（`test_bos_40_uri_smoke.py` ×3 +
   `test_bos_domain_chain.py` ×7，全是 `parents[3]` 反推到 `.subtrees` 的仓根缺陷 —— 即本轮要修的那个），
   终态同一面这 10 条全绿，剩 §5.1「单例重置打空」那条会话级 flake（同树同 env 三次读数：0/1/1 红且不是同一条）。
   根仓 `make gac-local-gate` 两次跑（`/tmp/t10239_gate.log`、`/tmp/t10239_gate2.log`，均 EXIT=2）
   读数一致：`[FAIL] service-config-drift` + `[FAIL] check-work-landed` + `2 SOFT WARN`，逐条定性如下 ——
   **两条都不是本轮新增**，但定性方式不同：
   ① `service-config-drift`（`bin/mof/gen-service-configs.py --check`，`gac-local-gate.py:204` 标 `ci_skip: True`
   ⇒ CI 看不到它）：`rc=1`，逐字打印一条 `com.omostation.zhixing-projection-fullrefresh: plist 与 services.yaml 不一致`；
   **同一命令在主工作区（不含本 lane）跑出逐字节相同的 `rc=1` 与同一条 drift**（`/tmp/t10239_drift_main.out` vs
   `/tmp/t10239_drift_lane.out`），且本 lane 未碰 `config/**` 与任何 plist ⇒ 它是 host 级 LaunchAgent 漂移，
   修它需 `gen-service-configs.py --write` + LaunchAgent 重载（用户授权面，任务 #97/#91 同族）。
   ② `check-work-landed`：门禁 FAIL 的是**计时装置**，不是内容 —— 直跑 `bin/gac/check-work-landed.py`
   得 `rc=0`、打印 `check-work-landed: PASS / closed=106 settled=71 no_ref=32 warn=3 blocking=0`，
   耗时 54.0s 与 60.1s 两次读数都超 `gac-local-gate.py:251` 的 `"timeout": 45`（该文件不在本 lane diff 里）。
   ⚠️ 但**这台机器此刻有并发污染**：另一会话在主工作区跑 `pytest -q` 已 2h22m（PID 89943），
   还带 3 个挂死的 `swarm-git rebase origin/main` 子进程（PID 67913-67915），所以 54/60s 是**负载下读数**，
   不能据此断言 45s 上限结构性偏小 —— 只能说「在无负载复测前，该 FAIL 是内容 PASS 被计时杀掉」。
   该 cap 未登记 `gate-known-debt.yaml`（`grep` 零命中），属未登记的债 ⇒ 记为独立一轮，本轮不放宽 cap、不改判据。
4. gitlink bump 经 `bin/ssot/submodule-pointer-transaction.sh`，根仓 PR CI 全绿后 squash 合并。
   **本轮该脚本结构性不可用（实测，不是绕门禁）**，三条读数：
   - 默认基线走 `:47` 的 `upstream/main` 优先分支，而本机有一个**孤儿 ref**
     `refs/remotes/upstream/main` = `6330e8202`（`git remote -v` 里根本没有 `upstream`）。
     它比 HEAD 的 `.gitmodules` 少 50 行（`git diff --numstat HEAD refs/remotes/upstream/main -- .gitmodules`
     ⇒ `0 50`），于是 `:69` 的安全 bail 命中：打印
     `.gitmodules changed; incremental staging is unsafe (rerun with --all)`，**真实 rc=2**
     （无管道复测拿到 2；套 `| tail` 时 `$?` 是 tail 的 0 —— zsh 里 `${PIPESTATUS[0]}` 恒空）。
     对面 `git diff --stat HEAD origin/main -- .gitmodules` **为空** ⇒ 触发的是 ref 陈旧，不是真实治理面变化。
   - 换 `--changed-from origin/main --dry-run`：`统计: 待push=0 失败=0 无上游=0 缺失=16` +
     `submodule-reachability: PASS (0 gitlinks, ...)` ⇒ 可暂存集为空。原因是**上游已自行 bump 到同一值**
     （base `75cb6f5bf` 的 `projects/omo` = `d8ca1a250`，`origin/main` = `5befe6ad7` = 本分支 HEAD），
     而脚本按 `git diff --quiet <base> -- <path>` 判差异，所以结构上**造不出**「分支记录的指针落后于上游现值」
     这一形态的 bump commit。该形态仍必须落到分支上：`governance-verify` 检出 PR **head tree**
     （`governance-check.yml:176`），head 上没有这个 gitlink，`verify-omo.sh [4/5]` 的文件表就解析不到。
   - `--all` 会 stage 全部 16 个子模块（含另一会话未提交的 `projects/knowledge/kairon`），**不用**；
     非 dry 路径 `:113` 的 `sync-submodules-push.sh` 会真推子模块，**不跑**。
   - **替代做法**：只手工执行该脚本 `:120-137` 的校验语义（不含 push），提交后仍可用无副作用的形式复现：
     `python3 bin/change-lane-check.py --file projects/omo` ⇒ `PASS (1 files, lanes=submodule_pointer)` rc=0；
     `python3 bin/ssot/submodule-reachability-gate.py --source worktree --require-main --changed-from 75cb6f5bf`
     ⇒ `PASS (1 gitlinks, source=worktree, mode=changed-from 75cb6f5bf)` rc=0。单 lane、零生成态、零他人 gitlink。
   - 孤儿 `upstream` ref 是全机共享面（这台机器上每个 agent 的 pointer transaction 都会同样 bail），
     属他人状态 ⇒ **本轮不删**，作为待授权项上报。
   - **push 时该 gitlink 又被上游反超（同日二次实测）**：`git fetch origin main` 后
     `origin/main:projects/omo` = `e8c7aa0ed`（omo #211，`EMBED_NODE_URL` 改 MagicDNS 名），
     本分支仍记 `5befe6ad` ⇒ pre-push `gitlink-ancestry` 判为**指针回退**并阻断（push rc=1，
     同批还打出 `submodule-reachability` 129s 慢读数）。处置走**前进**不走豁免标签：
     `git -C projects/omo checkout e8c7aa0ed002` + 单独 commit（`83667fcd8`），三条前置判据 ——
     `merge-base --is-ancestor 5befe6ad7530 e8c7aa0ed002` 为真（中间只这 1 个 commit，与本 BET 面无关）、
     三个新检测器用例在 `e8c7aa0ed` 上 `git cat-file -e` 逐个 PRESENT、`omo_paths.code_root()` 存在。
     不打 `[gitlink-regress: …]`：那会把别人的前进登记成自己的债，而 `gate-known-debt.yaml`
     是 `shrink_only` 面，只增不减。该 worktree 的 `projects/omo` 实测
     `--is-shallow-repository=false` ⇒ ancestry 判据在此有意义（§6 worktree 深浅取决于 claim 路径，
     1-commit 检出里这类判据无意义）。
   - **台账面与上游相撞（同一 push 前置窗口实测）**：`git merge-tree --write-tree --name-only
     origin/main HEAD` rc=1，唯一冲突文件是 `docs/plans/3y-bet-ledger.yaml`。上游 #4706（T10-240 收口包）
     改写了 `bets:` 段尾（`@@ -41618,3 +41636,3 @@` ⇒ `overall_state: evaluating → delivery_accepted`
     与 engineering `status: NOT_STARTED → VERIFIED`），而本 BET 的 135 行条目插在紧邻的下一行
     （`@@ -41619,0 +41620,135 @@`）—— 两侧都碰同一段尾，所以「只改文档就必然与上游无交集」的假设在这里不成立。
     **处置不用 merge/rebase/pull 吸收上游**（本仓 §6 禁止），改为「上游字节为底 + 我的条目逐字重放」。
     **但「逐字采纳上游字节」本身不消冲突**（一次错误假设，实测否证）：插在 `bets:` 段末后复探
     `git merge-tree --write-tree --name-only origin/main HEAD` 仍 **rc=1**（tree `cae25c8a8`，
     冲突 blob 42283 行），且**不是**一个冲突区而是两个 —— 标记行 `41627 <<<<<<< / 41628 ||||||| /
     41631 ======= / 41771 >>>>>>>` 与 `41782 / 41784 / 41786 / 41788`。
     用 `difflib` 对 base(`75cb6f5bf`)→origin/main 逐行取改动区间才看清根因：上游在 `bets:` 段的
     改动区间是 **main 41611-41626、41629-41633、41637**（即最后一行也在改），而 `--show-bounds`
     给的 `insert before 1-based line 41638` 紧贴其下；再加上我的条目**尾部三行与 T10-240 的尾部
     逐字相同**（`      value:` / `        status: NOT_PROVEN` / `        evidence: {}`），xdiff 把我的
     条目对齐到 T10-240 的尾部上，于是把一处纯插入拆成两个内容冲突区。
     **改插上游未触碰位**：`- id: BET-Y2Q4-T10-240`（main 41555）之前，距上游首条改动行 56 行。
     这是对 `ledger-safe-insert.py` `:213-218`「插入后须为 `bets:` 末条」断言的**刻意偏离** ——
     那条是 append-only 纪律而非 schema 约束；此处为消除段尾重叠改插 T10-240 之前，
     id 数值序反而归位（`[... T10-238, T10-16-03, T10-239, T10-240]`）。写出仍逐字插入，因为该工具
     `:199-202` 会把条目 `format_entry_as_list_item()` 重新 dump，逐字面会漂移 ——
     **只用它的定界与校验语义，不用它的写出**。
     `meta.total_bets` 按该工具 `:220-230` 的纪律由插入后 `len(bets)` **绝对派生**（537→538，禁止 old+1）；
     该行在 base 与 main 都是 537 ⇒ 只有我这侧改，结构上不可能进冲突区。
     五条复核读数：`bets=538 == total_bets=538`、id 集合无重复、`BET-Y2Q4-T10-240` 的 83 行块与上游
     **逐字节相等**（含它新写入的 `overall_state: delivery_accepted`）⇒ 无回流、无反向删除；
     行数增量恰 135（`rebuilt 42267 − origin/main 42132 = 135`，插入位改变不影响增量）；
     `git diff --numstat origin/main -- docs/plans/3y-bet-ledger.yaml` = `136 1`（135 行条目 + 1 行 meta）。
     判据：该 numstat 里出现任何「删掉上游既有内容」的形态即按 PITFALL-COO-005 立即回退。
     **终态读数**（commit `662d5f0d4`）：`git merge-tree --write-tree --name-only origin/main HEAD`
     **rc=0**，merged tree `704776348`；对 merged blob 直接跑结构契约 ⇒ `len(bets)=538 ==
     declared total_bets=538`、id 唯一、T10-240 `engineering.status=VERIFIED`（上游那半边在合并后
     仍在）、T10-239 在位、`<<<<<<<`/`>>>>>>>` 零命中。判据：合并**干净**不等于**内容对** ——
     rc=0 只说明没有重叠，仍要解析 merged tree 的 blob 数两侧条目，否则「上游把我的插入吃掉了」
     这类自动合并结果也是 rc=0。
5. `bet-ledger.py complete BET-Y2Q4-T10-239` 通过（evidence matrix + `merged_reachable_commit`
   **须含终态** —— 判据见 BET-Y2Q4-T10-238 第 9 条：可达 ≠ 含终态，用
   `git show <sha>:<path>` 数站点，不数 `^def test_`）。
6. **变异对照（ISC-6 的 no-op 反证，一次性脚本不落仓）**：五个变异各自的读数必须是 ——
   把写者错挂 `code_root()` ⇒ ISC-5 红；**同一挂法在未声明 profile 下 ⇒ ISC-4 必须仍然绿**
   （这条不是失败，是 ISC-5 承重的证明）；把台账尾段打错一个字母 ⇒ ISC-4 红并点名站点；
   让 `code_root()` 读 `OMOSTATION_ROOT` ⇒ ISC-1 红；把台账两个分叉站点退回检出根 ⇒ ISC-5 红。
   实测 5/5 符合要求（`/tmp/t10239_mutation_probe.py`，2026-10-10）。
7. **检测器进 CI 白名单**：三个新用例（scan / parity / plane）追加到
   `bin/ssot/verify-omo.sh` `[4/5]` 的显式文件表 —— 该表是 `make governance-verify`
   （governance-check.yml 的 "Run full governance verification" step）唯一跑到 `projects/omo/tests/**` 的地方，`omo/tests/unit/**`
   不在任何 CI 白名单里，不点名则「CI 绿」只是本地证据。gitlink 必须先指到含这三个文件的
   omo 提交，否则白名单里的文件不存在会让该 step 直接红。
   实测：`[4/5]` 表 10 项（7 存量 + 3 新增），10/10 在 gitlink 目标 `5befe6ad` 上
   `git cat-file -e HEAD:<file>` 全命中（2026-10-10）—— 先 bump 再接线，顺序不可反。
   同轮接线的根侧 step（`governance-check.yml` 新增 `pytest tests/unit/test_delivery_anchor_contract.py`）
   不能只在开发机的全量 venv 里绿 —— 它跑的那个 job 只 `pip install pyyaml pydantic pytest`
   （`governance-check.yml:217`）。实测按 CI 的依赖面复刻：`uv run --no-project --with pyyaml --with pydantic
   --with pytest` + `HOME=<空目录>` + `env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB`
   ⇒ 两次都 **11 passed**（0.61s / 1.66s）。该用例自带 `sys.path.insert(projects/omo/src)`，
   所以它依赖的是「recursive submodule 检出」而非「装好的 omo 包」—— 这正是它敢进白名单的前提。
   反向记账：`bet-ledger.py verify BET-Y2Q4-T10-239` 在未提交 gitlink 时把三个新用例报为
   `[未入库] absent from pinned gitlink: projects/omo@d8ca1a2505d1` —— 该读数即「指针还没落地」的
   可执行判别量，bump 提交后应转 `[OK]`。
8. **改动文件面的两把 lint 尺**：`projects/omo/.github/workflows/ci.yml` 只对 `$changed_py`
   跑 `ruff check --select I` 与 `ruff format --check`，因此本轮动过的全部 `.py`（39 个）
   两个都必须绿；其中 `tests/test_omo_bos.py` 的 import 序是**改前就红**的存量，但该文件在本轮
   改动集内，CI 照样会拦（PITFALL-COO-004），所以顺手一并修。
   实测（真通道，不是本地代理读数）：omo PR #210 的 `lint` job 即 ci.yml:27-28 这两把尺，
   在合并提交上 `pass 10s`（`gh pr checks 210`，2026-10-10）。
9. **隔离名单由源码对拍，且反基线三个形状全灭**：名单唯一来源是 `omo_paths.PROFILE_ENVS`，
   `test_profile_env_roster_equals_the_derived_path_override_face` 用 AST 从 `src/**` 重导出
   「env 值进路径语境」的名字集合对（双向：漏一名红、留死名也红）。尺自身由两条用例反证
   （注入一条 `Path(os.environ.get(...))` 必须被点名、`int(...)`/URL/开关不得被算进来；
   `_vendored` 在含/不含两种口径下读数不同），实测 11 passed。变异对照（一次性脚本，不落仓）：
   本轮之前的三份手抄名单形状 —— parity 侧 7 名、plane 侧 6 名（**都缺 `OMOSTATION_STATE_ROOT`
   或它的同伴**）、今晨的 4 名版 —— 全部被该用例杀死（3/3）。这条判据的起因是一次真实失败：
   dev profile 全量跑 `1 failed / 3040 passed`，红的不是生产代码而是两份测试各抄一份名单。

## 7 回滚

改动分两侧且互不依赖：omo 侧回滚 = revert omo 提交并把 gitlink 退回 `d8ca1a2`；
根仓侧回滚 = revert 检测器用例。两侧都未声明 profile，因此回滚不影响任何在跑服务；
`OMO_DIR` 的显式覆盖语义保留，外部调用方不破。
