---
schema_version: specification/v1
spec_version: 1.0.0
title: T7-04 场景卡归一遗留 — omo phase15/16 死链清理 + ecos 第四家存储收口
bet_id: BET-Y2Q1-T7-04
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T7-04 场景卡归一遗留 — 死链 + 第四家存储

## 1. 目标

T7-03 (PR #3226) 把场景卡从 `.omo/_truth/scenarios/*.yaml` 归一到 `docs/scene-cards/*.yaml`. 但 omo 子模块 phase15/16 仍有 6 处旧路径引用, 形成死链; ecos registry 内的 `scene-cards.yaml` 是 schema/contract 而非实例, 需在文件头加 SSOT 注记明确分工.

## 2. In scope

1. **omo phase15**: `omo_phase15.py` 内 3 处 `".omo/_truth/scenarios/research-pipeline.yaml"` 改指 `docs/scene-cards/research-pipeline.yaml` (或删除 evidence_refs, 视上下文)
2. **omo phase16**: `omo_phase16.py` 内 3 处 `".omo/_truth/scenarios/knowledge-capture-search.yaml"` 改指真实路径 (knowledge-capture-search.yaml 实际不存在, 必须删除或重定向)
3. **ecos scene-cards.yaml**: 文件头加 SSOT 注记, 明确本文件是 schema/contract, 实例在 `docs/scene-cards/`
4. 验证 `rg -c "_truth/scenarios" projects/omo/src/omo/omo_phase15.py projects/omo/src/omo/omo_phase16.py` = 0

## 3. Out of scope

- 不改场景卡本体 (T7-03 已 ship)
- 不动 `docs/scene-cards/` 内容
- 不引入新 SSOT

## 4. 验收

1. `rg -c "_truth/scenarios" projects/omo/src/omo/omo_phase15.py projects/omo/src/omo/omo_phase16.py` → 0
2. `ecos/src/ecos/ssot/registry/scene-cards.yaml` 文件头含 SSOT 注记
3. omo + ecos 子模块 commit + 主仓 pointer bump 合并到 main
