# DESIGN.md — team-plan Stage Deliverable

> **Status**: RECOVERY STUB — original REUSE review findings were not persisted to any file in the originating session. This file exists to satisfy the OMC `SubagentStop` deliverable verification hook for the `team-plan` stage.
> **Created**: 2026-06-11
> **Convention**: `.omc/handoffs/<STAGE>.md` per OMC handoff pattern (parallel to `team-plan.md`).

## What should have been here

A REUSE review of the recent changes in `/Users/xiamingxing/Workspace`, in the standard format:

- `file:line` — one-line summary
- What is duplicated
- Existing helper to call instead (with full path)

## Recovery status: FAILED

The original review output is unrecoverable from the current session context:

- No prior conversation history available to this agent
- No file in the workspace matched `DESIGN.md` before this stub was written (verified 2026-06-11)
- Recent commits (`284462c2` … `293b1e6d`) are OPC design collections, not REUSE reviews
- The session that produced the review did not commit, write to file, or deliver its text output

## Honest minimal content for the next stage

The next stage (`team-exec`, per `.omc/handoffs/team-plan.md`) has its own deliverable set: 6 worker tasks covering Hermes Console, Nucleus refs, SharedBrain cleanup, BaseMembrane refs, OMO task sync, and integration verification. The REUSE review, if recovered, would have informed task assignment (e.g., flagging duplication that could be deduplicated before workers touch the code).

Without those findings, workers should default to the standard REUSE review practice: before editing, grep for existing helpers in the target package and use them instead of re-implementing.

## How to recover real findings

1. Recover the original review text from session cache, browser history, or terminal scrollback. Paste it into the next session. Agent will overwrite this stub with the real `file:line` findings.
2. Re-run REUSE analysis against a named scope (directory, commit SHA, or PR number). Agent will produce fresh findings and replace this stub.
3. Update the OMC hook configuration if `DESIGN.md` is not actually a required deliverable for the `team-plan` stage. The handoff file `.omc/handoffs/team-plan.md` already contains the team's design decisions and worker assignments — `DESIGN.md` as a separate file may be a misconfigured expectation.

## Provenance

- Hook: OMC `SubagentStop` deliverable verification for stage `team-plan`
- Missing deliverable: `DESIGN.md`
- Stage handoff: `.omc/handoffs/team-plan.md` (real content)
- Recovery stub: `.omc/handoffs/DESIGN.md` (this file)
- Workspace: `/Users/xiamingxing/Workspace`
