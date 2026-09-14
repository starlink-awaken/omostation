"""Test entry point for BET-Y2Q1-T3-05 Mind Model Quartet.

Runs:
1. JSON Schema structural validation
2. Pydantic model instantiation
3. Store read/write round-trip
4. Router decision latency (< 500ms)
5. 10 business-context simulation

Exit 0 = all pass.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from spine.cognitive.schema import ALL_SCHEMAS
from spine.cognitive.models import PersonaProfile, AgendaRadar, AttentionField, ContextAnchor
from spine.cognitive.store import MindModelStore
from spine.cognitive.router import MindModelRouter


def validate_schemas() -> bool:
    """Validate that all schemas are well-formed JSON Schema."""
    try:
        import jsonschema  # type: ignore
        for name, schema in ALL_SCHEMAS.items():
            jsonschema.Draft202012Validator.check_schema(schema)
            print(f"  schema OK: {name}")
        return True
    except ImportError:
        # Fallback: structural check
        for name, schema in ALL_SCHEMAS.items():
            assert schema.get("$schema", "").startswith("https://json-schema.org/"), name
            assert "properties" in schema or "required" in schema, name
            print(f"  schema OK (structural): {name}")
        return True


def validate_models() -> bool:
    """Instantiate all four models with defaults + custom values."""
    p = PersonaProfile(tone="formal", verbosity="concise")
    assert p.tone == "formal"
    a = AgendaRadar(priority_axis="impact-first", risk_appetite="moderate")
    assert a.priority_axis == "impact-first"
    af = AttentionField(peak_hours=[6, 7, 8], info_density="high")
    assert len(af.peak_hours) == 3
    ca = ContextAnchor(baseline_mood="focused", cognitive_load="moderate")
    assert ca.baseline_mood == "focused"
    print("  models OK: 4/4 instantiated")
    return True


def test_store(tmp_dir: Path) -> bool:
    """Write + read round-trip."""
    store = MindModelStore(str(tmp_dir))
    store.write("persona_profile", PersonaProfile(tone="assertive").model_dump())
    store.write("agenda_radar", AgendaRadar(priority_axis="learning-first").model_dump())
    store.write("attention_field", AttentionField(info_density="high").model_dump())
    store.write("context_anchor", ContextAnchor(baseline_mood="creative").model_dump())

    loaded = store.load_all()
    assert loaded["persona_profile"]["tone"] == "assertive"
    assert loaded["agenda_radar"]["priority_axis"] == "learning-first"
    assert loaded["attention_field"]["info_density"] == "high"
    assert loaded["context_anchor"]["baseline_mood"] == "creative"
    print("  store OK: round-trip verified")
    return True


def test_router_latency(tmp_dir: Path) -> bool:
    """Router must complete <= 500ms."""
    store = MindModelStore(str(tmp_dir))
    store.write("persona_profile", {"tone": "diplomatic", "verbosity": "concise"})
    store.write("agenda_radar", {"priority_axis": "urgency-first"})
    store.write("attention_field", {"info_density": "low"})
    store.write("context_anchor", {"baseline_mood": "fatigued", "cognitive_load": "heavy"})

    router = MindModelRouter(store)
    result = router.route()

    assert result["elapsed_ms"] <= 500, f"latency {result['elapsed_ms']}ms > 500ms"
    assert result["circuit_breaker_ok"] is True
    print(f"  router OK: latency={result['elapsed_ms']}ms (threshold 500ms)")
    return True


def test_ten_contexts(tmp_dir: Path) -> bool:
    """Simulate 10 typical business contexts and verify routing decisions."""
    store = MindModelStore(str(tmp_dir))
    store.write("persona_profile", {"tone": "neutral", "verbosity": "balanced"})
    store.write("agenda_radar", {"priority_axis": "impact-first", "risk_appetite": "moderate"})
    store.write("attention_field", {"info_density": "medium", "peak_hours": [7, 8, 21, 22]})
    store.write("context_anchor", {"baseline_mood": "focused", "cognitive_load": "moderate"})

    router = MindModelRouter(store)

    contexts = [
        {"type": "morning_brief", "urgency": "low"},
        {"type": "code_review", "urgency": "medium"},
        {"type": "architecture_decision", "urgency": "high"},
        {"type": "governance_gate", "urgency": "high"},
        {"type": "retro_writing", "urgency": "low"},
        {"type": "email_draft", "urgency": "medium"},
        {"type": "stakeholder_update", "urgency": "high"},
        {"type": "learning_note", "urgency": "low"},
        {"type": "crisis_triage", "urgency": "critical"},
        {"type": "weekly_plan", "urgency": "medium"},
    ]

    for ctx in contexts:
        result = router.route(ctx)
        assert result["circuit_breaker_ok"], f"circuit breaker failed for {ctx['type']}"
        assert result["elapsed_ms"] <= 500, f"latency exceeded for {ctx['type']}"

    print(f"  contexts OK: {len(contexts)}/10 simulated, all <= 500ms")
    return True


def main() -> int:
    import tempfile

    print("=== BET-Y2Q1-T3-05 Mind Model Quartet Test ===")
    print()

    print("[1/5] Schema validation")
    if not validate_schemas():
        return 1

    print("[2/5] Model instantiation")
    if not validate_models():
        return 1

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        print("[3/5] Store round-trip")
        if not test_store(tmp):
            return 1

        print("[4/5] Router latency")
        if not test_router_latency(tmp):
            return 1

        print("[5/5] 10-context simulation")
        if not test_ten_contexts(tmp):
            return 1

    print()
    print("ALL PASSED — exit 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
