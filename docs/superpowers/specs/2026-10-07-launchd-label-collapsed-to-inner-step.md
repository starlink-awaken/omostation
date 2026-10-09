---
schema_version: specification/v1
spec_version: 1.0.0
title: 机器级 launchd 的一个 label 被改成「包装器的子进程」—— service-config-drift 的真实成因与裁定归属
bet_id: BET-Y2Q4-T10-237
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-07
---

# G8 的镜像面：注册在案、机器上也装着，但装的是另一回事

## 1 触发（2026-10-07 实测，非引用）

BET-Y2Q4-T10-235 收尾复跑 `make gac-local-gate` 时由 `PASS` 转 `FAIL`，唯一 hard fail 是
`service-config-drift`（`python3 bin/mof/gen-service-configs.py --check` → rc=1，1 条）：

```
❌ 1 drift:
  - com.omostation.zhixing-projection-fullrefresh: plist 与 services.yaml 不一致 (drift)
```

三条读数把它定性成 **host 面、不由该交付引入**：① 该检查在 `bin/gac/gac-local-gate.py:198-205`
带 `ci_skip: True`，属 T10-235 receipt §4.1 量出的「本机 strict 才执行」的 7 条面 ⇒ 对 PR 的 CI 判定零影响；
② `git diff HEAD origin/main -- .omo/_truth/registry/services.yaml bin/mof/gen-service-configs.py`
**空输出**（fetch 后实测）⇒ 真源与生成器一行未动，也不是分支落后；③ 漂移两侧不是「字段不同」而是
「不是同一个服务」——见 §2。

## 2 两侧读数：声明的是 driver，装的是 driver 的第 3 步

声明侧（`.omo/_truth/registry/services.yaml:6022` 起，`id: omostation.zhixing-projection-fullrefresh`，
BET-Y2Q4-T10-227 引入）：

| 要素 | 声明值 |
|---|---|
| `program.entrypoint` | `bin/panorama/projection-full-refresh.py` |
| `trigger` / `interval_sec` | `interval` / **21600**（6h） |
| `generate` | `true` |
| `env` | 未声明 |

已安装侧（`~/Library/LaunchAgents/com.omostation.zhixing-projection-fullrefresh.plist`，
mtime `2026-10-07T23:34:35`，恰在本轮两次门禁之间）：

```
ProgramArguments: [<python3.14>, '-B', '/Users/xiamingxing/.local/opt/omostation-publisher/bin/panorama/panorama-collect.py', '--json']
StartInterval: 180
WorkingDirectory: /Users/xiamingxing/.local/opt/omostation-publisher
EnvironmentVariables: PANORAMA_ROOT / PANORAMA_CODE_ROOT / OMOSTATION_ROOT / OMOSTATION_STATE_ROOT
                      = ~/.local/opt/omostation-publisher
                      ZHIXING_DASHBOARD_STATE_ROOT = ~/.local/share/zhixing-dashboard
                      ZHIXING_DASHBOARD_CODE_ROOT  = ~/.local/share/zhixing-dashboard-runtime-clean-20261008
                      OMO_EVENT_LEDGER_DB          = /Users/xiamingxing/Workspace/runtime/omo/event-ledger.sqlite3
                      OMO_MANAGED_PYTHON, PYTHONDONTWRITEBYTECODE
```

`bin/panorama/projection-full-refresh.py::main()` 的真实步骤是：**0)** `flock` 防重入
（`LOCK_PATH = revisions/.fullrefresh.lock`）→ **1)** 专用检出存在性 + **remote 卫生校验**
（`EXPECTED_ORIGIN_SUFFIX = starlink-awaken/omostation.git`）→ **2)** `fetch` /
`reset --hard origin/main` / `clean -fdx` / 浅子模块对齐 → **3)** 以 `env`（`PANORAMA_ROOT` /
`PANORAMA_CODE_ROOT` / `ZHIXING_DASHBOARD_STATE_ROOT` / `OMO_EVENT_LEDGER_DB` /
`ZHIXING_DASHBOARD_CODE_ROOT`，`:106-111`）为检出内 `panorama-collect.py` 发布。

