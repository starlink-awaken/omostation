---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B3 准入评审清单 — E4 未分区 22 条 + E5 双向不一致 2 条逐条取证，把署名裁定摊成一次可答的清单
bet_id: BET-Y2Q4-T10-259
status: accepted
lifecycle: contract
last-reviewed: 2026-10-26
owner: governance-team
schema: md/v1
---

# B3 准入评审清单（E4 22 条 + E5 2 条）

> **2026-10-26 重签（BET-Y2Q4-T10-271）**：E4 由 19 条长到 22 条，新增的 3 条已由 principal 逐条署名
> 并写入机读豁免面（`launchd_namespace.exempt_labels` 11 → 14，classification 全为 `external`），
> 见下表第 20—22 行。本表其余 **19 行的 disposition 仍待逐条署名**，`--reality-check` 的 E4 因此
> 从 22 降到 19 而**未归零**（原因见 §1 末尾的判据本体说明）。

> 上游契约：`ADR-0456`（code_root / state_root 双根）。B3 完成判据 =
> `gen-service-configs.py --check` exit 0 **且**「已安装 label 集合 == 注册表集合」。
> 本轮交付的是**清单本身**：逐条取证 + 只陈述可用机制与选项，**不替任何一条决定「该不该活」**。

## 1. 实测读数（基线 2026-10-19T10:08Z，`origin/main@17c0a3286`；复测 2026-10-20T01:29Z，同一隔离检出）

```
python3 bin/mof/gen-service-configs.py --reality-check --json
ok=false  e1_drift=0  e2_undeclared=0  e3_lint_debt=0  unclassified=0
e4_prefix_ok=false（未分区 18 条 → 复测 19 条）  e5=1+1
installed_total=76 → 复测 77  workspace_scoped=38
owned_declared=owned_installed=47  external=5  registry_declared_total=75
dev_label_prefix=com.omostation.dev.
```

即：T10-253 / T10-258 已把 `--check` 的 E1/E3 与 E2 等式的 owned 半边归零；
`ok` 仍为 false 的全部剩余理由就是本清单的 21 条。**在那之前 B3 未闭合。**

⚠️ **复测读数的变化只落在两个字段上**：`installed_total` 76→77、E4 18→19，新增一条
`com.local.magpie-refresh`（mtime 2026-10-19T19:26:33Z，即基线测量**之后**才落盘）。
`e1_drift` / `e2_undeclared` / `e3_lint_debt` / `unclassified` / `workspace_scoped` /
`owned_declared=owned_installed=47` / `registry_declared_total=75` / `e5` 两项**全部逐字段未变**
—— 本轮交付没碰判据本体的可测后果正是「只有运行面自己动的字段才动」。
下表已按复测读数补齐为 **19 行**，见 §5 第 3 条：这张表的效力来自那条命令的**当次重导**，
不来自本文抄写。

⚠️ 同一条命令在主工作区（HEAD `fdb106c9f`，落后三个合并）读数不同：`e2_undeclared=5 /
owned_declared=42 / registry_declared_total=70`，缺的 5 条正是 T10-253 回填的 4 条 +
T10-258 回填的 1 条。**判据必须由 origin/main 那棵树产出**，陈旧检出的读数不是回归。

### 1.1 2026-10-26 重签读数（同一条命令，补登前后各跑一次）

| 阶段 | 未分区 E4 | external | e4_prefix_ok | 其余字段 |
|---|---|---|---|---|
| 补登前（`services.yaml@6b8160311242`） | 22 条 | 5 | false | E1=0 / E2=0 / E3=0 / unclassified=0 / 本机 81 / workspace_scoped=39 / owned_declared=owned_installed=48 / registry_declared_total=75 / E5 1+1 / ok=false |
| 补登后（`services.yaml@5b2d198dd670`） | **19 条** | **8** | false | 与上一行**逐字段相同** |

