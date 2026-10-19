---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B3 批次 5 — 1 条已装未声明 label 登记为 observe-only 并同面对齐 cron 现实，使「已安装 label 集合 == 注册表集合」重新成立
bet_id: BET-Y2Q4-T10-258
status: accepted
lifecycle: contract
last-reviewed: 2026-10-19
owner: governance-team
schema: md/v1
---

# 1 读数 — 判据由哪棵树产出

立项前实测（2026-10-19T08:54Z），注册表树 = `origin/main@4c6f5d425`，隔离检出
`~/ws-t10-258-e2-backfill` HEAD 与该 SHA 逐字相同。沿 T10-246 / T10-253 的教训：**E1/E2 不是机器属性，
是「本机 launchd × 你所在检出的注册表」的积**，所以不声明树的读数一律作废。

⚠️ 本轮立项过程中亲手踩到一次假读数并纠正：第一次 `--reality-check` 从主工作区
`~/Workspace`（HEAD `fdb106c9f`，落后 origin/main 三个批次）跑，报 E2 = 5；同一份检测器在
`4c6f5d425` 检出上报 **E2 = 1**。差额 4 正是 T10-253 已合并的 4 条登记 —— 陈旧检出的注册表看不到它们，
于是把已闭合的债重新数了一遍（PITFALL-COO-006）。**判据**：凡读治理注册表，先证明检出 == `origin/main`，
或用 `git show origin/main:<path>` 取 blob。

同一对扫描（`python3 bin/mof/gen-service-configs.py --reality-check --registry <file> --json`）
产出基线与候选两侧：

| 字段 | 基线（检出原文件） | 候选（叠加本条登记） | 期望 |
|---|---|---|---|
| `e2_undeclared` | **1** | **0** | 归零 |
| `owned_declared` / `owned_installed` | **46 / 47** | **47 / 47** | 集合相等成立 |
| `e1_drift` | 0 | 0 | 不得新增 |
| `e3_lint_debt` | 0 | 0 | 不得新增 |
| `e4_prefix_ok` / 未分区条数 | False / 18 | False / 18 | 逐字未变 |
| `e5_enabled_missing` / `e5_disabled_residual` | 1 / 1 | 1 / 1 | 不得为 E2 造新 E5 |
| `installed_total` | 76 | 76 | 本机零改动 |
| `registry_declared_total` | 74 | 75 | +1，即本条 |

候选文件 = 基线字节 + 在 `services:` 末项（`:6271`）后插入本条，其余 6 300+ 行逐字未动。

# 2 范围 — 一条，且谓词化

纳入条件（三条同时成立）：

1. `~/Library/LaunchAgents/<label>.plist` 存在，且 `launchctl print gui/501/<label>` rc = 0；
2. `classify_label(label, policy) == "workspace"`（命中 `launchd_namespace.workspace_prefixes`）；
3. 该 label 在 `origin/main` 的 `services.yaml` 里零声明。

命中 1 条：`com.omostation.omo-state-sync`。谓词而不是列表：列表每次 E2 回潮都要重写，
谓词能被检测器执行（ISC-4）。

# 3 三面对齐 — 真正要修的不自洽

这一条不是「漏登记」这么简单。同一个服务的三个真值面互相矛盾，且矛盾已被写进提交信息：

| 面 | 位置 | 基线声明 | 机器现实 |
|---|---|---|---|
| launchd | `~/Library/LaunchAgents/com.omostation.omo-state-sync.plist` | —— | **已装已跑** |
| 服务注册表 | `.omo/_truth/registry/services.yaml` | **零声明** | 应声明 |
| cron 注册表 | `.omo/cron/registry.yaml` `jobs[omo-state-sync]` | `reality: declared_only` / `status: proposed` / note「尚未安装」 | **错** |

安装证据（三个独立来源，全部带时间戳）：

- `5aa728f90`（PR #4816，2026-10-19 **07:33:35Z**）只加了 plist 与 cron 条目，提交信息写明
  「declared_only/proposed **until installed**」—— 即作者知道会有一次后续安装，但没把安装动作
  与 services.yaml 登记放在同一批；
- 本机 plist mtime/ctime = 2026-10-19 **07:35:46Z**（合并后 2 分 11 秒），与仓内
  `bin/ops/launchd/com.omostation.omo-state-sync.plist` **逐字节相同**
  （`sha256:191b69e2647d3032b7243da0181bf2e104c4801184189edcd8211a3fdcf5bff2`，3 033 字节，
  `a == b` 为 True）；
- `launchctl print gui/501/com.omostation.omo-state-sync` rc = 0，`state = not running`、
  `last exit code = 0`、`spawn type = daemon`；日志
  `runtime/cron/omo-state-sync.log` mtime 08:28:51Z，尾行是
  `artifact: runtime/omo/_delivery/ingress/state/state-sync-2026-10-19T08-27-06Z.yaml`
  —— 它按 `StartCalendarInterval Minute: 27` 真实触发过，不是装了没跑。