⇒ 本机那份是**把第 3 步的 subprocess 直接提成 label**，并把它当时的 env 快照冻结进 plist：
0–2 步（防重入、remote 卫生、与 `origin/main` 对齐）在调度路径上**整体消失**，频率 6h → 3min
（720 次/天）。且 env 里 `ZHIXING_DASHBOARD_CODE_ROOT` 指向一个**带今天日期**的
`…-runtime-clean-20261008`，而 driver 计算的是 `str(DEPLOY_DIR)`（`= ~/.local/share/zhixing-dashboard`，
`:111`）⇒ 它连「复制粘贴 driver 的 env」都不是，是一份每天在变的临时面被固化进了机器级配置。

## 3 没有任何仓库装置能产出这份 plist（装置与读数）

| 探测 | 读数 |
|---|---|
| `gen_launchd_plist(svc)` 的内存产物 vs 盘上文件 `unified_diff`（同一棵检出、同一份注册表，只读不落盘） | **63 行**差异；生成的 `ProgramArguments` 是 `[<python3>, /Users/…/Workspace/bin/panorama/projection-full-refresh.py]`、`StartInterval 21600`，**不含** `-B` / `--json` / `WorkingDirectory` / `EnvironmentVariables` |
| **缩进指纹**（同一个 label 的两侧） | 盘上 **tab 缩进 40 行 / 4 空格 0 行**，生成侧 **tab 0 / 4 空格 15** ⇒ 结构上不是这台装置写的 |
| 全注册表 371 条服务扫描（`yaml.safe_load_all`，取第 2 个 doc 的 `services`） | 没有任何一条声明 `interval_sec` ∈ {180, 240}；`omostation.zhixing-projection-republisher` 是 480 |
| 声明 `panorama-collect.py` 的条目 | 只有 `omostation.panorama-dashboard-refresh`，它 `generate: false` 且 entrypoint 是**另一个**路径 `~/.local/share/zhixing-dashboard/panorama-collect.py` |
| 仓内 `Library/LaunchAgents` 写入点（全仓 Grep） | 只有 `gen-service-configs.py:691`、`runtime/cron/install-foundry-cron.sh`、`bin/gac/documents-jobs-scheduler.py`、`projects/omlxc/.../launchd.py`；无一命中该 label。`OMO_MANAGED_PYTHON` 在仓内只被 `bin/gac/managed-python:115` **读**，没有任何装置把它**写进 plist** |
| `launchctl list` | 该 label **PID 24697 正在跑**，`com.omostation.panorama-dashboard-refresh` PID 23373 同时在跑；`~/.local/log/projection-fullrefresh.log` 在两次相隔 3 分钟的读取里 `projection_revision` 从 `466002b9…` 变成 `fd1e3834…`，`out` 恒为 `~/.local/share/zhixing-dashboard/current-revision.json` ⇒ 它不是「装了没跑」，是**按 3 分钟节奏真实发布** |

⇒ 结论：盘上那份由**仓外的一次机器级写**产生（与该 label 的注册 PR #4636/#4638 之后的 panorama/dashboard 线一致，
近例见 `#4619` 「launchd 注册」）。这不是「注册表落后于现实」，是**现实被绕开注册表改过**。

## 4 与 G8、与 ADR-0456 的关系

- **G8**（`morning-brief` 注册在案、机器上从未安装）是「有声明、无实体」；本轮是「有实体、实体说的不是声明」。
  两面合起来才是 launchd 现实面的完整失败模式，所以 T10-237 与 G8 **不能并成一条**。
- **第三个安装位要精确措辞**：`~/.local/opt/omostation-publisher` **不是未登记**——它就写在该 label 的
  `notes` 里（「维护专用洁净检出 `~/.local/opt/omostation-publisher`…机器属主，不进 ws-* 卫生面」），
  也是 driver 的 `CHECKOUT` 默认值（env seam `OMOSTATION_PUBLISHER_CHECKOUT`）。
  缺的是它在 **ADR-0456 的根词汇**里没有位置：`repo_root.install_root()` 只认
  `~/.local/opt/omostation`（B4a），而这份 plist 把 `OMOSTATION_ROOT` 与 `OMOSTATION_STATE_ROOT`
  **双双**指向 publisher ⇒ 一个跑在 profile env 下的进程，其 `state_root()` 落在一个 ADR 未定义的位置，
  同时 `OMO_EVENT_LEDGER_DB` 又回指 `Workspace/runtime/omo/event-ledger.sqlite3`。
  ⇒ 这才是本 BET 对计划的真实贡献：**双根契约在机器级进程里被部分采用、部分绕过**。

