---
schema_version: specification/v1
spec_version: 1.0.0
title: B2 收口 —— 注册 43195 进端口表，并订正 resident-web 的根与摘要
bet_id: BET-Y2Q4-T10-283
status: accepted
lifecycle: contract
last-reviewed: 2026-11-04
---

# B2 收口 —— 注册 43195 进端口表，并订正 resident-web 的根与摘要

## 1. 判据出处与缺口

ADR-0456 分期表 B2 行（`/Users/xiamingxing/.qoder-cn/plans/nimble-bay-asp.md:139`）的验收原文是：

> prod 全量在跑时 `make gac-local-gate` 绿 + **未注册端口 0**

2026-11-03 实测：本仓自有服务中有 **1 个**监听端口不在 `protocols/port-registry.yaml` 里，因此该行按构造读不到 0。缺口不是推测，下面是可复算的读数。

## 2. 实测事实

### 2.1 声明侧

`protocols/port-registry.yaml` 的端口是**数字 mapping 键**（`:116` 形如 `  4000:`、`:124` 形如 `  5173:`），不是 `port: N` 标量。按结构解析（`yaml.safe_load` 后递归收数字键）得 4 个簇：

| 簇 | 数字键数 |
|---|---|
| `/ports` | 57 |
| `/env_vars` | 35 |
| `/conflicts_resolved` | 10 |
| `/types` | 3 |

声明集大小 57，含 4000 与 5173。**正则 `port[s]?\s*:\s*(\d{2,5})` 对该文件命中 0** —— 用它测会得到假零。

### 2.2 监听侧

`/usr/sbin/lsof -nP -iTCP -sTCP:LISTEN` 得 44 行、39 个 (端口, 进程) 站点、31 个端口不在声明集里。逐站点取 `ps -ww -o command=` 与 `lsof -p <pid>` 的 `cwd` 归因后：

- 第三方不计：LM Studio、magpie、magpie-bu、ControlCenter、Raycast、WeChat、rapportd、CleanMyMac、Google(9222)、ssh 转发、pinokio、eg2-runtime、decision-svc、clash-dist-serve、hermes、LifeOS PULSE(31337)、`agy`（本 agent 进程，cwd 恰在检出根，非受治服务）。
- **本仓自有且未注册：43195** —— PID 2460：

```
Python -B -c import sys; sys.path.insert(0, '/Users/xiamingxing/.local/opt/omostation/projects/omo/src');
from omo.resident.cli import main; main(['web', '--port', '43195', '--host', '0.0.0.0'])
```

绑定地址 `*:43195`（**非 loopback**）。端口值同时硬编码在 `projects/omo/src/omo/resident/interact.py:1060`（`def cmd_web(port: int = 43195, host: str = "0.0.0.0")`）与 `:1550`（argparse default），故它**不是** `env-only` 端口。

### 2.3 登记的自述推迟

`43195` 目前只出现在 `.omo/_truth/registry/services.yaml:6282` 的 observe-only 条目里，其 `notes` 明写：

> 端口 43195 只在此记录, 本轮不写 ports 键以免新增耦合面.

该推迟是 BET-Y2Q4-T10-253 的单轮范围决定，与本计划 B2 行的验收线不同层：它使 B2 停留在 FAIL。

### 2.4 同一条记录还错着（第二个缺口）

实盘 `~/Library/LaunchAgents/com.omostation.resident-web.plist` 已于 2026-10-28 改道到安装位（同目录留有 `com.omostation.resident-web.plist.bak-20261028T1745`）：

| 项 | 实盘 | `services.yaml` 记录 |
|---|---|---|
| `-c` 载荷里的 `sys.path.insert` | `/Users/xiamingxing/.local/opt/omostation/projects/omo/src` | `:6295` 仍为 `/Users/xiamingxing/Workspace/projects/omo/src` |
| `WorkingDirectory` | `/Users/xiamingxing/.local/opt/omostation` | 未记录 |
| 文件 sha256 | `b5aa390d85fb5c655b2e52c840663da0e2c3c5a3517456c7d8ad025b09006a30` | `:6286` `3e8eb76a1046634e7ff9b5fc3795ada0f6d7813b76ccb219f438762e2d20a66a` |

**为什么没有尺会红**（这是事实陈述，不是免责）：`content_digest` 这个键在全仓的读者只有 BET 绑定面 —— `bin/plan/bet-ledger.py`、`bin/gac/ledger-safe-insert.py`、`bin/ssot/sync-bet-digests.py`，**没有任何代码读 `services.yaml` 的该键**；而 `bin/mof/gen-service-configs.py:211` 对 `generate: false` 的服务直接跳过校验。所以这条记录既像检查又是死元数据：它会一直错着。

同一批证据还修正了一个读数解释：B4b 现实核对 E6 报 `undetermined 3`，其中 resident-web 实际是**已完成改道**（载荷写在 `-c` 内联串里，E6 的 argv 根扫描认不出），不是未知。

## 3. 范围（本 BET 只动注册面）

1. `protocols/port-registry.yaml` 的 `/ports` 追加 `43195`，owner 归 `omo` / resident-web，并登记其环境名（若有）与用途注记。遵守该文件自身策略原文：「分配即固定, 只追加不重排」—— 不重排、不改写既有条目。
2. `.omo/_truth/registry/services.yaml` 的 `omostation.resident-web`：`program.args` 的根改为安装位实测值、`content_digest` 改为实盘 sha256、补记 `WorkingDirectory`。
3. 新增 `tests/unit/` 用例钉住第 4 节的判据，使该结论可由 CI 之外的本地命令复算。

## 4. 验收判据

1. 结构解析后的声明集**必须包含 43195**，且 `/ports` 簇计数由 57 变 58 —— 判据用计数非零/增量表达，不用「文件里有 43195 字串」：写成注释或标量值也会命中字串。
2. 复算未注册端口：本仓自有服务未注册监听数 **1 → 0**，第三方站点数不因本次改动变化（两侧都在同一次扫描里产出）。
3. `services.yaml` 记录的根与 `content_digest` 与实盘 plist **逐字一致**（digest 由实盘文件重新计算得到，不手填）。
4. **反证**：把 `/ports` 里的 43195 键名改成非数字（或移到注释）时，第 1 条断言必须红 —— 否则该测试没有钉住结构解析口径。
5. 本 BET 不得声称修复了任何门禁；第 4 节所有断言都由新增用例与本地命令产出。

## 5. non_goals

- 不改 plist、crontab、`launchctl` 状态或任何机器级配置 —— 实盘 plist 已是对的，本轮只让记录追上它。
- 不把 resident-web 的 `--host 0.0.0.0` 收成 loopback（暴露面变更是运行时效应，需单独授权）。
- 不改 `interact.py` 的端口默认值；不在本轮引入端口分配算法。
- 不动 `content_digest` 的消费侧（要让该键真正被校验，需先立「记录 vs 实盘」比较器，属尺尺改造，另案）。
- 不重排或清理 `services.yaml` 其他服务的检出根字面量（`:5957`、`:6272` 等属 B4b 批次面，逐批授权）。

## 6. 中止判据

若注册 43195 需要改动任何正在监听的服务配置才能自洽（例如该端口与 `/conflicts_resolved` 既有条目冲突、或 dev 段 `15000–15099` 策略禁止该值进入 `/ports`），则**停止实现**并把本 BET 停在 `in_progress`，把冲突原文与判据登记进 retro，不用注释式命中或放宽解析口径凑数。
