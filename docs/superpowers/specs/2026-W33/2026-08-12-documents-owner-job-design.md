---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# Documents Owner Job MVP Design

## Goal

Prove one real, read-only Documents owner job end to end for the `creative`
domain without moving execution into Documents or creating a second domain
authority.

## Authority split

- L4 `ManifestRegistry` and `DOMAIN.yaml` own domain identity, path, and
  manifest validation.
- Workspace `documents-domain-projects.yaml` owns the binding from a domain to
  an explicit Runtime job and owner command.
- Runtime owns isolation, timeout, process execution, and state-only evidence.
- Documents remains read-only. The job may write only under
  `OMOSTATION_RUNTIME_STATE_ROOT`.

## MVP binding

The binding registry declares one manual job, `creative-manifest-check`, for
domain `creative`. It reads the Documents registry and the resolved domain
manifest, invokes the formal L4 `domain validate-manifest` command, has no
Documents write declarations, and emits only a metadata receipt.

The runner accepts the L4 executable path explicitly. This keeps client and
installation concerns outside the binding SSOT and prevents an implicit PATH
fallback from selecting a different owner implementation.

## Failure semantics

- Invalid or ambiguous binding data fails before execution.
- Unknown domains and invalid manifests return the L4 non-zero result.
- Missing isolation returns Runtime exit 125 without starting the owner.
- Evidence or state I/O failures remain non-zero.
- Dry-run validates and resolves the binding but creates no state.

## Acceptance

The MVP is accepted when dry-run, success, owner failure, repeat execution,
receipt evidence, and a before/after Documents tree digest all behave as
declared on the real `creative` domain.
