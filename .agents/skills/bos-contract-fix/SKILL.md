---
name: fix-bos-contract
description: Use when user says "fix this BOS contract error" / "帮我修复 BOS 契约错误" / "mof contract-lint failed". Triggers on keywords: fix-bos-contract, BOS 契约, contract error, mof contract-lint failed. End-to-end workflow: diagnose → impact analysis → propose edit → validate → commit. Phase 3 (P110+).
---

# fix-bos-contract — Intent-Driven Development for BOS Contracts

> **Phase 3 (BOS Contract Linter 30-day plan, P110+)** — End-to-end workflow that turns
> natural-language intent ("fix this BOS contract error") into validated, committed fixes.

## When to use this skill

Trigger this skill when:
- User pastes an `INTERNAL_MODULE_NOT_FOUND` / `INVALID_SCOPE` / `SCOPE_VALIDATION_SKIPPED` / `ACTION_NAMING_CONVENTION` error from `mof contract-lint`
- User says "帮我修复这个 BOS 契约错误" / "fix this contract error" / "mof contract-lint failed"
- CI fails with `omo lint**` exit 1 (after Phase 1 wired mof contract-lint into CI)

## What this skill does

Runs **5 phases** in sequence:

1. **Diagnose**: Run `mof-contract-agent diagnose <error_log>` → get error_id + explanation + suggested_fix
2. **Analyze Impact**: Run `mof-contract-agent analyze <uri>` → get affected_files + direct_dependencies
3. **Read YAML**: Read `bos-services.yaml` to get current state
4. **Propose Edit**: Based on diagnosis + impact, propose a precise YAML edit (no hardcoded strings)
5. **Validate & Commit**: Run `mof contract-lint --bos-yaml <path>` again, then `git add + git commit`

## Phase 3 adjustments vs original proposal (paste_1.txt)

| 编号 | 调整 | 原因 |
|:-----|:-----|:-----|
| **C1** | agent 用 `ecos.agents` entry-points (非 `qoder.agents`) | qoder framework 不存在, ecos 自有命名 |
| **C2** | agent `analyze_service()` 解析真实 `--json` (非 mock) | mock 数据无价值, 复用 Phase 2 v0.2 |
| **C3** | agent `diagnose_error()` 复用 Phase 2 v0.2 `explain_error()` (4 IDs) | 提案仅 2 IDs, 覆盖率不足 |
| **C4** | YAML 无 hardcoded 旧字符串 (`func_name: run_governance_audit_xxx`) | hardcoded 不在真实文件中, fix 无变化 |
| **C5** | YAML 字段用 omostation Claude SKILL.md 格式 (非 `phases`/`steps`) | workspace 无 `phases` schema, 现有 SKILL.md 范例更兼容 |
| **C6** | agent CLI 支持 `--bos-yaml` 参数 (显式路径) | 默认路径 CWD 敏感 (Phase 0 A4 教训) |

## How to invoke

### From another AI Agent (via entry-points)

```python
# Standard setuptools entry-points discovery
from importlib.metadata import entry_points
agents = entry_points(group="ecos.agents")
mof_agent = agents["mof-contract-agent"].load()()

# Call from other agents
result = mof_agent.analyze_service("bos://governance/omo/audit")
diagnosis = mof_agent.diagnose_error("INTERNAL_MODULE_NOT_FOUND: ...")
```

### From CLI directly

```bash
# Phase 3 entry-points install mof-contract-agent via `uv pip install -e projects/ecos`
mof-contract-agent analyze "bos://governance/omo/audit" --bos-yaml projects/agora/etc/bos-services.yaml
mof-contract-agent diagnose "INTERNAL_MODULE_NOT_FOUND: ..."
```

## 5-phase workflow

### Phase 1: Diagnose

**Tool**: Bash
**Command**:
```bash
mof-contract-agent diagnose "<error_log>"
```

**Output**: JSON with `error_id`, `explanation`, `suggested_fix`.

### Phase 2: Analyze Impact

