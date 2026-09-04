---
type: ssot
last-reviewed: 2026-08-26
owner: governance-team
---

# Domain Facts Audit Design

> Date: 2026-08-13
> Scope: Documents content-plane convergence, Task 7 Cockpit owner parity slice

## Goal

Expose a read-only Cockpit facts audit for registered Documents **document** domains. It replaces no schedule and makes no claim that the legacy Documents script has been retired. The command reports missing or unusable `_entities/facts.md` files with a truthful non-zero result.

## Boundary and rationale

`@驾驶舱/_runtime/check-vault-audit.py` is a manual legacy audit. It resolves a domain list, checks `_entities/facts.md`, shows its modification date, and currently exits zero even when files are absent. Cockpit already has the authoritative L4 registry projection and a no-follow regular-file probe from `domain-status`; this slice exposes that inspection through one Workspace-owned read surface with corrected exit semantics.

Freshness policy, KEMS health, project binding and gateway health are excluded. They need separate policies and are not implied by the presence of a facts file.

| Information | Authority | Cockpit responsibility |
| --- | --- | --- |
| Domain identity, type, path and manifest validity | L4 `ManifestRegistry` / `DOMAIN.yaml` | Reuse `_load_domains()`; never parse a second registry. |
| Facts artifact | Registered document-domain root | Probe only `_entities/facts.md`; return no content. |
| Legacy script, cron, LaunchAgent, client schedule | Existing Documents/system configuration | Out of scope; no bridge, cutover or mutation. |

Cockpit must not write Documents, Workspace state, Runtime state/evidence, manifests, bindings or third-party client configuration. It does not invoke Runtime, Kairon, OMO or a subprocess.

## Adapter contract

```python
def domain_facts_audit(
    domain_id: str = "",
    *,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
) -> dict[str, Any]
```

The adapter calls `_load_domains()` once and selects all registered L4 Documents domains only when `domain_id` is empty. `ManifestRegistry.as_legacy_registry()` is already the authority projection for these manifests and marks them as document domains; Cockpit does not invent a separate type rule. An empty registry is `unavailable` with the `no registered domain projects` error; an unknown requested ID is also `unavailable` and does not silently widen the request.

The response schema is `cockpit.domain-facts-audit.v1`:

```json
{
  "schema": "cockpit.domain-facts-audit.v1",
  "status": "ok | violations | unavailable",
  "available": true,
  "requested_domain_id": "vault",
  "total": 1,
  "summary": {"present": 1, "missing": 0, "unreadable": 0, "invalid": 0},
  "domains": [{
    "id": "vault",
    "name": "@学习进化",
    "facts": {"status": "present", "path": "…/_entities/facts.md", "modified_on": "2026-08-13"}
  }],
  "sources": {"domain_registry": "…"}
}
```

`modified_on` exists only for a readable, regular facts file. It is the local calendar date from the valid file's `lstat` timestamp, matching the legacy display meaning; it is never a freshness decision.

| Adapter status | Meaning | CLI exit |
| --- | --- | --- |
| `ok` | All selected document domains have readable, regular facts files. | 0 |
| `violations` | L4 authority loaded, but at least one facts artifact is missing, unreadable or invalid. | 1 |
| `unavailable` | L4 authority cannot load, the requested ID is unknown, or no registered domain projects. | 2 |

This corrects the legacy script's false-success exit behavior. It is a new owner command, not byte-for-byte CLI compatibility. The legacy script remains untouched and its migration family remains `in_progress` until a later bridge and consumer-cutover phase.

## Safety

The implementation reuses the existing no-follow artifact probe. `_entities/facts.md` is valid only if each component remains inside the registered domain root and the final artifact is a regular file. Static symlinks, directories, FIFOs and path escapes are reported without being followed or opened; unreadable files are reported. A regular file may be opened with `O_NOFOLLOW` solely to validate readability, but the probe never reads or returns facts content.

## CLI and MCP

- CLI: `cockpit facts-audit [DOMAIN_ID] --json`. Without an ID it audits all document domains; JSON is the exact adapter envelope; default output renders the same ID/name/status/date fields.
- MCP: `domain_facts_audit(domain_id: str = "") -> str` returns that envelope through the existing JSON serializer.

No web route, Runtime job, generated dashboard, new registry, client config, or Documents gateway edit is added.

## Acceptance evidence

1. Adapter tests cover present, missing, unreadable/invalid, unknown and malformed-authority paths.
2. CLI tests prove exact JSON forwarding and 0/1/2 mapping.
3. MCP tests prove registration and selected-domain forwarding.
4. Focused Cockpit tests and scoped Ruff pass.
5. A live all-domain read-only command records its actual outcome without mutating Documents.
6. Cockpit CI passes; root adopts its gitlink only in a separate PR after upstream merge.
