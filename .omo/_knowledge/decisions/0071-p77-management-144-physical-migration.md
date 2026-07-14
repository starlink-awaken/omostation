---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0071: P77 management 144 物理迁移 (workflows/playbooks/guides)

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P77
- **Extends**: ADR-0069 (P75 management 142 frontmatter 分类)
- **Superseded by**: (无)

## Context and Problem Statement

P76 收口后, P77 调研 3 项候选, 实施 1 项:

1. **management 144 物理迁移** (沿 P75 category, 拆 3 子目录)

跳过 2 项:
- 跨子仓联动 (P78+ 评估)
- graphify 实际扫描 (需 OPENAI_API_KEY, 已留 wrapper)

## Decision

### D1: management 144 物理迁移 (P77 R1)

**新工具**: `bin/ssot/management-migrate.py` (130 行)

**迁移策略**:
- 沿 P53 双指针, 但简化版 (因 P75 已加 category 字段, 不需要原位 deprecated)
- 3 子目录: `workflows/` (127) / `playbooks/` (5) / `guides/` (12)
- 物理 mv 文件到子目录
- 不修改原文件 (因 mv 后原位不存在)

**实测**:
```
============================================================
📁 P77 management 物理迁移 (实际迁移)
============================================================
📁 总文件: 144
✏️  迁移: 144

按 category:
  guides           12
  playbooks         5
  workflows       127
============================================================
```

**迁移后**:
- `.omo/_knowledge/management/` 仅含 3 子目录
- 144 文件分散在 `workflows/`, `playbooks/`, `guides/`
- 双指针: git 历史可查 (commit log 记录迁移)
- category 字段保留, 未来可基于 category 筛选

**vs P53 严格双指针**:
- P53 严格: 原位 deprecated + 新位 active (双份)
- P77 简化: 仅新位 (因 P75 已加 category, 不需要原位)

**沿用现有工具**:
- `bin/ssot/management-categorize.py` (P75) → 加 category
- `bin/ssot/management-migrate.py` (P77) → 物理迁移

## Consequences

### Positive

- **management 144 物理迁移完成**: 3 子目录清晰
- **沿 P53 简化版**: 不需要原位双份, P75 category 字段已够
- **git 历史可查**: commit log 完整记录

### Negative

- **不是严格双指针**: 原位文件消失, 引用可能断裂
- **无 OPENAI_API_KEY**: graphify 实际扫描无法跑

### Neutral

- **不增 linter 维度**: 沿用 P58 独立 bin 工具
- **不增 mof-drift 维度**: 8 维度持续

## Compliance

### 验证指标

| 指标 | P76 末 | **P77 末** | 变化 |
|------|-------:|-----------:|-----:|
| mof-version | v0.0.65 | **v0.0.66** | +1 |
| governance | 100 A+ | **100 A+** | 持平 |
| 独立 bin 治理工具 | 15 | **16** | +1 (management-migrate) |
| management 子目录 | 0 | **3** (workflows/playbooks/guides) | +3 |
| management 物理迁移 | 0 | **144** | +144 |
| ADR 数量 | 30 | **31** | +1 (0071) |

### 关联 ADR

- **ADR-0069**: P75 management 142 frontmatter 分类 (P77 直接扩展)
- **ADR-0053**: P53 双指针 (P77 简化版, 因 P75 已加 category)

### 关联 L0 规则

- `X2-FRESH-DOC-LIFECYCLE` — 迁移后 frontmatter 字段仍有效
- `CR-GOV-CLOSED-LOOP-01` — 迁移 commit 即闭环

## Notes

本 ADR 记录 P77 1 项候选实施:
- ✅ management 144 物理迁移 (P77 简化版双指针)
- ⏸ 跨子仓联动 (P78+)
- ⏸ graphify 实际扫描 (需 OPENAI_API_KEY, 留 P78+)

后续 P78+ 候选:
- 跨子仓联动 (ecos/agora/cockpit)
- graphify 实际扫描 (需 OPENAI_API_KEY 配)
- management 子目录 INDEX.md 更新
- alert-history 自动洞察
- P0 listener 真实事件 API
- 跨子仓 omo event 联动

---

*最后更新: 2026-06-23 · P77 · omostation 治理方法论持续深化*