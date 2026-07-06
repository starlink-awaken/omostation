---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0132-l0-mof-m4-metamodel.md
  - ../audits/2026-06-29-l0-ssot-m0-mof-alignment.md
  - 0128-state-generation-concurrency.md
  - 0129-state-projection-plane-phase3.md
  - ../../../projects/ecos/src/ecos/ssot/mof/m2/constraint_l0.yaml
  - ../../../../bin/l0-constraints-migrate.py
supersedes: []
---

# ADR-0133: L0-constraints v2 派生面 — 双轨切单轨

> **For agentic workers**: REQUIRED SUB-SKILL: `superpowers:executing-plans`。
> **本 ADR 是 ACCEPTED 状态**(2026-07-06),切单轨已完成。

---

## 0. TL;DR

L0-constraints.yaml 的 77 条 v1 形状(7 元组扁平)在 M4 Phase 1.2 通过 schema 升级到 v2 形状(13 字段 + m3_parent 闭合 + severity 严格枚举),派生到 `.omo/_derived/l0-constraints.v2.yaml`(ADR-0129 投影面范式)。

**关键变更**:
- v1 7 元组 (`id/description/applies_to/dimension/rule/type/violation`) → v2 13 字段
- `type: required/preferred/advisory` → `severity: high/medium/low`
- `violation: "E-X-N: msg"` 字符串 → `{violation_code, violation_message}` 结构化
- `rule: "predicate"` 字符串 → `rule_expr: {kind, args}`
- 新增 `m3_parent: ConstraintL0`,L0-constraints 进入 M3 闭环

---

## 1. 切轨条件(已满足)

| 条件 | 验证 | 状态 |
|------|------|------|
| 77 条 v1 全部迁移到 v2 | `bin/l0-constraints-migrate.py` 输出 | ✅ 77/77 |
| 派生面 schema 100% 校验通过 | `--validate` 全绿 | ✅ 0 errs |
| v1/v2 id 一致 | 集合重合度 100% | ✅ 77 重合 |
| mof-validate 复测无回归 | 1380 节点 / 错误 38(不变) | ✅ |
| P1-S0 loader bug 已修 | M2 schema 49 → 50 | ✅ |

---

## 2. 派生面 schema

`projects/ecos/src/ecos/ssot/mof/m2/constraint_l0.yaml`:

```
requiredProperties (8):
  - id, description, applies_to, dimension,
  - severity (枚举: critical/high/medium/low),
  - rule_expr (map: kind + args/ref),
  - violation_code,
  - relation_constraints (map: affects/depends_on/conflicts_with)
optionalProperties (5):
  - confidence, examples, references, rationale, half_life_days
stateMachine (9): draft→identified→scored→scored_active→aging→
                  deprecated→accepted→resolved→archived
validationRules (4):
  - critical 只能用于 L0/M0
  - hypothesis/estimated 不能升 high/critical
  - kind=ref 必须有 ref 字段
  - state=aging 应有较短 half_life_days
relationConstraints:
  can_be_source_of: [Constrains, ConflictsWith]
  can_be_target_of: [Constrains, DependsOn, Supersedes, ConflictsWith]
m3_parent: ConstraintMgmt  ← 继承现有 M2 schema
```

---

## 3. 派生面产物(本次提交)

| 文件 | 状态 | 作用 |
|------|------|------|
| `bin/l0-constraints-migrate.py` | 新增 | 双向迁移 + 校验 + 报告 |
| `.omo/_derived/l0-constraints.v2.yaml` | 新派生 | 1837 行,77 条 v2 |
| `docs/generated/l0-constraints-migration-report.md` | 新生成 | 48 行,迁移明细 |

**派生面 gitignored**:符合 ADR-0129 投影面范式。

---

## 4. 双轨保留

**v1 yaml 文件物理保留**(不删,gitignored 入仓同样按规则):

| 文件 | 保留原因 |
|------|---------|
| `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` | 人类可读,审计回溯,ADR-0132 D5 永久保留决策 |

**v1 与 v2 不冲突**:
- v1 = SSOT 事实源(7 元组,被现有 132 GaC rules 引用)
- v2 = 派生面(M2 schema 形状,可被 M3 closure 校验)

后续:Phase 4 P4-3 写 38 回归测试覆盖此切轨。

---

## 5. 不在本 ADR 范围

- ❌ 修改 projects/cockpit / omo / agora / model-driven (caller 跨仓)
- ❌ 删除 v1 yaml
- ❌ 改 m3.yaml
- ❌ 改 model-driven 7 阶段引擎

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 132 GaC rules 引用 v1 id(X1-C01 等)破坏 | 不动 v1 yaml,id 在 v1/v2 一致(77 重合) |
| 派生面入仓被 git tracked | .gitignore + ADR-0129 兜底 |
| v2 schema 升级破坏老迁移数据 | v2 是新派生面,不影响 v1 读取 |

---

## 7. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (PROPOSED → ACCEPTED P1 阶段内)
- [ADR-0129](./0129-state-projection-plane-phase3.md) (派生面范式)

---

## 8. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (P1-S2 完成,P1-S3 验收) |
