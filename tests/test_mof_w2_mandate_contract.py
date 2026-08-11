"""Focused contract tests for the DelegationMandate M2 (W2-02, BET-Y1Q2-T1-05).

Covers: model-truth semantics (required fields / enums / patterns / state
machine / owner / migration policy), invalid examples, deterministic
generation (byte-identical repeated output), missing / tampered / drift
detection via the compiler's check mode, and validation against the
generated Pydantic ``DelegationMandate`` model.
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

MANDATE_MODEL_NAME = "DelegationMandate"

# Required fields fixed by BET-Y1Q2-T1-05 done_when (model-first contract).
REQUIRED_FIELDS = {
    "mandate_id",
    "schema_version",
    "principal_id",
    "executor_id",
    "episode_id",
    "role_context_id",
    "role_assignment_id",
    "role_assignment_version",
    "responsibility_id",
    "responsibility_version",
    "purpose",
    "capability_scope",
    "autonomy_level",
    "risk_ceiling",
    "valid_from",
    "expires_at",
    "approval_mode",
    "disclosure_policy",
    "budget_limit",
    "budget_unit",
    "revocable",
    "trace_id",
    "mandate_version",
    "status",
}

AUTONOMY_LEVELS = ("A0", "A1", "A2", "A3")
RISK_CEILINGS = ("R0", "R1", "R2", "R3")
APPROVAL_MODES = (
    "matrix",
    "approval_required",
    "per_action_approval_required",
    "human_adjudication_required",
    "deny",
)


@pytest.fixture(scope="module")
def mandate_yaml() -> dict:
    path = M2_DIR / "delegation_mandate.yaml"
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


def _valid_mandate_kwargs(overrides: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    kwargs: dict = {
        "mandate_id": "mandate:family-mail-draft",
        "schema_version": "delegation-mandate/v1",
        "principal_id": "principal:alice",
        "executor_id": "agent:planner",
        "episode_id": "episode_001",
        "role_context_id": "role:family-steward",
        "role_assignment_id": "assignment:family-steward-001",
        "role_assignment_version": 1,
        "responsibility_id": "responsibility:family-commitments",
        "responsibility_version": 1,
        "purpose": "draft family mail replies",
        "capability_scope": ["bos://mail/draft"],
        "autonomy_level": "A3",
        "risk_ceiling": "R2",
        "approval_mode": "matrix",
        "disclosure_policy": "disclosure:private",
        "valid_from": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
        "budget_limit": 1,
        "budget_unit": "call",
        "revocable": True,
        "trace_id": "b6a94b3c5f2a41e8a1d9e0f1c2b3a4b5",
        "mandate_version": 1,
        "status": "active",
    }
    if overrides:
        kwargs.update(overrides)
    return kwargs


def _mandate_model(generated_models):
    return generated_models.__dict__[MANDATE_MODEL_NAME]


# ── model truth: DelegationMandate M2 ───────────────────────────────


def test_mandate_model_truth_is_loaded(compiler: MofCompiler) -> None:
    schemas = {s.name: s for s in compiler.load()}
    assert MANDATE_MODEL_NAME in schemas
    schema = schemas[MANDATE_MODEL_NAME]
    assert schema.version == "1.0.0"
    # A DelegationMandate is an authorization policy, not an execution process.
    assert schema.m3_parent == "GovernanceElement.Policy"
    assert set(schema.required_names) == REQUIRED_FIELDS


def test_mandate_model_truth_envelope_and_ownership(mandate_yaml: dict) -> None:
    assert mandate_yaml["m2_type"] == MANDATE_MODEL_NAME
    assert mandate_yaml["version"] == "1.0.0"
    # owner / migration policy declared at model truth level.
    assert mandate_yaml["owner"]["team"] == "execution-control"
    assert "policy" in mandate_yaml["owner"]
    assert mandate_yaml["migrationPolicy"]["strategy"] == "additive-only"
    assert mandate_yaml["migrationPolicy"]["constraints"]


def test_mandate_has_no_ungrounded_relation_constraints(mandate_yaml: dict) -> None:
    """DelegationMandate must declare no relationConstraints.

    The real ledger event types are Mandate.Granted.v1 / Mandate.Revoked.v1 —
    ledger event names, not MOF relationship vocabulary. Invented relation
    terms (e.g. MandateGrantedEvent / MandateRevokedEvent) would be ungrounded
    until real MOF relation vocabulary exists, so the block is omitted until
    then.
    """
    body = mandate_yaml[MANDATE_MODEL_NAME]
    assert "relationConstraints" not in body
    assert "can_be_source_of" not in body
    assert "can_be_target_of" not in body


def test_mandate_state_machine_active_to_revoked(mandate_yaml: dict) -> None:
    body = mandate_yaml[MANDATE_MODEL_NAME]
    sm = body["stateMachine"]
    assert sm["active"]["transitions"] == ["revoked"]
    assert sm["revoked"]["transitions"] == []
    # Active is the only entry state; no re-activation edge may exist.
    all_transitions = {t for s in sm.values() for t in s["transitions"]}
    assert "active" not in all_transitions


def test_mandate_required_fields_and_enums(mandate_yaml: dict) -> None:
    body = mandate_yaml[MANDATE_MODEL_NAME]
    req = body["requiredProperties"]
    assert set(req) == REQUIRED_FIELDS
    assert req["autonomy_level"]["values"] == list(AUTONOMY_LEVELS)
    assert req["risk_ceiling"]["values"] == list(RISK_CEILINGS)
    assert req["approval_mode"]["values"] == list(APPROVAL_MODES)
    assert req["status"]["values"] == ["active", "revoked"]
    assert req["schema_version"]["pattern"] == "^delegation-mandate/v1$"
    assert req["mandate_id"]["pattern"].startswith("^mandate:")
    assert req["role_assignment_id"]["pattern"].startswith("^assignment:")
    assert req["capability_scope"]["items"]["type"] == "string"


def test_mandate_approval_mode_is_matrix_default_without_allow(
    mandate_yaml: dict,
) -> None:
    """approval_mode is matrix-driven: the runtime matrix evaluates request
    risk at admission; explicit modes only tighten. allow is not a valid mode."""
    body = mandate_yaml[MANDATE_MODEL_NAME]
    values = body["requiredProperties"]["approval_mode"]["values"]
    assert "matrix" in values
    assert "allow" not in values
    assert values[0] == "matrix"


def test_mandate_validation_rules_declare_local_invariants_only(
    mandate_yaml: dict,
) -> None:
    body = mandate_yaml[MANDATE_MODEL_NAME]
    rules = [r["rule"] for r in body.get("validationRules", [])]
    assert rules, "validationRules must be present"
    # capability_scope: non-empty + no wildcards (exact match only).
    assert any("len(capability_scope) > 0" in r for r in rules)
    assert any("not any(('*' in c or '?' in c)" in r for r in rules)
    # W2-01 strict role-assignment prefix is a local invariant.
    assert any("role_assignment_id.startswith('assignment:')" in r for r in rules)
    # Lifecycle: revoked requires mandate_version >= 2.
    assert any("status == 'revoked' and mandate_version < 2" in r for r in rules)
    # The 16-cell autonomy/risk matrix must NOT be encoded as M2 rules: it is
    # evaluated against request risk at runtime in OMO, and approval_mode may
    # only tighten. No rule may pin risk_ceiling to an exact outcome or bind
    # approval_mode to a specific cell.
    assert not any("risk_ceiling" in r and "approval_mode" in r for r in rules), (
        "approval_mode must never be bound to a risk cell in M2"
    )
    assert not any(
        "risk_ceiling != 'R" in r or "risk_ceiling == 'R" in r for r in rules
    ), "risk_ceiling cell equality must be a runtime OMO decision, not an M2 rule"


# ── invalid examples ─────────────────────────────────────────────────


def test_mandate_invalid_examples_are_declared(mandate_yaml: dict) -> None:
    body = mandate_yaml[MANDATE_MODEL_NAME]
    examples = body.get("examples", [])
    # Model truth declares at least the active-v1 and revoked-v2 archetypes.
    assert any("revoked v2" in e["name"] for e in examples)
    assert any("active v1" in e["name"] for e in examples)


# ── deterministic generation ─────────────────────────────────────────


def test_mandate_generation_is_deterministic(compiler: MofCompiler) -> None:
    first = compiler.compile()
    second = compiler.compile()
    for artifact in ARTIFACT_CLASSES:
        assert first[artifact] == second[artifact], f"{artifact} not deterministic"


def test_mandate_artifacts_contain_model(compiler: MofCompiler) -> None:
    compiled = compiler.compile()
    assert '"DelegationMandate"' in compiled["json-schema"]
    assert "class DelegationMandate" in compiled["pydantic"]
    assert "DelegationMandate" in compiled["zod"]
    assert "delegation_mandate" in compiled["sqlite"]


# ── missing / tampered / drift detection ────────────────────────────


def test_check_detects_missing_artifact(compiler: MofCompiler, tmp_path: Path) -> None:
    compiler.write(tmp_path)
    (tmp_path / "mof_control_models.py").unlink()
    problems = compiler.check(tmp_path)
    assert problems, "missing artifact must be reported"
    assert any("missing artifact" in p for p in problems)


def test_check_detects_tampered_artifact(compiler: MofCompiler, tmp_path: Path) -> None:
    compiler.write(tmp_path)
    target = tmp_path / "mof-control.schema.json"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            '"DelegationMandate"', '"DelegationMandateX"'
        ),
        encoding="utf-8",
    )
    problems = compiler.check(tmp_path)
    assert problems, "tampered artifact must be reported"
    assert any("tampered artifact" in p for p in problems)


def test_check_detects_manifest_tamper(compiler: MofCompiler, tmp_path: Path) -> None:
    compiler.write(tmp_path)
    manifest = tmp_path / "mof-control.manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["artifacts"]["json-schema"] = "0" * 64
    manifest.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    problems = compiler.check(tmp_path)
    assert problems, "tampered manifest hash must be reported"
    assert any("tampered manifest" in p for p in problems)


def test_check_detects_missing_manifest(compiler: MofCompiler, tmp_path: Path) -> None:
    compiler.write(tmp_path)
    (tmp_path / "mof-control.manifest.json").unlink()
    problems = compiler.check(tmp_path)
    assert any("missing manifest" in p for p in problems)


def test_check_detects_drift_from_model_truth(
    compiler: MofCompiler, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Check-mode proof: mutate the M2 truth and the stale artifacts must fail
    compiler.check.

    Copies the full M2 truth dir, writes artifacts from that copy, mutates the
    copied DelegationMandate model, then asserts the *same* compiler's check on
    the stale output reports problems (drift is detected, not just observable).
    """
    # 1. Copy all M2 YAML files into an isolated truth dir.
    drift_dir = tmp_path_factory.mktemp("m2-drift")
    for src in sorted(M2_DIR.glob("*.yaml")):
        (drift_dir / src.name).write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    # 2. Write the artifact set from that copy and prove it is clean.
    drift_compiler = MofCompiler(m2_dir=drift_dir)
    out_dir = drift_dir / "out"
    drift_compiler.write(out_dir)
    assert drift_compiler.check(out_dir) == [], (
        f"fresh artifacts must pass check, got: {drift_compiler.check(out_dir)}"
    )
    # 3. Mutate the copied DelegationMandate model (drop the matrix approval
    #    mode so every emitted enum surface drifts).
    mandate_path = drift_dir / "delegation_mandate.yaml"
    mutated = mandate_path.read_text(encoding="utf-8").replace(
        "values: [matrix, approval_required, per_action_approval_required, human_adjudication_required, deny]",
        "values: [allow, approval_required]",
    )
    assert mutated != mandate_path.read_text(encoding="utf-8"), "mutation no-op"
    mandate_path.write_text(mutated, encoding="utf-8")
    # 4. The stale output must now fail the same compiler's check.
    problems = drift_compiler.check(out_dir)
    assert problems, "check must report stale artifacts after M2 drift"
    assert any("tampered" in p for p in problems), (
        f"expected tampered-artifact problems, got: {problems}"
    )


