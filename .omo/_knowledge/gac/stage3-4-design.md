# GaC 阶段 3/4 设计 — 元模型派生 + 治理仪表盘 (ADR-0106)

> 阶段 3 (元模型机制 7) + 阶段 4 (度量+自愈) **设计文档**. 实现需专项 (ecos/cockpit).
> 本文档是阶段 3/4 的"阶段 0 设计"交付, 实现路径 + 阻塞明确.

---

## 阶段 3: 规则上 MOF 元模型 (机制 7, omostation 独有)

### 为什么 (收益)

当前 gac-validate 的 schema 是**硬编码** (Python enum). 上 MOF 后, 规则结构由**元模型约束** (M1), mof-validate 统一校验 — 机制 7 比 OPA 强 (OPA 无元模型层).

### M1 RuleDefinition 元模型 (规则的 schema 的 schema)

```yaml
# projects/ecos/src/ecos/ssot/mof/m1/governance/RULE-DEFINITION.yaml (阶段 3 新建)
kind: M1_MetaModel
id: RULE-DEFINITION
description: "GaC 规则元模型 (M1), 派生 M2 规则实例, 约束规则结构"
fields:
  - {name: id, type: string, pattern: "^CR-[A-Z0-9-]+$", required: true, unique: true}
  - {name: dimension, type: "enum[X1,X2,X3,X4]", required: true}
  - {name: layer, type: "enum[M0,L0,L1,L2,L3,meta]", required: true}
  - {name: check_type, type: "enum[ssot_pointer,mof_stage_gate,bos_resolve,task_field,drift_audit,freshness,value_roi,audit_chain]", required: true}
  - {name: executor, type: "list[enum[hook_pre_edit,hook_post,ci_gate,omo_audit,mcp_tool,mof_validate,mof_audit,evidence_smoke,radar_cron,gc_cron]]", required: true, min_items: 1}
  - {name: lifecycle, type: "enum[draft,active,deprecated,removed]", required: true}
  - {name: version, type: semver, required: true}
  - {name: target, type: string, optional: true}
  - {name: adr, type: string, optional: true}
```

### 派生链 (M1→M2→M3)

```
M1 RuleDefinition (元模型, 本文件)
  ↓ mof-derive (派生约束)
M2 RuleInstance (governance-checks.yaml::gac.rules, 当前 7 条实例)
  ↓ mof-validate (校验 M2 符合 M1)
M3 ExecutionBinding (规则→hook/MCP/gate 绑定, 阶段 1 后)
  ↓ mof-bridge-sync (Stage/Gate 纳入规则变更)
```

### 实现路径 (专项, 需 ecos)

1. 新建 `projects/ecos/src/ecos/ssot/mof/m1/governance/RULE-DEFINITION.yaml` (M1 元模型)
2. `mof-derive` 校验 `governance-checks.yaml::gac.rules` 符合 M1
3. `mof-validate` 集成 GaC (替代 `gac-validate` 硬编码 schema — 元模型驱动)
4. `mof-bridge-sync` Stage/Gate 纳入规则变更 (规则改走 MOF 流程)
5. gac-validate 降级为 mof-validate 的 thin wrapper (保 backward compat)

### 阻塞
- 需 ecos (m1 改动, 中风险, ecos 26h 未 commit 但有 M compute_engine)
- 建议专项 session + ecos 无活跃并发

---

## 阶段 4: 治理仪表盘 (度量 + drift 自愈)

### GaC 度量指标

| 指标 | 来源 | 意义 | 目标 |
|------|------|------|------|
| 规则总数 | `gac.rules` len | 治理覆盖 | 增长 (动态) |
| dimension 覆盖 | `gac-validate` | X1-X4 均衡 | 4 维全覆盖 |
| lifecycle 分布 | `gac-validate` | draft/deprecated 健康 | active 为主 |
| drift 数 | `gac-drift` | SSOT 违反量 | 趋降 |
| drift 率 | drift/规则数 | 治理健康分 | < 10% |
| 规则触发率 | hook/MCP log (阶段 1 后) | 规则活跃度 | 高触发 = 真拦问题 |
| 矛盾数 | `gac-validate --gate` | 规则间一致 | 0 |

### 仪表盘页面 (cockpit dashboard)

- **路由**: `cockpit /dash/gac`
- **数据源**: `gac-validate --json` + `gac-drift --json` (需加 --json 输出)
- **展示**:
  - 规则表 (id/dimension/layer/check_type/executor/lifecycle/version)
  - drift 列表 (文件 + 违反字段 + 修复建议)
  - lifecycle 饼图 (active/draft/deprecated 占比)
  - dimension 覆盖柱图 (X1-X4)
  - 趋势线 (drift 率随时间, radar 每日数据)

### drift 自愈 (机制 4 进阶)

- `gac-drift` 检测**漏执行规则** (声明 executor 但 hook 未注册 — 需阶段 1 hook 绑定后)
- `drift.auto_heal: true` 时 (注册表已配, 阶段 4 激活), 自动绑定规则到对应 hook
- `gac-drift --auto-heal` 实现

### 实现路径 (专项, 需 cockpit)

1. `gac-validate` / `gac-drift` 加 `--json` 输出 (仪表盘数据源)
2. cockpit `dashboard_server` 加 `/dash/gac` 路由 (Python 后端 + 数据聚合)
3. cockpit-ui 加 GaC 页 (React/TS, 表格 + 图表)
4. drift 自愈逻辑 (`gac-drift --auto-heal`, 漏执行规则自动绑定 hook)
5. 趋势数据持久化 (radar 每日 drift 数存 `.omo/_delivery/gac-trend.jsonl`)

### 阻塞
- 需 cockpit (dashboard_server + cockpit-ui, 中风险, cockpit 26h 未 commit 工作区干净)
- 阶段 1 hook 绑定是 drift 自愈前置 (需 omo, 并发阻塞)
- 建议专项 session + 阶段 1 完成后

---

## 实现优先级 (建议)

| 阶段 | 优先级 | 前置 | 估时 |
|------|:---:|------|:---:|
| 阶段 1 T1.2 hook | P0 | omo 无并发 | 1-2 天 |
| 阶段 1 T1.3 MCP | P0 | omo 无并发 | 1-2 天 |
| 阶段 3 元模型 | P1 | ecos 无并发 | 2-3 天 |
| 阶段 4 仪表盘 | P1 | 阶段 1 done + cockpit | 3-5 天 |
| 机制 6 完整 | P2 | schema 加 created_at | 1 天 |

**关键路径**: 阶段 1 (hook/MCP) → 阶段 4 (仪表盘+自愈). 阶段 3 可并行 (ecos 独立).

---

## 当前状态 (2026-06-26)

- ✅ 阶段 3/4 **设计 done** (本文档)
- ⏳ 实现待专项 (ecos/cockpit, 需无并发 session)
- 上游: GaC 核心框架 (阶段 0/1部分/2/5部分) 已 done, 可运作

---

*阶段 3/4 设计 v1.0 · 2026-06-26 · ADR-0106 · 实现待专项*
