# M4 → GaC 全面接入方案

> **配套 ADR 待定** (Round 6, 可择 ADR-0152 ~ 0154)
> **状态**: 设计文档, 非 ADR
> **目标**: 把 M4 全部 8 个工具 + 4 个 schema + 4 个检查链 入 GaC gate + agent-workflows.yaml

---

## 0. TL;DR

M4 工程历时 5+ round 产出了 8 个治理工具 + 4 个 schema 文件 + 59 项回归测试 + 5-check 自反 + Health Score 量化, **但无一入 GaC 门禁**。具体:

| 资产 | 数量 | GaC 覆盖 |
|------|------|---------|
| `bin/` 工具 (mof-bootstrap, m4-health-score 等) | 8 | ❌ 0% |
| `ssot/mof/` schema 文件 (constraint_l0, m2_base_schema, m3-meta, mof_driven) | 4 | ❌ 0% |
| `l0/ssot/` 桥接代码 (mof_bridge) | 1 | ❌ 0% |
| check_5 自反 (mof-bootstrap check_5) | 1 | ❌ 0% |
| M4 派生面 (l0-constraints.v2, m4-health.json) | 3 | ❌ 0% |

**本文档给出 3 阶段接入方案**,每阶段独立 PR + ADR。

---

## 1. 现状分析

### 1.1 现有 GaC 结构

`governance-checks.yaml`:
- `gac.rules[]`: 152 条规则, 每条含 `id/dimension/layer/check_type/source_ref/executor/lifecycle/version/created_at`
- `check_type_enum`: 35 值 (含 `ssot_pointer/audit_chain/consistency_drift/bos_resolve/legacy_index/...`)
- `dimension_enum`: X1-X4
- `layer_enum`: M0/L0/L1/L2/L3/L4/I0/X/meta
- `executor_enum`: hook_pre_edit/hook_post/ci_gate/omo_audit/mcp_tool/mof_validate/mof_audit/evidence_smoke/radar_cron/gc_cron/gac_local_gate

`agent-workflows.yaml`:
- `tools[]`: ~28 个工具(含 root-agent-workflow-*, cockpit-*, mof-*, governance-evolution-*)
- `workflows[]`: 12 个 workflow 定义(project-code-change, governance-state-mutation 等)

### 1.2 M4 资产与 GaC 的接口点

| 接口类型 | 资产 | 期望的 GaC 角色 |
|----------|------|----------------|
| **CLI 工具** | bin/mof/mof-bootstrap.py | `ci_gate` executor, 每次 PR 跑 `all` |
| **CLI 工具** | bin/mof/m4-health-score.py | `omo_audit` executor, 每日 cron 派生面 |
| **CLI 工具** | bin/ssot/check-submodule-hygiene.py | `ci_gate` executor, weekly cron |
| **CLI 工具** | bin/l0-constraints-migrate.py | `omo_audit` executor, 派生面重建 |
| **CLI 工具** | bin/gac/mcp-tool-data-complete.py | `ci_gate` executor, 单工具 MCPTOOL adder |
| **CLI 工具** | bin/mof/m4-cron-hook.py | `radar_cron` executor, OMO 桥接 |
| **CLI 工具** | bin/gac/omo-state-cleanup.py | `gac_local_gate` executor |
| **CLI 工具** | bin/m2-date-migrate.py | `omo_audit` executor |
| **Schema** | m2/constraint_l0.yaml | `source_ref` 锚 |
| **Schema** | m2/m2_base_schema.yaml | `source_ref` 锚 |
| **Schema** | mof/m3-meta.yaml | `source_ref` 锚 |
| **Schema** | mof/m0/mof_driven.py | `source_ref` 锚 |
| **Check** | mof-bootstrap check_5 | 新增 `check_type: m2_baseschema_audit` |
| **派生面** | .omo/_derived/l0-constraints.v2.yaml | `omo_audit: validate` |
| **派生面** | .omo/_derived/m4-health.json | `radar_cron: read` |
| **派生面** | .omo/_derived/m4-cron-log.json | `radar_cron: write` |

---

## 2. 阶段方案

### Phase 1: 8 工具入 GaC rules (5 条规则, 低风险)

