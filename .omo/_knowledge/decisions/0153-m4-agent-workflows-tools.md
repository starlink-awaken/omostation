---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0152-m4-gac-rules.md
  - 0151-submodule-hygiene-gate.md
  - ../../../../.omo/_truth/registry/agent-workflows.yaml
  - ../../../../bin/mof-bootstrap.py
  - ../../../../bin/m4-health-score.py
  - ../../../../bin/check-submodule-hygiene.py
  - ../../../../bin/mcp-tool-data-complete.py
supersedes: []
---

# ADR-0153: M4 4 工具入 agent-workflows (Phase 2b)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。
> **Phase 2b of M4→GaC 全面接入**: agent-workflows 工具注册。

---

## 0. TL;DR

向 `.omo/_truth/registry/agent-workflows.yaml` 的 `tools[]` 追加 4 个 M4 治理工具,
让它们可被 governance-agent 调度、health_check 和 P74 workflow 识别。

**工具列表**:
- mof-bootstrap — M4 5-check 自反校验器 (required, timeout=60)
- m4-health-score — M4 Health Score 量化 (optional, timeout=120)
- check-submodule-hygiene — 子模块卫生守门 (optional, timeout=60)
- mcp-tool-data-complete — MCPTOOL 数据完整性守门 (optional, timeout=30)

**agent-workflows tools 总数**: ~28 → 32 (+4)

---

## 1. 工具注册

### 1.1 4 个 M4 tool 定义

```yaml
- id: mof-bootstrap
  type: local_tool
  description: "M4 5-check 自反校验器"
  command: ["uv", "run", "--with", "pyyaml", "python", "bin/mof-bootstrap.py", "all"]
  health_check: true
  required: true
  timeout: 60

- id: m4-health-score
  type: local_tool
  description: "M4 Health Score 量化(派生面引擎)"
  command: ["uv", "run", "--with", "pyyaml", "python", "bin/m4-health-score.py", "--emit"]
  health_check: true
  required: false
  timeout: 120

- id: check-submodule-hygiene
  type: local_tool
  description: "子模块卫生守门(3类检查)"
  command: ["uv", "run", "--with", "pyyaml", "python", "bin/check-submodule-hygiene.py", "--strict"]
  health_check: true
  required: false
  timeout: 60

- id: mcp-tool-data-complete
  type: local_tool
  description: "MCPTOOL 数据完整性守门"
  command: ["uv", "run", "--with", "pyyaml", "python", "bin/mcp-tool-data-complete.py"]
  health_check: true
  required: false
  timeout: 30
```

### 1.2 workflow paths 扩展

在 `governance-state-mutation` workflow 的 `paths` 中追加:

```yaml
- bin/mof-bootstrap.py
- bin/m4-health-score.py
- bin/check-submodule-hygiene.py
- bin/mcp-tool-data-complete.py
```

---

## 2. 关联

- [ADR-0152](./0152-m4-gac-rules.md) (GaC rules, Phase 1)
- [ADR-0154](./0154-m4-omo-cron-integration.md) (OMO cron, Phase 4)
- [ADR-0135](./0135-derived-plane-unification.md) (派生面范式)
- [ADR-0145](./0145-mcptool-collection-skip.md) (MCPTOOL 集合占位)

---

## 3. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Phase 2b, agent-workflows tools 28→32) |
