---
status: active
lifecycle: plan
owner: governance-team
last-reviewed: 2026-08-18
last_updated: 2026-09-03
title: Documents Owner Job MVP Implementation Plan
type: doc
---
# Documents Owner Job MVP Implementation Plan

1. Extend the Workspace binding registry schema with one explicit Runtime job.
2. Add fail-closed registry checks for job ID, domain ID, owner, reads, writes,
   schedule, timeout, evidence path, and command contract.
3. Add a thin Workspace runner that loads the binding, resolves the L4
   executable explicitly, registers a Runtime `JobSpec`, and delegates to
   `run_job`.
4. Cover dry-run, success, owner failure, repeat execution, malformed binding,
   and state-only evidence with tests.
5. Run focused checks, live `creative` smoke, Documents digest verification,
   code review, root CI, PR, and accepted deployment.