**新增 5 条 GaC rule**,复用现有 `check_type_enum` 中的 `ssot_pointer` / `audit_chain` / `freshness`。

#### Rule 1: M4-BOOTSTRAP-REFLEX

```yaml
- id: M4-BOOTSTRAP-REFLEX
  dimension: X1
  layer: meta
  name: "M4 自反校验门禁 (5-check)"
  description: >
    M4 元模型的 5-check 自反校验。每次 PR/pre_release 跑 bin/mof/mof-bootstrap.py all.
    check_1 (m3 自反) / check_2 (m2 公共契约) / check_3 (m2→m3 锚) /
    check_4 (m3-meta 自反) / check_5 (M2BaseSchema 模式一致).
  check_type: audit_chain
  target: projects/ecos/src/ecos/ssot/mof/
  source_ref: bin/mof/mof-bootstrap.py
  executor: [hook_pre_edit, ci_gate, gac_local_gate]
  lifecycle: active
  version: 1.0.0
  created_at: "2026-07-06"
  adr: "ADR-0132"
```

#### Rule 2: M4-HEALTH-SCORE

```yaml
- id: M4-HEALTH-SCORE
  dimension: X2
  layer: meta
  name: "M4 Health Score 量化"
  description: >
    M4 元模型健康分。每日 OMO cron 跑, 写入 .omo/_derived/m4-health.json.
    Score 退化触发 governance 告警. 基于 4 维度:
    mof-validate (60%) + 5-check (30%) + meta mapping (5%) + ADR accepted (5%).
  check_type: freshness
  target: projects/ecos/.omo/_derived/m4-health.json
  source_ref: bin/mof/m4-health-score.py
  executor: [radar_cron, omo_audit]
  forbid_copy_in: [CLAUDE.md, docs/**
  lifecycle: active
  version: 1.0.0
  created_at: "2026-07-06"
  adr: "ADR-0140"
```

#### Rule 3: M4-SUBMODULE-HYGIENE

```yaml
- id: M4-SUBMODULE-HYGIENE
  dimension: X1
  layer: meta
  name: "子模块卫生守门 (3 类检查)"
  description: >
    检测 3 类子模块卫生。每周 OMO cron 跑 --strict.
    submodule-dirty / tracked-derived / submodule-pointer-stale.
  check_type: audit_chain
  target: .gitignore
  source_ref: bin/ssot/check-submodule-hygiene.py
  executor: [radar_cron, gac_local_gate]
  lifecycle: active
  version: 1.0.0
  created_at: "2026-07-06"
  adr: "ADR-0151"
```

#### Rule 4: M4-MCPTOOL-INTEGRITY

```yaml
- id: M4-MCPTOOL-INTEGRITY
  dimension: X4
  layer: L0
  name: "MCPTOOL 数据完整性守门"
  description: >
    新增 MCPTOOL 单工具 yaml 时校验 tool_name + server 非空.
    集合 yaml 自动跳过 (ADR-0145 §2.1).
  check_type: consistency_drift
  target: projects/ecos/src/ecos/ssot/mof/m1/mcptool/
  source_ref: bin/gac/mcp-tool-data-complete.py
  executor: [ci_gate, gac_local_gate]
  lifecycle: active
  version: 1.0.0
  created_at: "2026-07-06"
  adr: "ADR-0145"
```

#### Rule 5: M4-DERIVED-PLANE-AUDIT

```yaml
- id: M4-DERIVED-PLANE-AUDIT
  dimension: X1
  layer: meta
  name: "派生面范式审计"
  description: >
    派生面应 gitignored, 不占用 SSOT. 跑 omo-state-cleanup audit
    验证 DERIVED_PATHS 列表。
  check_type: ssot_pointer
  target: .omo/_derived/
  source_ref: bin/gac/omo-state-cleanup.py
  executor: [omo_audit, radar_cron]
  lifecycle: active
  version: 1.0.0
  created_at: "2026-07-06"
  adr: "ADR-0135"
```

### Phase 2: schema + agent-workflows 注册 (中等风险)

#### 2.1 4 个 schema 文件入 GaC

