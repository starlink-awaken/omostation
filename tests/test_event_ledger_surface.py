"""W1-04 Event Ledger Surface API — tests against real Agora StdioAdapter contract.

The real envelope (StdioAdapter._build_stdio_request):
  {"args": <JSON array>, "kwargs": <dict>}

Rules enforced:
  - args must be [] or [single_mapping]; reject dicts, strings, multi-item arrays
  - CLI subcommand is authoritative; args cannot override it
  - Unknown Agora fields → nonzero, no DB mutation, reason unknown_field
  - Positional mapping + nonempty kwargs → reject ambiguity
  - parse_agora_stdin raises AgoraValidationError (no sys.exit in surface)
  - kwargs.arguments is unwrapped (dict or JSON string)
  - --agora success → pure JSON stdout; nonzero → receipt on stderr
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tmp_surface(tmp_path: Path) -> Any:
    from omo.event_ledger.surface import EventLedgerSurface

    return EventLedgerSurface(db_path=tmp_path / "custom.db")


def _cli_env(tmp_path: Path) -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(OMO_SRC), "WORKSPACE_ROOT": str(tmp_path)}


def _run(
    tmp_path: Path, *args: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "omo.omo_ledger", *args],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(OMO_SRC),
        env=_cli_env(tmp_path),
    )


def _agora_envelope(args: list[Any], kwargs: dict[str, Any]) -> str:
    return json.dumps({"args": args, "kwargs": kwargs})


# ---------------------------------------------------------------------------
# Surface API basics
# ---------------------------------------------------------------------------


def test_surface_append_and_read(tmp_path: Path) -> None:
    surface = _tmp_surface(tmp_path)
    surface.append(
        event_type="Test.v1", producer="test-producer", payload={"msg": "hello"}
    )
    assert surface.read().count == 1
    surface.close()


def test_surface_verify_clean_chain(tmp_path: Path) -> None:
    surface = _tmp_surface(tmp_path)
    for i in range(3):
        surface.append(payload={"i": i})
    assert surface.verify().ok
    surface.close()


def test_surface_status(tmp_path: Path) -> None:
    surface = _tmp_surface(tmp_path)
    for i in range(5):
        surface.append(payload={"i": i})
    assert surface.status().count == 5
    surface.close()


def test_surface_context_manager(tmp_path: Path) -> None:
    from omo.event_ledger.surface import EventLedgerSurface

    with EventLedgerSurface(db_path=tmp_path / "ctx.db") as s:
        s.append(payload={"x": 1})
    assert s._broker is None


# ---------------------------------------------------------------------------
# db_path resolution
# ---------------------------------------------------------------------------


def test_db_path_explicit(tmp_path: Path) -> None:
    from omo.event_ledger.surface import EventLedgerSurface

    with EventLedgerSurface(db_path=tmp_path / "explicit.db") as s:
        assert s.db_path == (tmp_path / "explicit.db").resolve()


def test_db_path_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from omo.event_ledger.surface import EventLedgerSurface

    env_path = tmp_path / "env.db"
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(env_path))
    with EventLedgerSurface() as s:
        assert s.db_path == env_path.resolve()


def test_db_path_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from omo.event_ledger.surface import EventLedgerSurface, _default_db_path

    monkeypatch.delenv("OMO_EVENT_LEDGER_DB", raising=False)
    assert EventLedgerSurface().db_path == _default_db_path()


def test_explicit_wins_over_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omo.event_ledger.surface import EventLedgerSurface

    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(tmp_path / "env.db"))
    with EventLedgerSurface(db_path=tmp_path / "wins.db") as s:
        assert s.db_path == (tmp_path / "wins.db").resolve()


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def test_surface_duplicate_event_id_rejected(tmp_path: Path) -> None:
    from omo.event_ledger.broker import LedgerError

    surface = _tmp_surface(tmp_path)
    surface.append(event_id="evt-fixed")
    with pytest.raises(LedgerError):
        surface.append(event_id="evt-fixed")
    surface.close()


def test_surface_duplicate_idempotency_rejected(tmp_path: Path) -> None:
    from omo.event_ledger.broker import DuplicateEventError

    surface = _tmp_surface(tmp_path)
    surface.append(producer="p", idempotency_key="dup-key", payload={"a": 1})
    with pytest.raises(DuplicateEventError):
        surface.append(producer="p", idempotency_key="dup-key", payload={"b": 2})
    surface.close()


# ---------------------------------------------------------------------------
# parse_agora_stdin — real envelope (raises, no sys.exit)
# ---------------------------------------------------------------------------


def test_parse_agora_stdin_real_args_array() -> None:
    import io

    from omo.event_ledger.surface import parse_agora_stdin

    old = sys.stdin
    try:
        sys.stdin = io.StringIO(_agora_envelope(["append"], {"payload": {"k": "v"}}))
        args_list, kwargs = parse_agora_stdin()
        assert args_list == ["append"]
        assert kwargs == {"payload": {"k": "v"}}
    finally:
        sys.stdin = old


def test_parse_agora_stdin_empty_args() -> None:
    import io

    from omo.event_ledger.surface import parse_agora_stdin

    old = sys.stdin
    try:
        sys.stdin = io.StringIO(_agora_envelope([], {}))
        args_list, kwargs = parse_agora_stdin()
        assert args_list == []
        assert kwargs == {}
    finally:
        sys.stdin = old


def test_parse_agora_stdin_rejects_dict_args() -> None:
    """Args as object (invented contract) must be rejected."""
    import io

    from omo.event_ledger.surface import AgoraValidationError, parse_agora_stdin

    old = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps({"args": {"cmd": "append"}, "kwargs": {}}))
        with pytest.raises(AgoraValidationError, match="args_type"):
            parse_agora_stdin()
    finally:
        sys.stdin = old


def test_parse_agora_stdin_kwargs_arguments_dict() -> None:
    import io

    from omo.event_ledger.surface import parse_agora_stdin

    old = sys.stdin
    try:
        sys.stdin = io.StringIO(
            _agora_envelope([], {"arguments": {"db": "/tmp/db.sqlite"}})
        )
        args_list, kwargs = parse_agora_stdin()
        assert kwargs == {"db": "/tmp/db.sqlite"}
    finally:
        sys.stdin = old


def test_parse_agora_stdin_kwargs_arguments_string() -> None:
    import io

    from omo.event_ledger.surface import parse_agora_stdin

    old = sys.stdin
    try:
        sys.stdin = io.StringIO(
            _agora_envelope([], {"arguments": json.dumps({"db": "/tmp/db.sqlite"})})
        )
        args_list, kwargs = parse_agora_stdin()
        assert kwargs == {"db": "/tmp/db.sqlite"}
    finally:
        sys.stdin = old


def test_parse_agora_stdin_invalid_json_raises() -> None:
    import io

    from omo.event_ledger.surface import AgoraValidationError, parse_agora_stdin

    old = sys.stdin
    try:
        sys.stdin = io.StringIO("{not json")
        with pytest.raises(AgoraValidationError, match="parse_error"):
            parse_agora_stdin()
    finally:
        sys.stdin = old


def test_parse_agora_stdin_args_string_rejected() -> None:
    import io

    from omo.event_ledger.surface import AgoraValidationError, parse_agora_stdin

    old = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps({"args": "not_a_list", "kwargs": {}}))  # type: ignore[arg-type]
        with pytest.raises(AgoraValidationError, match="args_type"):
            parse_agora_stdin()
    finally:
        sys.stdin = old


def test_parse_agora_stdin_ambiguous_kwargs_raises() -> None:
    import io

    from omo.event_ledger.surface import AgoraValidationError, parse_agora_stdin

    old = sys.stdin
    try:
        sys.stdin = io.StringIO(
            json.dumps({"args": [], "kwargs": {"arguments": {"a": 1}, "extra": "bad"}})
        )
        with pytest.raises(AgoraValidationError, match="ambiguous_kwargs"):
            parse_agora_stdin()
    finally:
        sys.stdin = old


# ---------------------------------------------------------------------------
# emit_receipt stability
# ---------------------------------------------------------------------------


def test_emit_receipt_stable_json() -> None:
    from omo.event_ledger.surface import emit_receipt

    parsed = json.loads(
        emit_receipt({"ok": True, "count": 5, "db_path": "/tmp/test.db"})
    )
    assert parsed["ok"] is True
    assert parsed["count"] == 5


# ---------------------------------------------------------------------------
# Legacy CLI backward compatibility
# ---------------------------------------------------------------------------


def test_legacy_with_message_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omo import omo_ledger

    omo_dir = tmp_path / ".omo"
    for d in ["state", "goals", "debt/dashboard", "tasks/active", "tasks/planned"]:
        (omo_dir / d).mkdir(parents=True, exist_ok=True)
    (omo_dir / "state" / "system.yaml").write_text("status: active\n", encoding="utf-8")
    (omo_dir / "goals" / "current.yaml").write_text("goals: []\n", encoding="utf-8")
    (omo_dir / "debt" / "dashboard" / "current.yaml").write_text(
        "summary: {}\n", encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omo_ledger, "get_omo_dir", lambda base_dir: omo_dir)
    assert omo_ledger.main(["--message", "test message"]) == 0


@pytest.mark.parametrize(
    "message", ["append", "read", "verify", "status", "normal message"]
)
def test_legacy_message_with_subcommand_name_still_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    """--message <subcommand-name> must NOT route to subcommand."""
    import yaml

    from omo import omo_ledger

    omo_dir = tmp_path / ".omo"
    for d in ["state", "goals", "debt/dashboard", "tasks/active", "tasks/planned"]:
        (omo_dir / d).mkdir(parents=True, exist_ok=True)
    (omo_dir / "state" / "system.yaml").write_text("status: active\n", encoding="utf-8")
    (omo_dir / "goals" / "current.yaml").write_text("goals: []\n", encoding="utf-8")
    (omo_dir / "debt" / "dashboard" / "current.yaml").write_text(
        "summary: {}\n", encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omo_ledger, "get_omo_dir", lambda base_dir: omo_dir)
    rc = omo_ledger.main(["--message", message])
    assert rc == 0, f"--message '{message}' returned {rc}"

    latest = (
        omo_dir / "_delivery" / "governance-evidence" / "ledgers" / "ledger-latest.yaml"
    )
    payload = yaml.safe_load(latest.read_text(encoding="utf-8"))
    assert payload["message"] == message


def test_omo_ledger_accepts_multi_document_yaml_inputs_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import yaml

    from omo import omo_ledger

    omo_dir = tmp_path / ".omo"
    for d in ["state", "goals", "debt/dashboard", "tasks/active", "tasks/planned"]:
        (omo_dir / d).mkdir(parents=True, exist_ok=True)
    (omo_dir / "state" / "system.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\ncurrent_phase: 46\n",
        encoding="utf-8",
    )
    (omo_dir / "goals" / "current.yaml").write_text(
        "---\nstatus: active\n---\n---\ngoals:\n  - id: G46.1\n    status: pending\n",
        encoding="utf-8",
    )
    (omo_dir / "debt" / "dashboard" / "current.yaml").write_text(
        "---\nstatus: active\n---\n---\nsummary:\n  total: 1\n", encoding="utf-8"
    )
    (omo_dir / "tasks" / "active" / "TASK-1.yaml").write_text(
        "id: TASK-1\n", encoding="utf-8"
    )
    (omo_dir / "tasks" / "planned" / "TASK-2.yaml").write_text(
        "id: TASK-2\n", encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omo_ledger, "get_omo_dir", lambda base_dir: omo_dir)
    assert omo_ledger.main(["--message", "multi-doc snapshot"]) == 0

    latest = (
        omo_dir / "_delivery" / "governance-evidence" / "ledgers" / "ledger-latest.yaml"
    )
    payload = yaml.safe_load(latest.read_text(encoding="utf-8"))
    assert payload["system_state"]["current_phase"] == 46
    assert payload["debt"]["summary"]["total"] == 1


# ---------------------------------------------------------------------------
# Plain CLI subprocess
# ---------------------------------------------------------------------------


def test_cli_append_read_continuity(tmp_path: Path) -> None:
    db = tmp_path / "c.db"
    _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--producer",
        "p1",
        "--payload",
        "{}",
        "--json",
    )
    p = _run(tmp_path, "read", "--db", str(db), "--json")
    assert p.returncode == 0
    r = json.loads(p.stdout)
    assert r["ok"] is True and r["count"] == 1


def test_cli_verify_and_status_subprocess(tmp_path: Path) -> None:
    db = tmp_path / "vs.db"
    for i in range(3):
        p = _run(
            tmp_path,
            "append",
            "--db",
            str(db),
            "--producer",
            "p",
            "--payload",
            "{}",
            "--json",
        )
        assert p.returncode == 0
    assert _run(tmp_path, "verify", "--db", str(db), "--json").returncode == 0
    r = json.loads(_run(tmp_path, "status", "--db", str(db), "--json").stdout)
    assert r["count"] == 3


def test_cli_duplicate_nonzero(tmp_path: Path) -> None:
    db = tmp_path / "dup.db"
    args = [
        "append",
        "--db",
        str(db),
        "--producer",
        "dup",
        "--idempotency-key",
        "k",
        "--payload",
        "{}",
        "--json",
    ]
    _run(tmp_path, *args)
    p = _run(tmp_path, *args)
    assert p.returncode != 0


def test_cli_bad_payload_nonzero(tmp_path: Path) -> None:
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(tmp_path / "bp.db"),
        "--payload",
        "{bad",
        "--json",
    )
    assert p.returncode != 0


# ---------------------------------------------------------------------------
# --agora: args shape validation
# ---------------------------------------------------------------------------


def test_agora_rejects_args_object(tmp_path: Path) -> None:
    """Dict args (invented contract) must be rejected nonzero."""
    db = tmp_path / "r1.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=json.dumps({"args": {"cmd": "append"}, "kwargs": {}}),
    )
    assert p.returncode != 0, p.stdout
    if p.stderr.strip():
        r = json.loads(p.stderr)
        assert r["ok"] is False


def test_agora_rejects_args_array_with_other_subcommand(tmp_path: Path) -> None:
    """args=["status"] must NOT override the CLI `append` subcommand."""
    db = tmp_path / "r2.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope(["status"], {"producer": "bad"}),
    )
    # ["status"] is not [] and not [mapping] -> rejected
    assert p.returncode != 0
    r = json.loads(p.stderr.strip())
    assert r["ok"] is False
    assert "args_shape" in r.get("reason", "")


def test_agora_rejects_multi_item_args(tmp_path: Path) -> None:
    db = tmp_path / "r3.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope(["a", "b"], {}),
    )
    assert p.returncode != 0
    r = json.loads(p.stderr.strip())
    assert r["ok"] is False
    assert "args_shape" in r.get("reason", "")


def test_agora_args_single_mapping_applies_producer_and_payload(tmp_path: Path) -> None:
    """args=[mapping] applies its fields, read back verifies."""
    db = tmp_path / "m1.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope(
            [{"producer": "pos-producer", "payload": {"from_pos": True}}], {}
        ),
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout.strip())
    assert r["ok"] is True
    assert r["sequence"] == 1

    # Read to verify
    p2 = _run(tmp_path, "read", "--db", str(db), "--json")
    r2 = json.loads(p2.stdout)
    assert r2["events"][0]["producer"] == "pos-producer"


def test_agora_rejects_positional_plus_kwargs_ambiguity(tmp_path: Path) -> None:
    """args=[mapping] + nonempty kwargs → ambiguity rejection."""
    db = tmp_path / "amb.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([{"producer": "p1"}], {"payload": {"k": "v"}}),
    )
    assert p.returncode != 0
    r = json.loads(p.stderr.strip())
    assert r["ok"] is False
    assert "ambiguous" in r.get("reason", "").lower()


# ---------------------------------------------------------------------------
# --agora: unknown field rejection (no DB mutation)
# ---------------------------------------------------------------------------


def test_agora_rejects_unknown_field_no_db_mutation(tmp_path: Path) -> None:
    """Unknown field must fail nonzero, with no DB mutation."""
    db = tmp_path / "uf.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"producer": "uf-test", "bad_unknown": 999}),
    )
    assert p.returncode != 0
    r = json.loads(p.stderr.strip())
    assert r["ok"] is False
    assert r["reason"] == "unknown_field"

    # Verify no DB mutation: ledger should be empty
    p2 = _run(tmp_path, "status", "--db", str(db), "--json")
    r2 = json.loads(p2.stdout)
    assert r2["count"] == 0


def test_agora_rejects_multiple_unknown_fields(tmp_path: Path) -> None:
    db = tmp_path / "uf2.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"producer": "t", "bad1": 1, "bad2": 2}),
    )
    assert p.returncode != 0
    r = json.loads(p.stderr.strip())
    assert r["reason"] == "unknown_field"
    r2 = json.loads(_run(tmp_path, "status", "--db", str(db), "--json").stdout)
    assert r2["count"] == 0


def test_agora_status_unknown_field_rejected(tmp_path: Path) -> None:
    db = tmp_path / "uf3.db"
    p = _run(
        tmp_path,
        "status",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"bad_field": "nope"}),
    )
    assert p.returncode != 0, p.stdout
    r = json.loads(p.stderr.strip())
    assert r["reason"] == "unknown_field"


# ---------------------------------------------------------------------------
# --agora: success paths
# ---------------------------------------------------------------------------


def test_agora_args_empty_plus_kwargs_success(tmp_path: Path) -> None:
    db = tmp_path / "s1.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"producer": "s1", "payload": {"ok": True}}),
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout.strip())
    assert r["ok"] is True and r["sequence"] == 1


def test_agora_kwargs_arguments_success(tmp_path: Path) -> None:
    db = tmp_path / "s2.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope(
            [], {"arguments": {"producer": "s2", "payload": {"in_args": True}}}
        ),
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout.strip())
    assert r["ok"] is True


def test_agora_kwargs_arguments_str_success(tmp_path: Path) -> None:
    db = tmp_path / "s3.db"
    inner = json.dumps({"producer": "s3", "payload": {"nested": True}})
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"arguments": inner}),
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout.strip())
    assert r["ok"] is True


def test_agora_duplicate_receipt_on_stderr(tmp_path: Path) -> None:
    db = tmp_path / "dup-agora.db"
    _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--producer",
        "da",
        "--idempotency-key",
        "k",
        "--payload",
        "{}",
        "--json",
    )
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope(
            [], {"producer": "da", "idempotency_key": "k", "payload": {}}
        ),
    )
    assert p.returncode != 0
    r = json.loads(p.stderr.strip())
    assert r["ok"] is False
    assert (
        "duplicate" in r.get("error", "").lower()
        or r.get("reason") == "duplicate_event"
    )


def test_agora_full_append_read_verify_cycle(tmp_path: Path) -> None:
    db = tmp_path / "cycle.db"
    for i in range(2):
        p = _run(
            tmp_path,
            "append",
            "--db",
            str(db),
            "--agora",
            stdin=_agora_envelope([], {"producer": "cycle", "payload": {"i": i}}),
        )
        assert p.returncode == 0

    p = _run(
        tmp_path, "read", "--db", str(db), "--agora", stdin=_agora_envelope([], {})
    )
    assert p.returncode == 0
    assert json.loads(p.stdout)["count"] == 2

    p = _run(
        tmp_path, "verify", "--db", str(db), "--agora", stdin=_agora_envelope([], {})
    )
    assert p.returncode == 0


# ---------------------------------------------------------------------------
# Bug 1: db_path from envelope
# ---------------------------------------------------------------------------


def test_agora_envelope_db_writes_to_intended_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Envelope db=intended must write there, not to OMO_EVENT_LEDGER_DB=fallback."""
    fallback = tmp_path / "fallback.db"
    intended = tmp_path / "intended.db"
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(fallback))

    p = _run(
        tmp_path,
        "append",
        "--agora",
        stdin=_agora_envelope(
            [],
            {
                "db": str(intended),
                "producer": "db-test",
                "payload": {"from": "intended"},
            },
        ),
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout.strip())
    assert r["ok"] is True

    # Intended db has the event
    p2 = _run(tmp_path, "status", "--db", str(intended), "--json")
    r2 = json.loads(p2.stdout)
    assert r2["count"] == 1

    # Fallback db is absent/empty
    p3 = _run(tmp_path, "status", "--db", str(fallback), "--json")
    r3 = json.loads(p3.stdout)
    assert r3["count"] == 0