**Tool**: Bash
**Command**:
```bash
mof-contract-agent analyze "<uri>" --bos-yaml projects/agora/etc/bos-services.yaml
```

**Output**: JSON with `direct_dependencies`, `affected_files`, `match_found`.

### Phase 3: Read YAML

**Tool**: Read
**Args**: `file_path: "<yaml_path>"`

### Phase 4: Propose Edit

**Tool**: Agent (uses mof-contract-agent knowledge)
**Prompt**:
```
Given:
- Diagnosis from Phase 1 (error_id, suggested_fix)
- Impact from Phase 2 (direct_dependencies, affected_files)
- YAML content from Phase 3

Propose a precise Edit to fix the error. Common fixes:
- INTERNAL_MODULE_NOT_FOUND: correct `func_name` (e.g. remove "_xxx" suffix typos)
- INVALID_SCOPE: add scope to `required_scopes` (or remove invalid scope from YAML)
- ACTION_NAMING_CONVENTION: rename action or move backend file to convention
- SCOPE_VALIDATION_SKIPPED: out of scope (informational)

Output format:
  old_string: |
    <exact YAML lines to change>
  new_string: |
    <corrected YAML lines>
```

### Phase 5: Validate & Commit

**Tool**: Bash
**Commands**:
```bash
# Re-lint
uv --directory projects/ecos run mof-contract-lint --bos-yaml "../<yaml_path>"

# If validation passes, commit
git add <yaml_path>
git commit -m "fix(bos): resolve <uri> via /quest fix-bos-contract"
```

## Example invocation

```text
User: 帮我修复这个 BOS 契约错误
       INTERNAL_MODULE_NOT_FOUND: bos://governance/omo/audit -> Cannot import module 'omo.omo_audit'.

Skill: fix-bos-contract activated.

Phase 1 (Diagnose):
  → error_id: INTERNAL_MODULE_NOT_FOUND
  → suggested_fix: "1. Check that the module_path ..."

Phase 2 (Analyze Impact):
  → direct_dependencies: 17 services
  → affected_files: projects/omo/src/omo/omo_audit.py + x1-governance-policies.yaml

Phase 3 (Read YAML):
  → Read projects/agora/etc/bos-services.yaml

Phase 4 (Propose Edit):
  → diff -u old_string new_string

Phase 5 (Validate & Commit):
  → mof contract-lint pass
  → git commit -m "fix(bos): resolve bos://governance/omo/audit via /quest fix-bos-contract"
```

## Prerequisites

- Phase 0 v0.1 完成 (commit 197d670b): mof-contract-lint 基础工具
- Phase 2 v0.2 完成 (commit 4c1fc70f): --explain + --impact JSON support
- Phase 3 v0.1 完成 (本 skill): mof-contract-agent + ecos.agents entry-points
- omo, agora, ecos, kairon 等 submodule 已 `git submodule update --recursive`

## Limitations & Future work

- **Phase 3 范围内**: Skill 文件 + agent 注册 + workflow 定义
- **Phase 3 范围外** (需 Phase 4+ 实施):
  - omostation quest handler 解析 workflow YAML
  - AI Agent runtime 自动调用 mof-contract-agent
  - Skill discovery (agents 找到 fix-bos-contract)
  - 端到端 Autonomy Review (Phase 3 提案要求)
  - Cross-submodule fix (e.g. 修改 aetherforge 解决 INTERNAL_MODULE_NOT_FOUND)

## Related

- Phase 0 v0.1 (commit 197d670b): mof-contract-lint 基础
- Phase 2 v0.2 (commit 4c1fc70f): --explain + --impact
- ADR-0105, ADR-0106, ADR-0107 (本 skill 决策)
- pre-analysis: `.omo/_knowledge/decisions/phase3-bos-contract-linter-pre-analysis.md`
- precedent skill: `projects/omo/.claude/skills/omo-srp-refactor/SKILL.md`

---

*最后更新: 2026-06-25 · P110+ · Phase 3 BOS Contract Linter Autonomy 作战包*