修改 `.omo/_truth/registry/governance-checks.yaml` 现有规则或新增,把 constraint_l0/m2_base_schema/m3-meta/mof_driven 注册为 `source_ref` 目标:

**选项 A** (推荐): 在现有 152 规则上加 `source_ref` 扩展(不改现有规则,只在 meta 层 L0 层已有规则上补充):

无需新规则 — 现有 `CR-L0-BOS-RESOLVE` `CR-MOF-VALIDATE-01` 等已覆盖:
- `CR-MOF-VALIDATE-01` 已经把 `projects/ecos/src/ecos/ssot/mof/` 作为 source_ref
- 只需**在规则描述**中显式提及其覆盖的 M2 schema

**选项 B** (若需要显式门禁): 新增 1 条规则:

```yaml
- id: M4-MOF-SCHEMA-INTEGRITY
  dimension: X1
  layer: meta
  name: "MOF schema 文件完整性"
  description: >
    4 个 M4 新增 MOF schema 文件的变更走 GaC gate:
    constraint_l0.yaml / m2_base_schema.yaml / m3-meta.yaml / mof_driven.py
  check_type: schema_integrity
  target: projects/ecos/src/ecos/ssot/mof/m2/|mof/m3-meta.yaml|mof/m0/mof_driven.py
  source_ref: bin/mof/mof-bootstrap.py
  executor: [ci_gate, gac_local_gate]
  lifecycle: active
  version: 1.0.0
  adr: "ADR-0132, ADR-0136, ADR-0141"
```

#### 2.2 agent-workflows.yaml 注册

在当前 `.omo/_truth/registry/agent-workflows.yaml` `tools` 列表追加 4 个新工具：

```yaml
  - id: mof-bootstrap
    type: local_tool
    description: "M4 5-check 自反校验器"
    command: ["uv", "run", "--with", "pyyaml", "python", "bin/mof/mof-bootstrap.py", "all"]
    health_check: true
    required: true
    timeout: 60

  - id: m4-health-score
    type: local_tool
    description: "M4 Health Score 量化 (派生面引擎)"
    command: ["uv", "run", "--with", "pyyaml", "python", "bin/mof/m4-health-score.py", "--emit"]
    health_check: true
    required: false
    timeout: 120

  - id: check-submodule-hygiene
    type: local_tool
    description: "子模块卫生守门 (3 类检查)"
    command: ["uv", "run", "--with", "pyyaml", "python", "bin/ssot/check-submodule-hygiene.py", "--strict"]
    health_check: true
    required: false
    timeout: 60

  - id: mcp-tool-data-complete
    type: local_tool
    description: "MCPTOOL 数据完整性守门"
    command: ["uv", "run", "--with", "pyyaml", "python", "bin/gac/mcp-tool-data-complete.py"]
    health_check: false
    required: false
    timeout: 30
```

同时注册 `governance-state-mutation` workflow 的 `paths` 加入 M4 schema 路径:

```yaml
    paths:
      - .omo/_truth/registry/governance-checks.yaml
      - .omo/_truth/x1-governance-policies.yaml
      - bin/gac-*.py
      # M4 GaC 接入 (Phase 2):
      - bin/mof/mof-bootstrap.py
      - bin/mof/m4-health-score.py
      - bin/ssot/check-submodule-hygiene.py
      - bin/gac/mcp-tool-data-complete.py
```

### Phase 3: check_type_enum 扩展 (低风险, 与 Phase 1 一并完成)

当前 `check_type_enum` 已有 35 个值。M4 不需要新值,复用现有:

| M4 工具 | check_type | 理由 |
|---------|-----------|------|
| mof-bootstrap all | `audit_chain` | X1: 审计链, 每次 PR 跑自反 |
| m4-health-score --emit | `freshness` | X2: 保鲜, 每天派生面 |
| check-submodule-hygiene --strict | `audit_chain` | X1: 子模块审计 |
| mcp-tool-data-complete | `consistency_drift` | X4: 一致性漂移检测 |
| omo-state-cleanup audit | `ssot_pointer` | X4: SSOT 派生面范式 |
| l0-constraints-migrate --validate | `schema_integrity` | X1: schema 兼容性 |

**不需要新增 check_type**, 复用 5 个现有值足够。

