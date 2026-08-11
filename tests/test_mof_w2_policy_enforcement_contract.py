"""Focused contract tests for the PolicyDecision + ActionReceipt M2 pair (W2-03, BET-Y1Q2-T1-06).

Covers: model-truth semantics (required fields / enums / patterns / state
machine / owner / migration policy), invalid examples, deterministic
generation (byte-identical repeated output), missing / tampered / drift
detection via the compiler's check mode, and validation against the
generated Pydantic ``PolicyDecision`` and ``ActionReceipt`` models shared by
OMO (PDP/LedgerBroker) and Agora (PEP).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from ecos.ssot.mof.compiler import (
    ARTIFACT_CLASSES,
    MofCompiler,
)

M2_DIR = Path(__file__).resolve().parents[1] / "src/ecos/ssot/mof/m2"
GENERATED_CONTROL_DIR = M2_DIR.parent / "generated" / "control"

DECISION_MODEL_NAME = "PolicyDecision"
RECEIPT_MODEL_NAME = "ActionReceipt"

# Stable reason vocabulary fixed by BET-Y1Q2-T1-06 done_when (at least these
# five; "allowed" is the success-path counterpart so no broad exception maps
# to allow/succeeded).
STABLE_REASONS = (
    "policy_denied",
    "pdp_unavailable",
    "ledger_unavailable",
    "provider_failed",
    "receipt_unconfirmed",
)
REASON_VOCABULARY = ("allowed",) + STABLE_REASONS

SERVER_RISKS = ("R0", "R1", "R2", "R3")

# Required fields fixed by the BET done_when strict decision-context binding.
POLICY_DECISION_REQUIRED_FIELDS = {
    "decision_id",
    "schema_version",
    "decision",
    "action_id",
    "principal_id",
    "executor_id",
    "episode_id",
    "mandate_id",
    "mandate_version",
    "capability",
    "server_risk",
    "budget_limit",
    "budget_unit",
    "disclosure",
    "request_hash",
    "trace_id",
    "issued_at",
    "expires_at",
    "reason",
}

ACTION_RECEIPT_REQUIRED_FIELDS = {
    "receipt_id",
    "schema_version",
    "decision_id",
    "action_id",
    "principal_id",
    "executor_id",
    "episode_id",
    "mandate_id",
    "mandate_version",
    "capability",
    "server_risk",
    "budget_limit",
    "budget_unit",
    "disclosure",
    "request_hash",
    "trace_id",
    "issued_at",
    "expires_at",
    "status",
    "started_at",
}


@pytest.fixture(scope="module")
def policy_decision_yaml() -> dict:
    path = M2_DIR / "policy_decision.yaml"
    assert path.is_file(), f"missing M2 truth: {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def action_receipt_yaml() -> dict:
    path = M2_DIR / "action_receipt.yaml"
    assert path.is_file(), f"missing M2 truth: {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture()
def compiler() -> MofCompiler:
    return MofCompiler(m2_dir=M2_DIR)


def _import_generated_models(models_path: Path):
    """Import the generated Pydantic models module from a directory."""
    spec = importlib.util.spec_from_file_location(
        "mof_control_models_under_test", models_path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def generated_models(tmp_path: Path):
    """Compile to a temp dir once and import the generated Pydantic module."""
    MofCompiler(m2_dir=M2_DIR).write(tmp_path)
    return _import_generated_models(tmp_path / "mof_control_models.py")


def _valid_decision_kwargs(overrides: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    kwargs: dict = {
        "decision_id": "decision:family-mail-draft-001",
        "schema_version": "policy-decision/v1",
        "decision": "allow",
        "action_id": "action:draft-reply",
        "principal_id": "principal:alice",
        "executor_id": "agent:planner",
        "episode_id": "episode_001",
        "mandate_id": "mandate:family-mail-draft",
        "mandate_version": 1,
        "capability": "bos://mail/draft",
        "server_risk": "R2",
        "budget_limit": 1,
        "budget_unit": "call",
        "disclosure": "disclosure:private",
        "request_hash": "req-hash-8b3f2a9c1e7d5b6a",
        "trace_id": "b6a94b3c5f2a41e8a1d9e0f1c2b3a4b5",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "reason": "allowed",
    }
    if overrides:
        kwargs.update(overrides)
    return kwargs


def _valid_receipt_kwargs(overrides: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    kwargs: dict = {
        "receipt_id": "receipt:family-mail-draft-001",
        "schema_version": "action-receipt/v1",
        "decision_id": "decision:family-mail-draft-001",
        "action_id": "action:draft-reply",
        "principal_id": "principal:alice",
        "executor_id": "agent:planner",
        "episode_id": "episode_001",
        "mandate_id": "mandate:family-mail-draft",
        "mandate_version": 1,
        "capability": "bos://mail/draft",
        "server_risk": "R2",
        "budget_limit": 1,
        "budget_unit": "call",
        "disclosure": "disclosure:private",
        "request_hash": "req-hash-8b3f2a9c1e7d5b6a",
        "trace_id": "b6a94b3c5f2a41e8a1d9e0f1c2b3a4b5",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "status": "started",
        "started_at": now.isoformat(),
    }
    if overrides:
        kwargs.update(overrides)
    return kwargs


def _terminal_receipt_kwargs(status: str, overrides: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    kwargs = _valid_receipt_kwargs(
        {"status": status, "completed_at": now.isoformat()}
    )
    if status == "failed":
        kwargs["reason"] = "provider_failed"
    if overrides:
        kwargs.update(overrides)
    return kwargs


def _model(generated_models, name: str):
    return generated_models.__dict__[name]


# ── model truth: PolicyDecision M2 ──────────────────────────────────


def test_policy_decision_model_truth_is_loaded(compiler: MofCompiler) -> None:
    schemas = {s.name: s for s in compiler.load()}
    assert DECISION_MODEL_NAME in schemas
    schema = schemas[DECISION_MODEL_NAME]
    assert schema.version == "1.0.0"
    assert schema.m3_parent == "GovernanceElement.Decision"
    assert set(schema.required_names) == POLICY_DECISION_REQUIRED_FIELDS


def test_policy_decision_envelope_and_ownership(policy_decision_yaml: dict) -> None:
    assert policy_decision_yaml["m2_type"] == DECISION_MODEL_NAME
    assert policy_decision_yaml["version"] == "1.0.0"
    assert policy_decision_yaml["owner"]["team"] == "execution-control"
    assert "policy" in policy_decision_yaml["owner"]
    assert policy_decision_yaml["migrationPolicy"]["strategy"] == "additive-only"
    assert policy_decision_yaml["migrationPolicy"]["constraints"]


def test_policy_decision_required_fields_and_enums(policy_decision_yaml: dict) -> None:
    body = policy_decision_yaml[DECISION_MODEL_NAME]
    req = body["requiredProperties"]
    assert set(req) == POLICY_DECISION_REQUIRED_FIELDS
    # Fail-closed decision outcome: only allow|deny, never a loose passthrough.
    assert req["decision"]["values"] == ["allow", "deny"]
    assert req["server_risk"]["values"] == list(SERVER_RISKS)
    assert req["schema_version"]["pattern"] == "^policy-decision/v1$"
    assert req["decision_id"]["pattern"].startswith("^decision:")
    assert req["action_id"]["pattern"].startswith("^action:")
    assert req["mandate_id"]["pattern"].startswith("^mandate:")
    assert req["capability"]["pattern"].startswith("^bos://")
    assert req["issued_at"]["format"] == "date-time"
    assert req["expires_at"]["format"] == "date-time"


def test_policy_decision_reason_vocabulary_covers_stable_reasons(
    policy_decision_yaml: dict,
) -> None:
    body = policy_decision_yaml[DECISION_MODEL_NAME]
    values = body["requiredProperties"]["reason"]["values"]
    for stable in STABLE_REASONS:
        assert stable in values, f"stable reason {stable} missing from vocabulary"
    assert "allowed" in values


def test_policy_decision_reason_is_fail_closed(policy_decision_yaml: dict) -> None:
    """allow decisions must carry reason=allowed; deny decisions must not."""
    body = policy_decision_yaml[DECISION_MODEL_NAME]
    rules = [r["rule"] for r in body.get("validationRules", [])]
    assert any("decision == 'allow' and reason != 'allowed'" in r for r in rules)
    assert any("decision == 'deny' and reason == 'allowed'" in r for r in rules)
    # No broad exception may map to allow: the vocabulary has no wildcard value.
    assert "allow" not in body["requiredProperties"]["reason"]["values"]


def test_policy_decision_validation_rules_declare_local_invariants(
    policy_decision_yaml: dict,
) -> None:
    body = policy_decision_yaml[DECISION_MODEL_NAME]
    rules = [r["rule"] for r in body.get("validationRules", [])]
    assert rules, "validationRules must be present"
    assert any("capability.startswith('bos://')" in r for r in rules)
    assert any("issued_at <= expires_at" in r for r in rules)
    assert any("mandate_version >= 1" in r for r in rules)


def test_policy_decision_has_no_ungrounded_relation_constraints(
    policy_decision_yaml: dict,
) -> None:
    body = policy_decision_yaml[DECISION_MODEL_NAME]
    assert "relationConstraints" not in body
    assert "can_be_source_of" not in body
    assert "can_be_target_of" not in body


def test_policy_decision_invalid_examples_are_declared(
    policy_decision_yaml: dict,
) -> None:
    body = policy_decision_yaml[DECISION_MODEL_NAME]
    examples = body.get("examples", [])
    assert any("allow" in e["name"] for e in examples)
    assert any("policy_denied" in e["name"] for e in examples)


# ── model truth: ActionReceipt M2 ───────────────────────────────────


def test_action_receipt_model_truth_is_loaded(compiler: MofCompiler) -> None:
    schemas = {s.name: s for s in compiler.load()}
    assert RECEIPT_MODEL_NAME in schemas
    schema = schemas[RECEIPT_MODEL_NAME]
    assert schema.version == "1.0.0"
    assert schema.m3_parent == "StructuralElement.Artifact"
    assert set(schema.required_names) == ACTION_RECEIPT_REQUIRED_FIELDS


def test_action_receipt_envelope_and_ownership(action_receipt_yaml: dict) -> None:
    assert action_receipt_yaml["m2_type"] == RECEIPT_MODEL_NAME
    assert action_receipt_yaml["version"] == "1.0.0"
    assert action_receipt_yaml["owner"]["team"] == "execution-control"
    assert action_receipt_yaml["migrationPolicy"]["strategy"] == "additive-only"


def test_action_receipt_state_machine_started_to_terminal(
    action_receipt_yaml: dict,
) -> None:
    body = action_receipt_yaml[RECEIPT_MODEL_NAME]
    sm = body["stateMachine"]
    assert set(sm) == {"started", "succeeded", "failed"}
    assert sm["started"]["transitions"] == ["succeeded", "failed"]
    assert sm["succeeded"]["transitions"] == []
    assert sm["failed"]["transitions"] == []
    # started is the only entry state; terminal states have no outgoing edges.
    all_transitions = {t for s in sm.values() for t in s["transitions"]}
    assert "started" not in all_transitions


def test_action_receipt_required_fields_and_enums(action_receipt_yaml: dict) -> None:
    body = action_receipt_yaml[RECEIPT_MODEL_NAME]
    req = body["requiredProperties"]
    assert set(req) == ACTION_RECEIPT_REQUIRED_FIELDS
    assert req["status"]["values"] == ["started", "succeeded", "failed"]
    assert req["schema_version"]["pattern"] == "^action-receipt/v1$"
    assert req["receipt_id"]["pattern"].startswith("^receipt:")
    assert req["decision_id"]["pattern"].startswith("^decision:")
    assert req["started_at"]["format"] == "date-time"
    # The receipt carries the same decision-context vocabulary as the decision.
    assert req["mandate_id"]["pattern"].startswith("^mandate:")
    assert req["capability"]["pattern"].startswith("^bos://")


def test_action_receipt_validation_rules_declare_terminal_invariants(
    action_receipt_yaml: dict,
) -> None:
    body = action_receipt_yaml[RECEIPT_MODEL_NAME]
    rules = [r["rule"] for r in body.get("validationRules", [])]
    assert any("status == 'failed' and reason in" in r for r in rules)
    assert any("status in ('succeeded', 'failed') and completed_at is None" in r for r in rules)
    assert any("started_at <= completed_at" in r for r in rules)


def test_action_receipt_invalid_examples_are_declared(action_receipt_yaml: dict) -> None:
    body = action_receipt_yaml[RECEIPT_MODEL_NAME]
    examples = body.get("examples", [])
    assert any("started" in e["name"] for e in examples)
    assert any("succeeded" in e["name"] for e in examples)
    assert any("failed" in e["name"] for e in examples)


# ── deterministic generation ─────────────────────────────────────────


def test_w2_03_generation_is_deterministic(compiler: MofCompiler) -> None:
    first = compiler.compile()
    second = compiler.compile()
    for artifact in ARTIFACT_CLASSES:
        assert first[artifact] == second[artifact], f"{artifact} not deterministic"


def test_w2_03_artifacts_contain_models(compiler: MofCompiler) -> None:
    compiled = compiler.compile()
    assert '"PolicyDecision"' in compiled["json-schema"]
    assert '"ActionReceipt"' in compiled["json-schema"]
    assert "class PolicyDecision" in compiled["pydantic"]
    assert "class ActionReceipt" in compiled["pydantic"]
    assert "PolicyDecision" in compiled["zod"]
    assert "ActionReceipt" in compiled["zod"]
    assert "policy_decision" in compiled["sqlite"]
    assert "action_receipt" in compiled["sqlite"]


# ── missing / tampered / drift detection ────────────────────────────


def test_w2_03_check_detects_missing_artifact(
    compiler: MofCompiler, tmp_path: Path
) -> None:
    compiler.write(tmp_path)
    (tmp_path / "mof_control_models.py").unlink()
    problems = compiler.check(tmp_path)
    assert problems, "missing artifact must be reported"
    assert any("missing artifact" in p for p in problems)


def test_w2_03_check_detects_tampered_artifact(
    compiler: MofCompiler, tmp_path: Path
) -> None:
    compiler.write(tmp_path)
    target = tmp_path / "mof-control.schema.json"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            '"PolicyDecision"', '"PolicyDecisionX"'
        ),
        encoding="utf-8",
    )
    problems = compiler.check(tmp_path)
    assert problems, "tampered artifact must be reported"
    assert any("tampered artifact" in p for p in problems)


def test_w2_03_check_detects_manifest_tamper(
    compiler: MofCompiler, tmp_path: Path
) -> None:
    compiler.write(tmp_path)
    manifest = tmp_path / "mof-control.manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["artifacts"]["json-schema"] = "0" * 64
    manifest.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    problems = compiler.check(tmp_path)
    assert problems, "tampered manifest hash must be reported"
    assert any("tampered manifest" in p for p in problems)


def test_w2_03_check_detects_drift_from_model_truth(
    compiler: MofCompiler, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Check-mode proof: mutate the PolicyDecision M2 truth and the stale
    artifacts must fail compiler.check."""
    drift_dir = tmp_path_factory.mktemp("m2-drift")
    for src in sorted(M2_DIR.glob("*.yaml")):
        (drift_dir / src.name).write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    drift_compiler = MofCompiler(m2_dir=drift_dir)
    out_dir = drift_dir / "out"
    drift_compiler.write(out_dir)
    assert drift_compiler.check(out_dir) == [], "fresh artifacts must pass check"
    # Mutate the decision enum so every emitted enum surface drifts.
    decision_path = drift_dir / "policy_decision.yaml"
    mutated = decision_path.read_text(encoding="utf-8").replace(
        "values: [allow, deny]",
        "values: [allow, deny, escalate]",
    )
    assert mutated != decision_path.read_text(encoding="utf-8"), "mutation no-op"
    decision_path.write_text(mutated, encoding="utf-8")
    problems = drift_compiler.check(out_dir)
    assert problems, "check must report stale artifacts after M2 drift"
    assert any("tampered" in p for p in problems)


