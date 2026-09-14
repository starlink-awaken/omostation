---
id: ADR-0409
title: Documents capability routes converge on Workspace owners
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-13
related:
  - ADR-0342
type: ssot
---

# ADR-0409: Documents Capability Routes Converge on Workspace Owners

## WHY

The Documents domain-project registry correctly declared Workspace as the owner
of skills and workflows, but its executable route references still pointed at
`@公共/_control/SKILL-INDEX.md` and `@公共/_control/REGISTRY.md` through `bos://`
URIs. Those Documents files are useful human projections, not the authoritative
Workspace implementations. The checker and Cockpit also accepted the references
without proving that their sources existed, so a stale projection could report
an apparently healthy domain context.

## WHAT

For every Documents domain project:

- skill discovery is owned by `workspace-skills` and resolves to
  `.agents/skills`;
- workflow execution is owned by `workspace-workflow-mesh` and resolves to
  `.omo/_truth/registry/agent-workflows.yaml`;
- Documents keeps domain identity, content, guidance projections, and evidence,
  but does not own executable skills or workflows;
- the root consistency checker rejects URI, absolute, escaping, missing, or
  wrong-type sources and owner mismatches;
- Cockpit resolves the same sources at request time, returns their derived paths,
  and degrades the binding instead of reporting success when a source is invalid.

The validation intentionally uses ordinary path resolution and existence/type
checks. The personal-workspace threat model does not justify a second sandbox or
adversarial race-hardening layer for these read-only declarations.

## REJECTED ALTERNATIVES

### Keep Documents indexes as executable authority

Rejected because it creates a second skills/workflow truth and makes client
behavior depend on manually synchronized Documents content.

### Copy Workspace skills into each domain

Rejected because twelve domain copies would add drift without improving domain
identity or user outcomes.

### Add another MCP tool for capability discovery

Rejected because the existing `domain_context` surface already carries the
binding. Enriching that response is smaller and preserves one user entrypoint.

## ROLLBACK

Revert the binding registry, checker, and Cockpit commits together. Do not point
the routes back to Documents projections unless a later ADR explicitly transfers
capability ownership away from Workspace.

## NEXT

After the code and registry changes are installed, relabel the two Documents
indexes as projections, run the twelve-domain live checker and `domain_context`
smoke, and record the installed evidence in the existing convergence report.
