---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-29
last_updated: 2026-09-03
title: Wave B Exact Capability Binding Implementation Plan
type: doc
---

# Wave B Exact Capability Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make accepted WorkPackets declare exact Skill/Workflow/MCP/BOS requirements and make every admitted dispatch produce replayable, identity-bound native execution receipts without introducing a second registry, scheduler, database, or value truth.

**Architecture:** Extend the existing WorkPacket v2 contract with an optional strict `capability_requirements` list, then make new BETs compile and preflight it at workflow start. Dispatch rebinds the same requirements to real assignment/admission/dispatch identities. Task 6B adds one root read-only `verify-material` projection over the existing material v1 and OMO Workflow Mesh, then makes Cockpit consume that verdict before any effect; it does not add an OMO service, Cockpit-local validator, registry, daemon or cache. Delivery stays staged across eCOS, OMO, root verifier, Cockpit child, root gitlink and a final production-topology canary.

**Tech Stack:** Python 3.9-compatible source, Python 3.13 test runtime via uv, YAML SSOT/MOF, Pydantic v2, pytest, Git submodules, GitHub PR checks, Orca orchestration.

## Global Constraints

- Canonical Spec: `docs/superpowers/specs/2026-08-24-exact-capability-binding-design.md`, version `1.1.2`, digest `sha256:41b7175076f14129b5e62989042f2f97d5f2b6ffb60cdd3a0ac9d60c27c0267a`. The 1.1.2 amendment records the current root/Cockpit pointer divergence and freezes the C-lite verifier contract: reuse material v1, bind its admission digest to `WorkflowAdmitted.proof`, verify persisted step/worker identity read-only, gate Cockpit before effects and leave OMO/Agora unchanged in this slice.
- BET: `BET-Y1Q3-T1-12`; every edit must be covered by its WorkPacket and a current claim.
- No new capability registry writer, scheduler, broker, database, workflow, or dispatch truth.
- No automatic Human Verdict, decision outcome, time-saved estimate, or personal value promotion; all execution receipts keep `value_indicator_policy=false`.
- No query first-match, wildcards, caller-supplied adapter/transport/argv, or legacy invoke strings.
- New blocking behavior rolls out shadow → warning → fail. The root native `load`/`invoke` path now enforces complete binding fail-closed; effectful HTTP/MCP paths still require their separately measured rollout evidence. Missing binding returns a redacted receipt and prevents registry/gateway/provider execution.
- Child repository PRs merge and tag before the root gitlink moves; root pointers must reference child `origin/main` descendants.
- Use independent clone v2 delivery attempts. Never edit `/Users/xiamingxing/Workspace` or reuse a linked worktree as a writer.
- Every implementation task ends with targeted tests, an independent Orca review, commit, source tag, PR-context CI, merge, and lifecycle retirement receipt.
- After every two or three PRs, rerun the main/open-PR/submodule strategic delta audit and update Documents.
- The bootstrap waiver ended with merged PR #2137. The 1.1.2 amendment is governed by run `20260826T112630Z-bet-execution-555d73bb`; it does not extend or reuse any waiver.

---

## File Responsibility Map

| File or module | Responsibility |
|---|---|
| `projects/ecos/src/ecos/ssot/mof/m2/work_packet.yaml` | Cross-language `CapabilityRequirement` and WorkPacket field authority |
| `projects/omo/src/omo/orchestration_contract.py` | Strict packet validation at OMO boundary |
| `projects/omo/src/omo/blueprint_control.py` | Preserve exact requirements through compile/admit/dispatch |
| `bin/plan/bet-ledger.py` | Validate ledger requirements and compile WorkPacket v2 |
| `projects/omo/src/omo/workflow/lifecycle.py` | Start-time native preflight and immutable run identity |
| `bin/ssot/gen-capability-registry.py` | Existing generated projection writer; add skill/workflow projection only |
| `bin/capability-sync.py` | Public exact find/inspect/load/invoke boundary and B4-D receipt consumer |
| `lib/capability_trace_binding.py` | Pure capability kind semantics and replay validation |
| `lib/capability_native_execution_*` | Pure material/marker/receipt/cleanup/replay contracts; no provider I/O |
| `projects/omo/src/omo/worker_lifecycle.py` | Persisted admission recheck before StepDispatched |
| `projects/omo/src/omo/omo_worker_dispatch.py` | Single admitted worker dispatch path; remove dead legacy grant |
| `projects/cockpit/src/cockpit/commands/bos.py` | Human CLI consumer that forwards canonical binding inputs |
| `projects/cockpit/src/cockpit/_subcommands.py` | Canonical BOS parser owns the five existing bundle flags |
| `projects/cockpit/src/cockpit/adapters/capability_binding.py` | One fixed-argv subprocess adapter; no local validation rules |
| `projects/cockpit/src/cockpit/web/api_kems.py` | Remove the already-dead naked dispatch endpoint |
| `projects/agora/src/agora/capability_gateway.py` | Existing binding-digest carrier; unchanged by Task 6B unless a new direct gap is proved |
| `docs/architecture/*` and Instruction Pack | Durable status, entrypoint and handoff contract |

---

### Task 1: Add strict CapabilityRequirement to eCOS WorkPacket v2

**Files:**
- Modify: `projects/ecos/src/ecos/ssot/mof/m2/work_packet.yaml`
- Modify: `projects/ecos/src/ecos/ssot/mof/compiler/api.py`
- Modify: `projects/ecos/src/ecos/ssot/mof/compiler/emitters.py`
- Modify: `projects/ecos/src/ecos/ssot/tools/work_packet_compiler.py`
- Modify: `projects/ecos/src/ecos/ssot/mof/generated/control/mof-control.schema.json`
- Modify: `projects/ecos/src/ecos/ssot/mof/generated/control/mof-control-schemas.ts`
- Modify: `projects/ecos/src/ecos/ssot/mof/generated/control/mof-control.manifest.json`
- Modify: `projects/ecos/src/ecos/ssot/mof/generated/control/mof_control_models.py`
- Modify: `projects/ecos/src/ecos/ssot/mof/generated/control/mof-control.sql`
- Test: `projects/ecos/tests/test_mof_compiler.py`
- Test: `projects/ecos/tests/test_work_packet_compiler.py`

**Interfaces:**
- Consumes: existing `work-packet/v2` contract and extends the current direct inline-map IR/emitter support to closed inline-map list items.
- Produces: optional strict `capability_requirements` list with inline exact fields; the ordered list participates in the invariant packet hash; old v1/v2 packets remain readable and no new M2 type file is created.

- [ ] **Step 1: Write the failing MOF compiler test**

Add this contract assertion to `projects/ecos/tests/test_mof_compiler.py`:

```python
def test_work_packet_capability_requirements_are_strict_cross_language_contract(
    compiler: MofCompiler,
) -> None:
    artifacts = compiler.compile()
    schema = json.loads(artifacts["json-schema"])
    work_packet = schema["$defs"]["WorkPacket"]
    requirement = work_packet["properties"]["capability_requirements"]["items"]
    assert set(requirement["required"]) == {"capability_id", "operation", "effect"}
    assert requirement["additionalProperties"] is False
    assert requirement["properties"]["capability_id"]["pattern"] == (
        "^(skill|workflow|mcp-server|mcp-tool|bos-service):[A-Za-z0-9._:@/-]+$"
    )
    assert requirement["properties"]["operation"]["enum"] == ["find", "inspect", "load", "invoke"]
    assert requirement["properties"]["effect"]["enum"] == ["read_only", "effectful"]
    assert work_packet["properties"]["capability_requirements"]["type"] == "array"
    assert "capability_requirements" in artifacts["pydantic"]
    assert "capability_requirements" in artifacts["zod"]
```

The same RED/GREEN test must dynamically import the generated Pydantic module,
validate one complete requirement, and reject list items with an extra field,
a missing required field, a wildcard/invalid ID, or an invalid operation/effect
enum. This proves the emitted validator does more than declare
`list[dict[str, Any]]`.

Lock the Zod item shape rather than checking only the field name:

```python
zod = artifacts["zod"]
assert "capability_requirements: z.array(z.object({" in zod
assert "capability_id: z.string().regex(" in zod
assert 'operation: z.enum(["find", "inspect", "load", "invoke"])' in zod
assert 'effect: z.enum(["read_only", "effectful"])' in zod
assert "}).strict()).optional()" in zod
```

If the eCOS test environment exposes a runnable Zod toolchain, execute the same
valid/extra/missing/pattern/enum matrix against the generated schema; otherwise
the exact emitted expression above is the minimum cross-language artifact gate.

Also add deterministic compiler regressions in `tests/test_work_packet_compiler.py`:

- the same v2 packet with a different ordered `capability_requirements` list must produce a different packet hash;
- duplicate IDs, wildcard IDs, extra fields, and `skill:*` with `operation=invoke` must fail before canonical serialization;
- a packet without the optional field remains readable during the shadow rollout.

- [ ] **Step 2: Run the RED test**

Run:

```bash
cd projects/ecos
uv run pytest tests/test_mof_compiler.py::test_work_packet_capability_requirements_are_strict_cross_language_contract -q
```

Expected: FAIL because `$defs.CapabilityRequirement` and the WorkPacket property do not exist.

- [ ] **Step 3: Add the M2 schema**

First extend the existing compiler IR and emitters so a `type: list` whose
`items` is a closed inline map preserves the item `properties`, `required`,
patterns, and `additionalProperties: false` in JSON Schema, Pydantic, and Zod.
The current compiler only preserves those fields for a direct `type: map`; a
plain `items: {type: map}` would otherwise degrade to an unconstrained object.
Keep SQLite representation JSON-encoded and do not create a new M2 type.

Add one inline optional WorkPacket property in `work_packet.yaml`:

```yaml
optionalProperties:
  capability_requirements:
    type: list
    description: Ordered exact native capabilities required by this WorkPacket
    items:
      type: map
      additionalProperties: false
      required: [capability_id, operation, effect]
      properties:
        capability_id:
          type: string
          pattern: '^(skill|workflow|mcp-server|mcp-tool|bos-service):[A-Za-z0-9._:@/-]+$'
        operation:
          type: enum
          values: [find, inspect, load, invoke]
        effect:
          type: enum
          values: [read_only, effectful]
```

Add validation rules that reject duplicates and invalid kind/operation combinations:

```yaml
  - rule: "capability_requirements is None or len({r.get('capability_id') for r in capability_requirements}) == len(capability_requirements)"
    level: error
    message: capability_requirements capability_id 必须唯一
  - rule: "capability_requirements is None or all(r.get('operation') != 'invoke' or not r.get('capability_id', '').startswith('skill:') for r in capability_requirements)"
    level: error
    message: Skill 只能 load，禁止 invoke
```

Update `work_packet_compiler.py` in the same RED→GREEN change: add
`capability_requirements` to `INVARIANT_FIELDS` and apply the same strict shape,
ID, operation/effect, duplicate, and Skill-invoke validation before emitting the
canonical payload. M2-generated models own the per-item structural contract;
the deterministic packet compiler owns ordered identity, duplicate-ID, and
kind/operation semantics (repeated again by the later OMO boundary consumer).
Do not claim that arbitrary `validationRules` are emitted as executable
cross-language validators; this compiler currently stores but does not translate
those expressions.

- [ ] **Step 4: Regenerate all eCOS control artifacts**

Run the existing generator command used by `tests/test_mof_compiler.py`:

```bash
cd projects/ecos
uv run python src/ecos/ssot/tools/mof-compile.py compile \
  --out-dir src/ecos/ssot/mof/generated/control
```

Expected: the five tracked generated control files change together; no unrelated M2 output changes.

- [ ] **Step 5: Run eCOS GREEN and regression tests**

```bash
cd projects/ecos
uv run pytest tests/test_mof_compiler.py tests/test_work_packet_compiler.py -q
uv run ruff check src/ecos/ssot tests/test_mof_compiler.py tests/test_work_packet_compiler.py
```

Expected: PASS.

- [ ] **Step 6: Commit, tag, PR, merge, and retire the eCOS attempt**

Commit message: `feat(mof): add exact WorkPacket capability requirements`.

Source tag: `delivery/exact-capability-binding-ecos-20260824-v1`.

Merge only after eCOS CI is green; record merged child SHA for root reachability.

---

### Task 2: Make OMO validate and preserve WorkPacket capability requirements

**Files:**
- Modify: `projects/omo/src/omo/orchestration_contract.py`
- Modify: `projects/omo/src/omo/blueprint_control.py`
- Test: `projects/omo/tests/test_orchestration_contract.py`
- Test: `projects/omo/tests/test_blueprint_control.py`

**Interfaces:**
- Consumes: eCOS optional strict capability-requirement list from Task 1.
- Produces: canonical, ordered requirements preserved through compiled packet, admission request and dispatch result.

- [ ] **Step 1: Write RED packet-validation tests**

Add a helper and negative cases:

```python
CAPABILITY_REQUIREMENTS = [
    {"capability_id": "skill:git-discipline", "operation": "load", "effect": "read_only"},
    {"capability_id": "workflow:bet-execution", "operation": "load", "effect": "read_only"},
    {"capability_id": "mcp-server:agora", "operation": "load", "effect": "read_only"},
]

@pytest.mark.parametrize(
    "requirements",
    [
        [CAPABILITY_REQUIREMENTS[0], CAPABILITY_REQUIREMENTS[0]],
        [{"capability_id": "skill:*", "operation": "load", "effect": "read_only"}],
        [{"capability_id": "skill:git-discipline", "operation": "invoke", "effect": "effectful"}],
    ],
)
def test_v2_packet_rejects_invalid_capability_requirements(requirements):
    with pytest.raises(OrchestrationContractError, match="capability_requirements_invalid"):
        validate_capability_requirements(requirements)
```

- [ ] **Step 2: Run RED tests**

```bash
cd projects/omo
uv run pytest tests/test_orchestration_contract.py -q
```

Expected: at least one invalid requirement is accepted or silently dropped.

- [ ] **Step 3: Add one strict canonicalizer in `orchestration_contract.py`**

```python
_CAPABILITY_ID_RE = re.compile(
    r"^(?:skill|workflow|mcp-server|mcp-tool|bos-service):[A-Za-z0-9._:@/-]+$"
)

def validate_capability_requirements(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise OrchestrationContractError(
            "capability_requirements_invalid", "capability requirements must be a list"
        )
    canonical: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping) or set(raw) != {"capability_id", "operation", "effect"}:
            raise OrchestrationContractError(
                "capability_requirements_invalid", "capability requirement fields are invalid"
            )
        item = {key: str(raw[key]) for key in ("capability_id", "operation", "effect")}
        if (
            _CAPABILITY_ID_RE.fullmatch(item["capability_id"]) is None
            or item["capability_id"] in seen
            or item["operation"] not in {"find", "inspect", "load", "invoke"}
            or item["effect"] not in {"read_only", "effectful"}
            or (item["capability_id"].startswith("skill:") and item["operation"] == "invoke")
        ):
            raise OrchestrationContractError(
                "capability_requirements_invalid", "capability requirement is unsafe"
            )
        seen.add(item["capability_id"])
        canonical.append(item)
    return canonical
```

Call it before `WorkPacket.model_validate`, then require the Pydantic dump to equal the canonical list.

- [ ] **Step 4: Preserve requirements in BlueprintControl**

In `compile_packet`, set:

```python
"capability_requirements": validate_capability_requirements(
    bet.get("capability_requirements")
),
```

In `dispatch_packet`, replace capability label extraction with exact requirements plus derived worker labels:

```python
capability_requirements = validate_capability_requirements(
    packet.get("capability_requirements")
)
required_capability_ids = [item["capability_id"] for item in capability_requirements]
```

Persist both `capability_requirements` and a canonical digest in the request identity and dispatch result.

- [ ] **Step 5: Run OMO GREEN tests**