def test_generated_control_dir_is_clean(compiler: MofCompiler) -> None:
    """The checked-in generated/control directory must pass the compiler check."""
    assert GENERATED_CONTROL_DIR.is_dir(), (
        "run mof-compile.py compile --out-dir src/ecos/ssot/mof/generated/control"
    )
    problems = compiler.check(GENERATED_CONTROL_DIR)
    assert problems == [], f"checked-in control artifacts drifted: {problems}"


# ── generated Pydantic PolicyDecision validation ────────────────────


def test_pydantic_policy_decision_validates_allow(generated_models) -> None:
    model_cls = _model(generated_models, DECISION_MODEL_NAME)
    instance = model_cls(**_valid_decision_kwargs())
    assert instance.decision == "allow"
    assert instance.reason == "allowed"
    assert instance.mandate_id == "mandate:family-mail-draft"
    assert instance.mandate_version == 1
    assert instance.capability == "bos://mail/draft"
    assert instance.server_risk == "R2"


def test_pydantic_policy_decision_validates_deny(generated_models) -> None:
    model_cls = _model(generated_models, DECISION_MODEL_NAME)
    instance = model_cls(
        **_valid_decision_kwargs(
            {"decision": "deny", "reason": "policy_denied"}
        )
    )
    assert instance.decision == "deny"
    assert instance.reason == "policy_denied"


