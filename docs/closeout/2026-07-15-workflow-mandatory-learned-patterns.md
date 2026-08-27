# Closeout — 2026-07-15 Workflow 强制 + Learner patterns 入库

## Landed

| Item | Detail |
|------|--------|
| ADR-0203 | 需求迭代强制走 Agent Workflow（`mode: required`） |
| Registry | `agent-workflows.yaml::requirement_iteration_policy` |
| Contract | `agent-workflow-contract.md` §3.1 |
| Red lines | `AGENTS.md` §1.6 · `CLAUDE.md` Step B.1 · `project-governance` skill |
| Patterns | ADR 撞车 / 主机双闸门 / pre-push 路径漂移（learner 2026-07-15 栈复盘） |

## Run evidence

- Workflow: `project-doc-change`
- Run: see closeout of this PR after verify

## Verify

```bash
uv run --with pyyaml python bin/agent-workflow.py lint
rg -n "requirement_iteration_policy" .omo/_truth/registry/agent-workflows.yaml
test -f .omo/_knowledge/decisions/0203-requirement-iteration-workflow-mandatory.md
```
