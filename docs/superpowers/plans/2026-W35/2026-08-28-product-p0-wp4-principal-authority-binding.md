---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---
# Product P0 WP4 Principal Authority Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind every effectful principal to a short-lived Cockpit credential authority receipt that OMO verifies before ledger/mandate/provider work and Agora only transports.

**Architecture:** Reuse Cockpit's existing API-key authentication and engineering-review HMAC key as the trusted-local credential authority; persist only a receipt, digest, and proof, never the API key. OMO owns receipt verification, PDP admission, Event Ledger persistence, and WorkflowAdmitted propagation. Cockpit authenticates and issues; Agora PEP and capability gateway require and forward the already-verified digest without minting identity.

**Tech Stack:** Python 3.13, dataclasses, HMAC-SHA256, pytest, OMO sovereignty/Event Ledger/Workflow Mesh, Cockpit FastAPI/MCP auth, Agora PEP/capability gateway, child-first Git delivery.

## Global Constraints

- BET: `BET-Y1Q3-T4-04`; WorkPacket: `WP-BET-Y1Q3-T4-04`.
- Accepted Spec: `docs/superpowers/specs/2026-08-28-product-p0-wp4-principal-authority-binding-design.md`.
- OMO is the verifier/admission authority; Cockpit is the credential source; Agora is transport/PEP only.
- No principal registry, credential database, raw API key persistence, Cockpit/Agora receipt fabrication, or new identity control plane.
- `principal:alice` and any fixture-only identity are rejected on production entry paths.
- Receipt digest is 64 lowercase SHA-256 hex; proof reuses the existing trusted-local HMAC signing key and expires.
- All negative cases prove zero Event Ledger append, mandate evaluation, provider, runtime, probe, and tool calls.
- Delivery order: OMO -> Cockpit -> Agora -> root pointers. Final state `delivery_accepted`; value remains `NOT_PROVEN`.

---

### Task 1: Amend WP4 to Cover the Actual Production Path

**Files:**
- Modify: `docs/superpowers/specs/2026-08-28-product-p0-wp4-principal-authority-binding-design.md`
- Modify: `docs/plans/3y-bet-ledger.yaml`

**Interfaces:**
- Adds OMO Workflow Mesh propagation, Cockpit credential authority, and Agora PEP surfaces omitted from the initial Spec.

- [ ] **Step 1: Add exact write surfaces**

Add:

```text
projects/omo/src/omo/workflow_mesh.py
projects/omo/tests/test_workflow_mesh.py
projects/cockpit/src/cockpit/web/auth.py
projects/cockpit/src/cockpit/tests/test_dashboard_server.py
projects/agora/src/agora/mcp/policy_enforcement.py
projects/agora/tests/test_pep_integration.py
```

Retain the existing `principal_authority.py`, enforcement, agent runtime, capability gateway, and focused test surfaces.

- [ ] **Step 2: Lock the trusted-local proof and propagation semantics**

The amendment must state that Cockpit issues a short-lived HMAC proof after `authenticate_api_principal`, OMO verifies it before any ledger read/append or mandate call, and the complete receipt/digest/proof is included in the canonical `WorkflowAdmitted.admission` proof material. ECOS generated models are not changed; authority fields live in the Event Ledger/WorkflowAdmitted payload envelope.

- [ ] **Step 3: Recalculate T4-04's digest and merge the amendment**

Compile the WorkPacket, commit Spec and ledger in separate lanes, merge required checks, close the superseded run, and start a fresh WP4 implementation run from main.

---

### Task 2: Implement the OMO Principal Authority Contract

**Files:**
- Create: `projects/omo/src/omo/sovereignty/principal_authority.py`
- Modify: `projects/omo/src/omo/sovereignty/__init__.py`
- Modify: `projects/omo/tests/test_sovereignty_mandate_admission.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class PrincipalAuthorityReceipt:
    principal_id: str
    authority_ref: str
    credential_digest: str
    membership_version: int
    verified_at: str
    expires_at: str

    def to_dict(self) -> dict[str, Any]: ...


class PrincipalAuthorityError(ValueError):
    def __init__(self, reason: str, message: str) -> None: ...


def principal_receipt_digest(
    receipt: PrincipalAuthorityReceipt | Mapping[str, Any],
) -> str: ...


def validate_admitted_principal_context(
    admission: Mapping[str, Any],
    *,
    principal_authority_ref: str,
    principal_receipt_digest: str,
    now: str,
) -> PrincipalAuthorityReceipt: ...
```