def test_pydantic_policy_decision_rejects_invalid_decision(generated_models) -> None:
    model_cls = _model(generated_models, DECISION_MODEL_NAME)
    with pytest.raises(Exception) as exc:
        model_cls(**_valid_decision_kwargs({"decision": "maybe"}))
    assert "decision" in str(exc.value)


def test_pydantic_policy_decision_rejects_invalid_reason(generated_models) -> None:
    model_cls = _model(generated_models, DECISION_MODEL_NAME)
    with pytest.raises(Exception) as exc:
        model_cls(**_valid_decision_kwargs({"reason": "escalated"}))
    assert "reason" in str(exc.value)


def test_pydantic_policy_decision_rejects_invalid_server_risk(
    generated_models,
) -> None:
    model_cls = _model(generated_models, DECISION_MODEL_NAME)
    with pytest.raises(Exception) as exc:
        model_cls(**_valid_decision_kwargs({"server_risk": "R9"}))
    assert "server_risk" in str(exc.value)


def test_pydantic_policy_decision_rejects_bad_pattern(generated_models) -> None:
    model_cls = _model(generated_models, DECISION_MODEL_NAME)
    with pytest.raises(Exception) as exc:
        model_cls(**_valid_decision_kwargs({"decision_id": "not-a-decision"}))
    assert "decision_id" in str(exc.value)


