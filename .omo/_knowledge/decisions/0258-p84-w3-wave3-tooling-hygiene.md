---
id: ADR-0258
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-07-28
related:
  - 0256-p84-w3-throughput-wave.md
  - 0257-p84-w3-wave2-mof-d4-l0-debt.md
  - 0240-mof-d1d4-decisions-aaaa-phase1.md
---

# ADR-0258: W3 wave3 — dualtrack gap 工具 + M2 inventory + planned 卫生

## Decision

1. **产能轨可观测**: `export-dualtrack` 增加 `w3_done_target` / `gap_to_target` /
   `planned_active|inactive`；planned 递归扫子目录；`--throughput-only` 快速看 gap。
2. **能力轨 triage**: `adv-fail-report.py` 聚合对抗失败 criterion（不计产能轨）。
3. **MOF D3 前置**: `m2-ssot-inventory.py` 列出 YAML SSOT 与 ≤8 批计划（ADR-0240 P1-1）。
4. **planned 卫生**: 已 archived vision-roadmap 卡迁 `tasks/archived/`；已验收决策清单迁 `closed/`。
5. **红线**: 禁止为空冲 `done≥30` 造卡；本波只记真实工具与卫生工作。

## Status

**ACCEPTED** 2026-07-28.
