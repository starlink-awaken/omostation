---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-01
type: report
bet_id: BET-Y2Q4-T10-219
title: BET-Y2Q4-T10-219 closeout — system.yaml 字段写者归属实测，并让它第一次变得可机器校验
---

# BET-Y2Q4-T10-219 closeout — ADR-0456 B5 前置（字段写者归属）

契约：`docs/superpowers/specs/2026-10-01-bet-219-system-yaml-field-writer-ownership.md`
（v1.0.0，`status: accepted`，`lifecycle: contract`，digest
`sha256:30c50e4c138dcd27f2a1175869c1b5f3ca6237c79a381a141a27e8682d5c2cfb` —— 已按该值绑定进台账；
初稿 `37f799686b2f…` 因缺 `owner` frontmatter 被 `doc-governance-check` 判成新告警而重算，见 §6）。
交付：`bin/gac/omo-state-write-guard.py`（新增 `check_field_ownership()` + 自身双根修正）、
`.omo/_truth/registry/write-owners.yaml`（`fields` 段重写）、`bin/mof/generate-brief.py`（叙述改判据）、
`tests/unit/gac/test_omo_state_write_guard.py`（11 例，全 hermetic）。
run：`20261001T122818Z-project-doc-change-3ce40676`（governance-agent）。
复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-219.md`。
台账条目随 PR-2 走（`path:docs/plans/3y-bet-ledger.yaml` 被在活 run
`20261001T121621Z-project-code-change-6049af3d` 持有，不抢别人的锁）。

## 1 立项依据是一个测量，不是一段叙述

`fields` 段自登记以来**没有任何消费者**：`bin/ssot/write-owner-audit.py:54` 取的是
`data.get("write_owners")`（路径段），对该文件里 `fields` 的 grep 命中数为 **0**。
后果不是"少一条检查"，而是声明可以与事实任意背离而不报错。实测 HEAD 版：

| 量 | 值 |
|---|---|
| `fields` 声明键数 | **14** |
| `.omo/state/system.yaml` 实有顶层键 | **23** |
| 声明且存在 | **6**（`current_phase`、`governance_anomaly_score`、`health_score`、`health_score_generated_at`、`runtime_health_summary`、`service_online_ratio`） |
| 声明但文件里没有（幽灵） | **8**（`phase41_status`、`phase42_status`、`phase43_status`、`phase44_status`、`next_milestone`、`debt_adjusted_health_score`、`debt_items_total`、`debt_items_resolved`） |
| 存在但没声明（无主） | **17** |

覆盖率 6/23。幽灵还分两种去留理由，都记在 registry 注释里而非"看起来没用了"：
`debt_adjusted_health_score` / `debt_items_total` / `debt_items_resolved` 在**全仓零引用**；
`phase41-44_status` 是**不可达**——`ALLOWED_FIELDS` 白名单只放 `phase28_status`，
所以这四个键永远不会出现，声明它们是死条文。

## 2 三类违规，且新校验真的会响

`check_field_ownership()` 产出 `undeclared-key` / `ghost-declaration` / `unresolvable-owner`。
`owner` 词表本轮收敛为 `script:<repo-relative>` | `daemon:` | `human:` | `broker:` | `anyone`，
`script:` 者必须校验目标文件存在（绝对路径与含 `..` 的路径各判一条违规）。

不靠"应该能抓到"，靠一次瞬时注入探针（判据 3）：把真实 `system.yaml` 复制到 `mktemp -d`、
加一个 `probe_undeclared_key`、以 `OMOSTATION_STATE_ROOT=$T` 跑 guard ——

```
exit 1
  "check": "undeclared-key",
  "key":   "probe_undeclared_key",
  "message": "Top-level key 'probe_undeclared_key' is written into .omo/state/system.yaml
              but has no owner in write-owners.yaml"
