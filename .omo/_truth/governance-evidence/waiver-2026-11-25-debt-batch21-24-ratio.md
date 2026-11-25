---
schema_version: governance-waiver/v1
status: active
lifecycle: history
type: governance-ratio-waiver
owner: governance-agent
created: 2026-11-25
last-reviewed: 2026-11-25
bet_id: null
pr_numbers:
  - 5553  # 批次21-24：6 条判据/交付面机制债登记（纯 .omo/debt/items + debt.yaml，不碰 gitlink/services/阈值）
waiver_scope: PR #5553 single merge — 批次21-24 治理登记 run 造成的 30d governance ratio 越顶
---

# Waiver — 批次21-24 debt 登记的 governance-ratio 单次 merge 豁免（principal 已裁）

> ADR-0249 / P85 治理预算 40% ceiling 的**单次 merge** 豁免。形状与字段沿用先例
> `waiver-2026-09-17-4019-pitfall-fixes-ratio-debt.md`。本文件不改阈值、不改分类、不缩窗口起点。

## 授权原文（principal，2026-11-25）

问：「治理占比已被我这批登记推过 40% 上限（40.14%），后续治理批次怎么处置？」
答：**「走 waiver 承认这次超额」**

## 归因读数（可复算）

判据：`python3 bin/gac/check-governance-ratio.py`（population = `.omo/_delivery/agent-workflows/events.jsonl`
里 `event == agent_workflow_start` 且 `ts` 落在 `[max(now-30d, ENFORCED_FROM), now]`，分类见 `_classify:127-133`，
`GOVERNANCE_PROFILES` 含 `governance-agent`）。

| 读数时点 | 读数 |
|---|---|
| 2026-11-25T03:00Z（批次24 commit @`ead9c1fe6`） | `total=142 governance=57 ratio=40.1%` → FAIL (blocking) |
| 同窗口剔除 `20261125*` 的 4 个 `governance-state-mutation` run 后 | `total=137 governance=53 ratio=38.69%`（< 40%） |
| 2026-11-25T05:56Z（批次25 run 起后） | `total=141 governance=58 ratio=41.1%` → FAIL (blocking) |

⇒ 越顶由本串批次（`20261125T013212Z-be430a84` / `20261125T023431Z-0e51fdb9` / `20261125T025535Z-9d737c52` /
`20261125T055634Z-61c74ab7`，均属 `governance-agent` profile）造成；`bet-execution` 那条判为 flex 不计。
两次读数间 total 由 142 变 141，是 30d 窗口滚动令一条历史 start 事件出窗——本豁免绑定的是**当下这次越顶事实**，
不是某个固定总数。

## 本 PR 交付内容为何值得豁免

- 6 条债条目全部是**判据自身可靠性**类缺陷（扫源码的门禁不自证、只判文件存在、读宿主状态、有实现无接线），
  属本仓 `docs/pitfalls.md` 最大主题簇，逐条给变异/复现读数。
- 写面收敛在 `.omo/debt/items/**` + `.omo/_truth/registry/debt.yaml`（`seed_items` 113 → 119，无重复）；
  **不碰** `projects/ecos` gitlink、services 配置、launchd、任何 gate 阈值或接线。

## 生效边界与已知局限

1. `_active_waivers():281-287` 只在 env `GITHUB_PR_NUMBER` 存在时取数（CI 注入）⇒ **本地 `make gac-local-gate`
   与 workflow `verify` 不受本文件影响，仍判 FAIL**。因此批次 22/23/24 的 run 已按 `--status blocked` 如实入账
   `verify_ok=false`，本豁免不追溯改写那些读数。
2. 仅覆盖 PR #5553 这一次 merge；后续治理批次若再越顶需各自绑定 PR 号重开 waiver，**不构成常驻许可**。
3. 若 principal 认为应走另一条路（缩 `ENFORCED_FROM` 起点，或按先例 #3877 做 `_classify` 前向修正），
   把本文件 `status` 改为 `superseded` 即可失效——本文件不自行延长效力。
