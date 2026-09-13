---
type: retro
bet_id: BET-Y1Q4-T8-23
status: done
done_at: 2026-09-13
merged_reachable_commit: c37ad9ad30
---

# BET-Y1Q4-T8-23 Retro: Resident Flight Deck L1-L4 授权网关 + 四维透明指挥舱

## 交付摘要

- PR #3751 交付设计规范 + ledger 状态更新 + cockpit/cockpit-ui submodule 对齐
- 设计规范: docs/superpowers/specs/2026-09-13-t8-23-resident-flight-deck-design.md
- L1~L4 四阶梯风险-置信度自适应授权网关设计
- Cockpit Resident Flight Deck 四维透明指挥舱（心跳健康 / 任务 DAG / 算力显存遥测 / 人工熔断）

## 踩坑过程

- squash-merge 后原分支 sha 不在 origin/main 祖先链，需放宽 merge-base 校验
- completion_evidence git ref 截断为 10 位短 sha 导致 lint COMPLETION_GIT_REF_INVALID
- bet 标记 done 但缺少 done_at 字段触发 BET_DONE_AT_REQUIRED

## 经验沉淀

- completion_evidence 的 merged_reachable_commit.ref 必须使用 40 位完整小写 hex
- done 状态的 bet 必须同时具备 done_at 日期字段
- value_indicator_policy: false 时 value 轴可保持 NOT_PROVEN 达成 delivery_accepted