def test_pydantic_policy_decision_rejects_bad_schema_version(
    generated_models,
) -> None:
    model_cls = _model(generated_models, DECISION_MODEL_NAME)
    with pytest.raises(Exception):
        model_cls(**_valid_decision_kwargs({"schema_version": "policy-decision/v9"}))


def test_pydantic_policy_decision_rejects_missing_required_field(
    generated_models,
) -> None:
    model_cls = _model(generated_models, DECISION_MODEL_NAME)
    kwargs = _valid_decision_kwargs()
    del kwargs["principal_id"]
    with pytest.raises(Exception) as exc:
        model_cls(**kwargs)
    assert "principal_id" in str(exc.value)


def test_pydantic_policy_decision_rejects_bad_dates(generated_models) -> None:
    model_cls = _model(generated_models, DECISION_MODEL_NAME)
    with pytest.raises(Exception):
        model_cls(**_valid_decision_kwargs({"issued_at": "not-a-date"}))


# ── generated Pydantic ActionReceipt validation ─────────────────────


def test_pydantic_action_receipt_validates_started(generated_models) -> None:
    model_cls = _model(generated_models, RECEIPT_MODEL_NAME)
    instance = model_cls(**_valid_receipt_kwargs())
    assert instance.status == "started"
    assert instance.completed_at is None
    assert instance.decision_id == "decision:family-mail-draft-001"
    assert instance.capability == "bos://mail/draft"