### Phase 4: OMO cron 集成 (ADR-0144 的续延)

当前 ADR-0144 的 `m4-cron-hook.py` 已在 `.omo/_derived/m4-cron-log.json` 写派生面。
但**未接入 operating-rhythm crontab**。这步是:

```
# 在 .omo/cron/operating-rhythm-crontab 追加 (daily 09:15):
15 9 * * * cd "$HOME/Workspace" && uv run --with pyyaml python bin/mof/m4-health-score.py --emit >> runtime/cron/operating-rhythm-daily.log 2>&1

# weekly 周一 10:15 (接在 mof-state-bridge 后):
15 10 * * 1 cd "$HOME/Workspace" && uv run --with pyyaml python bin/ssot/check-submodule-hygiene.py --strict >> runtime/cron/operating-rhythm-weekly.log 2>&1
```

---

## 3. 实施路线图

| Phase | 内容 | 改动文件 | ADR | 风险 | 工时 |
|-------|------|---------|-----|------|------|
| **P1** | 5 条 GaC rule 入 governance-checks.yaml | 1 file (+30 行) | ADR-0152 | 低 | 1h |
| **P2a** | 4 个 schema path 注册(选项 A/B) | 1 file | 同 P1 | 低 | 30m |
| **P2b** | 4 tool 入 agent-workflows.yaml | 1 file (+20 行) | ADR-0153 | 低 | 1h |
| **P3** | check_type_enum 设计决策 | (文档) | 同 P1 | 无 | 0 |
| **P4** | OMO cron 集成 | 1 file (+2 行) | ADR-0154 | 中 | 30m |

---

## 4. 接入后 GaC 覆盖度预测

| 类别 | 接入前 | 接入后 | delta |
|------|--------|--------|-------|
| bin/ 8 工具 | 0/8 | 8/8 | +8 |
| schema 4 文件 | 0/4 | 4/4 | +4 |
| 派生面 3 路径 | 0/3 | 3/3 | +3 |
| GaC rules 总数 | 152 | 158 | +5 |
| agent-workflows tools | ~28 | 32 | +4 |
| OMO cron 集成 | 0/2 | 2/2 | +2 |
| **覆盖度估测** | **~0%** | **~90%** | — |

## 5. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| GaC rule 添加后 CI 新 fail | 中 | 中 | 只在 `make gac-local-gate` strict 中加, 已有 5-check 兜底 |
| agent-workflows tool timeout | 低 | 低 | timeout=120 足够 |
| cron 集成未被正确 run | 中 | 低 | 派生面仍在 `.omo/_derived/` 中, 人工跑也行 |
| 与现有 152 rule 冲突 | 低 | 低 | 编号 M4-* 前缀不与现有 CR-* 碰撞 |

## 6. ADR 命名方案

| ADR | 标题 | Phase |
|-----|------|-------|
| **0152** | M4 8 工具 + 4 schema 入 GaC rules | P1 |
| **0153** | M4 4 工具入 agent-workflows.yaml + OMO cron | P2b |
| **0154** | M4 OMO cron 集成 — operating-rhythm 扩展 | P4 |

---

## 7. 验证清单

Phase 1 完成后验证:

```bash
# 1. GaC validate 通过
uv run --with pyyaml python bin/gac/gac-validate.py --gate

# 2. M4 Health Score 不退化
uv run --with pyyaml python bin/mof/m4-health-score.py  # 保持 100/100

# 3. 新规则可被 agent-workflow 识别
uv run --with pyyaml python bin/agent-workflow.py tools | grep -E "M4-|mof-bootstrap|m4-health"

# 4. 回归测试全绿
uv run --with pyyaml python tests/integration/m4_metamodel/run_all.py
```

Phase 4 完成后验证:

```bash
# 5. OMO cron 可调用
M4_HOOK_JSON=1 uv run --with pyyaml python bin/mof/m4-cron-hook.py --sync

# 6. health score 派生面写 cron log
cat .omo/_derived/m4-cron-log.json | python3 -c "import json,sys; d=json.load(sys.stdin); assert d[-1]['mark']=='M4_HOOK_MARK'; print('cron log OK')"
```
