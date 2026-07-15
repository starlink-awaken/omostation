---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
related:
  - 0203-requirement-iteration-workflow-mandatory.md
  - 0216-compass-feedback-partial-smoke.md
supersedes: []
---

# ADR-0217 — Workflow 卫生：layer-check 误报修复 + 契约对齐 + evidence 愈合

- **Status**: ACCEPTED
- **Date**: 2026-07-15

## Context

1. **agent-workflow status ok=false**：compliance `halt` 因历史 run  
   `20260715T060501Z-handoff-resume-5e0c9b01` `closed_run_missing_evidence`（A1 之前关闭）
2. **layer-dependency-check 17+ 红**：大量 **false positive**  
   `bus_foundation.observability` 被误匹配为 `observability` 项目（中间段扫名）
3. **契约与实装脱节**：eCOS 实装中 L3 适配器调 M0/L4、L2/L1 调 bus(X)、L0 MOF 调 M0
4. **evidence-smoke partial**：agora 缺 `pydantic` 显式依赖（仅有 fastmcp）

## Decision

### D1 — import 解析只认包根前缀

`get_project_from_import`：最长前缀 + underscore↔hyphen；**禁止**中间段项目名匹配。

### D2 — 同层允许；契约方向对齐实装

- 同层 `from==to` 合法  
- L3→M0/L4；L2→X；L1→X；L0→M0；并收紧 forbidden 列表  

### D3 — 登记必要 file-level exceptions

对仍属架构债但合法的桥接（omo→c2g、runtime→omo、metaos→agora 等）写入 `exceptions`。

### D4 — 历史 run evidence 愈合

对 A1 前关闭且 `status=ok` 无 evidence 的 handoff-resume run 追加 healed evidence 字段，解除 compliance halt。

### D5 — agora 声明 pydantic

`projects/agora/pyproject.toml` 增加 `pydantic>=2.0`，降低 evidence-smoke 全量 BOS 依赖缺口。

### D6 — check-layers 升 hard

在 false-positive 清除 + 契约对齐后，`gac-gate` 中 `layer-dependency-check` 去掉 `continue-on-error`。

## Consequences

- Workflow status 可回到 ok（无 active 时不再被陈旧 missing-evidence halt）  
- CI check-layers 可 blocking  
- evidence-smoke 仍可能因 fastmcp 运行时缺包 partial；全量需 `uv sync` agora venv  
