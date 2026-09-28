---
schema: md/v1
status: active
lifecycle: planning
owner: governance-team
type: plan
last-reviewed: 2026-09-28
---

# Phase 2 通用规则引擎设计

## 目标

把 137 条 L0 规则从硬编码 inspector 中解放为外置 YAML 规则 + 通用执行器。

## 现状

- L0 约束声明在 `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`（137 条）
- 执行逻辑硬编码在 `projects/ecos/src/ecos/ssot/compiler/` 的 inspector 中
- 每加一条规则就要写一个 Python inspector

## 设计

### 1. 外置规则文件

```
.omo/standards/rules/
├── l0-constraints.yaml          # L0 约束（从现有文件迁移）
├── content-rules.yaml           # 内容规则（FM schema、引用完整性等）
└── rule-schema.yaml             # 规则文件自身的 schema
```

规则格式：
```yaml
- rule_id: CR-L0-001
  predicate: "file_exists"
  target: "protocols/port-registry.yaml"
  severity: blocking
  remediation: "创建 protocols/port-registry.yaml"
  dimension: X1
```

### 2. 通用规则执行器

`bin/ssot/rule_engine.py`：
- 加载 YAML 规则文件
- 解析目标内容（Markdown FM/body/YAML/JSON）
- 执行谓词（file_exists、fm_field_exists、ref_integrity 等）
- 输出 violations[]

### 3. 内容解析层

`bin/ssot/content_parser.py`：
- Markdown → {fm, headings, links, body_ast}
- YAML → 结构化树
- 统一中间表示

## 实施步骤

1. 设计规则文件 schema（1 天）
2. 实现通用规则执行器（2-3 天）
3. 实现内容解析层（2-3 天）
4. 迁移 20 条高频规则（1-2 天）
5. 在 ci-surfaces.yaml 登记新检查面（0.5 天）
6. 在 gac-local-gate.py GATES_LIST 插入（0.5 天）

## 风险

- 规则引擎性能（15,670 md）：增量执行 + 缓存解析结果
- 规则文件 schema 设计：需要覆盖所有规则类型
- 迁移脚本 bug：先 dry-run，人工 review 后再 apply

## 成功标准

- 通用规则执行器覆盖 ≥20 条高频规则
- 新增规则只需写 YAML，不再写 Python inspector
- 规则引擎在 CI 中可执行
