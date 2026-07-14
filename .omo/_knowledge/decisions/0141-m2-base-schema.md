---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0132-l0-mof-m4-metamodel.md
  - 0136-m3-yaml-extension-p5.md
  - 0140-m4-health-score.md
  - ../../../projects/ecos/src/ecos/ssot/mof/m2/m2_base_schema.yaml
  - ../../../../bin/mof-bootstrap.py
  - ../../../../bin/m4-health-score.py
supersedes: []
---

# ADR-0141: M2BaseSchema 抽象基类 + check_5 (Round 3a)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

新增 M2 schema 抽象基类 `M2BaseSchema`,定义 50 个 m2/*.yaml 文件共享的 4 字段
公共契约 (m2_type / version / created / body 含 m3_parent + description)。
新增 `bin/mof/mof-bootstrap.py check_5` 校验 50 schema 全合规,让"schema 异
常"可被持续监控。

**关键变化**:
- 1 新 M2 schema (`m2_base_schema.yaml`, M3 parent = Specification)
- 1 新 5-check (`check_5` m2 BaseSchema 一致性)
- mof-bootstrap check_4 → check_5 升级 (Round 3b health score 同步)
- 44/44 回归测试 PASS + 5-check strict 0/0/0/0/0

---

## 1. 触发

49 个 m2 schema 平铺 (Round 0 P2-S1 修复后), 但**形状各异**:
- m2_type / version / created 4 字段约定**无显式定义**
- body 顶层名有 PascalCase (ConstraintL0) 和 snake_case (availability_check) 两种
- description 字段在 top-level vs body 内部 两种风格
- created 字段有 date (2026-06-07) vs datetime (2026-06-07T23:27:00) 两种

**问题**: MOF bootstrap 无法**统一审计** schema 间一致性, 也无法新增 schema
时验证"是否符合已有模式"。

ADR-0141 治本: 显式定义 M2BaseSchema 抽象基类, + check_5 做模式一致性校验。

---

## 2. 决策

### 2.1 抽象基类 M2BaseSchema

`projects/ecos/src/ecos/ssot/mof/m2/m2_base_schema.yaml`:

```
m2_type: M2BaseSchema
version: 1.0.0
created: '2026-07-06T12:30:00'
M2BaseSchema:
  m3_parent: Specification  # M2 schema 本身就是 specification (formal model)
  abstract: true
  stateMachine: draft / registered / deprecated / archived
  requiredProperties:
    - m2_type (PascalCase, 必填)
    - version (semver, 必填)
    - created (ISO-8601 date 或 datetime, 必填)
    - <schema_body> 含 m3_parent + description (必填)
  optionalProperties:
    - icon (emoji, 可选)
    - m2_parent (显式 parent, 可选, 默认隐式继承)
    - examples (示范用例, 可选)
    - relationConstraints (关系约束, 可选)
  validationRules:
    - M2BS-VR01: m2_type not in reserved (SchemaSpecification)
    - M2BS-VR02: m3_parent 必须是 m3.yaml Element 集
    - M2BS-VR03: deprecated schema 应在 .deprecated. 子目录
```

### 2.2 check_5 m2 BaseSchema 一致性

`bin/mof/mof-bootstrap.py` 加 check_5: 50 个 m2/*.yaml 文件逐个检查:
- m2_type PascalCase (M2BS-01)
- version semver (M2BS-02)
- created ISO-8601 (M2BS-03)
- schema body 含 m3_parent + description (M2BS-04)
- 历史 snake_case body 兼容 (fallback 解析)
- description 接受 top-level 或 body (兼容历史风格)

### 2.3 不显式强制 m2_parent

**重要**: 50 现有 m2 schema **隐式**继承 M2BaseSchema (m2_parent 字段) 。
本 ADR **不** 强制改 50 文件, 只加 1 个新 check_5 审计现有 schema 合规。
未来新 schema 应**显式** 含 m2_parent 字段 (建议, 非强制)。

### 2.4 created 字段 ISO-8601 兼容性

8 schema (ComputeEngine/ComputeNode/HardwareAsset/NetworkZone/QuotaDefinition/
RoutingPolicy/VaultPath) 用 date (2026-06-07) 而非 datetime。
check_5 接受 date 格式 (扩展 regex), 但**建议**未来统一为 datetime。

---

## 3. 实施

### 3.1 新增 m2 schema (50 → 51)

`projects/ecos/src/ecos/ssot/mof/m2/m2_base_schema.yaml` (新增 119 行)

### 3.2 bin/mof/mof-bootstrap.py 新增 check_5

`def check_5(ws, verbose)` 返回 (ok, errors) tuple.

检查项:
1. m2_type PascalCase pattern `^[A-Z][A-Za-z0-9]+$`
2. version semver `^\d+\.\d+\.\d+$`
3. created ISO-8601 (兼容 date 或 datetime)
4. schema body 含 m3_parent + description (任一形式: top-level 或 body)

### 3.3 Round 3b 同步升级

- `bin/mof/m4-health-score.py::score_4check_strict` 改名为 `score_5check_strict`
- 派生面 metrics key 从 `four_check_strict` 改 `five_check_strict`
- 测试 T42 期望更新

---

## 4. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| 5-check strict | `bin/mof/mof-bootstrap.py all` | check_1/2/3/4/5 全 0 err |
| 44 回归测试 | `tests/integration/m4_metamodel/run_all.py` | 44/44 PASS |
| ADR 不破 99.17 | `bin/mof/m4-health-score.py --emit` | overall 99.17, 5-check 30/30 |
| m2 schema 数 | `ls m2/*.yaml \| wc -l` | 51 (50 + M2BaseSchema) |
| M3 闭合 | check_3 strict | m2_base_schema m3_parent=Specification 锚通 |

### 19 老的 round 1 决策的连锁通过

- ✅ P52 守门: 不改 50 schema 历史文件, 仅新增 1 schema + 1 check
- ✅ P72 不重做历史路径: 50 schema 隐式继承 (m2_parent 不强加)
- ✅ P74 governance 闭环: 5-check strict 全过, 派生面持续可观察
- ✅ ADR-0140 health score: 5-check 替代 4-check, 99.17/100 baseline

---

## 5. 不在本 ADR 范围

- ❌ 强制现有 50 schema 加 m2_parent 字段 (历史兼容性大于统一)
- ❌ 修 8 schema date → datetime (低优先级, 不破当前 check)
- ❌ Round 3d (mof-validate 99% 提升)
- ❌ 跨仓 caller 同步 (cockpit / omo 引用)

---

## 6. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (M4 主决策)
- [ADR-0136](./0136-m3-yaml-extension-p5.md) (Round 0.5, P5 4 gap 治本)
- [ADR-0140](./0140-m4-health-score.md) (Round 3b, 与本 ADR 同步升级)

---

## 7. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 3a, 50 → 51 m2 schema, 4-check → 5-check strict) |