def test_agora_envelope_db_conflict_with_cli_rejected(tmp_path: Path) -> None:
    """CLI --db=X + envelope db=Y (X != Y) → ambiguous_db."""
    db_a = tmp_path / "a.db"
    db_b = tmp_path / "b.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db_a),
        "--agora",
        stdin=_agora_envelope([], {"db": str(db_b), "producer": "p"}),
    )
    assert p.returncode != 0
    r = json.loads(p.stderr.strip())
    assert r["ok"] is False
    assert r["reason"] == "ambiguous_db"


def test_agora_envelope_db_same_as_cli_accepted(tmp_path: Path) -> None:
    """CLI --db=X + envelope db=X (same value) → accepted."""
    db = tmp_path / "same.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"db": str(db), "producer": "same"}),
    )
    assert p.returncode == 0, p.stderr


# ---------------------------------------------------------------------------
# Bug 2: payload type validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_payload,label",
    [
        ("[1,2,3]", "array"),
        ("42", "number"),
        ("true", "bool"),
        ('"just a string"', "string"),
    ],
)
def test_agora_bad_payload_type_rejected(
    tmp_path: Path, bad_payload: str, label: str
) -> None:
    """Non-mapping payload (array/number/bool/string) → payload_type, nonzero, stderr."""
    db = tmp_path / f"bp-{label}.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"producer": "pt", "payload": bad_payload}),
    )
    assert p.returncode != 0, f"{label} payload should fail: {p.stdout}"
    r = json.loads(p.stderr.strip())
    assert r["ok"] is False
    assert r["reason"] == "payload_type", f"reason={r.get('reason')}"
    # No DB mutation
    r2 = json.loads(_run(tmp_path, "status", "--db", str(db), "--json").stdout)
    assert r2["count"] == 0


