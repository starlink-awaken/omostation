---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-31
ssot: .omo/_truth/registry/document-governance.yaml
verifier: bin/ssot/doc-governance-check.py
---

# Document Governance Standard

The document governance registry is the machine-readable source for ownership,
lifecycle, review cadence, and discoverability policy.

## Contract

- Every governed document belongs to one registered surface.
- Entry documents keep metadata in the registry; governed content documents use
  YAML frontmatter.
- The frontmatter contract is `status`, `lifecycle`, `owner`, and
  `last-reviewed`. `ssot` and `verifier` identify authority and the executable
  check when a document needs a local override.
- `last-reviewed` is a review timestamp, not a content-generation timestamp.
- `active` documents must have a discoverable owner and a valid SSOT pointer.
- `stale`, `superseded`, and `archived` are explicit lifecycle outcomes; do not
  hide historical documents by deleting their references.

## Checks

Run the unified checker from the workspace root:

```bash
python3 bin/ssot/doc-governance-check.py
python3 bin/ssot/doc-governance-check.py --json
python3 bin/ssot/doc-governance-check.py --scope workspace
python3 bin/ssot/doc-governance-check.py --strict
python3 bin/ssot/doc-governance-check.py --no-new-warnings
```

The default tracked scope is the actionable PR gate. Workspace scope is for
auditing ignored plans and runtime projections. Findings use the common
`path/rule/owner/severity/workflow/evidence` shape so GaC and dashboards can
consume the same output.

## Warning debt

The registry's `warning_exceptions` section records the accepted warning budget
for legacy documents, including an owner, reason, and expiry date. The default
checker reports this baseline without blocking existing debt. `--no-new-warnings`
blocks expired exceptions, unbaselined warning buckets, and increases above the
registered budget while preserving grace for the current baseline. It is not a
replacement for `--strict`; the migration goal is to reduce each budget to zero
before removing the exception.