```bash
cd projects/omo
uv run pytest tests/test_orchestration_contract.py tests/test_blueprint_control.py -q
uv run ruff check src/omo/orchestration_contract.py src/omo/blueprint_control.py tests/test_orchestration_contract.py tests/test_blueprint_control.py
```

Expected: PASS; old v2 packets without the optional field remain readable.

- [ ] **Step 6: Commit/tag/merge OMO consumer before root producer**

Commit: `feat(omo): validate exact WorkPacket capabilities`.

Tag: `delivery/exact-capability-binding-omo-consumer-20260824-v1`.

Do not update the root gitlink until OMO main contains the commit.

---

### Task 3: Compile ledger requirements and persist start-time preflight identity

**Files:**
- Modify: `bin/plan/bet-ledger.py`
- Modify: `bin/agent-workflow.py`
- Modify: `projects/omo/src/omo/workflow/lifecycle.py`
- Test: `tests/test_agent_workflow.py`
- Test: `tests/test_spec_binding_lint.py`

**Interfaces:**
- Consumes: ledger `capability_requirements` and OMO/eCOS contracts.
- Produces: WorkPacket field, requirements digest, preflight inspection digests and immutable parent/child inheritance.

- [ ] **Step 1: Write RED compiler/start tests**

```python
def test_work_packet_compiles_exact_capability_requirements():
    bet = _bet()
    bet["capability_requirements"] = [
        {"capability_id": "skill:git-discipline", "operation": "load", "effect": "read_only"},
        {"capability_id": "workflow:bet-execution", "operation": "load", "effect": "read_only"},
    ]
    packet = bl._work_packet_from_bet(
        bet,
        {
            "spec_ref": "repo://docs/superpowers/specs/accepted.md",
            "spec_version": "1.0.0",
            "content_digest": "sha256:" + "a" * 64,
            "decision_ref": "decision://accepted/BET-TEST",
        },
        {
            "instruction_ref": "repo://docs/operations/blueprint-agent-instruction-pack-v1.md",
            "instruction_version": "blueprint-agent-instruction-pack/v1",
            "content_digest": "sha256:" + "b" * 64,
            "instruction_profile": "executor",
        },
    )
    requirements = packet["capability_requirements"]
    assert requirements == [
        {"capability_id": "skill:git-discipline", "operation": "load", "effect": "read_only"},
        {"capability_id": "workflow:bet-execution", "operation": "load", "effect": "read_only"},
    ]

def test_start_rejects_missing_capability_source_before_writing_run(
    _bet_workflow_workspace: Path,
    tmp_path: Path,
):
    workspace = tmp_path / "workspace"
    shutil.copytree(_bet_workflow_workspace, workspace, symlinks=True)
    ledger_path = workspace / "docs/plans/3y-bet-ledger.yaml"
    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    ledger["bets"][0]["capability_requirements"] = [
        {"capability_id": "skill:not-installed", "operation": "load", "effect": "read_only"}
    ]
    ledger_path.write_text(yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8")
    registry = _isolated_workflow_registry(tmp_path)
    result = _run_root_workflow_strict(
        "start",
        "bet-execution",
        "--registry",
        str(registry),
        "--profile",
        "governance-agent",
        "--bet",
        "BET-Y1Q3-T4-01",
        "--objective",
        "capability preflight",
        workspace=workspace,
    )
    assert result.returncode == 1
    assert "CAPABILITY_PREFLIGHT" in result.stderr
    assert list((tmp_path / "runs").glob("*.yaml")) == []
```

- [ ] **Step 2: Run RED tests**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_agent_workflow.py tests/test_spec_binding_lint.py -q
```

Expected: requirements are absent and no start preflight occurs.

- [ ] **Step 3: Add strict ledger compilation**

In `bet-ledger.py` add:

```python
CAPABILITY_OPERATIONS = {"find", "inspect", "load", "invoke"}
CAPABILITY_EFFECTS = {"read_only", "effectful"}
CAPABILITY_ID_RE = re.compile(
    r"^(?:skill|workflow|mcp-server|mcp-tool|bos-service):[A-Za-z0-9._:@/-]+$"
)

def validate_bet_capability_requirements(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list) or not value:
        raise SpecBindingContractError("CAPABILITY_REQUIREMENTS_REQUIRED")
    canonical: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != {"capability_id", "operation", "effect"}:
            raise SpecBindingContractError("CAPABILITY_REQUIREMENT_SHAPE")
        item = {key: str(raw[key]) for key in ("capability_id", "operation", "effect")}
        if (
            CAPABILITY_ID_RE.fullmatch(item["capability_id"]) is None
            or item["capability_id"] in seen
            or item["operation"] not in CAPABILITY_OPERATIONS
            or item["effect"] not in CAPABILITY_EFFECTS
            or (item["capability_id"].startswith("skill:") and item["operation"] == "invoke")
        ):
            raise SpecBindingContractError("CAPABILITY_REQUIREMENT_INVALID")
        seen.add(item["capability_id"])
        canonical.append(item)
    return canonical
