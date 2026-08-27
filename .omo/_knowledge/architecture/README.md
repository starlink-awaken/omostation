---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# `.omo/_knowledge/architecture/` — 审计/治理架构文档

> ⚠️ **本目录仅承载审计/治理架构文档**,不承载系统总架构。
> **系统总架构 SSOT**: `docs/PANORAMA.md` (334 行, 5+4+1+1 视图)

## 职责边界

| 类别 | 位置 | 权威读源 |
|------|------|----------|
| **系统总架构** | `docs/PANORAMA.md` | ✅ 唯一权威 |
| **审计/治理架构** | `.omo/_knowledge/architecture/` | 本目录 |
| **治理架构深度** | `.omo/_knowledge/management/` (e.g. `5+3+1-layer-deep-architecture.md`) | 管理面 |
| **设计蓝图** | `.omo/_knowledge/design/` | 设计面 |
| **架构决策** | `.omo/_knowledge/decisions/` (ADR-*) | 决策面 |

## 现有内容

| 文件 | 日期 | 性质 |
|------|------|------|
| `2026-06-15-unified-audit-architecture.md` | 2026-06-15 | 统一审计入口架构 (Round 43 P1) |

## 写入规则

- ✅ 新增: 审计/治理相关的架构设计 (如 omo governance 7 维度扩展设计)
- ❌ 禁止: 系统总架构快照 (应更新 PANORAMA.md)
- ❌ 禁止: 设计蓝图 (应入 `design/`)

## 关联文档

- PANORAMA.md (系统全景)
- `.omo/standards/omo-governance-surfaces.md` (`.omo` 三层治理契约)
- `.omo/_truth/registry/omo-governance-surfaces.yaml` (治理面注册表)

---

*最后更新: 2026-06-23 · P53 R2 收敛*