- [ ] **Step 1: Add receipt/digest RED tests**

```python
def test_admitted_principal_context_rejects_expired_receipt(monkeypatch) -> None:
    receipt = {
        "principal_id": "principal:owner",
        "authority_ref": "authority://cockpit-api",
        "credential_digest": "a" * 64,
        "membership_version": 4,
        "verified_at": "2026-08-28T00:00:00+00:00",
        "expires_at": "2026-08-28T00:01:00+00:00",
    }
    digest = principal_receipt_digest(receipt)
    admission = {
        "status": "admitted",
        "principal_id": "principal:owner",
        "principal_authority_receipt": receipt,
        "principal_receipt_digest": digest,
        "principal_authority_proof": "proof",
    }
    monkeypatch.setenv("COCKPIT_ENGINEERING_REVIEW_SIGNING_KEY", "k" * 32)

    with pytest.raises(PrincipalAuthorityError) as exc:
        validate_admitted_principal_context(
            admission,
            principal_authority_ref="authority://cockpit-api",
            principal_receipt_digest=digest,
            now="2026-08-28T00:02:00+00:00",
        )

    assert exc.value.reason == "principal_authority_expired"
```

Add missing, principal mismatch, authority mismatch, digest mismatch, proof mismatch, membership rollback, unknown authority, and fixture principal cases.

- [ ] **Step 2: Implement canonical digest and HMAC proof verification**

```python
def principal_receipt_digest(receipt: PrincipalAuthorityReceipt | Mapping[str, Any]) -> str:
    payload = receipt.to_dict() if isinstance(receipt, PrincipalAuthorityReceipt) else dict(receipt)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _expected_proof(receipt_digest: str) -> str:
    signing_key = os.environ.get("COCKPIT_ENGINEERING_REVIEW_SIGNING_KEY", "")
    if len(signing_key) < 32:
        raise PrincipalAuthorityError("principal_authority_unavailable", "signing key unavailable")
    return hmac.new(signing_key.encode(), receipt_digest.encode(), hashlib.sha256).hexdigest()
```

`validate_admitted_principal_context` must parse timezone-aware timestamps, require membership_version>=1, reject fixture principals, compare digests/proof with `hmac.compare_digest`, and return the frozen receipt.

- [ ] **Step 3: Run OMO authority contract GREEN**

```bash
cd projects/omo
uv run pytest tests/test_sovereignty_mandate_admission.py -q
uv run ruff check src/omo/sovereignty/principal_authority.py tests/test_sovereignty_mandate_admission.py
```

---

### Task 3: Enforce Authority Before PDP/Ledger/Provider Effects

**Files:**
- Modify: `projects/omo/src/omo/sovereignty/enforcement.py`
- Modify: `projects/omo/tests/test_sovereignty_policy_enforcement.py`

**Interfaces:**
- Extends `ActionRequest` with `principal_authority_ref: str` and `principal_receipt_digest: str`.
- Extends canonical request hash with both fields.
- `PolicyEnforcementService` validates the persisted authority context before mandate/capability evaluation and any decision append.

- [ ] **Step 1: Add format-only principal RED**

```python
def test_format_only_principal_is_rejected_before_ledger_and_provider(broker) -> None:
    pdp = PolicyEnforcementService(broker)
    provider = _CountingProvider()
    before = broker.count()

    outcome = pdp.execute(
        _make_request(
            principal_id="principal:alice",
            principal_authority_ref="authority://cockpit-api",
            principal_receipt_digest="a" * 64,
        ),
        provider,
    )

    assert outcome.status == OUTCOME_DENIED
    assert outcome.provider_calls == 0
    assert provider.calls == 0
    assert broker.count() == before
```

- [ ] **Step 2: Include authority in `compute_request_hash`**

