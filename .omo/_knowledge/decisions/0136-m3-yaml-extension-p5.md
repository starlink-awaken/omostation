---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0132-l0-mof-m4-metamodel.md
  - 0134-m3-meta-cutover.md
  - ../../../projects/ecos/src/ecos/ssot/mof/m3.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m2/constraint_l0.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m2/federation.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m2/plugin.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m2/concurrency_control.yaml
  - ../../../../bin/mof-bootstrap.py
supersedes: []
---

# ADR-0136: P5 phase — m3.yaml 扩展 4 gap 治本

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

ADR-0134 §2 暴露的 4 个 m3.yaml 缺失 Element gap 已**治本**:
- 3 个 m2 schema 的 m3_parent 名称对齐 m3.yaml(零 m3.yaml 改动)
- 1 个新 m3.yaml Element(`ConcurrencyElement`)填补真缺口

**结果**:`mof-bootstrap check_3 strict 0 err`(4-check 全 PASS)。

---

## 1. 变更清单

### 1.1 m2 schema 名称对齐(零 m3.yaml 改动)

| m2 文件 | 原 m3_parent | 新 m3_parent | 原因 |
|---------|-------------|-------------|------|
| constraint_l0.yaml | `ConstraintMgmt` | `Constraint` | m3.yaml 有 Constraint 类,无 ConstraintMgmt |
| federation.yaml | `ArchitectureElement.Federation` | `Architecture.Federation` | m3.yaml 有 Architecture,无 ArchitectureElement |
| plugin.yaml | `ArchitectureElement.Plugin` | `Architecture.Plugin` | 同上 |

合计 3 文件,11 行改动。

### 1.2 m3.yaml 新增 1 Element (真缺口填补)

`m3.yaml` line 105 后插入 `ConcurrencyElement`:

```yaml
ConcurrencyElement:
  id: ConcurrencyElement
  name: "并发控制元素"
  description: 并发控制元素 - m2 schema concurrency_control.yaml 的 m3 锚。
  parent: StructuralElement
  abstract: false
  properties:
    kind:        enum: lock/semaphore/actor/transaction/compare_and_swap
    granularity: enum: process/thread/fiber/coroutine
    fairness:    enum: fifo/priority/none
  applies_to: [M2, M1]
```

### 1.3 bin/mof-bootstrap.py check_3 改回 strict

原 P2-S4 走的是 lenient (P5 ADR 待办标记);现在 4 gap 已治本,改回 strict:

```python
- return True, errors  # (legacy P5 pending)
+ return (len(errors) == 0), errors  # strict
```

---

## 2. 决策理由

P52 / P72 教训元模型修改连环雷。本 ADR 采用**最小变更**原则:
- 3/4 通过 m2 schema 名称对齐(零 m3.yaml 改动, 风险最低)
- 1/4 (ConcurrencyElement) 必须新创 m3 Element — m2 schema `concurrency_control` 引用了一个语义正确的 m3 父类,此父在 m3.yaml 一直缺失。这是真治本,不是改名。

**结论**:
- 4-check strict 全 PASS, M4 元模型闭环闭合
- m3.yaml 仅增 1 Element(ConcurrencyElement),不破 P60/P52 守门
- mof_bridge.py 仍兼容(只读 m3.yaml,新 Element 自然入列)

---

## 3. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| 4-check strict | `bin/mof-bootstrap.py all` | check_1/2/3/4 全 0 err |
| mof-validate | `python3 src/ecos/ssot/tools/mof-validate.py` | 1361 / 1380 (98.61%, 不变) |
| mof_bridge 兼容 | 直接调用 | 全绿 |
| mof_driven 兼容 | `--validate` | 7 阶段 + 6 transitions |

---

## 4. 不在本 ADR 范围

- ❌ 改 model-driven 7 阶段引擎
- ❌ 改 ConstraintMgmt m2 type 名(它是 constraint_mgmt.yaml 的 m2 type,不是 m3 元素)
- ❌ 复活 P60 GOVERNANCE_MAINTENANCE 阶段
- ❌ 改 meta_model.py

---

## 5. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (主决策)
- [ADR-0133](./0133-l0-constraints-v2-cutover.md) (Phase 1)
- [ADR-0134](./0134-m3-meta-cutover.md) (Phase 2, 本 ADR 来源)
- [ADR-0117](./0117-p52-undo-p60-stage-8.md) (撤销 P60, P52 守住 model-driven 引擎)

---

## 6. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (P5 phase 4 gap 治本,4-check strict PASS) |
