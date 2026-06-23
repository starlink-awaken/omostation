---
plane: knowledge
type: design
status: active
freshness: 2026-05-31
maintainer: auto
---
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# Phase 5 secrets ownership model

## 1. Decision

Phase 5 freezes `secret_ref` ownership as a **reference-only truth model + external managed secret material**.

Concretely:

1. truth stores **metadata and references**, never secret values
2. control stores **policy and enablement**, never secret values
3. delivery stores **redacted audit evidence**, never secret values
4. actual secret material lives in a **managed provider outside tracked repo truth**

Wave 0 default provider policy:

| Layer | Decision |
|------|----------|
| canonical reference format | `secret_ref: secrets://<provider>/<name>` |
| default local provider | `keychain` on macOS |
| allowed fallback provider | `vault-file` using externally managed encrypted files, not plaintext repo files |
| prohibited provider | plain `_secret/` directory with unencrypted YAML |

This replaces the earlier ambiguous `_secret/` placeholder with a provider-backed reference contract.

## 2. Plane contract

| Plane | Allowed secret data | Forbidden |
|------|---------------------|-----------|
| truth | secret metadata, owners, rotation policy, `secret_ref` identifiers | secret value, decrypted blob, raw token |
| control | provider enablement, governance caps, rotation alarms | secret value |
| delivery | audit events, rotate/apply/verify traces, redacted failure reports | secret value, full request body with credentials |
| knowledge | design rules, operating procedures, review findings | secret value |

## 3. Canonical reference model

Task definitions and proposals may carry only this kind of field:

```yaml
secret_ref: secrets://keychain/webhook/github-ci
```

or

```yaml
secret_ref: secrets://vault-file/ilink/default-token
```

Interpretation:

1. `provider` identifies the storage backend
2. trailing path identifies the logical secret name
3. all runtime resolution happens inside a dedicated secret resolver, not by direct file reads from arbitrary task code

## 4. Ownership and lifecycle

### 4.1 Truth-owned metadata

Secret metadata belongs in a truth-owned catalog, for example:

`_truth/secrets/registry.yaml`

Expected metadata fields:

```yaml
id: webhook/github-ci
provider: keychain
purpose: github webhook HMAC
owner: task-center
rotation_policy:
  interval_days: 90
  manual_approval_required: true
audit_class: high
consumers:
  - _truth/task-center/registry.yaml:webhook.github-ci
```

### 4.2 Provider-owned material

Actual secret material is **not** committed into `_truth/` or `_control/`.

Provider rules:

1. `keychain` stores the value in macOS Keychain and is the default local provider
2. `vault-file` stores encrypted blobs outside tracked truth, with file permissions `600`
3. all providers must support get, rotate, and audit hooks

## 5. Policy freeze

1. **All secret creation, deletion, or rotation is L3.**
2. **Phase promotion that depends on secrets readiness is also L3.**
3. **Workers may reference `secret_ref` but may not resolve or mutate secret values.**
4. **Proposals may describe secret changes, but carry references and impact only; the material change happens through the provider workflow.**

## 6. Task Center-specific rules

### 6.1 Webhook secrets

Webhook definitions may include:

```yaml
webhook:
  path: /hooks/github-ci
  method: POST
  secret_ref: secrets://keychain/webhook/github-ci
```

Requirements:

1. HMAC validation must use `hmac.compare_digest()`
2. missing or unresolved `secret_ref` blocks webhook activation
3. webhook failure logs must redact headers and payload fields that may contain secrets

### 6.2 iLink / delivery tokens

iLink or similar outbound delivery channels also use `secret_ref`; tokens do not remain in `config.yaml` as durable plaintext policy.

The provider may materialize a runtime token into process memory, but the persisted config contract stays reference-only.

## 7. Audit and rotation

Required delivery evidence for secret operations:

1. create/rotate event with actor, timestamp, and secret id
2. last verification timestamp that confirms consumers still resolve the current reference
3. redacted failure note if resolution fails

Rotation contract:

1. rotations produce a new provider version but preserve the logical secret id where possible
2. consumers should not need YAML edits if the logical id is stable
3. stale references raise divergence or readiness blockers before enable/apply

## 8. Migration away from `_secret/`

Wave 0 freeze explicitly rejects `_secret/` as a vague repo-local bucket.

Migration rule:

1. existing docs that say "`_secret/`" should be read as "managed secret provider"
2. Wave 1 implementation must normalize docs, schemas, and code to `secret_ref: secrets://...`
3. any temporary compatibility shim must remain outside truth SSOT and must not become a new secret store of record

## 9. Non-goals of this freeze

This freeze does **not** choose:

1. the exact provider plugin API
2. the full `_truth/secrets/registry.yaml` schema beyond the ownership contract
3. the final audit event file format

Those details belong to Wave 1 implementation, but they must stay inside the reference-only, provider-backed model frozen here.