所以 C2 修的是**已存在为时 80 分钟的假陈述**，不是偏好。三个面必须一起翻，只翻两个仍自相矛盾。

# 4 机制 — 为什么必须 observe-only（`generate: false`）

沿用 T10-206 / T10-246 / T10-253 已验证的通道，三条结构性理由全部落在行号上（本轮重读确认）：

- **不能 `generate: true`。** 这份 plist 含 `StandardOutPath` / `StandardErrorPath` /
  `EnvironmentVariables` / `WorkingDirectory`，而 `gen_launchd_plist()` 不发射这些键；一旦
  `generate: true`，`--check` 立即逐字节比对并当场 +1 E1 漂移 —— 把已经 0 的漂移重新做坏。
- **不能走 `exempt_labels`。** `bin/mof/gen-service-configs.py:478-480` 主动把被 workspace 前缀遮蔽的
  exempt 项判为「E4 死数据」；E2 分桶由 `workspace_prefixes` 派生，`com.omostation.*` 下的 exempt 项
  结构上永远读不到。
- **`generate: false` 对 `--validate` 是零扰动，且这是代码性质而非运气。** 本轮实测两处早返回：
  `validate_service_declaration()` 在 `:156-157`（`scheduler != "launchd" or not enabled or not generate`
  → `return violations`）对本条直接空返回；`--validate` 主体在 `:627-628` 对 launchd+generate:false
  `continue`，连解释器解析都不做。`--check` 侧同理，`:652-656` 的比对循环显式跳过不生成的服务。
  因此 ISC-3 的「`--validate` 零新增违规」不是祈祷，是可复算的控制流。

# 5 `enabled` 取值与 cron 不变式

- `enabled: true`：本条已装且 LOADED，与 E5 不变式（`:503-505`「enabled ⇒ 必须已装」）一致、零扰动；
  写成 `enabled: false` 反而当场造出 1 条新的「disabled 却已装」E5 残留。
- cron 侧 `reality` 与 `status` **必须同翻**（`declared_only→installed` 且 `proposed→active`）。
  基线实测 `.omo/cron/registry.yaml` 73 条 job 的 I1（active 但未 installed）= 0、
  I2（installed 但非 active）= 0；只翻 `reality` 会 +1 条 I2 违规，只翻 `status` 会 +1 条 I1 违规。
  不变式由 `tests/unit/test_cron_registry_reality_invariants.py` 与
  `tests/test_cron_registry_contract.py` 钉住，两侧 `INSTALLED_REALITIES = {"installed","crontab_installed"}`
  （`:14`）同源。
- 三个受检测试文件**不含任何硬编码计数**（本轮 `re.findall` 实扫：
  `test_service_registry_reality.py` / `test_cron_registry_contract.py` 命中 0 处，
  `test_cron_registry_reality_invariants.py` 唯一数字命中是 dup-detector 自证里的
  `len(duplicated) == 1`），所以 +1 条登记不会撞数。

# 6 逐字段来源

`trigger` / `run_at_load` / `calendar` / `program.*` / `environment` / `outputs` 全部取自
`plistlib` 转出的实际键值，不做模板默认、不合并、不美化：

| 注册表字段 | 取自 plist | 值 |
|---|---|---|
| `label` | `Label` | `com.omostation.omo-state-sync` |
| `trigger` / `calendar` | `StartCalendarInterval` | `calendar` / `{Minute: 27}` |
| `run_at_load` | `RunAtLoad` | `true` |
| `program.interpreter` / `entrypoint` / `args` | `ProgramArguments[0..]` | `/bin/bash` / `-c` / `[<argv[2]>]` |
| `environment` | `EnvironmentVariables` | `PATH`、`no_proxy` 两条逐字 |
| `outputs.stdout` / `stderr` | `StandardOutPath` / `StandardErrorPath` | 同一文件 `runtime/cron/omo-state-sync.log` |
| `content_digest` | 安装态 plist `sha256` | `sha256:191b69e2647d…cf5bff2`（与仓内副本同值） |
| `config_source` | 指认得到就写实 | `bin/ops/launchd/com.omostation.omo-state-sync.plist` |

**`config_source` 与 T10-253 的 4 条不同**：那 4 条在检出内 grep 不到写 plist 的代码路径，只能记
「安装者未归属」并把 `config_source` 指到 `~/Library/LaunchAgents/…`；本条的源**就在仓内**
（`5aa728f90` 同时提交了 plist 文件本体），所以登记指向仓内路径 —— 这也是 ISC-4 守卫得以纯仓内可跑的前提。

`WorkingDirectory = /Users/xiamingxing/Workspace` 与 `ProgramArguments` 内的绝对 Workspace 路径
**照原样登记**，不改写：把它「修成缝」属 B4b 改道（逐批授权），不属本轮。

# 7 判据

- **ISC-1** `--reality-check --registry <本检出>` ⇒ `e2_undeclared == 0` 且
  `owned_declared == owned_installed == 47`；`e1_drift` / `e3_lint_debt` / `e4_prefix_ok` /
  E5 两项与基线逐字段相同；`installed_total` 76 不变。
