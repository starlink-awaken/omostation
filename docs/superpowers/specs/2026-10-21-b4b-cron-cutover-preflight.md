---
schema_version: specification/v1
spec_version: 1.0.0
title: B4b 批次 2 的 cron 侧改道前置条件与中止判据
bet_id: BET-Y2Q4-T10-263
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-21
---

# B4b 批次 2 的 cron 侧改道前置条件与中止判据

> 契约对象：`bin/ssot/install-resident-cron.sh` 从运行时安装位（`~/.local/opt/omostation`）
> 重装 crontab 这一动作的**可执行性**。
> 上游：ADR-0456 B4b「把写面与常驻面翻到 profile 根」；本轮**只做预检**，不改道、不安装、不判定任何 job 该不该活。
> 动机：plan 风险表两条（「双实例抢写 ledger」「静默跑旧代码的 daemon」）在 cron 侧的具体形状，
> 实测发现 installer 的输出**不是纯路径替换**，且安装位当前**根本执行不了**它写出的任何一行。

## 1. 结论（一句）

`install-resident-cron.sh` 从安装位跑一次，会往 crontab **净新增 9 条 resident 作业**（现存 crontab 里
`omo.cli resident` 计数为 **0**），而这十个角色已由 launchd 持有 —— 那是**双实例抢写同一 ledger**，
不是改道。且安装位子模块 **16/16 未初始化**，它写出的每一行 `python3 -m omo.cli …` 都当场
`ModuleNotFoundError`。因此 B4b 批次 2 的 cron 侧**不能**按「重跑 installer」理解，必须先满足 §5 前置条件。

## 2. 测量装置（可复现，零运行面效应）

| 项 | 装置 | 读数 |
|---|---|---|
| crontab 现状 | `crontab -l \| /usr/bin/grep -c 'omo\.cli resident'` | `0`（⚠️ 必须用 `/usr/bin/grep`，本机 `grep` 别名到 `rg`，`rg -c` 零匹配**不打印 0**，会读成空） |
| crontab 规模 | `crontab -l \| /usr/bin/grep -c .` | 67 行；其中 25 行含 `Workspace` 路径；`resident-agent-schedule` 标记 1 行（**孤儿标记**：标记在、被它管理的 resident 行不在） |
| 真实 crontab 未被本次预检改动 | `crontab -l \| shasum -a 256` 前 / 后各取 16 位 | 前后均为 `d2677b3321a39568`（逐字节一致） |
| installer 输出（不落到 crontab） | `PATH=/tmp/drybin:$PATH bash bin/ssot/install-resident-cron.sh`，`/tmp/drybin/crontab` 是 shim，`crontab -l` 读快照、`crontab -` 写临时文件 | 生成 88 行 crontab 文本，全程无 `crontab` 真调用 |
| 安装位子模块 | `git -C ~/.local/opt/omostation submodule status --recursive \| /usr/bin/grep -c '^- '` | **16 / 16 未初始化**（`projects/omo` 目录为空） |
| 安装位可 import | `PYTHONPATH=<opt>/projects/omo/src:<opt>/projects/bus-foundation/src /opt/homebrew/bin/python3 -c "import omo.cli, bus_foundation"` | rc=1 `ModuleNotFoundError: No module named 'omo'`；**对照**同一探针在 `~/Workspace` rc=0 `import OK` |
| 安装位写目录 | `ls -d <opt>/runtime/omo <opt>/.omo/_delivery/{resident-orchestrator,event-ingest,personal-signals,perception-inbox}` | 5 个全部 MISS（cron 行的重定向目标不存在） |

## 3. 精确 cron diff（从安装位重装相对现状）

现状 crontab 与 installer 生成文本逐条比对，真实差量是两类，**不是一类**：

1. **路径换 2 条** —— 现存的、由该 installer 管理的两条：
   `0 1 * * * … bin/ssot/proposal-to-adr.py` 与 `10 2 * * * … bin/ssot/system-health-check.py`，
   `cd` 目标从 `~/Workspace` 变为 `~/.local/opt/omostation`。
2. **净新增 9 条 resident 作业** —— installer 的 role 循环（`*/2` × orchestrator / sediment /
   decision / execute / monitor）加上 `CRON_INGEST`（`*/5`）、`CRON_SIGNALS`（`*/5`）、
   `CRON_INBOX`（`*/5`）、`CRON_PROMOTE`（`*/10`），每条都带
   `--ledger ${WORKSPACE}/runtime/omo/event-ledger.sqlite3`。