@pytest.mark.parametrize(
    "inline_payload,label",
    [
        ([1, 2, 3], "inline_array"),
        (42, "inline_number"),
        (True, "inline_bool"),
    ],
)
def test_agora_inline_non_dict_payload_rejected(
    tmp_path: Path, inline_payload: Any, label: str
) -> None:
    """Inline array/number/bool from Agora → payload_type."""
    db = tmp_path / f"il-{label}.db"
    envelope = json.dumps(
        {
            "args": [],
            "kwargs": {"producer": "il", "payload": inline_payload},
        }
    )
    p = _run(tmp_path, "append", "--db", str(db), "--agora", stdin=envelope)
    assert p.returncode != 0, f"{label} should fail: {p.stdout}"
    r = json.loads(p.stderr.strip())
    assert r["reason"] == "payload_type"


def test_agora_payload_null_maps_to_empty(tmp_path: Path) -> None:
    """null payload → maps to {}, succeeds."""
    db = tmp_path / "null.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"producer": "null-test", "payload": None}),
    )
    assert p.returncode == 0, p.stderr


def test_direct_json_bad_payload_type_stdout(tmp_path: Path) -> None:
    """--json with bad payload → JSON receipt on stdout, nonzero."""
    db = tmp_path / "dj.db"
    p = _run(tmp_path, "append", "--db", str(db), "--payload", "[1,2]", "--json")
    assert p.returncode != 0
    r = json.loads(p.stdout)
    assert r["ok"] is False
    assert r["reason"] == "payload_type"