## 5 判据

I1 **归属先于修复（本 BET 的主判据）**：该 label 的最终形态必须有**署名裁定**——
driver（sync+publish, 6h）或 collector-only（3min）二选一，裁定人写进
`.omo/_truth/registry/services.yaml` 该条的 `notes`/`owner` 或本 BET 的 receipt。
判据是「能指认到人」，不是「本机读数和注册表一致了」——后者可以由改窄注册表达成。

I2 **绿必须由对齐取得**：`python3 bin/mof/gen-service-configs.py --check` rc=0 且 `drift_count=0`，
同时 `git diff origin/main -- bin/mof/gen-service-configs.py` **为空**。
装置改判（放宽字段比对、跳过未登记 label、降级成 warning）即 `circuit_breaker` 命中。

I3 **0–2 步要么回来、要么被明确废弃**：若留 collector-only，必须解释 flock 防重入、
remote 卫生校验、`reset --hard origin/main` 三条在新形态里由谁承担；解释不了就是 I1 未闭合，
而不是「性能更好所以没问题」。

I4 **重叠调度可见**：两条 label 都调 `panorama-collect.py` 且都写 `current-revision.json`
（`interval` 180 / 240）这一事实，要在注册表或 receipt 里留下一条可读记录 + 可指认命令
（`plistlib` 枚举，只读、不 `launchctl`）。

I5 **env 快照不得带日期化 scratch 路径进机器级配置**：`…-runtime-clean-20261008` 这类字面量若最终保留，
必须先在注册表里有对应声明字段；否则判据是「它被消除」，因为 generator 无法重新产出它（§3 第三行）。

I6 **不宣布 B4b/B5 完成**：plist 改道与权威翻转属 B4b 批次 2+ 的逐批授权面；本 BET 只做这一条漂移的定性与裁定请求。

## 6 非目标

- 不动 `service-config-drift` 的 blocking 归属，不动 `CI_SKIP_CHECKS` / `SOFT_CHECKS`。
- 不 `launchctl bootout` / 不重载 / 不写 `~/Library/LaunchAgents`（机器级写，需授权）。
- 不裁定 panorama 与 zhixing-dashboard 两条线谁该留——只提交证据并请求署名。
- 不把 publisher 写进 `repo_root.install_root()`（那是 ADR-0456 文档与代码面的另一条 BET，需先有 I1 的裁定）。
- 不修 G9（`state-freshness-check` 的 optional-missing 均分语义与 CI 不执行面）。

## 7 验收（逐条可跑）

| # | 命令 | 期望 |
|---|---|---|
| 判据-1 改前基线 | `python3 bin/mof/gen-service-configs.py --check` | rc=1、`com.omostation.zhixing-projection-fullrefresh` 一条 drift（本轮实测） |
| 判据-2 两侧逐字节 | `gen_launchd_plist(svc)` 内存产物与盘上文件 `unified_diff`（只读） | 改前 **63 行**（本轮实测）且缩进指纹相反（盘 tab / 生成 4 空格）；改后 diff 为空 **且**指纹一致 |
| 判据-3 装置未改窄 | `git diff origin/main -- bin/mof/gen-service-configs.py` | 空输出 |
| 判据-4 门禁回绿不减项 | `python3 bin/gac/gac-local-gate.py --json` | `hard_fails` 不含 `service-config-drift`，且 executed check 总数不减少 |
| 判据-5 署名可读 | `Grep` 该 label 在 registry / receipt 里的裁定记录 | 命中一条含**人名或署名角色**的行，不含「先对齐再说」 |
| 判据-6 重叠面留痕 | `plistlib` 枚举「同程序多 label」输出贴进 receipt | 至少两条 label 指向 `panorama-collect.py`，interval 分别 180 / 240 |
