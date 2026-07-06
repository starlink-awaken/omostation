---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0132-l0-mof-m4-metamodel.md
  - 0133-l0-constraints-v2-cutover.md
  - ../../../projects/ecos/src/ecos/ssot/mof/m3.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m3-meta.yaml
  - ../../../projects/ecos/src/ecos/l0/ssot/mof_bridge.py
  - ../../../projects/ecos/src/ecos/ssot/mof/m0/mof_driven.py
  - ../../../../bin/mof-bootstrap.py
supersedes: []
---

# ADR-0134: meta_model ↔ m3.yaml 双轨桥接受 (M3-meta ACCEPTED)

> **For agentic workers**: REQUIRED SUB-SKILL: `superpowers:executing-plans`。
> **本 ADR 是 ACCEPTED 状态**(2026-07-06)。

---

## 0. TL;DR

完成 M4 Phase 2 (ADR-0132 P2-S1 ~ P2-S4): meta_model.py ↔ m3.yaml 双轨桥接
(ADR-0132 D3 决策) 通过 m3-meta.yaml + mof_bridge.py + mof_driven.py + mof-bootstrap
4-check 自反校验 落地。

**桥接闭合证据**:
- m3-meta.yaml 22 Element + 15 关系矩阵条目,镜像 meta_model.py 1:1
- mof_bridge.py 5 路 API 全绿 (8 MET-Entity 映射 + 元关系矩阵 + 置信度聚合 + 8 层架构 + Element list)
- mof_driven.py 7 阶段 + 6 transitions 全部捕获,model-driven 引擎**未触**(P52 守住)
- mof-bootstrap.py 4-check: check_1/2/4 全 PASS, check_3 报告 4 P5 中间类 gap

---

## 1. 决策落地(5 个开关全 ADR-0132 默认值)

| 开关 | ADR-0132 默认 | 本次落地 |
|------|---------------|----------|
| D1 双轨 vs 单轨 | 双轨 | ✓ 双轨 (m3.yaml + m3-meta.yaml 共存) |
| D2 L0-constraints schema 字段 | 12 字段 | ✓ ConstraintL0 8 required + 5 optional |
| D3 meta_model ↔ m3 关系 | 双轨桥接(C) | ✓ m3-meta.yaml + mof_bridge.py (新增) |
| D4 M0 model-driven 闭环 | 暴露桥(B) | ✓ mof_driven.py 暴露 7 阶段 (不改引擎) |
| D5 L0-constraints v1 历史保留 | 永久保留 gitignored(A) | ✓ v1 文件物理保留 |

---

## 2. P5 phase gap (m3.yaml 扩展候选)

mof-bootstrap check_3 实证发现 4 个 m3.yaml 缺失 Element 类:

| Gap | m3_parent 引用 | 建议 m3 Element |
|-----|----------------|------------------|
| ConstraintMgmt | ConstraintL0.m3_parent=ConstraintMgmt | `ConstraintMgmt: parent: Constraint` (GovernanceElement 子类) |
| InfrastructureElement | concurrency_control.m3_parent | `InfrastructureElement: parent: StructuralElement` |
| ArchitectureElement (x2) | federation/plugin.m3_parent | `ArchitectureElement: parent: StructuralElement` |

建议另起 ADR-0136 (Phase 5) 单独治本 — **不在本次范围**。

---

## 3. 验证

| 检查 | 工具 | 期望 | 结果 |
|------|------|------|------|
| m3-meta 自反 | `mof-bootstrap check_4` | 0 err | ✓ |
| M2 schema 自反 | `mof-bootstrap check_2` | 0 err | ✓ |
| m2→m3 strict 锚 | `mof-bootstrap check_3` | 0 strict err | ✓ (4 P5 gap 报告) |
| M3 自反 | `mof-bootstrap check_1` | 0 err | ✓ |
| mof_bridge 5 路 API | Python 直接调用 | 全绿 | ✓ |
| mof_driven 7 阶段 | `mof_driven --validate` | stage_count=7 | ✓ |
| mof_driven 6 transitions | 同上 | 6 transitions | ✓ |

---

## 4. 不在本 ADR 范围

- ❌ P5 phase m3.yaml 扩展 (另起 ADR-0136)
- ❌ model-driven 7 阶段引擎改动 (P52 撤销生效)
- ❌ m3.yaml 字段改动 (新增全在 m3-meta.yaml)
- ❌ meta_model.py API 改动 (8+4+4 enum 顺序不变)

---

## 5. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (PROPOSED → P0/P1/P2 完成,本 ADR)
- [ADR-0133](./0133-l0-constraints-v2-cutover.md) (ACCEPTED, P1 阶段)
- [ADR-0117](./0117-p52-undo-p60-stage-8.md) (model-driven 8 阶段撤销,P52 真治本)

---

## 6. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Phase 2 全部完成,P5 phase 移交) |