```

仓内跟踪文件一个字节未动，探针只在 tmp 里。

**一处刻意的 fail-open**：`state_root()/.omo/state/system.yaml` 不存在时（全新 dev 状态根首启），
三条检查一律返回空。这是沿用该 guard 既有行为，不是本轮新造的洞，已用一条测试钉住；
它意味着"缺文件"不等于"零违规"，判据 5 因此取 HEAD 版键集而不是工作副本来做等式。

## 3 23 个 owner 是量出来的：8 个写者模块、34 条键-写者边

| 写者模块 | 认领键数 |
|---|---|
| `projects/omo/src/omo/omo_audit_sync.py` | 9 |
| `bin/compass_radar.py` | 9 |
| `projects/omo/src/omo/omo_state.py` | 8 |
| `bin/gac/evidence-smoke.py` | 3 |
| `projects/omo/src/omo/omo_ingress_state.py` | 2 |
| `bin/gac/harness-omo-bridge.py` / `bin/gac/unified-health-score.py` / `bin/gac/self-evolution-loop.py` | 各 1 |

三个只有读代码才能定对的地方：

- **`bin/compass_radar.py` 而不是 `bin/meta/compass_radar.py`** —— 两份副本都在仓里，
  挂进 cron 的是前者；owner 指向副本等于校验一个不执行的文件。
- **同键多写者用列表，不用 `anyone` 糊过去**：`health_score` 有 3 个写者
  （compass_radar、`unified-health-score.py`、`omo_audit_sync.py`）依次覆写同一个键，
  `updated_at` 同样 3 个。声明成单 owner 会直接把事实写错。
- **有条件缺席的键一律不声明**（`next_milestone`、`health_score_raw`、`debt_watchlist_count`、
  `debt_gate_count`、`phase28_status`）—— 它们今天不在文件里，提前声明就废掉了
  `undeclared-key` 这条线：将来第一次真正落盘时会静默通过。判据选择让它们**第一次落地即触雷**。

## 4 guard 自己就是 ADR-0456 的违规者——先修自己再立门禁

改前 `omo-state-write-guard.py` 用 `__file__` 反推根。本轮把两个面分开：
`system.yaml`（写面）走 `state_root()`、`write-owners.yaml`（读面、治理 SSOT）走 `code_root()`。
判据 4 用读数把它们分开证明，而不是靠措辞：

```
SPLIT-OK write=/var/folders/…/tmp.QMynGJdTN6/.omo/state/system.yaml
         read=/Users/xiamingxing/ws-t10-218-write-owner-coverage/.omo/_truth/registry/write-owners.yaml