Add both fields to the canonical JSON payload. Update every ActionRequest fixture explicitly; do not default missing authority to a synthetic value on effectful paths.

- [ ] **Step 3: Persist verified receipt in the decision event payload**

The `Decision.Policy.v1` Event Ledger payload must include:

```python
{
    **decision.model_dump(mode="json"),
    "principal_authority_receipt": receipt.to_dict(),
    "principal_receipt_digest": principal_receipt_digest(receipt),
    "principal_authority_proof": admission["principal_authority_proof"],
}
```

No credential secret is included.

- [ ] **Step 4: Run enforcement GREEN**

```bash
cd projects/omo
uv run pytest tests/test_sovereignty_policy_enforcement.py tests/test_sovereignty_mandate_admission.py -q
```

---

### Task 4: Bind Authority into WorkflowAdmitted Proof Material

**Files:**
- Modify: `projects/omo/src/omo/workflow_mesh.py`
- Modify: `projects/omo/tests/test_workflow_mesh.py`

**Interfaces:**
- Consumes: verified receipt/digest/proof.
- Produces: `snapshot["admission"]` with immutable authority fields covered by the existing admission `proof` hash.

- [ ] **Step 1: Add RED for proof-covered propagation**

Seed `WorkflowAdmitted` with authority fields, verify the snapshot preserves them, then mutate `principal_receipt_digest` without recomputing proof and assert `WorkflowMeshEventError`.

- [ ] **Step 2: Add required authority fields to admission validation**

Effectful admissions require:

```python
{
    "principal_authority_receipt",
    "principal_receipt_digest",
    "principal_authority_proof",
}
```

Because `_canonical_admission` already hashes the complete unsigned admission mapping, no second signature/hash path is added.

- [ ] **Step 3: Run Workflow Mesh GREEN**

```bash
cd projects/omo
uv run pytest tests/test_workflow_mesh.py tests/test_sovereignty_policy_enforcement.py -q
```

---

### Task 5: Make Cockpit the Credential Source, Not the Verifier of Record

**Files:**
- Modify: `projects/cockpit/src/cockpit/web/auth.py`
- Modify: `projects/cockpit/src/cockpit/agent_runtime_server.py`
- Modify: `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_dashboard_server.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_agent_runtime_server.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_agent_runtime_mcp_server.py`

**Interfaces:**

```python
def issue_principal_authority_context(
    principal: AuthenticatedPrincipal,
    *,
    now: str,
    ttl_seconds: int = 300,
) -> dict[str, Any]: ...
```

- [ ] **Step 1: Add receipt-issuance RED**

Authenticate a real configured API key and assert the returned context has a stable `principal:64-hex-digest` ID, authority ref `authority://cockpit-api`, 64-hex credential digest, membership_version=1, bounded expiry, receipt digest, and HMAC proof. Assert example/unknown/missing keys issue nothing.

- [ ] **Step 2: Implement receipt issuance without persisting the key**

Derive the stable principal ID and credential digest from the already-authenticated key material inside the request boundary, construct the receipt, hash it, sign only the digest, and return the mapping. Do not write it to config or disk.

- [ ] **Step 3: Require the context on HTTP and MCP effectful calls**

Before constructing runtime requests, authenticate headers/session, issue the authority context, and delegate the complete mapping to OMO. On missing/mismatch, return 401/403 or structured MCP rejection before `AgentRuntime.run_task` or `chat` is called.

- [ ] **Step 4: Run Cockpit GREEN**

```bash
cd projects/cockpit
uv run pytest src/cockpit/tests/test_dashboard_server.py \
  src/cockpit/tests/test_agent_runtime_server.py \
  src/cockpit/tests/test_agent_runtime_mcp_server.py -q
uv run ruff check src/cockpit/web/auth.py src/cockpit/agent_runtime_server.py \
  src/cockpit/agent_runtime_mcp_server.py
```

---

### Task 6: Require the Verified Context at Agora PEP and Gateway

**Files:**
- Modify: `projects/agora/src/agora/mcp/policy_enforcement.py`
- Modify: `projects/agora/src/agora/capability_gateway.py`
- Modify: `projects/agora/tests/test_pep_integration.py`
- Modify: `projects/agora/tests/unit/test_capability_gateway.py`

