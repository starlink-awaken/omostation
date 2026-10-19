---
schema: md/v1
status: completed
lifecycle: report
owner: governance-team
last-reviewed: 2026-10-19
type: closeout-receipt
bet_id: BET-Y2Q4-T10-258
title: BET-Y2Q4-T10-258 closeout receipt — 1 条已装未声明 label 登记为 observe-only（E2 1→0）+ cron 现实三面对齐 + 纯仓内 plist 声明守卫进 CI 白名单
---

# BET-Y2Q4-T10-258 closeout receipt

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-258`
契约：`docs/superpowers/specs/2026-10-19-services-e2-observe-only-backfill-5.md`（spec_version 1.0.0，digest `sha256:71d8932ffe4c988b182f7a4265b4015fa6386a3271273fd1a5ad1d5c79f02ee4`）
Retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-258.md`
交付：PR #4823 → squash 合并 `15a6ad74775d6cf3cba6178a0d00417a4303a230`（CI 33 checks：30 pass / 3 skipping / 0 fail）

## 1 交付物

| # | 路径 | 性质 |
|---|---|---|
| 1 | `.omo/_truth/registry/services.yaml` | 新增 1 条 observe-only 声明（`omostation.omo-state-sync`，`generate: false`） |
| 2 | `.omo/cron/registry.yaml` | 同一 job 的 `reality: declared_only → installed`、`status: proposed → active`，并把「尚未安装」那句改成现实更正段 |
| 3 | `tests/unit/test_ops_launchd_plist_declared_guard.py` | 新建，9 个用例：纯仓内 plist↔声明守卫 + detector 自证 + 豁免面集合相等 |
| 4 | `.github/workflows/governance-check.yml` | 白名单点名第 8 件 + 日期化理由注释 |
| 5 | `docs/superpowers/specs/2026-10-19-services-e2-observe-only-backfill-5.md` | 契约（digest 已绑台账） |
| 6 | `docs/plans/3y-bet-ledger.yaml` | 台账条目 + spec 绑定 |

## 2 三个表面的矛盾与对齐（改前 → 改后）

| 表面 | 改前 | 改后 |
|---|---|---|
| `~/Library/LaunchAgents/…omo-state-sync.plist` | 已装（`launchctl print` 读得到，`last exit code 0`） | 逐字节未动（sha256 `191b69e2…`、mtime `2026-10-19T07:35:46Z`） |
| `bin/ops/launchd/…plist`（仓内源） | 已入库（commit `5aa728f90`，2026-10-19T07:33:35Z，早于 host mtime） | 未动 |
| `services.yaml` | 无该 label ⇒ E2=1，`owned_declared=46` vs `owned_installed=47` | 声明在案 ⇒ E2=0，`owned_declared == owned_installed == 47` |
| `.omo/cron/registry.yaml` | `declared_only` / `proposed` + 正文写「尚未安装」 | `installed` / `active` + 现实更正段 |
| `crontab -l` | 该 job 不在 crontab | 未动（sha256 `cbf14ddc…` 前后一致） |

## 3 判据实测

- **ISC-1** `bin/mof/gen-service-configs.py --reality-check --registry <本检出>`：改前 `ok=false, e2_undeclared=1, owned_declared=46, owned_installed=47` → 改后 `e2_undeclared=0, owned_declared=47=owned_installed`。`e1_drift=0`、`e3_lint_debt=0` 前后不变。
- **ISC-2**（变异对照）把本轮那条声明从 `services.yaml` 摘掉 ⇒ `e2_undeclared` 回到 1、`owned_declared` 回到 46，守卫同批 4 个用例当场红；随后按 sha256 逐字节复原。
- **ISC-3** `--validate --registry` → `{"ok": true, "violation_count": 0}` rc=0。
- **ISC-4** 守卫 9 pass；接线点 `governance-check.yml:164`（理由注释）与 `:203`（白名单行）；`tests/unit/**` 不在 `on.pull_request.paths` 里 ⇒ 白名单点名是该平面唯一的 CI 可见通道。
- **ISC-5** cron registry 不变量 I1/I2 均 ∅（73 jobs，reality `{installed 43, pending 6, declared_only 21, crontab_installed 3}`，status `{active 46, proposed 27}`）；焦点回归 66 passed。
- **ISC-6** 运行面零改动：plist sha256 / mtime / `crontab -l` sha256 三项前后逐字节相等，`launchctl list` 行数 631→631。
- **ISC-7** 本地门禁硬失败集合与基线逐条同形；`change-lane-check` 用 `--file` 回放三个 commit：本 commit `0ad20dee7` `ok=false lanes=code,docs,docs_data,governance_code,governance_state`，已在 main 的 T253 `a8f04bd05` `ok=false lanes=docs,docs_data,governance_state`、T257 `73c848b80` `ok=false lanes=code,docs,docs_data,governance_code` ⇒ 同一把尺（`allowed_for()`：`governance_state` 一混合即拒）判出的既有形状，非本轮引入。

## 4 结构性因（为什么必须有第 3 项那个守卫）

E2 的现实侧输入是 `~/Library/LaunchAgents` —— CI 上没有这个东西，`tests/test_service_registry_reality.py` 的 docstring 就明写这一点。 ⇒ 「往 `bin/ops/launchd/` commit 一份 plist 而不 commit 注册表声明」这种缺陷在 CI 上**结构性失明**：只有装过机的机器看得见。本轮补的是**纯仓内**判据（`bin/ops/launchd/*.plist` 的 label 集合 ⊆ `services.yaml` 声明集合 ∪ 豁免集），与 host 无关，因此可进 CI 白名单；豁免面按**集合相等**钉死（2 条，各带真实理由），新增即红、削减也红。

## 5 交付后一条 live 复核（ISC-6 加强）

09:27Z 恰撞登记的 `Minute: 27`：`launchctl print` 由 `job state = exited` 变 `running`（`pid 55772`，`runs` 2→3），`runtime/cron/omo-state-sync.log` mtime `2026-10-19T09:27:05Z` 且内容是 `omo state sync` 自己的输出。 ⇒ 该排程确实在执行，`reality=installed` 有据；而 plist 字节、mtime、crontab 三个写面逐字节未变、`runs` 未归零 ⇒ 本轮没有任何 bootout/bootstrap/kickstart 动作，符合 spec 的 `circuit_breaker`。

## 6 明确不做（留在台账/后续 BET）

- **E4 `e4_prefix_ok=false`（18 条未分区）** 与 **E5（2 条：`com.l4.omo.sync` enabled-missing、`com.cockpit.dashboard` disabled-residual）** 不属本轮判据，逐条准入归署名裁定。
- **B3 未闭合**：完整判据是「`--check` exit 0 **且** 已安装 label 集合 == registry 集合」。后半条本轮归零，前半条 `--reality-check ok` 仍为 `false`（由 E4/E5 所致）。 ⇒ 不宣布 B1/B3/B4/B5 或整个 plan 完成。
- `com.omostation.panorama-refresh-guard.plist` 的 XML 非法（注释体内出现 `--` ⇒ `ExpatError: line 26, column 48`）另铸 BET，本轮只在守卫里以「文件缺陷另铸 BET」的理由豁免。
- `program` / `outputs` 里的 `Workspace` 字面量按现状登记，改道属 ADR-0456 B4b 另一批。
