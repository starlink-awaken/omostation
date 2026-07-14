---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0132-l0-mof-m4-metamodel.md
  - 0136-m3-yaml-extension-p5.md
  - ../../../projects/ecos/src/ecos/ssot/mof/m3.yaml
  - ../../../projects/ecos/src/ecos/ssot/mof/m3-meta.yaml
  - ../../../projects/ecos/src/ecos/l0/ssot/mof_bridge.py
supersedes: []
---

# ADR-0138: 元元模型类目提升至 m3.yaml 主流 (Round 2b)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

把 meta_model.py 的 8+4+4 元分类(m3-meta.yaml 派生)提升至 m3.yaml 主根
第一类 `MetaElement`。修复 8+4+4 处于"游离派生层"的局面,让 mof_bridge 可
单入口读 m3.yaml 完整。

**新增 4 个 m3 Element**:
- `MetaElement` (根, parent=Element)
- `MetaEntity` (parent=MetaElement, abstract)
- `MetaRelationType` (parent=MetaElement, abstract)
- `MetaConstraintRule` (parent=MetaElement, abstract)

**m3 主根 Element 数**: 29 → 33(29 + 4 新增)

---

## 1. 触发回顾

Round 1 (ADR-0132 P2-S1) 落地时,8 MET-Entity / 4 MET-Relation / 4 MetaConstraint
放在 m3-meta.yaml 作为派生映射索引, m3.yaml 主根只有 4 大类 + Lifecycle + Value。
问题:
- **mof_bridge 必须读两份 yaml** 才能完整查询
- **未来新增 SSOT** 容易混淆"哪个文件才是 SSOT"
- **P74 治理原则**: SSOT 唯一, m3.yaml 应是大根

ADR-0138 治本: 把 8+4+4 提升至 m3.yaml 主根, 但保留 m3-meta.yaml 作为
**派生映射索引**(m3_implements 反向引用 meta_model.py enum)。

---

## 2. 设计决策

### 单一第一类 `MetaElement`

m3.yaml 现在有 7 大类:
- Structural / Behavioral / Governance / Descriptive (4 大基础)
- Lifecycle (ADR-0116 model-driven 同步)
- Value (ADR-0116 经济性)
- **Meta (本 ADR 新增)** — meta_model 8+4+4

### 抽象根 + 4 分类子根

- `MetaElement` 抽象根(Element 子类)
- `MetaEntity` 抽象子根(MetaElement 子类, abstract)
  - 8 类对应 m3-meta.yaml 的 MetaDomain/MetaFact/MetaInference/MetaState/MetaDocument/MetaConstraint/MetaProcessor/MetaRelation
- `MetaRelationType` 抽象子根(4 类)
- `MetaConstraintRule` 抽象子根(4 类)

### 8+4+4 具体子类不动

具体子类仍只活在 m3-meta.yaml(m3_implements 反向引用 meta_model enum)。
m3.yaml 主根只承担**抽象分类层**,具体子类不必重复。

**保持双轨桥接**(ADR-0132 D3 决策)。

---

## 3. 实施影响

### 3.1 m3.yaml 改动

新增 4 Element (`MetaElement`, `MetaEntity`, `MetaRelationType`, `MetaConstraintRule`)
至 §7 Decision 之后, §2 Relation Ontology 之前。

不动其他元素, 不动 property_types, 不动 relations。

### 3.2 mof_bridge.py 改动

`_build_meta_to_m3_map` 增强:
- 优先看 m3.yaml 主根 (MetaEntity/MetaRelationType/MetaConstraintRule 抽象类下的子类)
- fallback 到 m3-meta.yaml (派生映射)

`_get_element_anywhere` 新增辅助函数:查 m3.yaml 或 m3-meta.yaml 任一。

### 3.3 m3-meta.yaml 不动

m3-implements 反向引用 meta_model.py enum 仍由 m3-meta.yaml 保留。
ADR-0138 治本不止是改名/迁移,而是**让 m3.yaml 主根承担第一类 SSOT**,
m3-meta.yaml 仍保留作为派生投影。

---

## 4. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| m3.yaml 加载 | `yaml.safe_load` | 34 elements |
| 4-check strict | `bin/mof/mof-bootstrap.py all` | 0 err (10 sections of §1-§7) |
| mof_bridge 8 MET | Python 调用 | 全部映射仍 OK |
| mof_bridge 关系矩阵 | Python 调用 | DOMAIN→DOMAIN/STRUCT 通过 |
| mof_bridge Confidence | Python 调用 | fact=2 → 1.00 |
| 38 回归测试 | `tests/integration/m4_metamodel/run_all.py` | 38/38 PASS |

### 不破 P52 / P72

- m3.yaml 加 4 Element, 不改现有 29 Element 任何字段
- model-driven 7 阶段引擎未触
- meta_model.py API 未触
- m3-meta.yaml 不动

---

## 5. 不在本 ADR 范围

- ❌ 把 m3-meta.yaml 7 个具体子类(MetaDomain/MetaFact/...)也搬进 m3.yaml 主根
- ❌ 改 mof_bridge 现有 API 签名
- ❌ 改 Relation Ontology (m3.yaml §2)

---

## 6. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (主决策,D3 双轨桥接基础)
- [ADR-0136](./0136-m3-yaml-extension-p5.md) (preceding,P5 治本 4 gap)
- [ADR-0137](./0137-derived-plane-relocation.md) (并行, Round 2a)

---

## 7. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 2b, 8+4+4 提升至 m3.yaml 主根第 7 大类 MetaElement) |