新增的 3 条是 `com.fleetops.logrotate`、`com.fleetops.sync`、`com.localbrain.ops-engine`（下表 #20—#22），
零条退出 —— 旧 19 条全部仍在 E4 名单里，且与表内 19 行**双向集合相等**（missing=[] extra=[]，实测）。
本机总数 81 未变是预期：豁免面只改变「怎么归类」，不改变「装了哪些 job」。

⚠️ **E4 没有归零，且「补登 3 条」在结构上不可能让它归零**（判据本体读自
`bin/mof/gen-service-configs.py:773`，2026-10-26）：`e4_prefix_ok = not any(f.startswith("E4") for f in findings)`
—— E4 只要还剩**任何一条** finding 就为 False，而 `:684` 那条 finding 在 `unmanaged_unknown` 非空时必发。
所以 E4 归零要求 22 条**全部**有名有归处；本轮授权范围是 3 条 ⇒ 真实终态 E4=19、`prefix_ok` 仍 false。
余下 19 行是署名面（#13—#16、#18 明写「待署名」；`com.local.*` 13 条待整族裁定），
把它们写进豁免面属于「该不该活/归谁管」的裁定，不由本轮代办。

> 自伤留痕：本轮向 principal 出选项时把结果写成「E4 归零」，那是**在读 `:773` 之前**写下的措辞 ——
> 判据本体要从源码取，不能从「补登后少了几条」倒推。这句错话已经影响了一次授权决定，所以留在这里，
> 并在 receipt §2 与台账 `done_when` 的更正文里逐处消掉。

## 2. 准入机制只有三个（读 `bin/mof/gen-service-configs.py:345-357` 的 `classify_label` 得出）

| 机制 | 效果 | 代价 |
|---|---|---|
| `launchd_namespace.workspace_prefixes` 追加前缀 | 命中即归 `workspace`，进 E2 等式 | 会把该前缀下**所有** plist 一次性拉进本仓管辖，任何一条未登记立刻红 |
| `launchd_namespace.exempt_labels` 追加条目（`label` + `classification` ∈ {`external`, `unclassified`, `owned`}） | 归入该类，不进 E2 等式 | `owned` 意为「本仓服务却不在 registry」，与 E2 语义冲突，本清单不提议对它使用 |
| 改运行面（`bootstrap`/`bootout`、翻 `enabled`） | 让现实与声明一致 | **署名面**；且 B4b 批次 2+ 未获逐批授权前一律不动本机 launchd |

`classification` 拼错 → 落 `unmanaged_unknown` 并**计入 E4**（fail-closed，不会默认当 external），
所以下表每条都写明拟用的 classification。

## 3. E4 未分区 22 条（2026-10-19 基线 19 条 + 2026-10-26 新增 3 条）

取证方式：`plistlib.loads` 逐个读 `~/Library/LaunchAgents/<label>.plist`，记 `ProgramArguments`、
`RunAtLoad`/`KeepAlive`/`StartInterval`/`StartCalendarInterval`、`EnvironmentVariables` **条数**（值一律不抄）、
字节数、mtime（UTC）、sha256 前 16 位；并查仓内 `bin/ops/launchd/<label>.plist` 镜像是否存在。
**22 条的仓内镜像全部为不存在**（下表 `镜` 列 = N），这是「本仓不拥有这些 plist」的实测依据。

