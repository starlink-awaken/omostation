---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-23
bet_id: BET-Y2Q4-T10-265
---

# BET-Y2Q4-T10-265 收口 receipt — services.yaml per-service runtime_root + 常驻族 6 条改道

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-265`
规格：`docs/superpowers/specs/2026-10-22-b4b-resident-runtime-root.md`（spec_version 1.0.0，
digest `sha256:fc60a00f4e41f81e411acaf22cd85f70440ac452d225e5aaa7c23691c6729521`；
收口前用 `shasum -a 256` 对该字节复核，与台账 `content_digest` 逐字一致 —— done_when 第 6 条）
交付：**工程腿** PR #4866 squash 为 `a80d8908e75348b48b671337fd1972af30feb34f`
（GitHub `mergedAt 2026-10-22T09:04:38Z`）；**运行腿** = 本机 6 对 `bootout`+`bootstrap`，
执行于 `2026-10-23T02:00:53Z`（留档目录名即该时刻）

## 1 这一轮改了什么（一句话）

服务注册表获得 per-service 运行根选择器 `runtime_root ∈ {checkout, install}`（缺省 `checkout`、逐字节等价），
`com.l4.resident.*` 中 `enabled` 的 6 条声明为 `install`，随后把这 6 个 launchd plist 的执行入口改到
`repo_root.install_root()` = `/Users/xiamingxing/.local/opt/omostation`，且 **E1 最终读数为 0**。

## 2 逐项实测读数（verify 面，全部为收口时重测）

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| V1 | `python3 bin/mof/gen-service-configs.py --validate --json` | ok=true、violation_count=0 | `validate ok= True violations= 0` |
| V2 | `python3 bin/mof/gen-service-configs.py --check --json` | drift 计数 0（= E1） | `check ok= True drift_count= 0` |
| V3 | `pytest tests/unit/test_gen_service_runtime_root.py -q` | 全通过（CI 白名单不含 `tests/unit/**`，本地是唯一证据） | `9 passed in 0.70s`，装置：`HOME=/tmp/fakehome-rc2` + `uv run --no-project --with pytest --with pytest-timeout --with pyyaml` + `-p no:randomly`，`env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB` |
| V4 | 注册表 `runtime_root=='install'` 计数 | 恰好 6（两文档 YAML，取 `safe_load_all(...)[-1]`） | `install= 6 total= 378` |
| V5 | `--reality-check --json` | E1 归零、E2/E3 不受扰 | `e1_status=ok e1_drift=0`、`e2_undeclared=0`、`e3_lint_debt=0`、`owned_installed=47 owned_declared=47 unclassified=0` |
| V6 | 生成器未被偷改 | sha 逐字节 | `bin/mof/gen-service-configs.py` = `32fcd67a0e0c16c7…`（与变异还原后同一读数） |

E4/E5 明确**不在本 BET 验收内**（spec §4.7）。本轮读数：`e4_prefix_ok=False`，未分区 **20 条**
（2026-10-20 基线 19 条，增量 1 条，名单内**不含**任何 `com.l4.resident.*` ⇒ 与本轮无因果）；
E5 两条逐字未变（`com.l4.omo.sync` enabled-missing、`com.cockpit.dashboard` disabled-residual）。

## 3 改道前后逐条对照（本机 plist）

改道前把 6 份 plist 原样复制到 `~/.local/state/omostation/plist-backup-20261023T020053Z/`
（decision 704 B / event-ingest 677 B / execute 702 B / inbox 698 B / promote 702 B / signals 702 B）。
**每个 label 只有 `ProgramArguments` 的脚本项变化，键集零变化，`WorkingDirectory` 两侧均缺席。**

| label | 改前 ProgramArguments | 改后（launchd 自己的 `arguments` 读数） |
|---|---|---|
| com.l4.resident.decision | `/bin/bash …/Workspace/lib/resident-role-tick.sh decision` | `/bin/bash …/.local/opt/omostation/lib/resident-role-tick.sh decision` |
| com.l4.resident.execute | 同上，末项 `execute` | 同上，末项 `execute` |
| com.l4.resident.signals | 同上，末项 `signals` | 同上，末项 `signals` |
| com.l4.resident.inbox | 同上，末项 `inbox` | 同上，末项 `inbox` |
| com.l4.resident.promote | 同上，末项 `promote` | 同上，末项 `promote` |
| com.l4.resident.event-ingest | `/bin/bash …/Workspace/lib/resident-event-ingest.sh` | `/bin/bash …/.local/opt/omostation/lib/resident-event-ingest.sh` |

复核判据按 done_when 第 5 条用 `launchctl print` 的 `arguments`，**不用** `ps -o args=`；
`kickstart -k` 不重读 plist，因此走 `bootout` + `bootstrap`（6 对全部 rc=0）。

## 4 服务仍可加载、且改道后真跑过（live canary）

- 刚 `bootstrap` 后：6/6 `runs=1`、`last exit code=0`。
- 收口时（约 17 min 后）重测：`state=not running`，`runs` = decision 9 / execute 9 / signals 4 / inbox 4 /
  promote 2 / event-ingest 4，`last exit code` **全 0**（`StartInterval=600`，计数与间隔自洽）。
- 侧证写入面：`Workspace/.omo/state/agent-tick-daemon.jsonl` 在改道后连出三条
  `ts=2026-10-23T02:01:15Z / 02:07:56Z / 02:14:38Z`，每条 `agent_count=6 ok_count=6 failed_count=0`；
  `signal-poller-state.json` 最后写于 `2026-10-23T02:18:25Z`。
- **不可判定项（如实记录）**：`lsof -p <pid> | grep cwd` 在本机挂住（探针转后台后终止），
  因此 done_when 第 5 条里的 cwd 子检查**未取得读数**。它不承重的依据是第 3 节的键集对照：
  两侧都没有 `WorkingDirectory`，进程 cwd 由 launchd 默认供给，本轮未触碰。

## 5 本轮的实际后果：合入→改道之间存在一个 16 h 56 m 的**真** E1 红窗

授权措辞原文是「合入后再执行 bootout/bootstrap 改道并复跑 `--reality-check`。这是唯一能让 E1 保持 0 的路径」。
按此顺序执行的结果必须精确陈述：

- `2026-10-22T09:04:38Z` PR #4866 合入 ⇒ `canonical_root()` 那份注册表开始声明 `runtime_root: install`；
- `2026-10-23T02:00:53Z` 才执行改道 ⇒ **这 16 h 56 m 15 s 内 `--check` 报 6 条 drift**，
  且这 6 条是**声明与机器状态的真实不一致**（注册表已说 install、plist 仍指 Workspace），不是测量装置问题。
- spec §1 末条与 §4.2 只写了**反序**（先改道、注册表还没快进）会造「6 条假 drift」，
  **没有覆盖正序延迟产生的真红**；本 receipt 按实测补上这条，并把判据固化进 AGENTS.md §7。
- 因此「E1 保持 0」这句话的准确含义是：**最终读数为 0**（V2 实测），而不是「全程为 0」。
  若要把红窗也压成 0，需要「注册表改动与执行落在同一个授权动作内」，属逐批授权面，本轮未做。

另一条前提变化：**没有执行**授权里提到的 `bin/gac/sync-main.sh --allow-dirty`（其内含 `reset --hard`）。
执行窗口重测时 `~/Workspace` 已被并发 agent/cron 推进到含本次合并的 commit
（注册表 6 条 `install`、sha `4f846e6292bd…`），快进前提不成立 ⇒ 跳过该破坏性命令，改道直接在其实态上执行。

## 6 边界（本轮刻意没做到的部分）

- **selector 只搬 `ProgramArguments`，不搬被 exec 的治理内核**：两个 tracked wrapper 内部各写死检出字面量
  （`lib/resident-role-tick.sh:24`、`:28`、`lib/resident-event-ingest.sh:11`，均为
  `uv run --project /Users/xiamingxing/Workspace/projects/omo`）。两侧 wrapper **逐字节相同**
  （`772d97c10a7e1e1c…` / `48f9659f49ecb513…`），所以改道在 wrapper 层是行为保持的，
  但 omo 内核仍解析到检出 —— 「常驻族已从安装位起跑」这句话目前只对入口成立。后续项登记为
  「常驻 wrapper 内核字面量自解析」，前置 = 安装位 clone 追平（当前落后 `origin/main` **312 commits**）
  且跑过一次真实 tick。
- 未迁移常驻族以外的任何族（republisher / agora.daemon / mail.daemon / bet-claim-gc / morning-brief）；
  同族 4 条 `enabled:false` 保持缺省。
- 未清 E2/E5、未动 `repo_root` 定位链、未新增 env 名、未改 `launchd_namespace` 策略、
  未把 `--check`/`--validate` 改成带 flag 或读 env 选根、未把任何条目改成 `generate:false`。
- 未翻转权威 ledger、未动 crontab、未做 B4b 批次 2+ 与决策 3。
- **不宣布 ADR-0456 B1/B3/B4/B5/B4b 或整个 plan 完成。**

## 7 回滚（材料在位、命令实测可执行）

```bash
B=~/.local/state/omostation/plist-backup-20261023T020053Z
for l in decision execute signals inbox promote event-ingest; do
  cp "$B/com.l4.resident.$l.plist" ~/Library/LaunchAgents/
  launchctl bootout   gui/$(id -u)/com.l4.resident.$l
  launchctl bootstrap gui/$(id -u)  ~/Library/LaunchAgents/com.l4.resident.$l.plist
done
```

留档 6 份的 sha 前缀：decision `4f1034fd85e9` · event-ingest `971debd69012` · execute `b7e0b441a97d` ·
inbox `b9eb52190920` · promote `200b5c812871` · signals `9e0115f2d733`。
**回滚的完整性判据（本轮新查到的一面）**：上面那段只撤**机器侧一半**。撤完后 `--check` 的 drift 计数
会是 **6 而不是 0** —— 因为注册表已经合并了 `runtime_root: install`，plist 退回检出就重新构成第 5 节那种
真不一致。⇒ 完整回滚 = 机器侧复制回 + **仓内 revert 那 6 条声明**（一次 repo 动作），
单独执行机器侧回滚会把本机留在 E1 红灯上。这是「cutover 只有半可逆」的实测结论，不是脚本缺陷。
本轮未触发中止判据，故未执行回滚。

## 8 收尾面

- retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-265.md`
- 本 receipt + 台账 `done` 转换 + AGENTS.md §7 一条（合入即开真红窗）
- run：`20261023T020607Z-project-doc-change-4c397935`
