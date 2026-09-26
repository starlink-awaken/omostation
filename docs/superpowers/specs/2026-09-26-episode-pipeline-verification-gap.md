---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Episode Pipeline Verification Closure — SH-5 done_when 未达成与探针失效
bet_id: BET-Y2Q4-SH-5.2
---


# BET-Y2Q4-SH-5.2 — Episode Pipeline Verification Closure

## Context

`BET-Y2Q4-SH-5`（Episode Pipeline Activation）在台账记为 `status: done`，其
`done_when` 第一条是一个机器可判的条件：

> closeout synchronously invokes scene-outcome-recorder; ledger accumulates **≥1
> `producer=scene-outcome-recorder` row** within 24h of deployment.

2026-09-26 对生产 event ledger 的直接测量显示该条件**至今未达成**：

```
db: runtime/omo/event-ledger.sqlite3
total_events: 7
producer_distribution: {'omo-personal-episode': 6, 'omo-sovereignty': 1}
scene-outcome-recorder: 0        ← done_when 要求的行
ok: True                          ← 探针仍然放行
```

这不是历史遗留。该测量在 #4368（SH-5.1 principal-id 规范化）、#4369（scene-map 单文档
修复）、#4370（SH-5.1 收口）全部合入 origin/main **之后**复验，结论不变。

## 已定位并修复的根因（不在本 bet 范围内）

`bin/ssot/workflow-scene-map.yaml` 曾被写成两个 YAML 文档（数据段之后又出现一行 `---`
接说明性 prose）。`yaml.safe_load` 对多文档流抛 `ComposerError`，而
`bin/agent-workflow.py:_bridge_closeout_to_scene` 把它包在 `except Exception: return`
里静默吞掉 → 桥在每一次 closeout 都提前返回、一次都没有调用过 recorder。

该解析缺陷已由 **#4369** 修复（合并为 `8ba75e5b0`），修复后桥确实第一次产出了
`actor=closeout-bridge` 的 episode。**但桥的下游落账仍未达标**，且暴露了两个比"解析失败"
更值得处理的结构性问题，这就是本 bet 的范围。

## Problem

1. **探针测的是代理量。** `bin/gac/check-episode-pipeline.py:70` 的放行条件是
   `episode_count >= 1`，而该计数取自 `producer = 'omo-personal-episode'`（脚本 docstring
   第 5 行自述），**不是桥自己的 producer**。于是 6 条 `omo-personal-episode` 就足以让
   检查长期报 `ok: True`，而桥完全死亡也没人报警 —— 一个"为验证 SH-5 而造的仪器"无法
   验证 SH-5。这是"done 状态与实况不符"能够长期存在的直接机制。

2. **桥的产出落点与其 done_when 的度量口径不一致。** 实测：修复后 `scene-outcomes.jsonl`
   确实收到了 `closeout-bridge` 记录，但 `event_log` 中 `producer=scene-outcome-recorder`
   仍为 0 行。两者是分开的存储，`done_when` 断言的是后者。需要查清 recorder 的 ledger
   写入路径（`_write_event_ledger_outcome`）在真实 closeout 下是否被走到、其 `producer`
   标签到底是什么，再决定是修写入还是修正 `done_when` 的度量口径。

3. **静默吞异常的模式未被消除。** #4369 修掉了触发它的那个输入，`except Exception: return`
   本身仍在 `_bridge_closeout_to_scene` 里（同类结构至少 import / safe_load / scene_card
   三处）。下一次任何输入畸形，症状依旧是"零输出 + 零报错"。

4. **episode 存储是 gitignored 的运行时流。** `.gitignore:23` 排除
   `.omo/_knowledge/workflow-mesh/`，注释写明"运行时事件流，高频 churn，非治理 SSOT"。
   因此 worktree 内产生的 episode 随 `release` 一起消失。桥恢复后证据能否留存，需要 owner
   判断（属本 bet 的调查项，不是本 bet 擅自变更 .gitignore 的授权）。

## Goals

- G1：把 `check-episode-pipeline.py` 的放行判据从代理量改为桥自身的 producer，使
  done_when 第一条真正可判；沿用 SH-5 的"warn-only initially"口径接入，不在本 bet 内翻转
  共享 gate 的退出码。
- G2：查清并修复 `closeout → recorder → event_log` 的落账链路，使一次真实 closeout 能
  在 `event_log` 中留下可指认的行，或给出"该判据本身写错了"的结论并据实修正度量口径。
- G3：将 `_bridge_closeout_to_scene` 的静默返回改为可观测信号（不吞异常改为至少留痕），
  使同类失效不再表现为"正常运行"。

## Non-goals

- 不回填历史 closeout 为 episode（沿用 SH-5 `non_goals` 原文：*Do not backfill historical
  closeouts as episodes*）。本 bet 只走前向路径。
- 不修改 `PersonalEpisodeService` 的 gate 算法（30 qualifying + 4-week floor）。
- 不认领 `BET-Y2Q4-SH-6` —— SH-5.1 的 `non_goals` 已把 "refactor OMO_PRINCIPAL_ID usage
  across all callers" 明确 deferred 给 SH-6，本 bet 用 `SH-5.2` 子号，不占该语义位。
- 不修改 `governance-checks.yaml` 任何 registry 规则。
- 不回填、不改写 SH-5 / SH-5.1 的历史 done 记录与本仓任何历史审计结论；台账差异由本 bet
  自身条目承接。
- 不擅改 `.gitignore`；episode 存储留存策略作为调查项呈报 owner。

## done_when

1. `python3 bin/gac/check-episode-pipeline.py --json` 的 `ok` 判据可指认地绑定到桥自身
   producer（或该判据被明确改写并在 docstring 说明理由），且存在一个用例能在"桥产出 0 行"
   时使检查为假。
2. 一次真实（非 mock）closeout 之后，测量给出明确结论之一：`event_log` 中出现该桥写入的行
   （附 producer 标签实测值），或出具"done_when 第一条度量口径写错"的书面判定并同步修订
   SH-5.2 自身的 done_when。
3. `_bridge_closeout_to_scene` 在输入畸形时不再表现为静默成功 —— 有一条测试或留痕路径能
   证明该状态可被观测到。
