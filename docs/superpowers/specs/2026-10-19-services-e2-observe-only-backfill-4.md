---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B3 — 4 条本仓自有服务登记为 observe-only，使「已安装 label 集合 == 注册表集合」成立
bet_id: BET-Y2Q4-T10-253
status: accepted
lifecycle: contract
last-reviewed: 2026-10-19
owner: governance-team
schema: md/v1
---

# 1 读数 — 判据由哪棵树产出

立项前实测（2026-10-19T01:29Z），注册表树 = `origin/main@fdb106c9f`，且已验证工作树那份
`.omo/_truth/registry/services.yaml` 与 `origin/main` 的 blob **逐字节相同**
（`git hash-object` == `git rev-parse origin/main:` = `e62ade7e9b06cebd57e2c477bc1decdf598b1f73`）。
沿 BET-Y2Q4-T10-246 的教训：**E1/E2 这类读数不是机器属性，是「本机 launchd × 你所在检出的注册表」的积**，
所以不声明树的读数一律作废。

| 字段 | 基线读数 |
|---|---|
| `--check` | rc=0，`✅ 0 drift (68 launchd services)`（E1 = 0） |
| `e2_undeclared` | **4** |
| `owned_declared` / `owned_installed` | **42 / 46** |
| `e5_enabled_missing` / `e5_disabled_residual` | 1 / 1 |
| `e4_prefix_ok` | False（未分区 14 条） |
| `installed_total` / `registry_declared_total` | 71 / 70 |

计划与 ADR-0456 的 B3 中止判据是「`--check` exit 0 **且** 已安装 label 集合 == registry 集合」。
前半条已成立（E1 = 0，由 zhixing 线 #4796/#4798 闭合），后半条差 4 条。这 4 条就是本 BET 的全部范围。

# 2 范围 — 用谓词定义，不用列表定义

纳入条件（三条同时成立）：

1. `~/Library/LaunchAgents/<label>.plist` 存在且 `launchctl list` 报 LOADED；
2. `classify_label(label, policy) == "workspace"`，即 label 命中 `launchd_namespace.workspace_prefixes`；
3. 该 label 在 `origin/main` 与当前检出两棵注册表树里**都零引用**。

命中 4 条，且**与 T10-246 不同，这 4 条全部是本仓自有的服务**（执行体在本仓 `projects/omo` 或
`bin/panorama` 之下），不是异主 label：

| label | plist mtime | 执行体 | 触发 |
|---|---|---|---|
| `com.omostation.resident-agent` | 2026-10-18T22:03:12 | `projects/omo/.venv/bin/python -B -m omo.resident.service_runner --daemon` | KeepAlive + RunAtLoad |
| `com.omostation.resident-web` | 2026-10-16T07:06:57 | `python3 -B -c '… omo.resident.cli main(["web","--port","43195","--host","0.0.0.0"])'` | KeepAlive + RunAtLoad |
| `com.omostation.mbp-night-patrol` | 2026-10-16T12:44:49 | `python3 -B -c '… omo.resident.night_patrol run_night_patrol(force=False, deep=True)'` | StartCalendarInterval 02:30 |
| `com.omostation.panorama-compact-observation` | 2026-10-07T18:53:40 | `python3 <root>/bin/panorama/compact-observation.py` | StartInterval 240 + RunAtLoad |

# 3 机制 — 为什么必须是 observe-only（`generate: false`）

沿用 T10-206 / T10-246 已验证的通道，两条结构性理由都落在行号上：

- **不能 `generate: true`。** 这 4 份 plist 含 `StandardOutPath` / `StandardErrorPath` /
  `EnvironmentVariables`，其中 2 条还是内联 `python3 -c`。`gen_launchd_plist()` 不发射这些键，
  一旦声明成 `generate: true`，`--check` 立刻逐字节比对并当场 +4 E1 漂移 —— 把已经 0 的漂移重新做坏。
- **不能走 `exempt_labels`。** `bin/mof/gen-service-configs.py:478-480` 主动把被 workspace 前缀遮蔽的
  exempt 项判为「E4 死数据」；E2 分桶由 `workspace_prefixes` 派生而非由路径派生，所以
  `com.omostation.*` 下的 exempt 项结构上永远读不到。
- `generate: false` 时 `--check` 跳过比对（`:645-652`）、`validate_service_declaration()` 早返回（`:156-157`）、
  `--validate` 跳过解释器解析（`:627-629`）—— 登记这件事对 E1/E3 与 CI 可验面零扰动。

# 4 `enabled` 取值

