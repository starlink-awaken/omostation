---
schema_version: governance-waiver-evidence/v1
lifecycle: history
owner: human-principal
created: 2026-09-02
last_updated: 2026-09-02
expires_when: bootstrap restoration PR merges or closes
value_indicator_policy: false
title: Workflow self-hosting archive restoration waiver
type: doc
---

# Workflow self-hosting archive restoration waiver

## User authorization

```text
when: 2026-09-02
who: xiamingxing
quote: "帮我看看，目前本地仓库，所有项目和子项目，是否都是最新的，是否有没有合并的或者没有提交的，都处理一下吧。然后刚才的剩余工作，新建bet也提交了吧。完成之后记得pr合并提交，主仓和子仓都提交。"
```

## Exact bootstrap scope

`AGCP_REQUIREMENT_ITERATION_GATE=0` is authorized only because the current
main archive move removed files still hard-bound by `agent-workflow.py`, the
BET ledger, and a blocking gate. The bootstrap commit may restore these exact
archived bytes and record this waiver:

- `docs/operations/blueprint-agent-instruction-pack-v1.md` from
  `.omo/_archive/operations-2026H1/blueprint-agent-instruction-pack-v1.md`;
- `docs/operations/bin-scripts-convergence-manifest.json` from
  `.omo/_archive/operations-2026H1/bin-scripts-convergence-manifest.json`;
- `docs/operations/root-directory-governance-policy.yaml` from
  `.omo/_archive/operations-2026H1/root-directory-governance-policy.yaml`; and
- this waiver file.

## Prohibitions and residual controls

This waiver does not authorize any child source change, test/CI change,
gitlink update, runtime mutation, Documents access, branch-protection action,
BET completion, or value claim. After the exact files are restored, all further
work must start a normal `BET-Y1Q3-T6-15` workflow with exact claims and normal
PR review.
