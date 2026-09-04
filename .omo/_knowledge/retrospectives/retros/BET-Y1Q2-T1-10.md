---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-10 Retrospective
type: retro
---
# BET-Y1Q2-T1-10 Retrospective

## Q1. What was delivered?

A governed declaration and observation slice for the local agent pool:

- Pi, Oh My Pi, OpenCode, CodeBuddy, Claude Code, Crush, Grok, MiMo, AGY,
  Codex, Reasonix and Kilo share one static provider model and worker policy
  registry.
- A read-only observer emits sanitized CLI/quota/compute observations and a
  canonical checksum; it never dispatches or calls a model.
- OMO now rejects disabled or non-admitted workers before any dispatch state
  mutation, including explicit worker IDs and default selection.

## Q2. What evidence proves it?

- Root observer behavior tests: 17 passed.
- OMO admission/dispatch regression set: 27 passed.
- Targeted Ruff, diff checks, MOF self-reflection and write-owner audit passed.
- A real read-only probe produced 12 worker observations, an externally pinned
  checksum, no identity fields, and an unchanged OpenCode config hash.
- Independent review first blocked the change, then approved it after the OMO
  pre-mutation admission gate and checksum/privacy fixes.

## Q3. What was not delivered?

- No scheduler, router, queue, automatic model choice, fallback, retry or
  account switch.
- No model inference and no automatic admission of newly declared workers.
- No user configuration changes and no repair of the machine's omlxc PATH.
- No Multica, Kandev or Ruflo trial; those remain separate reversible pilots.

## Q4. What changed in surface area?

The root slice adds one observer and one focused test file, extends three
governance/model registries, one collaboration standard, the BET ledger, this
retro and one evidence note. The OMO submodule adds one admission helper, one
pre-mutation dispatch check and one focused regression file, plus two existing
fixture updates. Exact final line/file counts are recorded by
`bet-ledger.py surface` at closeout rather than copied here.

## Q5. What should happen next?

1. Admit one candidate at a time through a low-risk worker pilot and the
   existing task/Mesh/lease/review lifecycle; Pi or Oh My Pi is the preferred
   first trial.
2. Repair/align the machine-level omlxc CLI path in a separate runtime task,
   then observe AetherForge local compute without direct-port bypass.
3. Add Multica and Kandev as reversible control-plane trials; keep Orca as the
   terminal executor and Workspace manifests/receipts as delivery truth.
4. Use Ruflo later for memory/autonomy/cost experiments, not as the first
   delivery control plane.
