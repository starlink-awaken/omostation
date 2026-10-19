---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B3 准入评审清单 — E4 未分区 18 条 + E5 双向不一致 2 条逐条取证，把署名裁定摊成一次可答的清单
bet_id: BET-Y2Q4-T10-259
status: accepted
lifecycle: contract
last-reviewed: 2026-10-19
owner: governance-team
schema: md/v1
---

# B3 准入评审清单（E4 18 条 + E5 2 条）

> 上游契约：`ADR-0456`（code_root / state_root 双根）。B3 完成判据 =
> `gen-service-configs.py --check` exit 0 **且**「已安装 label 集合 == 注册表集合」。
> 本轮交付的是**清单本身**：逐条取证 + 只陈述可用机制与选项，**不替任何一条决定「该不该活」**。

## 1. 实测读数（2026-10-19T10:08Z，`origin/main@17c0a3286`，隔离检出与该内容逐字相同）

```
python3 bin/mof/gen-service-configs.py --reality-check --json
ok=false  e1_drift=0  e2_undeclared=0  e3_lint_debt=0  unclassified=0
e4_prefix_ok=false（未分区 18 条）  e5=1+1
installed_total=76  workspace_scoped=38
owned_declared=owned_installed=47  external=5  registry_declared_total=75
dev_label_prefix=com.omostation.dev.
```

即：T10-253 / T10-258 已把 `--check` 的 E1/E3 与 E2 等式的 owned 半边归零；
`ok` 仍为 false 的全部剩余理由就是本清单的 20 条。**在那之前 B3 未闭合。**

⚠️ 同一条命令在主工作区（HEAD `fdb106c9f`，落后三个合并）读数不同：`e2_undeclared=5 /
owned_declared=42 / registry_declared_total=70`，缺的 5 条正是 T10-253 回填的 4 条 +
T10-258 回填的 1 条。**判据必须由 origin/main 那棵树产出**，陈旧检出的读数不是回归。

## 2. 准入机制只有三个（读 `bin/mof/gen-service-configs.py:345-357` 的 `classify_label` 得出）

| 机制 | 效果 | 代价 |
|---|---|---|
| `launchd_namespace.workspace_prefixes` 追加前缀 | 命中即归 `workspace`，进 E2 等式 | 会把该前缀下**所有** plist 一次性拉进本仓管辖，任何一条未登记立刻红 |
| `launchd_namespace.exempt_labels` 追加条目（`label` + `classification` ∈ {`external`, `unclassified`, `owned`}） | 归入该类，不进 E2 等式 | `owned` 意为「本仓服务却不在 registry」，与 E2 语义冲突，本清单不提议对它使用 |
| 改运行面（`bootstrap`/`bootout`、翻 `enabled`） | 让现实与声明一致 | **署名面**；且 B4b 批次 2+ 未获逐批授权前一律不动本机 launchd |

`classification` 拼错 → 落 `unmanaged_unknown` 并**计入 E4**（fail-closed，不会默认当 external），
所以下表每条都写明拟用的 classification。

## 3. E4 未分区 18 条

取证方式：`plistlib.loads` 逐个读 `~/Library/LaunchAgents/<label>.plist`，记 `ProgramArguments`、
`RunAtLoad`/`KeepAlive`/`StartInterval`/`StartCalendarInterval`、`EnvironmentVariables` **条数**（值一律不抄）、
字节数、mtime（UTC）、sha256 前 16 位；并查仓内 `bin/ops/launchd/<label>.plist` 镜像是否存在。
**18 条的仓内镜像全部为不存在**（下表 `镜` 列 = N），这是「本仓不拥有这些 plist」的实测依据。

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

按前缀成族裁定可以少答 12 次：`com.local.*`（12 条，全部指向 local-ops / dotfiles / magpie / 第三方 .app，
无一有仓内镜像）拟整族 `external`；`com.localbrain.*`（4 条）同属 `~/Project/work-agent`，
但落盘时间是**今天**，需先确认属主意图（见 §5）。

## 4. E5 双向不一致 2 条

| label | finding | 实测取证 | 可选动作（均需署名） |
|---|---|---|---|
| `com.l4.omo.sync` | registry 声明 `enabled=true`，本机**无 plist** | `~/Library/LaunchAgents/com.l4.omo.sync.plist` = ABSENT，仓内 `bin/ops/launchd/` 亦无镜像；即「声明在跑却没装」 | A 装（运行面写，B4b 前不做）／B 翻 `enabled=false` 并注明原因／C 摘登记 |
| `com.cockpit.dashboard` | registry 声明 `enabled=false`，本机仍装着且在跑 | plist 2847 B、mtime 2026-10-15T14:39:02Z、sha256:16 `9dce873e69a8d9b7`、`RunAtLoad+KeepAlive`、12 条环境变量（值不抄）、WD = `~/.local/opt/omostation-cockpit/releases/<40 位 OID>`、argv = `Python.app … -B -m uvicorn cockpit.d…` | A `bootout` + 移 `archived/`（运行面写）／B 翻 `enabled=true` 承认现实／C 保留 false 并登记「残留」债 |

## 5. 清单里需要单独点出的两条观察（只陈述，不处置）

1. **`com.localbrain.*` 四条的 plist 全部是 2026-10-19 当天落盘**（01:39Z / 01:52Z / 02:24Z / 08:17Z），
   指向 `~/Project/work-agent/scripts/`。它们与 omostation 治理面无引用关系，但每条都在每次
   `--reality-check` 里贡献一条 E4。属主需确认这是「本机常驻新家族」还是「试验残留」——
   答案决定它进 `workspace_prefixes`（则该前缀下任何新 plist 未登记即红）还是 `exempt_labels`。
2. **`com.localbrain.preseed-http` 以 `--bind 0.0.0.0` 在 8088 暴露一个静态目录服务且 `KeepAlive`**。
   本清单只陈述这一事实。若属主确认不需要对外暴露，改 `--bind 127.0.0.1` 或撤掉该 job
   是运行面动作，需单独授权，不在本轮范围内。

## 6. 明确不做（本轮的边界）

- 不改 `workspace_prefixes` / `exempt_labels` / `--reality-check` 任一判据本体。
- 不动本机 launchd 与 crontab：无 `bootout`/`bootstrap`/`kickstart`，不写 `~/Library/LaunchAgents`。
- 不替任何一条 label 决定「该不该活」，也不为凑 `ok=true` 把任何 label 塞进 `services.yaml`。
- 不宣布 ADR-0456 B1 / B3 / B4 / B5 或整个 plan 完成。

## 7. 验收（本轮交付的可测判据）

1. 本文件在 `docs/superpowers/specs/` 下被跟踪，frontmatter 九键齐全且 `doc-governance` 无新告警。
2. 台账 `BET-Y2Q4-T10-259` 条目存在、`accepted_specifications` 绑定本文件且 `content_digest`
   与该文件实际 sha256 逐字节相等。
3. 清单覆盖度：E4 18 条与 E5 2 条**全部**出现在表中，条数由当次 `--reality-check` 读数导出，
   非手抄（`findings` 里的 label 集合 ⊆ 表内 label 集合，且两侧计数相等）。
4. 交付后 `--reality-check` 读数与交付前**逐字段相同**（本轮不碰判据本体，改了就是违例）。