def test_payload_file_non_object_rejected(tmp_path: Path) -> None:
    """--payload-file containing valid JSON that is not an object → payload_type."""
    pf = tmp_path / "pl.json"
    pf.write_text("[1,2,3]", encoding="utf-8")
    db = tmp_path / "plf.db"
    p = _run(tmp_path, "append", "--db", str(db), "--payload-file", str(pf), "--json")
    assert p.returncode != 0
    r = json.loads(p.stdout)
    assert r["ok"] is False
    assert r["reason"] == "payload_type"


def test_payload_file_object_succeeds(tmp_path: Path) -> None:
    """--payload-file containing a valid JSON object → succeeds."""
    pf = tmp_path / "pl2.json"
    pf.write_text('{"file":"ok"}', encoding="utf-8")
    db = tmp_path / "plf2.db"
    p = _run(tmp_path, "append", "--db", str(db), "--payload-file", str(pf), "--json")
    assert p.returncode == 0


# ---------------------------------------------------------------------------
# Agora value type/range validation (real-envelope subprocess)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value,label",
    [
        ("from_sequence", "bad", "bad_string"),
        ("from_sequence", True, "bool"),
        ("from_sequence", 0, "zero"),
        ("from_sequence", -1, "negative"),
        ("to_sequence", "bad", "bad_string"),
        ("to_sequence", 0, "zero"),
        ("to_sequence", -1, "negative"),
        ("limit", "bad", "bad_string"),
        ("limit", True, "bool"),
        ("limit", 0, "zero"),
        ("limit", -1, "negative"),
    ],
)
def test_agora_read_bad_numeric_field_rejected(
    tmp_path: Path, field: str, value: Any, label: str
) -> None:
    """Bad numeric field (string/bool/zero/negative) → invalid_field, stderr, nonzero, no traceback."""
    db = tmp_path / f"bn-{label}.db"
    p = _run(
        tmp_path,
        "read",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {field: value}),
    )
    assert p.returncode != 0, f"{field}={value}: {p.stdout}"
    assert "Traceback" not in p.stderr, p.stderr
    r = json.loads(p.stderr.strip())
    assert r["ok"] is False
    assert r["reason"] == "invalid_field"


