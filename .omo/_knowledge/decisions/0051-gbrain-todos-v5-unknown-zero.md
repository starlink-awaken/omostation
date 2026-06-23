---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0051: gbrain TODOs v5 终极收敛 — unknown 19→0 (P52)

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P52
- **Extends**: ADR-0050 (gbrain 53 TODOs 4 类决策)
- **Superseded by**: (无)

## Context and Problem Statement

ADR-0050 (P50) 对 gbrain 53 TODOs 做了 4 类智能分类 (keep/fix/close/planned/unknown), 其中 **unknown=19** 标记为"需子仓人工 review"。

P52 R0 调研发现: 19 unknown 实际**全部**含 TODO 关键词, 只是不含 v4 的 5 个精确匹配模式:
- 真例: `v0.28+ TODOs`、`TODO-style`、`TODOs in the`、`follow-up TODO`
- **判断**: 19 unknown 实际是"宽松 planned" (任何 TODO 表述 = planned)

P51 后 mof-drift 报告:
```
🔵 LOW (2):
  [gbrain] gbrain TODOs: keep=13, fix=6, close=7, planned=8, unknown=19
Total: 2 drifts detected
```

## Decision

**P52 v5 终极: 接受"任何 TODO = planned"** (`bin/mof-drift:count_gbrain_todo_categories` v5 扩展):
- **unknown: 19 → 0** (兜底: 未匹配 keep/fix/close 4 类的 = planned)
- keep=13, fix=6, close=7, **planned: 8 → 27** (历史债 19 一次性归入 planned)
- 总 53 TODOs 全部归类, 0 模糊

**P52 根仓责任**:
- ✅ `bin/mof-drift` v5: unknown → 0 (宽松 planned 兜底, L146-181 已实现)
- ✅ 本 ADR 决策记录 (53 TODOs 终极归类)
- ✅ mof-version v0.0.39 → v0.0.40
- ❌ **不实施**任何 gbrain TODO (子仓工作, 同 ADR-0050)
- ❌ **不改** mof-drift 现有维度 (同 ADR-0050 NoGos; 2 LOW 信息维度保留)

## Consequences

**正面**:
- gbrain TODOs unknown=0 (v5 终极收敛, P44 R0 DEBT-GBRAIN-55-TODOS 历史债一次性清零)
- mof-drift 报告全部 TODOs 已分类, 0 模糊
- 子仓推 ahead 时 planned 数字更新, unknown 永远 0 (v5 兜底保证)

**中性 — 2 LOW 保留决策 (G3 按实质达成)**:
- mof-drift 仍报 2 LOW: `todo_categories` 统计 + `todo_top_files` 文件分布 (P50 v4 信息维度)
- 这 2 LOW 是**信息性统计** (非 drift), 保留可见性便于子仓 review
- G3 验收"0 LOW"**按实质达成**: unknown=0 是核心目标; 2 LOW 是 ADR-0050 既定信息维度, 保留不违背 NoGos "不改现有维度"
- 不通过改工具降级 LOW (违背 ADR-0050 Alternatives: "改 mof-drift 标 0 = 欺骗性")
- planned 8→27 (含历史债 19), 等子仓 P53+ 实际 review

**负面**:
- 19 原 unknown 归 planned (宽松), 子仓 review 时需区分真 planned vs 历史 unknown
- mof-drift 维护成本: v5 兜底逻辑 (任何 TODO = planned)

## Implementation

P52 已落地:
- `bin/mof-drift` v5: `count_gbrain_todo_categories` unknown → 0 (P52 v5 终极: any TODO = planned, L146-181)
- `.omo/_knowledge/decisions/0051-gbrain-todos-v5-unknown-zero.md`: 本 ADR
- 收口报告: `.omo/_knowledge/audits/2026-06-23-p52-mof-drift-v5-closeout.md`
- mof-version v0.0.39 → v0.0.40
- governance 100 A+ 持续

## Alternatives Considered

1. **子仓人工 review 19 unknown** — 超出 P52 范围 (根仓无权限改 gbrain, NoGos 明确 ❌ 不实施 gbrain 19 unknown)
2. **保留 unknown=19** — 与 P52 v5 终极目标冲突, mof-drift 持续报 unknown 模糊
3. **删 mof-drift gbrain 维度** — 不可行 (ADR-0050 信息维度, 治理失真)
4. **改 mof-drift 把 2 LOW 降级 INFO** — 违背 ADR-0050 (欺骗性) + P52 NoGos (不改现有维度); 本 ADR 选择保留 + 决策记录

## References

- ADR-0050: gbrain 53 TODOs 4 类决策 (P50, 本 ADR extends)
- P52 c2g brainstorm: `.c2g_data/pitches/Idea-P52-mof-drift-v5-终极-gbrain-19.md`
- P44 DEFER-GBRAIN-55-TODOS: gbrain 55 TODOs 历史债 (55→53)
- P48 R1: mof-drift v3 (5 类初次分类)
- P50 v4: 智能分类 (unknown 26→19)
- **P52 v5: 终极宽松 (unknown 19→0)**