4 条全部已装且 LOADED，所以 `enabled: true` 与 E5 不变式（`:503-505`「enabled ⇒ 必须已装」）一致、
零扰动；声明成 `enabled: false` 反而当场造出 4 条新的「disabled 却已装」E5 残留。

# 5 逐字段来源

每条声明的 `trigger` / `run_at_load` / `interval_sec` / `program.*` / `outputs.*` 一律取自
`plistlib` 转出的实际键值，不做模板默认；`content_digest` = 安装态 plist 的 `sha256`：

| label | content_digest |
|---|---|
| `com.omostation.resident-agent` | `sha256:12482c702e5f82b537d51839254d07acf2d67a465d7b4a7fa01f7027f5c7f813` |
| `com.omostation.resident-web` | `sha256:3e8eb76a1046634e7ff9b5fc3795ada0f6d7813b76ccb219f438762e2d20a66a` |
| `com.omostation.mbp-night-patrol` | `sha256:6a8bf32e5853edf93e9cce5aa5d1a91d3d15278d814085412d9c4cae6c63e209` |
| `com.omostation.panorama-compact-observation` | `sha256:55b300ca260e1bbaaf118ad064b7d49812b790837a18b2c84be382b74e70d9c4` |

`config_source` 只在能指认安装器时写实：`resident-agent` 由
`projects/omo/src/omo/resident/service_ctl.py:27`（`PLIST_LABEL`，`install` 子命令）写入；
其余 3 条本轮**未能指认**安装器，记作手写/未归因，不编造来源。

# 6 判据

候选注册表已用**检测器本身**验算（`/tmp/candpatch.py`，把 4 条叠加后跑 `reality_check()`）：

| 字段 | 基线 | 候选 | 期望 |
|---|---|---|---|
| `e2_undeclared` | 4 | **0** | 归零 |
| `owned_declared` / `owned_installed` | 42 / 46 | **46 / 46** | 集合相等成立 |
| `e1_drift` | 0 | 0 | 不得新增 |
| `e3_lint_debt` / `e4_prefix_ok` / E5 两项 | 0 / False / 1+1 | 逐字未变 | 不得为 E2 造新分类问题 |
| `installed_total` | 71 | 71 | 本机零改动 |

ISC-1 候选注册表 `e2_undeclared == 0` 且 `owned_declared == owned_installed`；ISC-2 E1/E3/E4/E5
逐字段未变；ISC-3 `--validate --json` `ok: true / violation_count: 0`；ISC-4 本机 4 份 plist 的
mtime + sha256 + `launchctl` 状态交付前后逐字节一致；ISC-5 登记内容与 plist 逐项一致、
`content_digest` 对拍；ISC-6 `make gac-local-gate` 硬失败集合等于基线（零新增）。

# 7 明确不做（留署名裁定，receipt 披露）

- **`com.cockpit.dashboard` 的 `enabled` 回写**：注册表声明 `enabled: false` +
  `disabled_reason: 刻意不加载: BET 台账约束「不切换人类 UI 入口」`（2026-09-28），而本机实测
  **LOADED**、`:8090 /api/health` 与 `/panorama` 均 HTTP 200、vite `:5173` 已不监听 —— 现实已切、
  真值面未跟。把真值面翻过去等于替「separately confirmed live action」背书，属署名裁定面，不在本 BET。
- **`com.l4.omo.sync`**：声明 `enabled: true` 但 plist 不存在。要么补装（机器侧动作）要么停用（真值面
  改写），两条都需要授权。
- **E4 未分区 14 条**：实测全部是主机侧个人 job（`~/local-ops`、`~/dotfiles`、`~/.local/bin`、Steam、
  `~/mac-local-ai-task-*`）。把它们逐条塞进 `exempt_labels` 能让 `e4_prefix_ok` 变 True（已验算），
  但那是手工枚举清单，每装一条个人 job 就 +1 噪声，结构性追不上 —— 正解是按归属证据派生分类，属检测器改造。
- **不做 plist/cron 改道**（B4b 批次 2+）；**不碰任何本机 launchd 状态**。

# 8 结构性因 —— 为什么 E2 会回潮

E2 从 2026-10-13 的 1 条涨到 4 条，不是旧债未清，而是**仓内有多个安装器直写
`~/Library/LaunchAgents` 而不写注册表**：`projects/omo/src/omo/resident/service_ctl.py:27`、
`bin/svc/service_view.py:281`、`bin/svc/service_view.py:487`、`bin/gac/install-watch-agent.py:26`、
`bin/gac/documents-jobs-scheduler.py`。只要这些通道不产注册表条目，B3 的集合相等就会被每一次 `install`
重新打破 —— 登记面与安装面不同源。本 BET 只做登记（把当下现实收口），安装面收口是另一条 BET。