def test_generated_control_dir_is_clean(compiler: MofCompiler) -> None:
    """The checked-in generated/control directory must pass the compiler check."""
    assert GENERATED_CONTROL_DIR.is_dir(), (
        "run mof-compile.py compile --out-dir src/ecos/ssot/mof/generated/control"
    )
    problems = compiler.check(GENERATED_CONTROL_DIR)
    assert problems == [], f"checked-in control artifacts drifted: {problems}"


# ── generated Pydantic DelegationMandate validation ─────────────────


def test_pydantic_model_validates_valid_mandate(generated_models) -> None:
    model_cls = _mandate_model(generated_models)
    instance = model_cls(**_valid_mandate_kwargs())
    assert instance.status == "active"
    assert instance.mandate_version == 1
    assert instance.capability_scope == ["bos://mail/draft"]
    assert instance.autonomy_level == "A3"


def test_pydantic_model_validates_revoked_mandate_v2(generated_models) -> None:
    model_cls = _mandate_model(generated_models)
    instance = model_cls(
        **_valid_mandate_kwargs(
            {"status": "revoked", "mandate_version": 2, "trace_id": "revoke-trace-001"}
        )
    )
    assert instance.status == "revoked"
    assert instance.mandate_version == 2


def test_pydantic_model_rejects_invalid_enum(generated_models) -> None:
    model_cls = _mandate_model(generated_models)
    with pytest.raises(Exception) as exc:
        model_cls(**_valid_mandate_kwargs({"autonomy_level": "A9"}))
    assert "autonomy_level" in str(exc.value)