def test_pydantic_action_receipt_validates_succeeded(generated_models) -> None:
    model_cls = _model(generated_models, RECEIPT_MODEL_NAME)
    instance = model_cls(**_terminal_receipt_kwargs("succeeded"))
    assert instance.status == "succeeded"
    assert instance.completed_at is not None
    assert instance.reason is None


def test_pydantic_action_receipt_validates_failed(generated_models) -> None:
    model_cls = _model(generated_models, RECEIPT_MODEL_NAME)
    instance = model_cls(**_terminal_receipt_kwargs("failed"))
    assert instance.status == "failed"
    assert instance.reason == "provider_failed"


def test_pydantic_action_receipt_rejects_invalid_status(generated_models) -> None:
    model_cls = _model(generated_models, RECEIPT_MODEL_NAME)
    with pytest.raises(Exception) as exc:
        model_cls(**_valid_receipt_kwargs({"status": "pending"}))
    assert "status" in str(exc.value)


def test_pydantic_action_receipt_rejects_invalid_reason(generated_models) -> None:
    model_cls = _model(generated_models, RECEIPT_MODEL_NAME)
    with pytest.raises(Exception):
        model_cls(
            **_terminal_receipt_kwargs("failed", {"reason": "crash_everything"})
        )


def test_pydantic_action_receipt_rejects_bad_decision_pattern(
    generated_models,
) -> None:
    model_cls = _model(generated_models, RECEIPT_MODEL_NAME)
    with pytest.raises(Exception) as exc:
        model_cls(**_valid_receipt_kwargs({"decision_id": "nope"}))
    assert "decision_id" in str(exc.value)