幂等块不足以挡下第 2 类：`install-resident-cron.sh:63-78` 的 awk `managed(l)` 只在
「schedule 命中 `/^\*\/(2|5|10) \* \* \* \* /` 或 `/^0 1 \* \* \* /` 或 `/^10 2 \* \* \* /`」**且**行内含
`omo\.cli resident` / `proposal-to-adr\.py` / `system-health-check\.py`」时判为已管理。
现状 crontab 里 `omo.cli resident` 命中数为 0 ⇒ 那 9 条按构造**不可能**被识别为已存在，
而 `:80 cat << EOF | crontab -` 是**无条件重写** ⇒ 净新增必然发生。

同时：这十个角色的常驻权当前在 launchd 侧（`services.yaml` 声明
`com.l4.resident.{orchestrator,sediment,decision,execute,monitor,heartbeat,event-ingest,signals,inbox,promote}`
与 `com.omostation.resident-daemon`，`launchctl list` 亦在列）。
⇒ cron 侧装上即与 launchd 形成**双实例**，两者写同一 ledger 文件。
这正是 plan 风险表「双实例抢写 ledger」的机制实例，**且 `flock` 不能解**（ADR-0456 决策 3 的措辞）。

## 4. 安装位可执行性（改道的前置物理条件）

installer 写出的每一行都形如：

```text
*/5 * * * * cd /Users/xiamingxing/.local/opt/omostation && PYTHONPATH=.../projects/omo/src:.../projects/bus-foundation/src: /opt/homebrew/bin/python3 -m omo.cli resident inbox --once --ledger /Users/xiamingxing/.local/opt/omostation/runtime/omo/event-ledger.sqlite3 >> /Users/xiamingxing/.local/opt/omostation/.omo/_delivery/perception-inbox/cron.log 2>&1
```

按 §2 读数，这一行会依次在三处失败：import（子模块未初始化）、`--ledger` 父目录不存在、
重定向目标目录不存在。`cd` 是唯一能成功的部分。
⇒ **在安装位重装 cron 得到的不是「跑在独立 clone 上的常驻面」，而是一组每分钟/每两分钟静默失败的作业**，
与 ADR-0456 风险表「静默跑旧代码的 daemon」同类但更糟（旧代码至少还能跑）。

## 5. 前置条件（B4b 批次 2 的 cron 侧必须逐条为真才可安装）

- **P1** 安装位子模块 16/16 已初始化，§2 的 import 探针 rc=0（对照读数须同时给出）。
- **P2** 安装位存在 `runtime/omo/` 与 `.omo/_delivery/{resident-orchestrator,event-ingest,personal-signals,perception-inbox}/`，
  且 `runtime/omo/event-ledger.sqlite3` 是**显式选定的目标库**（权威还是 `$(state_root())/runtime/omo/event-ledger.sqlite3`，见 §7）。
- **P3** resident 的常驻权**归属已由 Principal 裁定**：要么 launchd 侧 `bootout` 这些 label，
  要么 installer 的 role/ingest/signals/inbox/promote 段在 cron 侧**不装**。二者必居其一，不可都活。
- **P4** `install-resident-cron.sh` 的幂等判据升级：`managed()` 必须能识别「同一角色已由 launchd 持有」，
  否则任何一次重装都会重放 §3 的 9 条净新增。
- **P5** 装前用 §2 的 shim 装置做一次 dry-run 并把 diff 交 Principal 过目，**过目通过才允许真 `crontab -`**。

## 6. 中止判据（命中即停止并如实登记，不改判据本体）

- 若满足 P1–P5 需要改 `install-resident-cron.sh` 的**作业集合本体**（而不只是幂等判据）→ 停止，那是常驻权署名裁定面。
- 若需要 `bootout` / `bootstrap` / `kickstart` 任何 label，或写 `~/Library/LaunchAgents`，或改 crontab 才能验证 → 停止。
- 若需要在安装位 `git submodule update --init` / 建 venv / 动 39 条 `.pth` 才能过 §2 → 停止并保留原判据（那是另一条授权线）。
- 若把权威 ledger 从 `$(state_root())/runtime/omo/event-ledger.sqlite3` 翻到安装位 → 停止，属 B4b 批次 2+ 逐批授权面。
- 若宣布 ADR-0456 B1 / B3 / B4 / B5 或整个 plan 完成 → 不在本契约范围。

## 7. 非目标

- 不安装、不重写、不读取后修改 crontab；本轮唯一写动作是产生本 spec 与一条台账条目。
- 不动本机 launchd 与 crontab；不 init 任何子模块；不在安装位建目录。
- 不判定任何 resident 角色「该不该活」，不替 Principal 在 cron 与 launchd 之间选择。
- 不把 `--reality-check` 或 cron 预检注册进 `ci-surfaces` / `governance-checks`，不动 `script_baseline`。
- 不宣布 ADR-0456 B4b 完成。