def test_pydantic_model_rejects_invalid_approval_mode(generated_models) -> None:
    model_cls = _mandate_model(generated_models)
    with pytest.raises(Exception) as exc:
        model_cls(**_valid_mandate_kwargs({"approval_mode": "escalate"}))
    assert "approval_mode" in str(exc.value)


def test_pydantic_model_rejects_invalid_status(generated_models) -> None:
    model_cls = _mandate_model(generated_models)
    with pytest.raises(Exception):
        model_cls(**_valid_mandate_kwargs({"status": "suspended"}))


def test_pydantic_model_rejects_bad_pattern(generated_models) -> None:
    model_cls = _mandate_model(generated_models)
    with pytest.raises(Exception) as exc:
        model_cls(**_valid_mandate_kwargs({"mandate_id": "not-a-mandate-id"}))
    assert "mandate_id" in str(exc.value)


def test_pydantic_model_rejects_bad_schema_version(generated_models) -> None:
    model_cls = _mandate_model(generated_models)
    with pytest.raises(Exception):
        model_cls(**_valid_mandate_kwargs({"schema_version": "delegation-mandate/v9"}))


def test_pydantic_model_rejects_missing_required_field(generated_models) -> None:
    model_cls = _mandate_model(generated_models)
    kwargs = _valid_mandate_kwargs()
    del kwargs["principal_id"]
    with pytest.raises(Exception) as exc:
        model_cls(**kwargs)
    assert "principal_id" in str(exc.value)