def test_agora_read_valid_integer_path(tmp_path: Path) -> None:
    """Valid integer from_sequence should work fine via Agora."""
    db = tmp_path / "valid-int.db"
    # Append one event so range 1..1 is populated
    _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--producer",
        "vi",
        "--payload",
        "{}",
        "--json",
    )
    p = _run(
        tmp_path,
        "read",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"from_sequence": 1}),
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout.strip())
    assert r["count"] >= 1


@pytest.mark.parametrize(
    "value,label",
    [
        (42, "number"),
        (["list"], "list"),
        (True, "bool"),
    ],
)
def test_agora_read_bad_string_field_rejected(
    tmp_path: Path, value: Any, label: str
) -> None:
    """String fields (event_type/producer/episode_id) must be string or null."""
    db = tmp_path / f"bs-{label}.db"
    p = _run(
        tmp_path,
        "read",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"producer": value}),
    )
    assert p.returncode != 0, f"{label}: {p.stdout}"
    assert "Traceback" not in p.stderr, p.stderr
    r = json.loads(p.stderr.strip())
    assert r["reason"] == "invalid_field"


@pytest.mark.parametrize(
    "value,label",
    [
        (["list"], "list"),
        (True, "bool"),
        (42, "number"),
    ],
)
def test_agora_append_bad_meta_field_rejected(
    tmp_path: Path, value: Any, label: str
) -> None:
    """Append metadata must be string or null."""
    db = tmp_path / f"am-{label}.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"producer": value, "payload": {}}),
    )
    assert p.returncode != 0, f"{label}: {p.stdout}"
    r = json.loads(p.stderr.strip())
    assert r["reason"] == "invalid_field"


