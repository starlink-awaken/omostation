---
schema_version: retro/v1
bet_id: BET-Y2Q1-T7-04
title: "场景卡归一遗留 — omo phase15/16 死链清理 + ecos 第四家存储收口"
closed_at: "2026-09-05T22:30:00Z"
verdict: success
---

## 回顾

### 做了什么
- 修复 omo phase15.py 中 2 处 `.omo/_truth/scenarios/research-pipeline.yaml` 死链 → `docs/scene-cards/research-pipeline.yaml`
- 修复 omo phase16.py 中 4 处 `_truth/scenarios/knowledge-capture-search.yaml` 死链 → `_truth/contracts/knowledge-capture-search.yaml`
- 在 ecos `scene-cards.yaml` 头部添加 scope note，明确该文件是 schema/contract，实例数据在 `docs/scene-cards/`

### 交付产物
- omo PR: fix/t7-04-dead-links (6 处引用修正)
- ecos PR: fix/t7-04-registry-note (scope note)
- 主仓 PR: #3246 (submodule pointers)

### 验证
- `rg -c '_truth/scenarios' omo_phase15.py omo_phase16.py` → 0 matches ✅
- gac-local-gate: pre-existing SOFT WARN only, 无新增失败 ✅

### 教训
1. T7-03 归一迁移后子模块消费者引用完整性检查缺失
2. SSOT 文件 scope/boundary 应显式声明在头部
