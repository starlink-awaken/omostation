---
schema: md/v1
status: completed
lifecycle: evidence
owner: xiamingxing
last-reviewed: 2026-11-26
type: report
bet_id: BET-Y2Q4-T10-354
title: BET-Y2Q4-T10-354 合并后独立复测 — done_when#3 真值为 drifted，BET 暂不置 done
---

# BET-Y2Q4-T10-354 合并后独立复测

复测环境：worktree `/Users/xiamingxing/ws-t354ledger`，HEAD = origin/main = `4f074508b`
（`zhixing-host-sync.py check` 自报 `behind_origin_main: 0` / `stale: false`，即齐备非陈旧检出）。
live payload 取自 `curl http://127.0.0.1:43191/data.json`（HTTP 200，114 顶层键）。

## 结论

**本 BET 暂不置 done。** 工程腿（PR #5586，squash 合并 `cd4ae2ec3`）本身成立且已落地，
但 done_when#3 在合并后的真值是 **drifted**，不是先例记录的 in_sync；页面尚未吃到修复。
把 evidence matrix 写成 `operational: PROVEN` 会替一个未生效的交付盖章。

## done_when 逐条复测

| 条款 | 命令 | 本次实测 | 判定 |
|---|---|---|---|
| #1 模板 `D.<7 字段>` 引用清零 | `python3` 对 `bin/panorama/assets/host/template.html`（6493 行）跑 `re.findall(r"\bD\.<field>\b")` 七字段求和 | **0 命中** | 达成 |
| #2 守卫 dry-run missing 7 → 0 | 复刻 `_check_template_data_consistency`（`bin/panorama/panorama-collect.py`：`refs = set(re.findall(r"D\.([a-z_][a-z0-9_]*"), template))`，`missing = refs - payload 非空键`）× live payload | SSOT 模板 refs **55**、missing **[]** (0) | 达成（限 SSOT 面，见下） |
| #3 `zhixing-host-sync.py check` 维持 in_sync | `python3 bin/gac/zhixing-host-sync.py check` | rc=1，`ok: false`，`template.html state: drifted`，`source_sha 0fd5ce5d… ≠ runtime_sha 70999e07…` | **未达成** |

## #3 为何与先例读数相反（时序，非分歧）

- 合并瞬间：`mergedAt = 2026-11-25T14:38:42Z`（本地 22:38）。
- 最新 release `releases/4ac8447107…`（= `current` symlink 目标）目录 mtime **11-25 15:59 本地 = 07:59Z**。
- 即**当前在跑的 release 早于合并 6h39m**，其 `template.html` 四个最近版本 sha 一律 `70999e07…`（修复前）。

先例回执 `docs/reports/2026-11-25-dashboard-template-contract-t10-354-closeout.md` 生成于
`2026-11-25T14:00Z`，**早于合并 38 分钟**，且明写「主仓对照实测」。主仓当时并非 origin/main
（本次实测：canonical HEAD `488d737ca` ≠ origin/main `4f074508b`，其 debt registry 128 条 vs 主干 130 条）。
`zhixing-host-sync.py:852-856` 正是为这种读数写的告警：「源真值来自哪棵树——缺了它，在陈旧检出上跑会报
`in_sync` 假安心」。**#3 的原始判定属该假安心形状 + 合并前时点，两者叠加。**

## 另一条仍活的告警（属本 BET non-goal，但影响解读）

守卫实际读的不是 SSOT，而是 `ZHIXING_DASHBOARD_CODE_ROOT`（默认 `~/.local/share/zhixing-dashboard`）
下的那份副本：6372 行、refs **62**、missing **7**（原样是那七个字段）。spec 已把它列为 non-goal
（「不动宿主根 stale 副本」），所以**发布时的告警仍会打**——债条目标 `resolved` 与之不矛盾，
但别把「SSOT 清零」读成「告警消失」。

## 待 owner 裁定（未代决）

1. 让修复真正生效需一次 `python3 bin/gac/zhixing-host-sync.py publish`（受管发布：版本目录 +
   原子切 `current` + SHA 校验 + `restore` 回滚）。属部署面动作，本次未执行、也未申请。
   注意 `apply` / `capture` 在 `:119` `BLOCKED_COMMANDS` 内，只有 `publish` 是正规通路。
2. `com.omostation.zhixing-host-drift`（= `workspace-wip-guard.py protect && zhixing-host-sync.py check`）
   上次退出码 1，其 err.log 末次写入 **10-08 16:57**（内容即宿主根 template/refresh/live_server 三件漂移）
   —— 漂移守护是否还在跑、该由谁 heal，是独立于本 BET 的一面，建议单独立项而非并入本条。
3. 服务实际运行根为 `releases/485e2518…--pub-682a2e7f…`，与 `current → 4ac84471…` **不同**；
   「发布平面到底改变了哪一字节」的判据缺口与已 closed 的 `ZHIXING-PUBLISH-EFFECT-PROVENANCE` 相邻，
   是否 reopen 由 owner 定（本次不动他人条目字段）。

## 台账处置

- `BET-Y2Q4-T10-354`：`status` 保持 `pending`，**不写** `completion_evidence`，不跑 `bet-ledger.py complete`。
  理由：`cmd_complete` 要求派生态 `delivery_accepted`（`bet-ledger.py:3350`），而 `value_indicator_policy: false`
  下该态要求 `operational: PROVEN`（`:1999-2004`）；#3 未达成 → 如实记 DEGRADED 会让派生态为 `blocked`（`:2013`）。
- 本回执即「先核证据再入账」的产物；重跑 #3 的判据命令附在上面表格第三行。

## 回滚

本文件为新增只读证据，revert 单提交即可；未改工程面、未改台账状态。