**Interfaces:**
- `enforce(..., principal_authority: Mapping[str, Any] | None = None)` includes the authority reference/digest in the trusted request hash and request dict.
- Gateway forwards the same digest and never verifies raw credentials or generates a principal.

- [ ] **Step 1: Add PEP zero-effect RED**

```python
def test_missing_principal_authority_rejects_before_pdp_or_provider(monkeypatch) -> None:
    provider = _CountingPepProvider()
    monkeypatch.setattr(policy_enforcement, "get_pep_provider", lambda: provider)

    with pytest.raises(PEPDenied, match="principal_authority_required"):
        enforce(uri="bos://tool/write", tool_name="write", operation="write")

    assert provider.evaluate_calls == 0
```

- [ ] **Step 2: Add authority fields to trusted PEP request material**

Strip any caller-injected duplicate from arguments, require the server-owned mapping, and include only `principal_id`, `authority_ref`, `receipt_digest`, and proof-covered receipt reference in the canonical request hash/request dict.

- [ ] **Step 3: Add gateway transport RED/GREEN**

Missing or mismatched authority returns `PRINCIPAL_AUTHORITY_REQUIRED` or `PRINCIPAL_AUTHORITY_MISMATCH` before adapter probe/invoke. Successful receipts echo the exact `principal_receipt_digest` returned by OMO; no credential is logged.

- [ ] **Step 4: Run Agora GREEN**

```bash
cd projects/agora
uv run pytest tests/test_pep_integration.py tests/unit/test_capability_gateway.py -q
uv run ruff check src/agora/mcp/policy_enforcement.py src/agora/capability_gateway.py
```

---

### Task 7: Child-First Delivery, Cross-Repo Canary, and Completion

**Files:**
- Child repositories: OMO, Cockpit, Agora files from Tasks 2-6
- Root pointers: `projects/omo`, `projects/cockpit`, `projects/agora`
- Coordinator-only completion: `docs/plans/3y-bet-ledger.yaml`
- Coordinator-only retro: `.omo/_knowledge/retros/BET-Y1Q3-T4-04.md`

**Interfaces:**
- Produces: three child-main receipts, root pointer receipts, one authority-bound Cockpit -> OMO -> Agora canary, and `delivery_accepted`.

- [ ] **Step 1: Merge OMO child first**

Run OMO focused/full contract tests, independent review, CI, merge, and main ancestry proof.

- [ ] **Step 2: Merge Cockpit against the OMO contract**

Run auth/HTTP/MCP tests, review, CI, merge, and main ancestry proof.

- [ ] **Step 3: Merge Agora against OMO/Cockpit digest semantics**

Run PEP/gateway tests, review, CI, merge, and main ancestry proof.

- [ ] **Step 4: Update root pointers in one root-last PR**

```bash
python3 bin/ssot/submodule-reachability-gate.py --source head --fetch --require-main --json
git ls-tree HEAD projects/omo projects/cockpit projects/agora
```

- [ ] **Step 5: Run the real local authority canary**

Use one non-example API key, issue a short-lived receipt, execute one admitted sandbox-capable request through Cockpit/OMO/Agora, and record equal digests at all three boundaries. Negative missing/mismatch/expired/replay requests must show zero calls.

- [ ] **Step 6: Serialize completion and rollback evidence**

T4-04 becomes `delivery_accepted`; value stays `NOT_PROVEN`. Rollback order is Agora -> Cockpit -> OMO; append-only decision/admission receipts remain. Retire every child/root clone, branch, terminal, and workflow lock.

---

## Self-Review

- Spec coverage: credential source, OMO verification, PDP precondition, WorkflowAdmitted proof, Cockpit ingress, Agora PEP/gateway, child/root order, canary, rollback, and value firewall are explicit.
- Placeholder scan: runtime IDs are obtained from commands; no missing production seam remains.
- Type consistency: receipt fields/digest/proof are identical across Cockpit, OMO, Workflow Mesh, PEP, and gateway; no ECOS generated model change is required.
