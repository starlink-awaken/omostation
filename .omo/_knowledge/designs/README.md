---
status: deprecated
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
deprecated-since: 2026-06-23
deprecation-reason: "P53 R2: designs/ 目录仅含 1 个 memtheta 算子设计文档,与 design/(单数)命名冲突且无 README。沿用不动路径原则,保留目录+加 deprecated frontmatter + 加 README 明确职责。新增设计文档统一入 design/specs/ 或 superpowers/specs/。"
superseded-by: "design/specs/memtheta-operators.md (待迁移)"
---

# `.omo/_knowledge/designs/` — 历史设计目录 (DEPRECATED)

> ⚠️ **本目录已 deprecated (P53 R2)** — 沿用"不动路径"原则,保留目录但不再写入新内容。

## 目录说明

- 创建时间: 早期 Phase (P28 之前)
- 当时定位: 设计文档备选目录 (与 `design/` 单数并存)
- 现状: 仅含 1 个 memtheta 算子设计文档,无 INDEX/README

## 现有内容

| 文件 | 状态 | 说明 |
|------|------|------|
| `2026-06-13-memtheta-operators.md` | Approved (Phase 1.2) | Memθ 记忆算子体系与接口规范设计 — 织星 Agent 架构组 |

## 后续计划

- 内容价值仍在,功能等价迁移目标: `.omo/_knowledge/design/specs/memtheta-operators.md`
- 待 P54+ 评估迁移时机 (避免破坏 mtime 链路)

## 维护原则

- **不再写入新文件**
- 已存文件保留 frontmatter `status: deprecated`
- 新设计文档统一入 `design/` (单数) 或 `superpowers/specs/`

---

*最后更新: 2026-06-23 · P53 R2 治理收敛*