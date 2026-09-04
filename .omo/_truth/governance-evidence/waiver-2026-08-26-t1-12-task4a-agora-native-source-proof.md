---
lifecycle: history
owner: governance-team
last_updated: 2026-08-26
title: Workflow waiver 证据 — BET-Y1Q3-T1-12 Task 4A Agora native sou
type: doc
---

# Workflow waiver 证据 — BET-Y1Q3-T1-12 Task 4A Agora native source proof

```text
waiver: user-explicit
when: 2026-08-26T01:11:18Z
who: xiamingxing
quote: "本次 BET-Y1Q3-T1-12 Task 4A Agora composite FastMCP native source proof 自举修复跳过 workflow start，允许使用 AGCP_REQUIREMENT_ITERATION_GATE=0；仅限 lib/capability_native_sources.py、lib/capability_native_inspection.py、tests/test_capability_native_inspection.py、bin/cockpit/gen-capability-registry.py、docs/generated/capability-registry.yaml、projects/agora 根 gitlink与其子仓内最小 native composition proof/tests，以及 .omo/_truth/governance-evidence/waiver-2026-08-26-t1-12-task4a-agora-native-source-proof.md；把本句写入 waiver 证据，不得修改 BET 状态、completion_evidence、价值指标、其他 capability kind 或运行态。"
supplement_when: 2026-08-26T02:29:09Z
supplement_quote: "补充本次 BET-Y1Q3-T1-12 Task 4A waiver：原授权路径 bin/cockpit/gen-capability-registry.py 已迁移且不存在，允许将该路径更正为 bin/ssot/gen-capability-registry.py；其余授权范围和禁止项保持不变，并把本补充句写入原 waiver 证据。"
scope:
  - lib/capability_native_sources.py
  - lib/capability_native_inspection.py
  - tests/test_capability_native_inspection.py
  - bin/ssot/gen-capability-registry.py
  - docs/generated/capability-registry.yaml
  - projects/agora
  - .omo/_truth/governance-evidence/waiver-2026-08-26-t1-12-task4a-agora-native-source-proof.md
reason: Task 3 correctly makes a new T1-12 workflow start fail closed while Agora's composite FastMCP entrypoint cannot yet produce an exact native source proof; Task 4A is the self-bootstrap correction for that proof boundary.
risk: no workflow run, claim, or lock exists for this narrowly scoped bootstrap change; all edits still require isolated clone provenance, TDD, review, PR, CI, and child-first delivery.
residual: keep BET-Y1Q3-T1-12 candidate; do not claim completion or value evidence; after the Agora proof lands, resume the registered workflow for the remaining Task 4 surfaces.
gate_bypass: 1
no_run_id: true
```

## Hard boundaries

- Do not modify BET status, completion evidence, value indicators, runtime state, or user configuration.
- Do not widen native proof semantics for Skill, Workflow, MCP/BOS kinds outside the exact Agora composite case.
- Do not add a second capability registry writer, duplicate dispatch truth, or synthetic tool manifest that can drift from native source.
