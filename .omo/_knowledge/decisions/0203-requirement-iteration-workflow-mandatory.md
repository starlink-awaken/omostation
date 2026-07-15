---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0203 — 需求迭代强制走 Agent Workflow

- **Status**: ACCEPTED
- **Date**: 2026-07-15
- **Owner**: governance-team

## Context

AGENTS.md / CLAUDE.md 已要求 multi-step 工作 `bootstrap → start → claim`，但：

1. Prompt 在压缩后易丢；agent 常直接改代码 / 开 PR，无 run 记录。  
2. P74 管的是 **workflow 沉默**，不管 **需求落地绕过 workflow**。  
3. 2026-07-15 Scheme C + Wave2 栈（#355–#370）暴露：无 run 时 claim/lock/verify/closeout 证据链断裂，并发与复盘成本上升。

## Decision

### D1 — 强制范围（requirement iteration）

以下一律视为 **需求迭代**，**必须** 经 `bin/agent-workflow.py` 生命周期执行：

| 纳入 | 例 |
|------|-----|
| 功能 / 缺陷 / 运维落地 | 改 `projects/*`、加 API、合 PR 栈 |
| 治理 / SSOT / ADR / 契约 | 改 `.omo/_truth`、standards、ADR |
| 文档中的交付/closeout（伴随产品或治理变更） | closeout + 实现同 PR 或同 run |
| 子模块 pointer 收口 | `submodule-pointer-close` |

### D2 — 强制生命周期

```text
bootstrap → status → start <workflow-id> --profile <agent-profile>
  → claim <run-id> --path <path>
  → (edit / test)
  → verify <run-id> --from-diff --execute
  → closeout <run-id>
```

禁止：无 active run 即改需求相关文件并宣称完成。

### D3 — 显式豁免（窄）

| 豁免 | 条件 |
|------|------|
| 纯只读问答 / 探索 | 不写工作区（或仅读） |
| `observer-audit` | 只读观察 run/lock/ledger |
| 用户显式 waiver | 用户书面说「跳过 workflow」且写进 closeout 证据 |

`handoff-resume` **不是** 豁免开写：它是恢复已有 run 的路径，仍须绑定 run-id。

### D4 — SSOT 与执行面

| 层 | 位置 |
|----|------|
| 策略字段 | `.omo/_truth/registry/agent-workflows.yaml::requirement_iteration_policy` |
| 契约 | `.omo/standards/agent-workflow-contract.md` §3.1 |
| Agent 红线 | `AGENTS.md` §1.6、`CLAUDE.md` Step B |
| Skill | `.agents/skills/project-governance/SKILL.md` |

`mode: required` 表示 **规范强制**；claim/verify 硬门仍由 `claim_policy` tiers 与 runner 执行。后续可将 compliance 升级为对「有 diff 无 run」发 warn/fail（本 ADR 不绑定具体 GaC 规则 ID）。

## Consequences

- 所有 agent（Claude / Cursor / OMC / 自建）同一标准：先 `start` 再改。  
- 与 P74 互补：P74 防「登记了不用」；本 ADR 防「该用却不用」。  
- 短问答与只读探索不受影响。

## Verification

```bash
uv run --with pyyaml python bin/agent-workflow.py list
uv run --with pyyaml python bin/agent-workflow.py lint
# 读 registry requirement_iteration_policy.mode == required
```

## References

- ADR-0130 P74 workflow solidification  
- `.omo/standards/agent-workflow-contract.md`  
- `docs/closeout/2026-07-15-stack-summary-retrospective.md`