| # | label | 实际执行的东西 | 调度形状 | 环境变量条数 | mtime (UTC) | 字节 | sha256:16 | 镜 | 拟 classification |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `com.local.agent-config-audit` | `python3 ~/local-ops/bin/agent-config-audit` | Calendar | 1 | 2026-10-05T02:11:14Z | 1313 | `8f1237f04cd5f582` | N | external（local-ops 属主） |
| 2 | `com.local.clash-dist-serve` | `python3 ~/dotfiles/sharedconf/ClashConfig/scripts/clash-dist-serve.py` | RunAtLoad+KeepAlive | 0 | 2026-10-10T04:44:30Z | 882 | `a98ab8fb235abe6e` | N | external（dotfiles 属主） |
| 3 | `com.local.codex-skills-sync` | `~/local-ops/bin/codex-skills-sync` | 无显式调度 | 0 | 2026-10-06T03:47:14Z | 718 | `d33d8bfefcf040fb` | N | external |
| 4 | `com.local.dotfiles-drift` | `zsh -lc "cd $HOME/dotfiles && exec python3 bin/sync-drift.py check"` | Calendar | 0 | 2026-10-09T14:25:13Z | 786 | `90857d9b3fc96ec2` | N | external |
| 5 | `com.local.lms-resident` | `~/local-ops/bin/lms-resident` | RunAtLoad + StartInterval 120 | 1 | 2026-10-06T01:52:29Z | 656 | `b44412354412e3dd` | N | external |
| 6 | `com.local.magpie-backup-prune` | `python3 ~/.local/bin/magpie-backup-prune` | Calendar | 0 | 2026-10-06T23:57:35Z | 1043 | `1098bb25a0942012` | N | external（magpie 工具链） |
| 7 | `com.local.magpie-watchdog` | `python3 ~/.local/bin/magpie-watchdog --once` | RunAtLoad + StartInterval 30 | 0 | 2026-10-10T00:39:41Z | 1083 | `18c83be3f2b290e9` | N | external |
| 8 | `com.local.omlx-headless` | oMLX.app 内置 python `-m omlx.server --model-dir ~/.local/share/omlxc/releases` | RunAtLoad+KeepAlive，WD 在 .app 内 | 1 | 2026-10-11T00:23:27Z | 1228 | `27e0d8fd902b5a26` | N | external（第三方 .app） |
| 9 | `com.local.route-pilot` | `~/local-ops/bin/route-pilot` | RunAtLoad + StartInterval 300 | 1 | 2026-10-06T09:39:26Z | 683 | `887075e3f3fc4afa` | N | external |
| 10 | `com.local.session-secrets-sweep` | `python3 ~/local-ops/bin/session-secrets-sweep` | Calendar | 0 | 2026-10-10T06:49:33Z | 1030 | `5ee7887de0500c69` | N | external |
| 11 | `com.local.tc-doctor` | `~/.local/bin/tc-doctor-daily` | Calendar | 0 | 2026-10-13T06:43:12Z | 1523 | `97b1686997a171ef` | N | external |
| 12 | `com.local.zg-server` | `/opt/homebrew/bin/zg server run` | RunAtLoad+KeepAlive | 1 | 2026-10-10T06:49:33Z | 1266 | `b3d7d7800a11c93a` | N | external（homebrew 装的服务） |
| 13 | `com.localbrain.backup-sync` | `~/Project/work-agent/scripts/sync-backups.sh` | Calendar | 0 | **2026-10-19T01:52:48Z** | 639 | `e98a021c747ea681` | N | 待署名：work-agent 属主 |
| 14 | `com.localbrain.daily-jobs` | `~/Project/work-agent/scripts/daily_jobs.sh` | Calendar | 0 | **2026-10-19T02:24:14Z** | 634 | `37688dbd5b2848a4` | N | 待署名 |
| 15 | `com.localbrain.monitor` | `~/Project/work-agent/scripts/um870_monitor.sh` | Calendar | 0 | **2026-10-19T01:39:02Z** | 639 | `6bfc4ff831c44e8c` | N | 待署名 |
| 16 | `com.localbrain.preseed-http` | `python3 -m http.server 8088 --bind 0.0.0.0 --directory ~/Project/work-agent/preseed` | RunAtLoad+KeepAlive | 0 | **2026-10-19T08:17:01Z** | 593 | `25aa5b7948eec57c` | N | 待署名，⚠️ 见 §5 |
| 17 | `com.valvesoftware.steamclean` | Steam `SteamApps/steamclean Public` | RunAtLoad | 0 | 2026-10-14T05:36:44Z | 882 | `b41bbe8ea814613f` | N | external（厂商安装，非本仓） |
| 18 | `com.xiamingxing.benchq-watch` | `python3 -I ~/mac-local-ai-task-2026-10-12/bin/benchq_watch.py` | RunAtLoad + StartInterval 600 | 1 | 2026-10-16T08:21:43Z | 780 | `a47fca13934ceead` | N | 待署名（一次性任务目录仍在跑） |
| 19 | `com.local.magpie-refresh` | `/Users/xiamingxing/local-ops/bin/magpie-refresh-cycle` | RunAtLoad + StartInterval | 1 | 2026-10-19T19:26:33Z | 769 | `f85c175180413b0d` | N | external（local-ops 属主，与 #6/#7 同族） |
| 20 | `com.fleetops.logrotate` | `/usr/bin/env uv run --script ~/Project/fleet-ops/tools/rotate_logs.py` | Calendar + RunAtLoad | 1 | 2026-10-24T09:40:28Z | 1052 | `3dfc5058ecb20b4d` | N | external（fleet-ops 属主）—— **2026-10-26 已署名，已写入 exempt_labels** |
| 21 | `com.fleetops.sync` | `/bin/sh ~/Project/fleet-ops/tools/sync_state.sh` | StartInterval + RunAtLoad | 0 | 2026-10-23T13:56:08Z | 722 | `8e761c20773b6720` | N | external（fleet-ops 属主）—— **2026-10-26 已署名，已写入 exempt_labels** |
| 22 | `com.localbrain.ops-engine` | `/usr/bin/python3 ~/Project/work-agent/scripts/ops_engine/main.py`（WD 同目录） | RunAtLoad + KeepAlive | 2 | 2026-10-21T08:45:37Z | 2045 | `3f92fb4459fdadda` | N | external（principal 2026-10-26 指定按 external 处，与 #13—#16 的待署名分开）—— **已写入 exempt_labels**；⚠️ 本条实测 launchctl 正在运行 |