def test_pydantic_action_receipt_rejects_missing_required_field(
    generated_models,
) -> None:
    model_cls = _model(generated_models, RECEIPT_MODEL_NAME)
    kwargs = _valid_receipt_kwargs()
    del kwargs["executor_id"]
    with pytest.raises(Exception) as exc:
        model_cls(**kwargs)
    assert "executor_id" in str(exc.value)


def test_pydantic_action_receipt_rejects_bad_date(generated_models) -> None:
    model_cls = _model(generated_models, RECEIPT_MODEL_NAME)
    with pytest.raises(Exception):
        model_cls(**_valid_receipt_kwargs({"started_at": "n/a"}))


def test_pydantic_action_receipt_keeps_result_map(generated_models) -> None:
    model_cls = _model(generated_models, RECEIPT_MODEL_NAME)
    instance = model_cls(
        **_terminal_receipt_kwargs(
            "succeeded", {"result": {"draft_id": "mail-draft-9"}}
        )
    )
    assert instance.result == {"draft_id": "mail-draft-9"}


# ── package import smoke + JSON Schema contract ─────────────────────


def test_generated_models_import_via_package_smoke() -> None:
    """The generated Pydantic module must be importable as a normal package
    (not only via importlib from a temp dir)."""
    from ecos.ssot.mof.generated.control.mof_control_models import (  # noqa: PLC0415
        ActionReceipt,
        PolicyDecision,
    )

    decision = PolicyDecision(**_valid_decision_kwargs())
    assert decision.decision == "allow"
    receipt = ActionReceipt(**_valid_receipt_kwargs())
    assert receipt.status == "started"


def test_generated_json_schema_matches_contract() -> None:
    compiler = MofCompiler(m2_dir=M2_DIR)
    schema = json.loads(compiler.compile()["json-schema"])

    d = schema["$defs"][DECISION_MODEL_NAME]
    assert set(d["required"]) == POLICY_DECISION_REQUIRED_FIELDS
    assert d["properties"]["decision"]["enum"] == ["allow", "deny"]
    assert d["properties"]["server_risk"]["enum"] == list(SERVER_RISKS)
    assert d["properties"]["schema_version"]["pattern"] == "^policy-decision/v1$"
    assert d["properties"]["issued_at"]["format"] == "date-time"
    assert "x-mof-state-machine" not in d, (
        "PolicyDecision is an immutable decision record, not a state machine"
    )

    r = schema["$defs"][RECEIPT_MODEL_NAME]
    assert set(r["required"]) == ACTION_RECEIPT_REQUIRED_FIELDS
    assert r["properties"]["status"]["enum"] == ["started", "succeeded", "failed"]
    assert r["properties"]["schema_version"]["pattern"] == "^action-receipt/v1$"
    assert r["x-mof-state-machine"] == {
        "started": ["succeeded", "failed"],
        "succeeded": [],
        "failed": [],
    }
    # The reason vocabulary shared by both models covers the stable reasons.
    assert set(d["properties"]["reason"]["enum"]) == set(REASON_VOCABULARY)
    assert set(r["properties"]["reason"]["enum"]) == set(REASON_VOCABULARY)
