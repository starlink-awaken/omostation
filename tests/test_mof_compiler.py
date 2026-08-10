"""Focused tests for the deterministic MOF Control Compiler (WP-W1-02-003).

Covers: model-truth loading, determinism (byte-identical repeated output),
semantics preservation (required / enum / pattern / scalar-list / explicit
reference), artifact validity (JSON Schema parses, Pydantic imports, SQLite
executes), and the tamper-detection check mode.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from ecos.ssot.mof.compiler import (
    ARTIFACT_CLASSES,
    MofCompiler,
    CompilerError,
    load_m2_dir,
)

M2_DIR = Path(__file__).resolve().parents[1] / "src/ecos/ssot/mof/m2"

W1_TYPES = ("EventEnvelope", "Signal", "Commitment", "Episode", "Outcome")


@pytest.fixture()
def compiler() -> MofCompiler:
    return MofCompiler(m2_dir=M2_DIR)


# ── model truth ─────────────────────────────────────────────────────


def test_loads_w1_contracts(compiler: MofCompiler) -> None:
    schemas = compiler.load()
    names = {s.name for s in schemas}
    assert set(W1_TYPES) <= names


def _canonical_m2_names(m2_dir: Path) -> set[str]:
    """Discover the canonical M2 type names in ``m2_dir``.

    A document is canonical when its YAML carries a top-level ``m2_type`` and
    ``version`` envelope — the same criterion the compiler's loader uses.
    Files without the envelope (READMEs, notes) are not part of the model
    truth and are skipped.
    """
    names: set[str] = set()
    for path in sorted(m2_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        m2_type = raw.get("m2_type")
        version = raw.get("version")
        if m2_type and version:
            names.add(str(m2_type))
    return names


def test_loads_exactly_canonical_m2_schemas(compiler: MofCompiler) -> None:
    """Compiler coverage equals the M2 SSOT: every canonical doc, nothing more.

    The expected set is discovered dynamically from the M2 directory instead
    of hardcoding a count, so adding or removing a schema document (e.g.
    CompletionManifest, WorkPacket) extends coverage without editing this
    test. Exact set equality is fail-closed: an unloaded canonical doc, a
    phantom schema, or a duplicated ``m2_type`` all fail.
    """
    canonical = _canonical_m2_names(compiler.m2_dir)
    assert canonical, "no canonical M2 documents discovered"
    schemas = compiler.load()
    loaded = {s.name for s in schemas}
    assert loaded == canonical, (
        "compiler.load() names diverge from the canonical M2 docs\n"
        f"  unloaded docs: {sorted(canonical - loaded)}\n"
        f"  phantom schemas: {sorted(loaded - canonical)}"
    )
    assert len(schemas) == len(loaded), "duplicate m2_type among loaded schemas"


def test_all_schemas_in_json_schema_defs(compiler: MofCompiler) -> None:
    doc = json.loads(compiler.compile()["json-schema"])
    names = {s.name for s in compiler.load()}
    assert names <= set(doc["$defs"].keys())


COMPAT_SCHEMAS = (
    "AvailabilityCheck",
    "ComputeEngine",
    "ComputeNode",
    "HardwareAsset",
    "NetworkZone",
    "QuotaDefinition",
    "RoutingPolicy",
    "VaultPath",
)


def test_compat_schemas_present_and_non_empty(compiler: MofCompiler) -> None:
    by_name = {s.name: s for s in compiler.load()}
    for name in COMPAT_SCHEMAS:
        assert name in by_name, f"{name} missing"
        assert by_name[name].properties, f"{name} has no properties"


def test_governance_schemas_non_empty(compiler: MofCompiler) -> None:
    by_name = {s.name: s for s in compiler.load()}
    for name in ("GovernanceCheck", "GovernanceEvent", "GovernancePolicy"):
        assert by_name[name].properties, f"{name} has no properties"
    conn = sqlite3.connect(":memory:")
    conn.executescript(compiler.compile()["sqlite"])
    for table in ("governance_check", "governance_event", "governance_policy"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        assert cols, f"{table} table empty"


def test_governance_event_result_is_model_reference(compiler: MofCompiler) -> None:
    by_name = {s.name: s for s in compiler.load()}
    result = next(
        p for p in by_name["GovernanceEvent"].properties if p.name == "result"
    )
    assert result.type == "ref"
    assert result.ref_target == "GovernanceCheck"
    doc = json.loads(compiler.compile()["json-schema"])
    assert doc["$defs"]["GovernanceEvent"]["properties"]["result"] == {
        "$ref": "#/$defs/GovernanceCheck"
    }


def test_missing_body_raises(tmp_path: Path) -> None:
    (tmp_path / "broken.yaml").write_text(
        "m2_type: BrokenSchema\nversion: 1.0.0\ncreated: 2026-01-01\nfoo: bar\n",
        encoding="utf-8",
    )
    with pytest.raises(CompilerError, match="no resolvable body"):
        load_m2_dir(tmp_path)


def test_divergent_body_raises(tmp_path: Path) -> None:
    (tmp_path / "divergent.yaml").write_text(
        "m2_type: DivSchema\nversion: 1.0.0\ncreated: 2026-01-01\n"
        "DivSchema:\n  m3_parent: X\n  requiredProperties:\n    a: {type: string}\n  stateMachine: {s1: {}}\n"
        "div_schema:\n  m3_parent: Y\n  requiredProperties:\n    b: {type: string}\n  stateMachine: {s2: {}}\n",
        encoding="utf-8",
    )
    with pytest.raises(CompilerError, match="divergent"):
        load_m2_dir(tmp_path)


def test_wrong_body_not_false_compat(tmp_path: Path) -> None:
    """A wrong_body key with markers does not become a false compatibility body."""
    (tmp_path / "wrong.yaml").write_text(
        "m2_type: FooBar\nversion: 1.0.0\ncreated: 2026-01-01\n"
        "wrong_body:\n  m3_parent: X\n  requiredProperties:\n    x: {type: string}\n"
        "  stateMachine: {s1: {}}\n",
        encoding="utf-8",
    )
    with pytest.raises(CompilerError, match="no resolvable body"):
        load_m2_dir(tmp_path)


def test_compat_body_loads(tmp_path: Path) -> None:
    """foo_bar compat key loads when FooBar exact is absent."""
    (tmp_path / "compat.yaml").write_text(
        "m2_type: FooBar\nversion: 1.0.0\ncreated: 2026-01-01\n"
        "foo_bar:\n  m3_parent: X\n  requiredProperties:\n    x: {type: string}\n"
        "  stateMachine: {s1: {}}\n",
        encoding="utf-8",
    )
    schemas = load_m2_dir(tmp_path)
    assert len(schemas) == 1
    assert schemas[0].name == "FooBar"
    assert schemas[0].properties


def test_exact_plus_divergent_compat_fails(tmp_path: Path) -> None:
    """Exact FooBar + divergent foo_bar → CompilerError."""
    (tmp_path / "div2.yaml").write_text(
        "m2_type: FooBar\nversion: 1.0.0\ncreated: 2026-01-01\n"
        "FooBar:\n  m3_parent: X\n  requiredProperties:\n    a: {type: string}\n"
        "  stateMachine: {s1: {}}\n"
        "foo_bar:\n  m3_parent: Y\n  requiredProperties:\n    b: {type: string}\n"
        "  stateMachine: {s2: {}}\n",
        encoding="utf-8",
    )
    with pytest.raises(CompilerError, match="divergent"):
        load_m2_dir(tmp_path)


def test_exact_plus_unrelated_wrong_body_loads(tmp_path: Path) -> None:
    """Exact FooBar + unrelated wrong_body → loads without ambiguity."""
    (tmp_path / "unrelated.yaml").write_text(
        "m2_type: FooBar\nversion: 1.0.0\ncreated: 2026-01-01\n"
        "FooBar:\n  m3_parent: X\n  requiredProperties:\n    a: {type: string}\n"
        "  stateMachine: {s1: {}}\n"
        "wrong_body:\n  m3_parent: Y\n  requiredProperties:\n    b: {type: string}\n"
        "  stateMachine: {s2: {}}\n",
        encoding="utf-8",
    )
    schemas = load_m2_dir(tmp_path)
    assert len(schemas) == 1
    assert schemas[0].name == "FooBar"


def test_conflicting_duplicate_property_raises(tmp_path: Path) -> None:
    (tmp_path / "dup.yaml").write_text(
        "m2_type: DupSchema\nversion: 1.0.0\ncreated: 2026-01-01\n"
        "DupSchema:\n  m3_parent: X\n  requiredProperties:\n    a: {type: string}\n"
        "  optionalProperties:\n    a: {type: string}\n  stateMachine: {s1: {}}\n",
        encoding="utf-8",
    )
    with pytest.raises(CompilerError, match="duplicate property"):
        load_m2_dir(tmp_path)


def test_unknown_named_type_raises(tmp_path: Path) -> None:
    (tmp_path / "unknown.yaml").write_text(
        "m2_type: UnkSchema\nversion: 1.0.0\ncreated: 2026-01-01\n"
        "UnkSchema:\n  m3_parent: X\n  requiredProperties:\n    x: {type: NoSuchModel}\n"
        "  stateMachine: {s1: {}}\n",
        encoding="utf-8",
    )
    with pytest.raises(CompilerError, match="unsupported type"):
        load_m2_dir(tmp_path)


def test_legacy_state_machine_shape(compiler: MofCompiler) -> None:
    by_name = {s.name: s for s in compiler.load()}
    states = {state for state, _ in by_name["AvailabilityCheck"].state_machine}
    assert "draft" in states


def test_missing_m2_dir_raises() -> None:
    with pytest.raises(CompilerError):
        MofCompiler(m2_dir=M2_DIR / "does-not-exist").compile()


# ── determinism ─────────────────────────────────────────────────────


def test_repeated_compile_is_byte_identical(compiler: MofCompiler) -> None:
    first = compiler.compile()
    for _ in range(3):
        assert compiler.compile() == first


def test_all_artifact_classes_emitted(compiler: MofCompiler) -> None:
    artifacts = compiler.compile()
    assert set(artifacts.keys()) == set(ARTIFACT_CLASSES)
    for content in artifacts.values():
        assert content


# ── semantics: required / pattern / scalar-list / reference ─────────


def test_required_semantics_json_schema(compiler: MofCompiler) -> None:
    doc = json.loads(compiler.compile()["json-schema"])
    ee = doc["$defs"]["EventEnvelope"]
    assert set(ee["required"]) == {
        "event_id",
        "schema_version",
        "source_ref",
        "emitted_at",
        "payload",
    }
    for name in ee["required"]:
        assert name in ee["properties"]


def test_pattern_preserved_json_schema(compiler: MofCompiler) -> None:
    doc = json.loads(compiler.compile()["json-schema"])
    assert (
        doc["$defs"]["EventEnvelope"]["properties"]["schema_version"]["pattern"]
        == "^event-envelope/v[0-9]+$"
    )
    assert (
        doc["$defs"]["Signal"]["properties"]["signal_id"]["pattern"]
        == "^[A-Za-z0-9_-]{8,}$"
    )


def test_explicit_reference_semantics_json_schema(compiler: MofCompiler) -> None:
    doc = json.loads(compiler.compile()["json-schema"])
    ee_props = doc["$defs"]["EventEnvelope"]["properties"]
    assert ee_props["episode_ref"] == {"$ref": "#/$defs/Episode"}
    assert ee_props["signal_ref"] == {"$ref": "#/$defs/Signal"}
    episode_props = doc["$defs"]["Episode"]["properties"]
    assert episode_props["contains_event_refs"]["items"] == {
        "$ref": "#/$defs/EventEnvelope"
    }
    outcome_props = doc["$defs"]["Outcome"]["properties"]
    assert outcome_props["from_commitment_ref"] == {"$ref": "#/$defs/Commitment"}


def test_scalar_and_list_semantics(compiler: MofCompiler) -> None:
    doc = json.loads(compiler.compile()["json-schema"])
    ee = doc["$defs"]["EventEnvelope"]["properties"]
    assert ee["payload"]["type"] == "object"
    assert ee["emitted_at"]["format"] == "date-time"
    episode = doc["$defs"]["Episode"]["properties"]
    assert episode["contains_event_refs"]["type"] == "array"


def test_state_machine_preserved_json_schema(compiler: MofCompiler) -> None:
    doc = json.loads(compiler.compile()["json-schema"])
    sm = doc["$defs"]["Signal"]["x-mof-state-machine"]
    assert set(sm.keys()) == {"detected", "escalated", "dismissed", "archived"}
    assert sm["detected"] == ["escalated", "dismissed"]


# ── artifact validity ───────────────────────────────────────────────


def test_json_schema_is_valid_json(compiler: MofCompiler) -> None:
    doc = json.loads(compiler.compile()["json-schema"])
    assert doc["$schema"].startswith("https://json-schema.org/draft/2020-12/")
    assert "$defs" in doc


def test_pydantic_models_import_and_instantiate(compiler: MofCompiler) -> None:
    content = compiler.compile()["pydantic"]
    with tempfile.TemporaryDirectory() as td:
        mod_path = Path(td) / "mof_control_models.py"
        mod_path.write_text(content, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("mof_control_models", mod_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["mof_control_models"] = module
        spec.loader.exec_module(module)
        envelope = module.EventEnvelope(
            event_id="evt_12345678",
            schema_version="event-envelope/v1",
            source_ref="test-source",
            emitted_at="2026-08-10T00:00:00Z",
            payload={"k": "v"},
        )
        assert envelope.event_id == "evt_12345678"


def test_sqlite_ddl_executes(compiler: MofCompiler) -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(compiler.compile()["sqlite"])
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "event_envelope" in tables
    assert "episode" in tables
    fks = {
        (f[2], f[3]) for f in conn.execute("PRAGMA foreign_key_list(event_envelope)")
    }
    assert ("signal", "signal_ref") in fks
    assert ("episode", "episode_ref") in fks


def test_zod_emits_object_and_lazy_refs(compiler: MofCompiler) -> None:
    content = compiler.compile()["zod"]
    assert "export const EventEnvelope = z.object({" in content
    assert "z.lazy(() => Episode)" in content
    assert "z.string().datetime()" in content


def test_zod_enforces_w1_patterns(compiler: MofCompiler) -> None:
    content = compiler.compile()["zod"]
    assert (
        'schema_version: z.string().regex(new RegExp("^event-envelope/v[0-9]+$"))'
        in content
    )
    assert 'signal_id: z.string().regex(new RegExp("^[A-Za-z0-9_-]{8,}$"))' in content


# ── adversarial: executable SQLite constraints ─────────────────────


def _ddl_connection(compiler: MofCompiler) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(compiler.compile()["sqlite"])
    return conn


def test_adversarial_valid_fk_chain(compiler: MofCompiler) -> None:
    conn = _ddl_connection(compiler)
    conn.execute(
        "INSERT INTO event_envelope (event_id, schema_version, source_ref, emitted_at, payload) "
        "VALUES ('evt_12345678', 'event-envelope/v1', 'src', '2026-08-10T00:00:00Z', '{}')"
    )
    conn.execute(
        "INSERT INTO signal (signal_id, schema_version, source_event_ref, detected_at, pattern) "
        "VALUES ('sig_12345678', 'signal/v1', 'evt_12345678', '2026-08-10T00:00:00Z', 'p')"
    )


def test_adversarial_invalid_fk_rejected(compiler: MofCompiler) -> None:
    conn = _ddl_connection(compiler)
    conn.execute(
        "INSERT INTO event_envelope (event_id, schema_version, source_ref, emitted_at, payload) "
        "VALUES ('evt_12345678', 'event-envelope/v1', 'src', '2026-08-10T00:00:00Z', '{}')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO signal (signal_id, schema_version, source_event_ref, detected_at, pattern) "
            "VALUES ('sig_99999999', 'signal/v1', 'no-such-event', '2026-08-10T00:00:00Z', 'p')"
        )


def test_adversarial_invalid_enum_rejected(compiler: MofCompiler) -> None:
    conn = _ddl_connection(compiler)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO action (action, intent, priority) VALUES ('a', 'i', 'P9')"
        )
    conn.execute(
        "INSERT INTO action (action, intent, priority) VALUES ('a', 'i', 'P0')"
    )


def test_adversarial_junction_fk_enforced(compiler: MofCompiler) -> None:
    conn = _ddl_connection(compiler)
    conn.execute(
        "INSERT INTO event_envelope (event_id, schema_version, source_ref, emitted_at, payload) "
        "VALUES ('evt_a1234567', 'event-envelope/v1', 's', '2026-08-10T00:00:00Z', '{}')"
    )
    conn.execute(
        "INSERT INTO episode (episode_id, schema_version, opened_at) "
        "VALUES ('epi_a1234567', 'episode/v1', '2026-08-10T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO episode_contains_event_refs (episode_id, event_id) "
        "VALUES ('epi_a1234567', 'evt_a1234567')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO episode_contains_event_refs (episode_id, event_id) "
            "VALUES ('epi_a1234567', 'no-such-event')"
        )


def test_adversarial_outcome_fk_degrades_honestly(compiler: MofCompiler) -> None:
    conn = _ddl_connection(compiler)
    fks = {(f[2], f[3]) for f in conn.execute("PRAGMA foreign_key_list(episode)")}
    assert ("outcome", "outcome_ref") not in fks
    content = compiler.compile()["sqlite"]
    assert '"outcome_ref" TEXT' in content
    assert "no FK target" in content


# ── check mode (tamper detection) ───────────────────────────────────


def test_write_then_check_passes(compiler: MofCompiler, tmp_path: Path) -> None:
    compiler.write(out_dir=tmp_path)
    assert compiler.check(out_dir=tmp_path) == []


def test_check_detects_tampering(compiler: MofCompiler, tmp_path: Path) -> None:
    compiler.write(out_dir=tmp_path)
    (tmp_path / "mof-control.schema.json").write_text("{}", encoding="utf-8")
    problems = compiler.check(out_dir=tmp_path)
    assert len(problems) == 1
    assert "mof-control.schema.json" in problems[0]


def test_check_detects_missing_artifact(compiler: MofCompiler, tmp_path: Path) -> None:
    compiler.write(out_dir=tmp_path)
    (tmp_path / "mof-control.sql").unlink()
    problems = compiler.check(out_dir=tmp_path)
    assert any("mof-control.sql" in p for p in problems)


def test_check_detects_missing_manifest(compiler: MofCompiler, tmp_path: Path) -> None:
    compiler.write(out_dir=tmp_path)
    (tmp_path / "mof-control.manifest.json").unlink()
    assert compiler.check(out_dir=tmp_path)


def test_check_detects_manifest_hash_tampering(
    compiler: MofCompiler, tmp_path: Path
) -> None:
    compiler.write(out_dir=tmp_path)
    manifest = tmp_path / "mof-control.manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["artifacts"]["json-schema"] = "0" * 64
    manifest.write_text(
        json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    problems = compiler.check(out_dir=tmp_path)
    assert any("manifest" in p and "json-schema" in p for p in problems)


# ── loader robustness ───────────────────────────────────────────────


def test_identity_precedence(compiler: MofCompiler) -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(compiler.compile()["sqlite"])
    by_table = {
        t: {r[1] for r in conn.execute(f"PRAGMA table_info({t})") if r[5] == 1}
        for t in ("event_envelope", "signal", "commitment", "episode", "omni_envelope")
    }
    assert by_table["event_envelope"] == {"event_id"}
    assert by_table["signal"] == {"signal_id"}
    assert by_table["commitment"] == {"commitment_id"}
    assert by_table["episode"] == {"episode_id"}
    assert by_table["omni_envelope"] == {"id"}


def test_ir_reference_targets(compiler: MofCompiler) -> None:
    by_name = {s.name: s for s in load_m2_dir(M2_DIR)}
    assert "EventEnvelope" in by_name
    episode_ref = next(
        p for p in by_name["EventEnvelope"].properties if p.name == "episode_ref"
    )
    assert episode_ref.type == "ref"
    assert episode_ref.ref_target == "Episode"
    contains = next(
        p for p in by_name["Episode"].properties if p.name == "contains_event_refs"
    )
    assert contains.type == "list"
    assert contains.items_type == "ref"
    assert contains.ref_target == "EventEnvelope"