按前缀成族裁定可以少答 13 次：`com.local.*`（13 条，全部指向 local-ops / dotfiles / magpie / 第三方 .app，
无一有仓内镜像）拟整族 `external`；`com.localbrain.*`（4 条）同属 `~/Project/work-agent`，
但落盘时间是**今天**，需先确认属主意图（见 §5）。

2026-10-26 重签补充：`com.localbrain.*` 现为 **5 条**（新增 #22 ops-engine，principal 指定 external），
`com.local.*` 仍 13 条待整族裁定；新出现的 `com.fleetops.*` 是第 4 个成族（2 条，fleet-ops 仓属主），
两条都已署名。按前缀成族裁定仍未被采用 —— `workspace_prefixes` 会把该前缀下所有 plist 一次性拉进
E2 等式（§2 的代价列），逐条 `exempt_labels` 才是本轮用的机制。

## 4. E5 双向不一致 2 条

| label | finding | 实测取证 | 可选动作（均需署名） |
|---|---|---|---|
| `com.l4.omo.sync` | registry 声明 `enabled=true`，本机**无 plist** | `~/Library/LaunchAgents/com.l4.omo.sync.plist` = ABSENT，仓内 `bin/ops/launchd/` 亦无镜像；即「声明在跑却没装」 | A 装（运行面写，B4b 前不做）／B 翻 `enabled=false` 并注明原因／C 摘登记 |
| `com.cockpit.dashboard` | registry 声明 `enabled=false`，本机仍装着且在跑 | plist 2847 B、mtime 2026-10-15T14:39:02Z、sha256:16 `9dce873e69a8d9b7`、`RunAtLoad+KeepAlive`、12 条环境变量（值不抄）、WD = `~/.local/opt/omostation-cockpit/releases/<40 位 OID>`、argv = `Python.app … -B -m uvicorn cockpit.d…` | A `bootout` + 移 `archived/`（运行面写）／B 翻 `enabled=true` 承认现实／C 保留 false 并登记「残留」债 |

