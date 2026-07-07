---
status: draft
lifecycle: architecture
owner: governance-team
last-reviewed: 2026-07-07
related:
  - ../../../.omo/_knowledge/decisions/0158-p76-phase4-promotion.md
  - ../../../.omo/_knowledge/decisions/STRAT-P76-strategic-roadmap.md
  - ../../../docs/SOP-GOD-MODULE-SPLIT.md
---

# Knowledge Foundry · 4-cron 编排 (P76 Phase 5 雏形)

> **For agentic workers**: 本文档是 DRAFT 状态, 是 P76 Phase 5 的 cron 调度设计雏形。
> 实施时间表: 启用雷达 (radar_cron) 调度, 6 小时循环。

## 0. 总览 — 4 cron 单一 deck

```
┌────────────────────────────────────────────────────────────────────┐
│              Knowledge Foundry (KFO) — 6h cycle                    │
│                                                                    │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐ │
│  │ 0:00  omo sync  │ → │ 0:30  compliance│ → │ 1:00  P74 detect│ │
│  └─────────────────┘   └─────────────────┘   └─────────────────┘ │
│           ↓                    ↓                    ↓              │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐ │
│  │ 2:00  mof-drift │ → │ 3:00  m4 score  │ → │ 4:00  bootloader│ │
│  └─────────────────┘   └─────────────────┘   └─────────────────┘ │
│           ↓                    ↓                    ↓              │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐ │
│  │ 5:00  debt-     │ → │ 5:30  submodule │ → │ 6:00  BRIEF gen │ │
│  │   closed-ratio  │   │   bump check    │   │   + INDEX sync  │ │
│  └─────────────────┘   └─────────────────┘   └─────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

## 1. 每个 cron 的细节

### 1.1 0:00 — omo state sync
```bash
uv run --project projects/omo omo state sync --json
# 触发: 每 6 小时一次
# 产出: .omo/state/system.yaml, .omo/_control/governance-data.json
# 守门: radar_backpressure > 24h 警告
```

### 1.2 0:30 — agent-workflow compliance
```bash
uv run --with pyyaml python bin/agent-workflow.py compliance --json
# 触发: 每 6 小时一次
# 产出: .omo/_knowledge/audits/compliance-<timestamp>.yaml
# 守门: P74 silent_workflow_policy warn_count > 0 警告
```

### 1.3 1:00 — P74 silent_workflow 检测
```bash
uv run --with pyyaml python bin/agent-workflow.py compliance --json | jq .p74_solidification
# 触发: 每 6 小时一次
# 产出: .p74_solidification.warn_count
# 守门: warn_count > 0 (排除 handoff-resume/observer-audit) → close run + ADR
```

### 1.4 2:00 — mof-drift 跨维度
```bash
uv run --with pyyaml python bin/mof-drift
# 触发: 每 6 小时一次
# 产出: .omo/_knowledge/audits/mof-drift-<timestamp>.yaml
# 守门: dimension 漂移 → 警示并自动修复
```

### 1.5 3:00 — M4 Health Score
```bash
uv run --with pyyaml python bin/m4-health-score.py --emit
# 触发: 每 6 小时一次
# 产出: .omo/state/m4-health.yaml (派生面)
# 守门: < 90 → 警示
```

### 1.6 4:00 — omostation-bootloader
```bash
uv run python bin/omostation-bootloader.py audit
# 触发: 每 6 小时一次
# 产出: .omo/_knowledge/decisions/draft/*.md (空时 no-op)
# 守门: ADR 草稿 > 5 → 召集 closeout
```

### 1.7 5:00 — debt-closed-per-feature
```bash
uv run --with pyyaml python bin/debt-closed-per-feature.py
# 触发: 每 6 小时一次
# 产出: .omo/_knowledge/audits/debt-ratio-<timestamp>.yaml
# 守门: ratio < 0.5 警告
```

### 1.8 5:30 — submodule-bump-check
```bash
uv run python bin/submodule-bump-check.py
# 触发: 每 6 小时一次
# 产出: stale-list
# 守门: stale > 0 → advisory; 24h → hard
```

### 1.9 6:00 — BRIEF 生成 + INDEX 同步
```bash
uv run --with pyyaml python bin/generate-brief.py --write
# 触发: 每 6 小时一次
# 产出: BRIEF.md, .omo/_knowledge/decisions/INDEX.md
# 守门: INDEX drift > 0 → 警示
```

## 2. 入口收敛 (L3 cockpit)

```
operator ──> cockpit
                ├─> cockpit agent (读状态)
                └─> cockpit governance evolution status (遍历 KFO 输出)
```

## 3. 守门总和 (Phase 5 完整守门)

| 守门 | 周期 | enforcement | 触达 |
|------|------|------|------|
| omo-state-sync | 6h | hard (radar) | system.yaml |
| agent-workflow compliance | 6h | hard | workflow registry |
| P74 silent_workflow | 6h | hard | compliance output |
| mof-drift | 6h | hard | all dimensions |
| m4-health-score | 6h | hard | M4 元模型 |
| bootloader | 6h | advisory | decisions/draft/ |
| debt-closed-per-feature | 6h | advisory | audit |
| submodule-bump-check | 6h | advisory → 24h hard | pointers |
| BRIEF generation | 6h | advisory | BRIEF.md + INDEX |
| **SUM** | **6h** | mixed | 整个 governance plane |

## 4. 守门与 L0 不变层的关系

```
L0 (ecos SSB):
  - 所有元数据写入都过 L0.constraints 验证
  - radar_cron 即 SSB 序列的旁路监听
M0 (model-driven):
  - Stage/Gate 是 cron 的元理论
  - KFO 的 "1.8 → 1.9 → close run" 即 Gate.execute()
```

## 5. 不在本雏形范围

- ❌ Knowledge Foundry 真正集成 (radar_cron 后端调度, 后续 Phase 6)
- ❌ Bootloader 自主 closeout 决策 (Phase 6)
- ❌ Knowledge Foundry vs mof-drift 双向反馈 (Phase 6)

## 6. 关联

- ADR-0158 (P76 Phase 4)
- ADR-0157 (P76 Phase 3)
- ADR-0156 (P76 Phase 2)
- ADR-0155 (P76 Phase 1)
- STRAT-P76-strategic-roadmap.md (规划)

---

*最后更新: 2026-07-07 · P76 Phase 5 雏形 · DRAFT · 待 Phase 6 实施*