def test_pydantic_model_rejects_bad_dates(generated_models) -> None:
    model_cls = _mandate_model(generated_models)
    with pytest.raises(Exception):
        model_cls(**_valid_mandate_kwargs({"valid_from": "not-a-date"}))


def test_pydantic_model_keeps_capability_scope_exact_strings(generated_models) -> None:
    """capability_scope items are plain strings; wildcards are a semantics-level
    constraint enforced at runtime by OMO mandate admission (not expressible in
    Pydantic). We assert the generated model accepts exact scopes and keeps
    them as strings (drift guard for the no-wildcard rule)."""
    model_cls = _mandate_model(generated_models)
    instance = model_cls(**_valid_mandate_kwargs())
    assert isinstance(instance.capability_scope, list)
    assert all(isinstance(c, str) for c in instance.capability_scope)


def test_generated_models_import_via_package_smoke() -> None:
    """The generated Pydantic module must be importable as a normal package
    (not only via importlib from a temp dir)."""
    from ecos.ssot.mof.generated.control.mof_control_models import (  # noqa: PLC0415
        DelegationMandate,
    )

    assert DelegationMandate is not None
    instance = DelegationMandate(**_valid_mandate_kwargs())
    assert instance.approval_mode == "matrix"
    assert instance.role_assignment_id == "assignment:family-steward-001"


def test_generated_schema_matches_contract() -> None:
    """The compiled JSON Schema for DelegationMandate matches the M2 truth."""
    compiler = MofCompiler(m2_dir=M2_DIR)
    schema = json.loads(compiler.compile()["json-schema"])
    d = schema["$defs"]["DelegationMandate"]
    assert set(d["required"]) == REQUIRED_FIELDS
    assert d["properties"]["autonomy_level"]["enum"] == list(AUTONOMY_LEVELS)
    assert d["properties"]["approval_mode"]["enum"] == list(APPROVAL_MODES)
    assert d["properties"]["schema_version"]["pattern"] == "^delegation-mandate/v1$"
    assert d["x-mof-state-machine"] == {"active": ["revoked"], "revoked": []}