## 5. 清单里需要单独点出的两条观察（只陈述，不处置）

1. **`com.localbrain.*` 四条的 plist 全部是 2026-10-19 当天落盘**（01:39Z / 01:52Z / 02:24Z / 08:17Z），
   ⚠️ 同前缀第 5 条 `com.localbrain.ops-engine`（#22）已于 2026-10-26 单独署名 external，本条待裁定的仍是 #13—#16 四条。
   指向 `~/Project/work-agent/scripts/`。它们与 omostation 治理面无引用关系，但每条都在每次
   `--reality-check` 里贡献一条 E4。属主需确认这是「本机常驻新家族」还是「试验残留」——
   答案决定它进 `workspace_prefixes`（则该前缀下任何新 plist 未登记即红）还是 `exempt_labels`。
2. **`com.localbrain.preseed-http` 以 `--bind 0.0.0.0` 在 8088 暴露一个静态目录服务且 `KeepAlive`**。
   本清单只陈述这一事实。若属主确认不需要对外暴露，改 `--bind 127.0.0.1` 或撤掉该 job
   是运行面动作，需单独授权，不在本轮范围内。
3. **这条清单天然会过期，且已在本轮交付窗口内过期一次**：基线 18 条 → 合并前复测 19 条，
   多出的 `com.local.magpie-refresh` 是在两次测量之间由本机运行面落盘的。因此本表的权威用法是
   **先重导再答**：`python3 bin/mof/gen-service-configs.py --reality-check --json` 取 `findings[0]`
   的 label 集合，与本表逐名对拍；两侧计数相等才可按表作答，否则以重导结果为准（表是快照，
   命令是判据）。这也解释了台账 `done_when` 为什么把「回归敏感字段」与「运行面自变量」分开断言——
   对活平面写「逐字段相同」会在交付者什么都没做的情况下自己变红，那种判据不成立。

## 6. 明确不做（本轮的边界）

- 不改 `workspace_prefixes` / `exempt_labels` / `--reality-check` 任一判据本体。
  （2026-10-26 更新：这一条约束的是 T10-259 那一轮。principal 之后在 BET-Y2Q4-T10-271 单独署名追加了 3 条 `exempt_labels`，判据本体与 `workspace_prefixes` 仍然未动。）
- 不动本机 launchd 与 crontab：无 `bootout`/`bootstrap`/`kickstart`，不写 `~/Library/LaunchAgents`。
- 不替任何一条 label 决定「该不该活」，也不为凑 `ok=true` 把任何 label 塞进 `services.yaml`。
- 不宣布 ADR-0456 B1 / B3 / B4 / B5 或整个 plan 完成。

## 7. 验收（本轮交付的可测判据）

1. 本文件在 `docs/superpowers/specs/` 下被跟踪，frontmatter 九键齐全且 `doc-governance` 无新告警。
2. 台账 `BET-Y2Q4-T10-259` 条目存在、`accepted_specifications` 绑定本文件且 `content_digest`
   与该文件实际 sha256 逐字节相等。
3. 清单覆盖度：E4 **22** 条与 E5 2 条**全部**出现在表中，条数由当次 `--reality-check` 读数导出，
   非手抄（`findings` 里的 label 集合与表内 label 集合**双向相等**，缺一名或多一名都算未达）。
4. 交付后 `--reality-check` 读数：回归敏感字段 `e1_drift=0` / `e2_undeclared=0` / `e3_lint_debt=0` /
   `unclassified=0` / `owned_declared=owned_installed=47` / `registry_declared_total=75` / `e5` 1+1
   **逐字段相同**；运行面自变量（`installed_total` 与 E4 集合）只允许因**可指认的外部落盘**变动，
   且必须在本文件 §1/§5 记名后才能放行——本轮 76→77、18→19 即为此例。