```

Add a compatibility test asserting `validate_bet_capability_requirements(None) == []`; only BETs that declare the field enter exact-capability preflight during shadow rollout.

Refactor `_work_packet_from_bet` from a direct `return {` into `packet = {` followed by `return packet`, then compile the list:

```python
requirements = validate_bet_capability_requirements(bet.get("capability_requirements"))
packet["capability_requirements"] = requirements
return packet
```

In `prepare_bet_execution`, extend the existing returned mapping:

```python
requirements = packet.get("capability_requirements", [])
return {
    "spec_binding": binding,
    "instruction_binding": instruction_binding,
    "work_packet": packet,
    "work_packet_hash": packet_hash,
    "capability_requirements_digest": compute_packet_hash(canonicalize(requirements)),
}
```

- [ ] **Step 4: Add start preflight before locks/run files**

In lifecycle, derive a preflight-only binding after `run_id` is known:

```python
identity_path = registry_workspace_root(registry) / ".git" / "agent-clone-identity.json"
try:
    clone_identity = json.loads(identity_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    raise WorkflowError("CAPABILITY_PREFLIGHT_CLONE_IDENTITY_REQUIRED") from exc
if (
    clone_identity.get("schema") != "agent-clone-identity/v2"
    or clone_identity.get("ready") is not True
    or not isinstance(clone_identity.get("actor_id"), str)
    or not clone_identity["actor_id"]
    or not isinstance(clone_identity.get("delivery_attempt_id"), str)
    or not clone_identity["delivery_attempt_id"]
):
    raise WorkflowError("CAPABILITY_PREFLIGHT_CLONE_IDENTITY_INVALID")

preflight_binding = {
    "correlation_id": run_id,
    "workflow_run_id": run_id,
    "packet_id": delivery_identity["work_packet"]["packet_id"],
    "packet_hash": delivery_identity["work_packet_hash"],
    "assignment_id": f"preflight:{run_id}:assignment",
    "dispatch_id": f"preflight:{run_id}:dispatch",
    "actor_id": clone_identity["actor_id"],
    "delivery_attempt_id": clone_identity["delivery_attempt_id"],
}
```

Run exact find/inspect for every requirement and store only:

```python
record["capability_preflight"] = {
    "requirements_digest": delivery_identity["capability_requirements_digest"],
    "binding": preflight_binding,
    "receipts": [
        {
            "capability_id": requirement["capability_id"],
            "source_digest": receipt["source_digest"],
            "receipt_digest": receipt["receipt_digest"],
        }
        for requirement, receipt in inspected
    ],
    "invoked": False,
    "value_indicator_policy": False,
}
```

Do this before `acquire_locks`; any rejection leaves run/lock/ledger unchanged.

- [ ] **Step 5: Make parent/child and refresh preserve the identity**

Add `capability_requirements_digest` and `capability_preflight` to `_DELIVERY_IDENTITY_KEYS`; parent runs must match byte-for-byte. `refresh-packet` may update them only when the accepted source revision is merged and no capability source drift exists.

- [ ] **Step 6: Run GREEN tests and Python 3.9 grammar**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/test_agent_workflow.py tests/test_spec_binding_lint.py -q
python3 - <<'PY'
import ast
from pathlib import Path
for name in ("bin/plan/bet-ledger.py", "bin/agent-workflow.py"):
    ast.parse(Path(name).read_text(encoding="utf-8"), filename=name, feature_version=(3, 9))
PY
```

Expected: PASS.

- [ ] **Step 7: Commit/tag/root PR after eCOS and OMO consumer SHAs are reachable**

Commit: `feat(workflow): bind exact capabilities at start`.

Tag: `delivery/exact-capability-binding-root-start-20260824-v1`.

---

### Task 4: Complete exact discovery/load and activate native execution receipts

**Files:**
- Modify: `bin/ssot/gen-capability-registry.py`
- Modify: `docs/generated/capability-registry.yaml`
- Modify: `bin/capability-sync.py`
- Modify: `lib/capability_federation_audit.py`
- Modify: `lib/capability_trace_binding.py`
- Modify: `lib/capability_native_receipt.py`
- Modify: `lib/capability_native_inspection.py`
- Modify: `lib/capability_native_execution_model.py`
- Modify: `lib/capability_native_execution_receipt.py`
- Test: `tests/test_capability_sync.py`
- Test: `tests/test_capability_federation_audit.py`
- Test: `tests/test_capability_trace_binding.py`
- Test: `tests/test_capability_native_inspection.py`
- Test: `tests/test_capability_native_execution_receipt.py`

**Interfaces:**
- Consumes: full trace binding, inspection/admission inputs and the single generated projection.
- Produces: exact Skill/Workflow/MCP/BOS discovery, binding-required execution, marker and completed native receipt.

- [ ] **Step 1: Write RED generator/index tests for skills and workflows**

```python
def test_projection_and_index_include_skills_and_workflows(generator, cap_sync):
    registry = generator.build_registry()
    assert any(row["id"] == "git-discipline" for row in registry["skills"])
    assert any(row["id"] == "bet-execution" for row in registry["workflows"])
    index = cap_sync.build_capability_index(registry)
    assert index["skill:git-discipline"][0]["kind"] == "skill"
    assert index["workflow:bet-execution"][0]["kind"] == "workflow"
```

- [ ] **Step 2: Add scans to the existing writer**

```python
def _skill_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    payload = yaml.safe_load(text[4:end])
    return dict(payload) if isinstance(payload, dict) else {}

def scan_skills() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted((WORKSPACE / ".agents" / "skills").glob("*/SKILL.md")):
        frontmatter = _skill_frontmatter(path)
        skill_id = str(frontmatter.get("name") or "")
        if skill_id and path.parent.name == skill_id:
            rows.append({"id": skill_id, "file": path.relative_to(WORKSPACE).as_posix(), "exists": True})
    return rows

def scan_workflows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    directory = WORKSPACE / ".omo" / "_truth" / "registry" / "agent-workflows" / "workflows"
    for path in sorted(directory.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        workflow_id = str(payload.get("id") or "")
        if workflow_id and path.name == f"{workflow_id}.yaml":
            rows.append({"id": workflow_id, "file": path.relative_to(WORKSPACE).as_posix(), "exists": True})
    return rows
```

Add `skills` and `workflows` to the existing registry/totals and index; retain backward compatibility when old projections omit them.

- [ ] **Step 3: Extend pure kind semantics**

```python
CAPABILITY_SEMANTICS = {
    "skill": {"native_owner": "workspace_skills", "adapter_kind": "instruction_native"},
    "workflow": {"native_owner": "agent_workflow", "adapter_kind": "workflow_native"},
    "mcp_server": {"native_owner": "mcp", "adapter_kind": "mcp_native"},
    "mcp_tool": {"native_owner": "mcp", "adapter_kind": "mcp_native"},
    "bos_service": {"native_owner": "agora", "adapter_kind": "bos_native"},
    "cli_command": {"native_owner": "cockpit", "adapter_kind": "cockpit_native"},
    "legacy_capability": {"native_owner": "legacy_projection", "adapter_kind": "legacy_discovery_only"},
}
```

Keep Skill load-only and workflow invocation authorized only by `workflow-controller`.

- [ ] **Step 4: Write RED bound-execution and shadow-compatibility tests**

```python
@pytest.fixture
def bound_files(registry, tmp_path):
    from capability_native_receipt import build_native_inspection_receipt
    digest = lambda value: "sha256:" + value * 64
    binding = {
        "correlation_id": "corr-test",
        "workflow_run_id": "run-test",
        "packet_id": "WP-TEST",
        "packet_hash": digest("a"),
        "assignment_id": "assignment-test",
        "dispatch_id": "dispatch-test",
        "actor_id": "actor-test",
        "delivery_attempt_id": "attempt-test",
    }
    capability_id = "bos-service:bos://governance/omo/state"
    projected = copy.deepcopy(registry)
    projected["bos_services"]["domains"]["governance"][0]["uri"] = "bos://governance/omo/state"
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(yaml.safe_dump(projected, sort_keys=False), encoding="utf-8")
    binding_path = tmp_path / "binding.json"
    binding_path.write_text(json.dumps(binding), encoding="utf-8")
    inspection = build_native_inspection_receipt(
        capability_id=capability_id,
        binding=binding,
        proof={
            "source_ref": "projects/agora/etc/bos-services.yaml",
            "content": b"services: []\n",
            "source_schema": "agora-bos-services-yaml/v1",
            "proof": {"method": "canonical_bos_exact_uri", "strength": "strong"},
            "native_version": "1.0.0",
            "native_version_status": "proved",
        },
        upstream={
            "status": "verified",
            "schema": "capability-resolution-receipt/v1",
            "receipt_digest": digest("1"),
            "registry_digest": digest("2"),
        },
    )
    inspection_path = tmp_path / "inspection.json"
    inspection_path.write_text(json.dumps(inspection), encoding="utf-8")
    admission = {
        "receipt_digest": digest("4"),
        "admission_id": "admission-test",
        "step_run_id": "step-test",
        "worker": {"status": "not_applicable", "id": None},
    }
    admission_path = tmp_path / "admission.json"
    admission_path.write_text(json.dumps(admission), encoding="utf-8")
    input_path = tmp_path / "input.json"
    input_path.write_text("{}\n", encoding="utf-8")
    return SimpleNamespace(
        binding=binding,
        invoke_argv=[
            "invoke", "--id", capability_id,
            "--input-json", str(input_path),
            "--registry", str(registry_path),
            "--binding-json", str(binding_path),
            "--inspection-receipt-json", str(inspection_path),
            "--admission-receipt-json", str(admission_path),
            "--operation-id", "omo.state",
            "--effect-classification", "read_only",
        ],
    )

def test_bound_invoke_emits_native_execution_receipt(
    cap_sync, bound_files, monkeypatch, capsys
):
    monkeypatch.setattr(
        cap_sync,
        "execute_gateway_operation",
        lambda *args, **kwargs: {"schema": "capability-invocation-receipt/v1", "status": "succeeded"},
    )
    rc = cap_sync.main(bound_files.invoke_argv)
    receipt = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert receipt["schema"] == "native-execution-receipt/v1"
    assert receipt["material"]["binding"] == bound_files.binding
    assert receipt["value_indicator_policy"] is False

def test_unbound_invoke_is_shadow_observed_before_fail_promotion(
    cap_sync, monkeypatch, registry, tmp_path, capsys
):
    registry_file = tmp_path / "registry.yaml"
    registry_file.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    input_file = tmp_path / "input.json"
    input_file.write_text("{}\n", encoding="utf-8")
    calls = 0
    def legacy_gateway(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {"schema": "capability-invocation-receipt/v1", "status": "succeeded"}
    monkeypatch.setattr(cap_sync, "execute_gateway_operation", legacy_gateway)
    rc = cap_sync.main([
        "invoke", "--id", "bos-service:bos://governance/shared",
        "--input-json", str(input_file), "--registry", str(registry_file),
    ])
    receipt = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert calls == 1
    assert receipt["binding_enforcement"] == "shadow_missing"
```

- [ ] **Step 5: Accept a complete binding bundle and shadow-observe legacy calls**

Add the binding bundle as optional parser inputs in this first rollout PR. Partial bundles fail closed; a fully absent bundle follows the old gateway path and adds `binding_enforcement=shadow_missing` to the CLI projection without claiming a native receipt.

```python
BINDING_ENFORCEMENT = "shadow"

for target in (load_parser, invoke_parser):
    target.add_argument("--binding-json", type=Path)
    target.add_argument("--inspection-receipt-json", type=Path)
    target.add_argument("--admission-receipt-json", type=Path)
    target.add_argument("--operation-id")
    target.add_argument("--effect-classification", choices=("read_only", "effectful"))

bundle = (
    args.binding_json,
    args.inspection_receipt_json,
    args.admission_receipt_json,
    args.operation_id,
    args.effect_classification,
)
if any(value is not None for value in bundle) and not all(value is not None for value in bundle):
    raise GatewayError("binding_bundle_incomplete")

if not any(value is not None for value in bundle):
    if BINDING_ENFORCEMENT == "fail":
        receipt = _gateway_error_receipt(args.command, selector, "binding_required")
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 5
    receipt = execute_gateway_operation(
        registry,
        args.command,
        args.capability_id,
        payload=payload,
    )
    receipt["binding_enforcement"] = f"{BINDING_ENFORCEMENT}_missing"
    if BINDING_ENFORCEMENT == "warning":
        print("capability binding is required for new callers", file=sys.stderr)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt.get("status") in {"ready", "succeeded"} else 5
```

Before loading the registry or gateway, parse and validate all three receipts. Build material with:

```python
from capability_native_execution_model import AUTHORIZATION_BY_KIND, canonical_digest
from capability_native_execution_receipt import (
    build_native_execution_material,
    build_native_execution_marker,
    build_native_execution_receipt,
    classify_native_execution_replay,
)

material = build_native_execution_material(
    binding=binding,
    capability=inspection["capability"],
    inspection={
        "receipt_digest": inspection["receipt_digest"],
        "source_digest": inspection["source_digest"],
    },
    operation_id=args.operation_id,
    request_digest=canonical_digest(payload),
    admission=admission,
    authorization_source=AUTHORIZATION_BY_KIND[inspection["capability"]["kind"]],
    effect_classification=args.effect_classification,
    execution_attempt=1,
)
```

Persist a marker through the existing caller-owned receipt path before `execute_gateway_operation`. After the gateway returns, compute a redacted result digest, build cleanup proof from exact before/after measurements, and return `native-execution-receipt/v1`. When the entire bundle is absent, emit the shadow marker on the legacy CLI receipt and print one structured warning to stderr; never label that response native or independently verified.

- [ ] **Step 6: Run root capability GREEN tests and regenerate projection**

```bash
python3 bin/ssot/gen-capability-registry.py
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_capability_sync.py \
  tests/test_capability_federation_audit.py \
  tests/test_capability_trace_binding.py \
  tests/test_capability_native_inspection.py \
  tests/test_capability_native_execution_receipt.py -q
python3 bin/ssot/gen-capability-registry.py --check --quiet
```

Expected: PASS; generated projection is the only generated file.

- [ ] **Step 7: Commit/tag/root PR**

Commit: `feat(capability): emit bound native receipts in shadow mode`.

Tag: `delivery/exact-capability-binding-root-native-20260824-v1`.

---

### Task 5: Recheck persisted admission before OMO dispatch and delete dead legacy grant

**Files:**
- Modify: `projects/omo/src/omo/worker_lifecycle.py`
- Modify: `projects/omo/src/omo/workflow_mesh.py`
- Modify: `projects/omo/src/omo/omo_worker_dispatch.py`
- Modify: `projects/omo/src/omo/workflow_dispatch.py`
- Modify: `projects/omo/src/omo/omo_worker_core.py`
- Test: `projects/omo/tests/test_omo_worker_admission_gate.py`
- Test: `projects/omo/tests/test_worker_lifecycle_mesh.py`
- Test: `projects/omo/tests/test_workflow_mesh.py`

**Interfaces:**
- Consumes: persisted WorkflowAdmitted payload and exact WorkPacket requirements.
- Produces: StepDispatched only from the same admitted run/grant/policy digest.

- [ ] **Step 1: Write RED zero-side-effect forgery tests**

```python
INSTRUCTION_BINDING = {
    "instruction_ref": "repo://docs/operations/blueprint-agent-instruction-pack-v1.md",
    "instruction_version": "blueprint-agent-instruction-pack/v1",
    "content_digest": "sha256:" + "c" * 64,
    "instruction_profile": "executor",
}

def test_step_dispatch_rejects_forged_admission_without_writing(tmp_path):
    omo_dir = tmp_path / ".omo"
    before = _file_snapshot(omo_dir)
    with pytest.raises(WorkerLifecycleError, match="admission binding mismatch"):
        record_step_dispatch(
            omo_dir,
            workflow_run_id="run-forged",
            trace_id="trace-forged",
            dispatch_id="dispatch-forged",
            worker_id="worker-1",
            step_run_id="step-1",
            admission_id="admission-forged",
            policy_digest="sha256:" + "a" * 64,
            packet_id="WP-FORGED",
            packet_hash="sha256:" + "b" * 64,
            instruction_binding=INSTRUCTION_BINDING,
        )
    assert _file_snapshot(omo_dir) == before
```

- [ ] **Step 2: Run RED tests**

```bash
cd projects/omo
uv run pytest tests/test_omo_worker_admission_gate.py tests/test_worker_lifecycle_mesh.py tests/test_workflow_mesh.py -q
```

Expected: forged grant reaches StepDispatched or the signature lacks `policy_digest`.

- [ ] **Step 3: Add persisted admission recheck**

Before creating a StepDispatched payload:

```python
snapshot = store.snapshot(workflow_run_id)
admission = snapshot.get("admission")
request_identity = admission.get("request_identity") if isinstance(admission, Mapping) else None
if (
    snapshot.get("state") != "admitted"
    or not isinstance(admission, Mapping)
    or not isinstance(request_identity, Mapping)
    or admission.get("admission_id") != admission_id
    or admission.get("policy_digest") != policy_digest
    or request_identity.get("packet_id") != packet_id
    or request_identity.get("packet_hash") != packet_hash
):
    raise WorkerLifecycleError("admission binding mismatch")
```

Persist `policy_digest` in StepDispatched and make Workflow Mesh reject `planned -> dispatched`; only `admitted -> dispatched` is legal.

- [ ] **Step 4: Delete the unreachable legacy empty-capability grant**

Remove the branch that creates `required_capabilities: []` when `workflow_packet is None`. Keep the existing early error:

```python
if workflow_packet is None:
    raise ValueError("unbound legacy dispatch is observer-only and cannot create worker state")
```

- [ ] **Step 5: Run OMO GREEN and full focused regression**

```bash
cd projects/omo
uv run pytest tests/test_omo_worker_admission_gate.py tests/test_worker_lifecycle_mesh.py tests/test_workflow_mesh.py tests/test_blueprint_control.py -q
uv run ruff check src/omo/worker_lifecycle.py src/omo/workflow_mesh.py src/omo/omo_worker_dispatch.py src/omo/workflow_dispatch.py src/omo/omo_worker_core.py
```

Expected: PASS; six negative cases preserve file snapshots.

- [ ] **Step 6: Commit/tag/merge OMO integrity PR**

Commit: `fix(omo): bind dispatch to persisted admission`.

Tag: `delivery/exact-capability-binding-omo-integrity-20260824-v1`.

---

### Task 6B: Verify persisted admission and gate every Cockpit effect path

**Files:**
- Modify: `bin/capability-sync.py`
- Modify: `tests/test_capability_sync.py`
- Modify: `projects/cockpit/src/cockpit/_subcommands.py`
- Modify: `projects/cockpit/src/cockpit/commands/bos.py`
- Modify: `projects/cockpit/src/cockpit/web/api_kems.py`
- Modify: `projects/cockpit/src/cockpit/agent_runtime_server.py`
- Modify: `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py`
- Create: `projects/cockpit/src/cockpit/adapters/capability_binding.py`
- Create: `projects/cockpit/src/cockpit/tests/test_capability_binding_adapter.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_bos_capability_invoke.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_api_kems_retired.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_agent_runtime_server.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_agent_runtime_mcp_server.py`
- Modify: `projects/cockpit/tests/test_api_kems_dispatch.py`

**Interfaces:**
- Consumes: bounded `capability-admission-verification-request/v1`, frozen `native-execution-material/v1`,
  and the existing OMO Workflow Mesh event log.
- Produces: one redacted `capability-admission-verification-receipt/v1`; no alternative identity, marker,
  cache or execution state. Cockpit only consumes the verdict through fixed argv/stdin.

- [ ] **Step 1: Write root RED verifier tests**

```python
def test_verify_material_rejects_cross_run_before_any_outbound_call(mesh, material, request, counters):
    material["binding"]["workflow_run_id"] = "other-run"
    receipt = verify_material_against_mesh(mesh.omo_dir, envelope(material, request))
    assert receipt["status"] == "rejected"
    assert receipt["failure_code"] == "admission_binding_mismatch"
    assert counters == {"provider": 0, "router": 0, "gateway": 0, "subprocess": 0}
```

- [ ] **Step 2: Implement root `verify-material` as a bounded read-only projection**

The CLI reads one envelope from stdin and calls the existing material validator. It recomputes the request digest,
checks expected capability/operation/effect, reads `WorkflowMeshStore.snapshot(workflow_run_id)`, and compares:

- admission id and `"sha256:" + admission.proof` to the material admission projection;
- packet id/hash to the trace binding and persisted request identity;
- admitted StepRun plus exact dispatch/worker/step/admission/packet context for effectful calls;
- live state and admission expiry.

It emits only a redacted verdict. It does not accept a caller-controlled OMO path, write a marker, or call a provider,
router, gateway or nested subprocess.

- [ ] **Step 3: Run root GREEN and no-write regression**

```bash
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_capability_sync.py tests/test_capability_native_execution_receipt.py -q
uv run --with ruff ruff check bin/capability-sync.py tests/test_capability_sync.py
```

Expected: valid dispatched/running bindings verify; missing, malformed, cross-run, wrong proof/digest, expired,
wrong capability/operation/effect/request and worker mismatch reject with stable codes and zero outbound/write calls.

- [ ] **Step 4: Write Cockpit RED adapter and entrypoint tests**

Cover these contracts before implementation:

1. canonical BOS parser exposes and forwards all five existing bundle flags;
2. adapter argv is fixed to root `bin/capability-sync.py verify-material`, uses stdin, `shell=False`, bounded timeout,
   and rejects non-verified/malformed output;
3. HTTP `/run-task` and chat-with-tools, MCP `run_task` and MCP `chat` reject seven invalid classes before
   `get_runtime()`, tool-schema construction or tool execution;
4. verifier unavailable is fail-closed; unbound chat returns `authority_state=non_authoritative` with no tools;
5. PoisonRequest/ASGI receive proves KEMS 410 never reads the body.

- [ ] **Step 5: Implement one shared Cockpit adapter and gate every effect path**

`agent_runtime_server.py` and `agent_runtime_mcp_server.py` import only the shared adapter. They do not import root
pure libraries or duplicate structural rules. MCP `chat` gains the binding input and both MCP tools gate before
runtime construction. KEMS moves the fixed 410 above `request.json()`. `_subcommands.py` owns the five BOS flags;
`commands/bos.py` keeps the existing forwarding implementation.

- [ ] **Step 6: Run Cockpit GREEN and focused regression**

```bash
cd projects/cockpit
uv run pytest \
  src/cockpit/tests/test_capability_binding_adapter.py \
  src/cockpit/tests/test_bos_capability_invoke.py \
  src/cockpit/tests/test_api_kems_retired.py \
  src/cockpit/tests/test_agent_runtime_server.py \
  src/cockpit/tests/test_agent_runtime_mcp_server.py \
  tests/test_api_kems_dispatch.py -q
uv run ruff check \
  src/cockpit/_subcommands.py src/cockpit/commands/bos.py \
  src/cockpit/adapters/capability_binding.py src/cockpit/web/api_kems.py \
  src/cockpit/agent_runtime_server.py src/cockpit/agent_runtime_mcp_server.py
```

- [ ] **Step 7: Deliver root first, then Cockpit child, then root gitlink**

1. Root verifier: commit/tag/PR/CI/merge without changing any gitlink.
2. Fresh Cockpit clone from child `origin/main` (`a271a0d` or descendant): commit/tag/PR/CI/merge.
3. Fresh root follow-up advances `projects/cockpit` only to a child-main descendant containing Task 6B.

Tags:

- `delivery/exact-capability-binding-root-verifier-20260826-v1`
- `delivery/exact-capability-binding-cockpit-gate-20260826-v1`
- `delivery/exact-capability-binding-root-pointer-20260826-v1`

Stop before implementation if reading persisted admission requires an OMO write/service change, any local validator copy,
new daemon/port/cache, caller-controlled authority path, or a negative case cannot prove zero runtime/tool/provider calls.

---

### Task 7: Root integration, production-topology canary, documentation and lifecycle closeout

**Files:**
- Modify: `docs/architecture/capability-federation-contract-v1.md`
- Modify: `docs/architecture/blueprint-multi-agent-execution-control-v1.md`
- Modify: `docs/architecture/digital-twin-blueprint-v1.md`
- Modify: `docs/operations/blueprint-agent-instruction-pack-v1.md`
- Modify: `docs/project-registry.yaml`
- Modify: `.omo/_knowledge/retros/BET-Y1Q3-T1-12.md`
- Update gitlinks: `projects/ecos`, `projects/omo`, `projects/agora`, `projects/cockpit`

**Interfaces:**
- Consumes: every merged child SHA and root capability implementation.
- Produces: one root main integration, canary receipt, periodic delta report and honest completion matrix.

- [ ] **Step 1: Verify each child SHA before changing gitlinks**

Fetch the exact source tags and current child main refs, then prove each tagged delivery is contained by the selected main SHA:

```bash
git -C projects/ecos fetch origin main refs/tags/delivery/exact-capability-binding-ecos-20260824-v1
ECOS_SOURCE_SHA="$(git -C projects/ecos rev-parse refs/tags/delivery/exact-capability-binding-ecos-20260824-v1^{})"
ECOS_MERGE_SHA="$(git -C projects/ecos rev-parse origin/main)"
git -C projects/ecos merge-base --is-ancestor "$ECOS_SOURCE_SHA" "$ECOS_MERGE_SHA"

git -C projects/omo fetch origin main refs/tags/delivery/exact-capability-binding-omo-consumer-20260824-v1 refs/tags/delivery/exact-capability-binding-omo-integrity-20260824-v1
OMO_CONSUMER_SOURCE_SHA="$(git -C projects/omo rev-parse refs/tags/delivery/exact-capability-binding-omo-consumer-20260824-v1^{})"
OMO_INTEGRITY_SOURCE_SHA="$(git -C projects/omo rev-parse refs/tags/delivery/exact-capability-binding-omo-integrity-20260824-v1^{})"
OMO_MERGE_SHA="$(git -C projects/omo rev-parse origin/main)"
git -C projects/omo merge-base --is-ancestor "$OMO_CONSUMER_SOURCE_SHA" "$OMO_MERGE_SHA"
git -C projects/omo merge-base --is-ancestor "$OMO_INTEGRITY_SOURCE_SHA" "$OMO_MERGE_SHA"

git -C projects/cockpit fetch origin main refs/tags/delivery/exact-capability-binding-cockpit-20260824-v1
COCKPIT_SOURCE_SHA="$(git -C projects/cockpit rev-parse refs/tags/delivery/exact-capability-binding-cockpit-20260824-v1^{})"
COCKPIT_MERGE_SHA="$(git -C projects/cockpit rev-parse origin/main)"
git -C projects/cockpit merge-base --is-ancestor "$COCKPIT_SOURCE_SHA" "$COCKPIT_MERGE_SHA"
```

Prove Agora the same way:

```bash
git -C projects/agora fetch origin main refs/tags/delivery/exact-capability-binding-agora-20260824-v1
AGORA_SOURCE_SHA="$(git -C projects/agora rev-parse refs/tags/delivery/exact-capability-binding-agora-20260824-v1^{})"
AGORA_MERGE_SHA="$(git -C projects/agora rev-parse origin/main)"
git -C projects/agora merge-base --is-ancestor "$AGORA_SOURCE_SHA" "$AGORA_MERGE_SHA"
```

Every ancestry command must exit 0 before the root pointer moves.

- [ ] **Step 2: Update root pointers with the registered transaction path**

Use `bin/gac/clone-lifecycle.py integrate` or the root submodule pointer transaction; do not checkout child branches in the root clone. Verify `git diff --submodule=log` contains only forward descendants.

- [ ] **Step 3: Run the production-topology canary**

The canary uses these exact requirements:

```json
[
  {"capability_id":"skill:git-discipline","operation":"load","effect":"read_only"},
  {"capability_id":"workflow:bet-execution","operation":"load","effect":"read_only"},
  {"capability_id":"mcp-server:agora","operation":"load","effect":"read_only"},
  {"capability_id":"bos-service:bos://governance/omo/state","operation":"invoke","effect":"read_only"}
]
```

Required positive evidence: one accepted Spec/WorkPacket start, one admitted dispatch, one confirmed read-only native receipt, one replay that performs zero new invocation, and one cleanup proof.

Required negative evidence: missing binding, wrong packet hash, ambiguous selector, wrong admission, source digest drift, and uncertain transport all return non-zero/blocked with provider invocation count 0.

- [ ] **Step 4: Promote binding enforcement from shadow to warning to fail**

Use the existing `BINDING_ENFORCEMENT` constant; do not add runtime configuration or a caller-controlled bypass.

1. Merge the Task 4 shadow PR and observe two consecutive PR-context/main scans. Record every `shadow_missing` caller by entrypoint; do not infer zero from tests alone.
2. If the list is empty or every caller has a named migration PR, change the constant to `warning`, rerun the same scans twice, and keep legacy execution only during that warning window.
3. When both warning scans show zero unbound production callers, change the constant to `fail` and add this final zero-call test:

```python
def test_fail_mode_rejects_missing_binding_before_gateway(
    cap_sync, monkeypatch, registry_file, input_file, capsys
):
    monkeypatch.setattr(cap_sync, "BINDING_ENFORCEMENT", "fail")
    calls = 0
    def forbidden_gateway(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("gateway must not be called")
    monkeypatch.setattr(cap_sync, "execute_gateway_operation", forbidden_gateway)
    rc = cap_sync.main([
        "invoke", "--id", "bos-service:bos://governance/omo/state",
        "--input-json", str(input_file), "--registry", str(registry_file),
    ])
    assert rc == 5
    assert calls == 0
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"
```

Each promotion is its own root commit and PR-context evidence point. Do not jump directly from shadow to fail.

- [ ] **Step 5: Run full scoped verification**

```bash
ACTIVE_RUN_ID="$(uv run --with pyyaml python bin/agent-workflow.py status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["current_run_id"])')"
test -n "$ACTIVE_RUN_ID"
uv run --with pyyaml --with pytest python -m pytest \
  tests/test_capability_sync.py \
  tests/test_capability_trace_binding.py \
  tests/test_capability_native_inspection.py \
  tests/test_capability_native_execution_receipt.py \
  tests/test_agent_workflow.py \
  tests/test_spec_binding_lint.py -q
uv run --with pyyaml python bin/agent-workflow.py verify "$ACTIVE_RUN_ID" --from-diff --execute
make gac-local-gate
make ssot-guardian
python3 bin/ssot/post-commit-sync-check.py
```

Expected: targeted tests PASS. Any unrelated main baseline red is separated with a fingerprint and platform CI remains authoritative; no admin merge.

- [ ] **Step 6: Rerun periodic strategic correction**

Audit all main commits and open PRs since the previous checkpoint. Explicitly confirm:

- maturity/readiness scores did not enter value truth;
- no automatic verdict/time estimate path merged;
- AGE-v2 Agent Cell either uses the same gate or remains deferred;
- there is still one capability writer and one dispatch truth.

Append results to the two current Documents handoff/strategy files.

- [ ] **Step 7: Write the five-question retro and honest completion matrix**

The retro must include actual elapsed time, every failed or unproven done_when, scope changes discovered during planning, exact surface delta, and the next owner guidance. Do not set value to ACCEPTED from engineering evidence; keep value NOT_PROVEN until the later Golden Slice.

- [ ] **Step 8: Root commit/tag/PR/merge and lifecycle retirement**

Root source tag: `delivery/exact-capability-binding-root-integration-20260824-v1`.

## 2026-08-29 fail-closed enforcement slice

The existing warning fallback was promoted to `BINDING_ENFORCEMENT="fail"`.
When a native `load` or `invoke` caller omits the complete binding bundle, the
CLI now returns exit `4` before registry/gateway/provider execution and emits a
redacted `capability-resolution-receipt/v1` with all invocation/evidence/
verification states false. The regression and live CLI canary both prove the
zero-call invariant. The production OMO consumer now accepts only confirmed,
successful `native-execution-receipt/v1` envelopes, binds workflow/step
identity, and projects digest-only evidence through the existing receipt broker
(merged child PR #109 and root PR #2493). Positive topology canary and
principal-bound value remain separate open T1-12 requirements.

Wait for every required PR-context check. Merge by standard squash only. Retire every writer clone through `clone-lifecycle retire`; use `--platform-rebased-pr` whenever GitHub update-branch changed the PR head. Preserve every JSON retirement receipt.

---

### Task 8: Phase8 root recovery — retire root wrapper bypass commands (scope amendment 1.1.1)

Bounded TDD task implementing Spec §2.3 / §5.5.5 / Wave E. It only retires the root-side
Phase8 bypass surface; it must not re-implement any retired child entrypoint, must not
add new capability surfaces, and must not touch files owned by other BETs.

**Files:**
- ~~Modify: `bin/omostation`~~ — retired in PR #2260 / ADR-0428; root wrapper bypass commands removed.
- Modify: `bin/gac/daemon-watchdog.py`
- Modify: `bin/ssot/real-scenario-runner.py`
- Modify: `bin/_registry/scripts/governance/daemon-watchdog.yaml`
- Modify: `bin/_registry/scripts/governance/real-scenario-runner.yaml`
- Test: `tests/unit/test_phase8_unified_ecosystem.py`
- Modify: `docs/CLI-REFERENCE.md`
- Modify: `docs/INDEX-MCP.md`
- Modify: `docs/generated/capability-registry.yaml`

**Status:**
- `bin/omostation` retirement completed in PR #2260. All five bypass commands (`daemon` / `watchdog` / `scenario` / `top` / arbitrary `run`) are removed. The unified human entrypoint is now `cockpit` only. See ADR-0428 for the decision record.

**Interfaces:**
- Consumes: merged Cockpit PR #78 (source `43dbf115`, child main merge `82dddbc9`) entrypoint retirement; existing value-firewall and no-write test patterns.
- Produces: compatibility-only root wrapper with `daemon`/`watchdog`/`scenario`/`top`/arbitrary `run` — five retired bypass commands — until Mesh-bound; the two `maturity: draft` registry entries transitioned to schema-valid `maturity: deprecated` while the execution surfaces are retired; synchronized docs and capability projection.

- [ ] **Step 1: Write RED negative no-write / value-firewall tests**

Extend `tests/unit/test_phase8_unified_ecosystem.py` (do not remove the existing
resolver/scenario unit tests) with retired-command coverage:

```python
import builtins
import importlib
import json
import runpy
import subprocess

def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.parts
    }

RETIRED_COMMANDS = ["daemon", "watchdog", "scenario", "top"]
FORBIDDEN_VALUE_KEYS = {
    "human_verdict",
    "human_verdict_id",
    "decision_outcome",
    "decision_outcome_id",
    "personal_value",
    "value_indicator",
}

omostation_globals = runpy.run_path(
    str(WORKSPACE / "bin" / "omostation"), run_name="omostation_test"
)
omostation_main = omostation_globals["main"]
daemon_watchdog = _load_module_from_file(
    "daemon_watchdog", WORKSPACE / "bin" / "gac" / "daemon-watchdog.py"
)
real_scenario_runner = _load_module_from_file(
    "real_scenario_runner", WORKSPACE / "bin" / "ssot" / "real-scenario-runner.py"
)

def _sentinel(name: str):
    def _raise(*_args, **_kwargs):
        raise AssertionError(f"retired refusal called forbidden {name}")
    return _raise

def _refusal_payload(message: str) -> dict:
    for line in reversed(message.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {"message": message}

def _assert_refusal_firewall(message: str) -> None:
    assert "retired" in message.lower()
    payload = _refusal_payload(message)
    assert FORBIDDEN_VALUE_KEYS.isdisjoint(payload)
    assert payload.get("value_indicator_policy") in (None, False)

def _guard_effects(monkeypatch) -> None:
    monkeypatch.setattr(runpy, "run_path", _sentinel("runpy.run_path"))
    monkeypatch.setattr(runpy, "run_module", _sentinel("runpy.run_module"))
    monkeypatch.setattr(subprocess, "run", _sentinel("subprocess.run"))
    monkeypatch.setattr(importlib, "import_module", _sentinel("importlib.import_module"))
    for module, names in (
        (daemon_watchdog, ("run_watchdog", "check_daemon_health", "restart_daemon", "log_event")),
        (real_scenario_runner, ("run_all_scenarios", "publish_to_bus", "record_resident_decision")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, _sentinel(f"{module.__name__}.{name}"))
    original_import = builtins.__import__
    def _project_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"agora", "cockpit", "ecos", "omo"}:
            raise AssertionError(f"retired refusal imported project module {name}")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", _project_import)

def test_retired_bypass_commands_exit_nonzero_with_zero_writes(tmp_path, monkeypatch, capsys):
    before = _snapshot(tmp_path)
    monkeypatch.setitem(omostation_globals, "_ROOT", tmp_path)
    monkeypatch.setattr(daemon_watchdog, "_ROOT", tmp_path)
    monkeypatch.setattr(real_scenario_runner, "_ROOT", tmp_path)
    _guard_effects(monkeypatch)

    for cmd in RETIRED_COMMANDS + ["run"]:
        argv = ["omostation", cmd] + (["some.module"] if cmd == "run" else [])
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exc:
            omostation_main()
        assert exc.value.code != 0
        out = capsys.readouterr()
        _assert_refusal_firewall(out.out + out.err)
    assert _snapshot(tmp_path) == before  # no-write: isolated tmp workspace is unchanged

def test_retired_governance_scripts_refuse_before_effects(tmp_path, monkeypatch, capsys):
    before = _snapshot(tmp_path)
    for module, argv in (
        (daemon_watchdog, ["daemon-watchdog", "--json"]),
        (real_scenario_runner, ["real-scenario-runner", "--dir", str(tmp_path)]),
    ):
        monkeypatch.setattr(module, "_ROOT", tmp_path)
        _guard_effects(monkeypatch)
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exc:
            module.main()
        assert exc.value.code != 0
        out = capsys.readouterr()
        _assert_refusal_firewall(out.out + out.err)
    assert _snapshot(tmp_path) == before
```

Every retired command must: exit non-zero, print a retirement notice naming the
Mesh-bound successor path, leave the isolated `tmp_path` byte-identical, perform
zero project-specific imports, subprocess/provider/router/gateway calls, or file
writes, and emit no human verdict, decision outcome, or personal value field;
side-effect-free stdlib/`env_resolver` setup is allowed before refusal.

- [ ] **Step 2: Make `bin/omostation` compatibility-only (GREEN)**

Remove the `daemon`, `watchdog`, `scenario`, `top`, and arbitrary `run <module>`
dispatch branches (including the ghost imports `cockpit.commands.daemon.daemon_cli`
and `cockpit.tui.swarm_dashboard` — the latter never existed on child main, so
`top` is retired with the other four bypass commands, not kept in transit). Keep
status/policy/resident/distill/gate transit only where the target still exists
on child main. Retired commands hit a shared refusal helper that may perform only
side-effect-free stdlib/`env_resolver` setup and exits before project-specific
imports, subprocess/provider/router/gateway calls, or file writes.

- [ ] **Step 3: Retire the two governance scripts and their registry entries**

Neutralize the unbound execution surfaces in `bin/gac/daemon-watchdog.py`
(`restart_daemon()` ghost import of `cockpit.commands.daemon.restart_daemon_service`)
and `bin/ssot/real-scenario-runner.py` (direct A2A bus publish + resident decision
write without WorkPacket/admission): refuse with a non-zero, no-write exit until
Mesh-bound, before project-specific imports, subprocess/provider/router/gateway calls,
or file writes; side-effect-free stdlib/`env_resolver` setup may occur. Flip both
`bin/_registry/scripts/governance/*.yaml` entries from `maturity: draft` to
schema-valid `maturity: deprecated` (the execution surface is retired), with a
retirement note referencing Spec §5.5.5 and PR #78, keeping the files append-only
honest history.

- [ ] **Step 4: Enforce child main → root pointer → projection ordering**

Before touching any root file, prove ordering per Spec Wave E:

```bash
git -C projects/cockpit fetch --no-tags origin main
test "$(git -C projects/cockpit rev-parse FETCH_HEAD)" = "82dddbc926cc4377808fe530bf135f08213cd213"
git -C projects/cockpit merge-base --is-ancestor 43dbf115db0fece980d3ffe2d8339e4fbc1b5b59 FETCH_HEAD
```

All three commands must exit 0 before moving the root gitlink, and only then
regenerate `docs/generated/capability-registry.yaml`.
Never regenerate the projection while the wrapper still exposes retired commands.

- [ ] **Step 5: Sync docs projection**

Update `docs/CLI-REFERENCE.md` and `docs/INDEX-MCP.md` so the retired commands are
gone from the available-surface listing (or explicitly marked retired with the
Mesh-bound successor reference); regenerate the capability projection in the same
commit so registry, docs, and wrapper agree.

- [ ] **Step 6: Separate governed post-merge ops follow-up**

This is not a Task8 repo write or Task8 code-PR completion prerequisite. The separate
governed post-merge ops follow-up targets the exact service
`com.omostation.agora.daemon` and plist
`~/Library/LaunchAgents/com.omostation.agora.daemon.plist`; it must first collect
read-only evidence:

```bash
launchctl list com.omostation.agora.daemon
lsof -nP -iTCP:7432 -sTCP:LISTEN
```

Do not execute `launchctl unload`/`bootout`, `rm`, `kill`, or any other mutation in
Task8. Until that separate follow-up is actually executed, operational cleanup
remains pending; never clean up host services while a half-retired binary can still
self-resurrect.

- [ ] **Step 7: Run GREEN tests and deliver**

```bash
uv run --with pyyaml --with pytest python -m pytest tests/unit/test_phase8_unified_ecosystem.py -q
python3 bin/ssot/gen-capability-registry.py --check --quiet
```

Commit: `fix(phase8): retire root wrapper bypass commands`.

Tag: `delivery/t1-12-phase8-root-scope-20260825-v3`.

## 2026-08-29 MetaOS admission-provider packaging follow-up

The positive native canary reached Agora but could not load the MetaOS
admission provider because building `projects/metaos` failed with a duplicate
Hatch wheel entry: `packages = ["src/metaos"]` already includes `metaos/config`,
while `force-include` added the same destination again. The fix is intentionally
scoped to removing that packaging collision from the T1-12 write surface;
provider installation and the positive canary remain pending until the child
package build and admission path are reverified.