@pytest.mark.parametrize(
    "value,label",
    [
        (42, "number"),
        (True, "bool"),
        ("", "empty"),
    ],
)
def test_agora_db_bad_value_rejected(tmp_path: Path, value: Any, label: str) -> None:
    """db must be a nonempty string."""
    p = _run(
        tmp_path,
        "status",
        "--agora",
        stdin=_agora_envelope([], {"db": value}),
    )
    assert p.returncode != 0, f"{label}: {p.stdout}"
    r = json.loads(p.stderr.strip())
    assert r["reason"] == "invalid_field"


@pytest.mark.parametrize(
    "value,label",
    [
        ("[1,2]", "serialized_array"),
        (999, "inline_number"),
        ([42], "inline_list"),
    ],
)
def test_agora_payload_bad_type_still_handled(
    tmp_path: Path, value: Any, label: str
) -> None:
    """Payload type errors remain payload_type (not swallowed)."""
    db = tmp_path / f"bp2-{label}.db"
    p = _run(
        tmp_path,
        "append",
        "--db",
        str(db),
        "--agora",
        stdin=_agora_envelope([], {"producer": "pt2", "payload": value}),
    )
    assert p.returncode != 0, f"{label}: {p.stdout}"
    r = json.loads(p.stderr.strip())
    # Payload gets its own reason (payload_type from _load_payload)
    assert r["reason"] == "payload_type"


# ---------------------------------------------------------------------------
# AgoraValidationError
# ---------------------------------------------------------------------------


def test_agora_validation_error_attributes() -> None:
    from omo.event_ledger.surface import AgoraValidationError

    e = AgoraValidationError("test_reason", "test message")
    assert isinstance(e, ValueError)
    assert e.reason == "test_reason"
    assert e.message == "test message"


def test_agora_validation_error_no_message_defaults() -> None:
    from omo.event_ledger.surface import AgoraValidationError

    e = AgoraValidationError("only_reason")
    assert e.reason == "only_reason"
    assert e.message == "only_reason"