- **ISC-2** 反向对照：同一次扫描里把本条声明摘掉 ⇒ E2 回到 1、`owned_declared` 回到 46。
  改后为 0 与改前为 1 必须由同一检测器、同一棵树产出（§7⑤ 纪律：只断言 0 则「少认一种形状」也能凑绿）。
- **ISC-3** `--validate --json` ⇒ `ok: true / violation_count: 0`，与基线一致（零新增）。
  CI 口径只用**仓内** plist 与注册表，不读 `~/Library/LaunchAgents`。
- **ISC-4** 新增结构守卫（纯仓内、CI 可跑）：`bin/ops/launchd/*.plist` 的每个 Label 必须在
  `services.yaml` 有声明，或在一份**钉成集合相等**的评审清单里。基线读数：8 份仓内 plist，
  6 份已声明，未声明 3 份中 1 份（本条）已装、2 份
  （`com.omostation.arch-health-weekly`、`com.omostation.panorama-refresh-guard`）
  从未安装 ⇒ 评审清单恰为这 2 条并各带理由。守卫必须**自证**：向合成树注入一份未声明 plist ⇒
  点名它；本条登记后同形不再命中（反面控制）。该守卫正是能在 `5aa728f90` 当时就拦住这次回潮的那道闸。
- **ISC-5** cron 侧：`jobs[omo-state-sync].reality == "installed"` 且 `status == "active"`；
  全文件 I1 = I2 = 0；`test_cron_registry_reality_invariants.py` + `test_cron_registry_contract.py`
  + `test_service_registry_reality.py` 全绿。
- **ISC-6** 零运行时效应，且用测量而非意图证明：交付前后 `launchctl print` rc 与 `state` 字段、
  本机 plist `sha256` + mtime、`crontab -l` 逐字节一致。
- **ISC-7** `make gac-local-gate` 硬失败集合等于基线（零新增）；新测试文件接进
  `.github/workflows/governance-check.yml` 的显式 pytest 白名单（`:118-127` 不含 `tests/unit/**`，
  不接线则 CI 永远看不见它）。

# 8 明确不做（留署名裁定，receipt 披露）

- **E4 未分区 18 条**（`com.local.*` 等）与 **E5 两条**（`com.l4.omo.sync` 声明 enabled 但无 plist、
  `com.cockpit.dashboard` 声明 disabled 但 LOADED）：装/卸与「谁 owns 一个个人 job」是署名裁定面，
  沿用 T10-253 §7 的处置。
- **`com.omostation.panorama-refresh-guard.plist` 不是合法 XML**（本轮新发现的独立缺陷）：
  头部说明注释里写了 `python3 bin/gac/panorama-refresh-guard.py --json --dry-run`，XML 注释体内
  不得出现 `--`，`plistlib.loads` 在 `line 26, column 48` 抛 `ExpatError`。这条与本 BET 无交集
  （它未安装 ⇒ 不进 E2），修它需动一份可能被别的会话正在推的 plist，且 `--validate` 一旦将来开始
  解析仓内 plist 就会当场红。登记为独立 BET，不在本轮顺手修。
- **`arch-health-weekly` / `panorama-refresh-guard` 的 `enabled` 取值**：两条仓内 plist 从未安装，
  进 ISC-4 的评审清单而不是 services.yaml —— 替它们决定「该不该活」是 G8/#116 同族裁定。
- **不改 `gen-service-configs.py` 的分桶或 E2 判据语义**；**不动任何本机 launchd / crontab 状态**；
  **不做 plist/cron 改道**（B4b 批次 2+）。
- **不宣布 ADR-0456 B1 / B3 / B4 / B5 或整个 plan 完成。** B3 的完整判据是
  「`--check` exit 0 **且** 已安装 label 集合 == registry 集合」：后半条本轮归零，
  前半条 `ok` 仍为 False（E4/E5 所致），因此 B3 未闭合。

# 9 结构性因 — E2 为什么第二次回潮

T10-253 §8 已经写下病因并列出 5 个直写 `~/Library/LaunchAgents` 而不写注册表的通道。
本轮是**同一病灶的第 5 次显形，且是第一个「仓内提交 plist、同批不提交 services.yaml」的实例**：
`5aa728f90` 加了 plist + cron 条目（84 行），没加 services.yaml 声明，E2 从 0 变 1，
B3 集合相等在 T253 合并且 14 小时后再次破裂。

这说明登记面与安装面不同源不是「某些手写 plist 的边角」，而是**提交动作本身可以只碰两个面而不碰第三个**。
因此本轮除归零外，唯一有结构价值的产物是 ISC-4：把「仓内出现 plist 就必须有声明」变成一条
纯仓内、CI 可跑、且带合成违规自证的闸 —— 它拦不住机器上的手写安装，但拦得住下一次 `git add bin/ops/launchd/`。