```

未声明 profile 时 `system_yaml` 必须逐字节等于检出内路径（不变量，同 T10-217），由判据 1 的测试钉住。

接线方式守了 done_when-1：**不新增 gate step、不动 bin-quota** ——
`bin/gac/gac-local-gate.py:218-223` 早就把 `bin/gac/omo-state-write-guard.py` 当命令跑
（step id 列在 `:976`），新校验加进该脚本即被既有 step 带响。

## 5 本轮量到、但按 non-goals 留在门外的两个缺陷

1. **G-CONV.5 `single_writer_immune` 是一条永久 hard fail，坏的只是一条路径。**
   `bin/gac/m1-closeout-report.py:216-232` 判 `ok = write_owners.is_file() and repair.is_file() and pre-commit 接线`，
   其中 `repair = bin/ssot/write-owner-repair-draft.py`。实测该路径**不存在**
   （`git cat-file -e HEAD:bin/ssot/write-owner-repair-draft.py` → 不在 HEAD），
   脚本本体还在，是被 `bca29b64e`（**#1839** "migrate scripts repo tools to root bin/ + archive scripts repo"）
   迁进了 `bin/_archive/write-owner-repair-draft.py`，**引用没跟着改**。`--json` 读数：
   `{"id":"g-conv.5","ok":false,"hard":true,"detail":{"write_owners":true,"repair_draft":false,"pre_commit_wired":true}}`
   —— 另两个合取项都为真，即写者免疫面本身完好，红的只是那条路径。
   它够不到 CI：`.github/workflows/phase-gate-enforce.yml:3` 明写
   "no m1-closeout-report import (anti self-blind, ADR-0202 D1)"。所以后果形态是
   **谁跑谁红一次**，并把"写者免疫破了"这个假信号常驻在治理报告里。修它 = 改一行路径，
   不在本轮 write_surfaces，另立。
2. **门禁自己造跟踪文件脏项**（第四次实证）。`make gac-local-gate` 经
   `bin/gac/evidence-smoke.py` 重写 `health_score_evidence_generated_at`，
   本轮实测 diff 恰为一行 `2026-09-27T08:42:13… → 2026-10-01T12:41:20…`，`git checkout --` 剔除。
   同坑 #4346 / #4359 / T10-217；这也是判据 5 为什么必须读 HEAD 而不是工作副本。

## 6 我自己交付物里的三处"跑不通"——提交前改掉

立完项第一次跑 `--execute` 就暴露两处**判据自身**的错（不是被测对象的错），
`git add` 之后又暴露第三处**文档自身**的错：

- 判据 4 初稿读 `json['system_yaml']`，而 guard 的 JSON 把它放在 `targets` 下 →
  永远 `KeyError`，exit 1。修正为 `['targets']['system_yaml']` 后同一条命令 exit 0（§4 读数）。
- 判据 6 与 done_when-6 写"交付文件清单恰为 **6 项**"，那是 receipt + retro 进 `write_surfaces`
  **之前**的草稿数（T10-217 的教训就是把这两行提前写进 scope）。改成"8 项"后跑真实读数仍是错的 ——
  `write_surfaces` 有 8 项，但台账那项被并发 run 的路径锁挡住要走 PR-2，**PR-1 交付清单是 7 项**。
  最终措辞按实测的拆分写（7 + 台账 1 走 PR-2），而不是按 scope 集合大小写。
  判据：**文件数类判据要按"这一次交付实际携带什么"写**，`write_surfaces` 是权限集合、不是交付集合。
- **spec 的 frontmatter 少 `owner`**，而这条只在文件被 git 跟踪之后才现形：
  `doc-governance-check.py --scope tracked` 在文件 untracked 时报
  `PASS (4530 files, 145 warnings)`；`git add` 之后同一条命令报
  `missing_frontmatter … bet-219-system-yaml-field-writer-ownership.md: missing required frontmatter fields: owner`，
  并升级成 `.omo/_truth/registry/document-governance.yaml: unbaselined_warning [error]
  (missing_frontmatter:accepted-specifications count=1)`。
  同目录两份已合并的 accepted spec（T10-216 / T10-217）都带 `owner: governance-team`。
  补齐即改内容，**digest 必须重算并回写台账绑定**：
  `37f799686b2f…` → `30c50e4c138d…c2cfb`，`bet-ledger.py lint` 复跑 `OK — 514 bets, no errors`。
  判据：**新建文档的治理检查要在 `git add` 之后跑**（`--scope tracked` 看不见未跟踪文件）；
  改任何 `lifecycle: contract` 文档都是一次 digest 事件，不是"顺手补一行"。

教训与 AGENTS.md §11"验收条款先实证通道行为"是同一条，本轮是我自己连踩三次：
**判据落台账之前必须先跑一遍**，否则它是一条永远不会绿的条文，
而下一个人会把它读成"交付有问题"。

## 7 七条 verify 的读数

| # | 命令 | 读数 |
|---|---|---|
| 1 | `pytest tests/unit/gac/test_omo_state_write_guard.py -q` | `11 passed in 0.60s`（含未声明键 / 幽灵 / 不存在 script 路径 / 绝对路径与 `..` / 缺文件 fail-open / `--json` 出口形状等负例，全走 tmp） |
| 2 | `omo-state-write-guard.py --json` | exit 0，`declared=23 present=23`，`undeclared-key=0 ghost-declaration=0 unresolvable-owner=0`，`findings=[]` |
| 3 | 注入探针 | exit 1，`undeclared-key / probe_undeclared_key`（§2） |
| 4 | 双根拆分 | `SPLIT-OK`，exit 0（修正后，§6） |
| 5 | HEAD 键集 vs registry 双向相等 | `missing []` `ghost []`，exit 0 |
| 6 | 交付清单 | exit 0：`.omo/state/**` 与 `BRIEF.md` 零命中，PR-1 打印 **7 项**（台账是第 8 项，走 PR-2） |
| 7 | `make gac-local-gate` | `GaC local gate: PASS (68 checks executed, 1 SOFT WARN)`，另 6 条 known-unavailable 跳过；无新增 hard fail |

判据 2 的三个 0 **就是交付物本身**：不是"门禁没响"，而是"响过、且现在没有可响的"。

文档治理面两份新文档各跑一次对读：`doc-governance-check.py --no-new-warnings --scope tracked`
= `PASS (4533 files, 145 warnings)` —— 文件数 +3（spec/receipt/retro），**告警数与 T10-216/217
轮末值相同**，即三份新文档零新告警。markdownlint 按仓内 `.markdownlint.json`
（关 `MD013`/`MD033`/`MD041`，`MD024.siblings_only`）逐文件与**已合并的同批文档**比规则集合：

| 文档 | 规则集合 |
|---|---|
| 本轮 spec | `MD025×1 MD060×10` |
| 已合并 T10-217 spec | `MD025×1 MD060×10` |
| 本轮 receipt | `MD025×1 MD040×2 MD060×14` |
| 已合并 T10-217 receipt | `MD025×1 MD040×2 MD060×10` |
| 本轮 / T10-217 retro | 各 `MD025×1` |

规则**集合**逐条相同（MD060 计数差只是表格行数差），即本轮没有带入任何新的违规类别；
`MD060`/`MD025` 是 `docs/superpowers/specs/**` 与 `docs/reports/**` 的既有背景噪声，
本轮不顺手改（改了会与同批已合并文档风格不一致，且属生成器/风格议题而非本轮契约）。

## 8 交付边界

未搬任何字段、未 `git rm --cached`、未改 `.gitignore` / `runtime-projections.yaml`（键摘库 = T10-220）；
未动 `projects/omo/**` 与 gitlink（`updated_at` 与 5 个 task 计数键的写者在
`omo_state.py:352-364` / `omo_audit_sync.py:319-335`，且 `omo_state.py:33` 无视
`omo_paths.STATE_SYSTEM_YAML`，属子模块批次）；未改三个检出根钉住的写者的根
（`harness-omo-bridge.py:181`、`self-evolution-loop.py:28`、`compass_radar` 的 `ws_root`）；
未碰 `write_owners` 路径段（消费者 `write-owner-audit.py:54` → pre-commit G-CONV.5，
改 owner 串会改变 pre-commit 行为）；未解决 `health_score_evidence` 的双口径覆写
（`compass_radar:1420` 把 evidence-smoke 的字段改写成自己的 `health_score` 并换掉 source 串，
本轮只把它写成读数）；未启停任何服务、未改 plist/cron、未删并发会话的锁。
