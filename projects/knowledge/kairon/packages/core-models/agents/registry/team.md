---
title: team
type: doc
---

# DigitalBrainOS Agent Team

Status: active bootstrap team.
Updated: 2026-05-15.

## Operating Principle

The Conductor owns task decomposition, dispatch, integration, and final
acceptance. Specialist agents are workers or reviewers, not autonomous owners of
truth. Their output must land in an isolated run artifact first, then be
integrated by the Conductor through a work packet.

## Core Team

Model and CLI routing are tracked separately in
`agents/registry/model-resource-pool.yaml` and
`docs/20-operating-model/model-resource-pool.zh-CN.md`.

| Seat | Primary agent | Best for | Default mode | Write authority |
|---|---|---|---|---|
| Conductor | Codex | planning, dispatch, integration, verification | controlled write | approved work packet only |
| Architecture Reviewer | Claude Code / DeepSeek or Codex sub-agent | architecture consistency, object model, API boundaries | read-only review | none by default |
| Governance Auditor | Claude/DeepSeek or Codex sub-agent | permissions, audit, control plane, failure modes | read-only review | none by default |
| Critic Agent | Gemini | alternative analysis, contradiction finding, gap review | read-only review | none by default |
| Copilot Worker | Copilot CLI | small edits, tests, schema stubs, boilerplate | scoped worker | low-risk explicit write scope |
| Implementation Planner | Droid GLM-4.7 | implementation plan review, file scope, dependency mapping | read-only review | none by default |
| Product Quality Reviewer | Crush MiniMax 2.5 | acceptance criteria, product flow, concise critique | read-only review | none by default |
| MiniMax Headless Reviewer | MMX MiniMax 2.5 | headless product review, summaries, acceptance criteria | read-only review | none by default |
| Deep Reasoning Reviewer | Claude Code | final preflight, governance edge cases, architecture consistency | read-only review | none by default |
| IDE Context Reviewer | Trae IDE | manual IDE chat, Builder/SOLO context review, subscription-model access | manual review | none by default |
| IDE Agent Manager Candidate | Antigravity | manual parallel agent manager, visual artifact review | unavailable | none by default |
| Secondary Implementation Worker | OpenCode DeepSeek V4 | implementation repair, bounded module pass | scoped worker | explicit disjoint write scope after artifact trial |
| Free-Tier Reviewer | KiloCode | cheap parallel review, prompt sanity check, small drafts | read-only review | artifact scope only until write trial |
| KOS Knowledge Operator | KOS | local retrieval, evidence discovery, source mapping | read-only retrieval | none by default |
| Evaluation Engineer | Codex/Gemini | acceptance checks, quality metrics, regression plans | read-only or scoped write | evaluation artifacts only |

## First Active Team

The first collaboration team is intentionally small:

- Conductor: Codex.
- Architecture Reviewer: Codex sub-agent.
- Governance Auditor: Codex sub-agent.

Copilot is now the first core execution assistant for scoped worker tasks.
Default Copilot authority is artifact-scoped write; canonical file writes require
an explicit work packet path list and Conductor review. Gemini is active as a
read-only Critic Agent for adversarial review before scoped implementation
starts. Other external CLIs stay read-only reviewers until their wrappers are
proven.

Droid GLM-4.7 and Crush MiniMax 2.5 are added as auxiliary reviewers:

- Droid GLM-4.7: implementation preflight and scoped file-plan review.
- Crush MiniMax 2.5: product-quality and acceptance-criteria review.
- MMX MiniMax 2.5: preferred MiniMax headless CLI for automated review because
  it returns JSON/text artifacts through stdout and supports `--non-interactive`.
- Claude Code is active as a deep reasoning reviewer through `claude -p`.
- Trae IDE is registered as a manual IDE chat bridge. Its local `trae chat`
  command can trigger IDE chat, but it does not return model output on stdout,
  so it is not used as an automated `dbos-agent` worker.
- Antigravity is registered as an IDE Agent Manager candidate only. No local
  `antigravity` command was detected, and no headless stdout workflow has been
  proven.
- OpenCode is smoke-tested with `opencode-go/deepseek-v4-flash` and can become
  a secondary scoped implementation worker after an isolated artifact write
  trial.
- KiloCode is smoke-tested with `kilo/kilo-auto/free` and should be used first
  as a free-tier parallel reviewer or small artifact drafter, not as a critical
  path gate.

## Escalation Rules

- Architecture decisions require Conductor integration and ADR update.
- Governance or security concerns block execution until resolved.
- Copilot output requires review before becoming canonical.
- Gemini/Claude review output is advisory until evidence-backed.
- Any destructive, external, production, credential, release, or Git publish
action requires explicit human approval.

## Near-Term Staffing Plan

1. Keep Conductor plus two reviewers for blueprint stabilization.
2. Use Copilot Worker for schema fixtures, template sections, adapter stubs, and
   bounded helper scripts with exact write scopes.
3. Add Gemini Critic for independent challenge reviews.
4. Use Droid GLM-4.7 before scoped implementation to challenge file scope and
   validation paths.
5. Use Crush MiniMax 2.5 to review product flow and acceptance criteria.
6. Use MMX MiniMax 2.5 for MiniMax automated review and concise operator-facing
   summaries.
7. Use Claude Code for final deep preflight reviews before scoped implementation.
8. Use Trae IDE manually for subscription-model review or Builder/SOLO sessions
   when the task benefits from IDE context.
9. Revisit Antigravity only after a deterministic command/bridge is available.
10. Trial OpenCode with isolated artifact writes before assigning canonical
    implementation paths.
11. Use KiloCode for cheap parallel critique and prompt/acceptance sanity checks.
12. Add KOS Knowledge Operator once local project asset indexing is wrapped.
13. Add broader Implementation Workers only after runtime API v0 and write locks
    exist.
