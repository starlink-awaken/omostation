---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0106-gac-governance-as-code.md
  - 0150-submodule-pr-reverse-review.md
  - 0151-submodule-hygiene-gate.md
  - 0132-l0-mof-m4-metamodel.md
  - ../../../../bin/mof-bootstrap.py
  - ../../../../bin/m4-health-score.py
  - ../../../../bin/check-submodule-hygiene.py
  - ../../../../bin/mcp-tool-data-complete.py
  - ../../../../bin/omo-state-cleanup.py
supersedes: []
---

# ADR-0152: M4 5 GaC 规则追加 (Phase 1)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。
> **Phase 1 of M4→GaC 全面接入**: 5 条治理规则。

---

## 0. TL;DR

M4 元模型工程产出的 8 个治理工具 + 4 个 schema 文件 + 5-check 自反校验 **此前未入 GaC 门禁**。
本 ADR 治本: 向 `governance-checks.yaml::gac.rules` 追加 5 条规则,
覆盖 M4 自反校验 / Health Score / 子模块卫生 / MCPTOOL 完整性 / 派生面范式。

**GaC rules 总数**: 152 → 157 (+5, 全部 ACCEPTED)
**覆盖的 M4 资产**: 5 tools + 3 检查链 + 2 派生面路径

---

## 1. 5 条规则

| id | dimension | layer | check_type | enforcement | 对应 M4 资产 |
|----|-----------|-------|------------|-------------|-------------|
| M4-BOOTSTRAP-REFLEX | X1 | meta | audit_chain | required | bin/mof/mof-bootstrap.py + 5-check |
| M4-HEALTH-SCORE | X2 | meta | freshness | advisory | bin/mof/m4-health-score.py + 派生面 |
| M4-SUBMODULE-HYGIENE | X1 | meta | audit_chain | preferred | bin/ssot/check-submodule-hygiene.py |
| M4-MCPTOOL-INTEGRITY | X4 | L0 | consistency_drift | required | bin/gac/mcp-tool-data-complete.py |
| M4-DERIVED-PLANE-AUDIT | X1 | meta | ssot_pointer | advisory | bin/gac/omo-state-cleanup.py + 派生面范式 |

### 1.1 规则详情

**M4-BOOTSTRAP-REFLEX** (required):
- 执行器: hook_pre_edit + ci_gate + gac_local_gate
- 每次 PR 必须通过 5-check strict (check_1 到 check_5 全 0 err)
- 覆盖 bin/mof/mof-bootstrap.py + ecs/ssot/mof/ 全部 schema

**M4-HEALTH-SCORE** (advisory):
- 4 维度加权:mof-validate 60%/5-check 30%/meta 5%/ADR 5%
- 派生面 m4-health.json 通过 radar_cron 每日写入
- 退化触发告警,不阻塞 gate

**M4-SUBMODULE-HYGIENE** (preferred):
- 每周 cron --strict 运行, CI 提示但不阻塞
- 3 类: submodule-dirty / tracked-derived / submodule-pointer-stale

**M4-MCPTOOL-INTEGRITY** (required):
- MCPTOOL 单工具 yaml 必填 tool_name+server
- 集合 yaml (有 tool_count / tools: 列表) 自动跳过

**M4-DERIVED-PLANE-AUDIT** (advisory):
- 派生面应 gitignored 不占用 SSOT
- 顺序 omo_audit + radar_cron 周期性验证

---

## 2. 关联

- [ADR-0106](./0106-gac-governance-as-code.md) (GaC 框架)
- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (M4 主决策)
- [ADR-0145](./0145-mcptool-collection-skip.md) (MCPTOOL 集合占位)
- [ADR-0153](./0153-m4-agent-workflows-tools.md) (agent-workflows 工具注册, 配套 PR)
- [ADR-0154](./0154-m4-omo-cron-integration.md) (OMO cron 集成, 配套 PR)

---

## 3. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Phase 1, GaC rules 152→157) |
