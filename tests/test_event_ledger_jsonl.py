"""W1-05 JSONL shadow import/export/compare — BET-Y1Q2-T1-03.

TDD 批次 1：幂等导入、坏行隔离、反向拒绝。

后续批次（export-jsonl / compare-jsonl / CLI receipt 与错误路径）在
检查点通过后追加。
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

from omo.event_ledger.broker import DuplicateEventError  # noqa: E402
from omo.event_ledger.surface import EventLedgerSurface  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _healthy(seq: int) -> str:
    return json.dumps({"id": seq, "kind": "health", "score": seq * 1.5}, sort_keys=True)


class SpyBroker:
    """Duck-typed LedgerBroker that records every append call.

    Rejects a repeated ``(producer, idempotency_key)`` exactly like the real
    broker's UNIQUE constraint, so double-import behaves identically.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._keys: set[tuple[str, str]] = set()

    def append(
        self,
        *,
        event_type: str,
        producer: str,
        principal_id: str,
        space_id: str,
        correlation_id: str,
        idempotency_key: str,
        payload: dict[str, Any] | None,
        **_: Any,
    ) -> int:
        # 记录每一次 append 调用（含命中重复的尝试），以便断言“每条健康
        # 记录都走 LedgerBroker.append”。
        self.calls.append(
            {
                "event_type": event_type,
                "producer": producer,
                "principal_id": principal_id,
                "space_id": space_id,
                "correlation_id": correlation_id,
                "idempotency_key": idempotency_key,
                "payload": dict(payload or {}),
            }
        )
        key = (producer, idempotency_key)
        if key in self._keys:
            raise DuplicateEventError(
                f"duplicate event: producer={producer!r} "
                f"idempotency_key={idempotency_key!r}"
            )
        self._keys.add(key)
        return len(self.calls)


# ---------------------------------------------------------------------------
# 批次 1a — 双导入幂等（真实 DB + spy append）
# ---------------------------------------------------------------------------


def test_double_import_idempotent_real_db(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import import_jsonl

    src = _write_jsonl(tmp_path / "src.jsonl", [_healthy(1), _healthy(2), _healthy(3)])
    db = tmp_path / "ledger.db"
    with EventLedgerSurface(db_path=db) as surface:
        r1 = import_jsonl(surface.broker, src)
        assert r1["healthy"] == 3
        assert r1["imported"] == 3
        assert r1["duplicates"] == 0

        r2 = import_jsonl(surface.broker, src)
        assert r2["healthy"] == 3
        assert r2["imported"] == 0
        assert r2["duplicates"] == 3

        assert surface.broker.count() == 3
        assert surface.broker.verify_chain()["ok"] is True


def test_spy_append_called_per_healthy_record(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import (
        SHADOW_EVENT_TYPE,
        SHADOW_PRODUCER,
        import_jsonl,
    )

    src = _write_jsonl(tmp_path / "s.jsonl", [_healthy(1), _healthy(2)])
    spy = SpyBroker()

    r1 = import_jsonl(spy, src)
    assert r1["imported"] == 2
    assert len(spy.calls) == 2
    for call in spy.calls:
        assert call["event_type"] == SHADOW_EVENT_TYPE
        assert call["producer"] == SHADOW_PRODUCER
        assert call["payload"]["source"] == "s.jsonl"
        assert call["payload"]["hash"]
        assert call["payload"]["original"]["id"] in (1, 2)

    r2 = import_jsonl(spy, src)
    assert r2["imported"] == 0
    assert r2["duplicates"] == 2
    # 每条健康记录都走 append；第二次导入全部命中重复。
    assert len(spy.calls) == 4


# ---------------------------------------------------------------------------
# 批次 1b — 坏行隔离（bad JSON / 非对象 / 未知版本）且健康行继续
# ---------------------------------------------------------------------------


def test_bad_lines_quarantined_and_healthy_continue(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import import_jsonl

    lines = [
        _healthy(1),
        "{not json",
        json.dumps([1, 2, 3]),
        json.dumps({"id": 2, "kind": "x", "schema_version": "v99"}),
        _healthy(3),
    ]
    src = _write_jsonl(tmp_path / "mixed.jsonl", lines)
    db = tmp_path / "q.db"
    quarantine = tmp_path / "quarantine.jsonl"

    with EventLedgerSurface(db_path=db) as surface:
        r = import_jsonl(surface.broker, src, quarantine_path=quarantine)
        assert r["healthy"] == 2
        assert r["imported"] == 2
        assert r["quarantined"] == 3
        reasons = {e["reason"] for e in r["quarantine_entries"]}
        assert reasons == {"parse_error", "not_object", "unknown_version"}
        assert surface.broker.count() == 2

        entries = [
            json.loads(line)
            for line in quarantine.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(entries) == 3
        assert all(e["source"] == "mixed.jsonl" for e in entries)
        assert all(e["line"] >= 1 for e in entries)
        assert all(e["reason"] in reasons for e in entries)


def test_no_quarantine_path_writes_nothing_beside_source(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import import_jsonl

    src = _write_jsonl(tmp_path / "q2.jsonl", [_healthy(1), "{bad"])
    db = tmp_path / "q2.db"
    with EventLedgerSurface(db_path=db) as surface:
        r = import_jsonl(surface.broker, src)
        assert r["quarantined"] == 1
    assert not (tmp_path / "q2.jsonl.quarantine").exists()
    assert list(tmp_path.glob("*.quarantine*")) == []


# ---------------------------------------------------------------------------
# 批次 1c — 反向写拒绝（authority=ledger / read_only=true）
# ---------------------------------------------------------------------------


def test_reverse_write_flags_quarantined(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import import_jsonl

    lines = [
        json.dumps({"id": 1, "authority": "ledger"}),
        json.dumps({"id": 2, "read_only": True}),
        json.dumps({"id": 3, "_meta": {"authority": "ledger"}}),
        json.dumps({"id": 4, "_meta": {"read_only": True}}),
        _healthy(5),
    ]
    src = _write_jsonl(tmp_path / "rev.jsonl", lines)
    db = tmp_path / "rev.db"
    with EventLedgerSurface(db_path=db) as surface:
        r = import_jsonl(surface.broker, src)
        assert r["imported"] == 1
        assert r["quarantined"] == 4
        assert all(
            e["reason"] == "reverse_write_rejected" for e in r["quarantine_entries"]
        )
        assert surface.broker.count() == 1
        assert surface.broker.verify_chain()["ok"] is True


# ---------------------------------------------------------------------------
# 批次 2a — export-jsonl：元数据、合法性、稳定顺序、不增长 DB
# ---------------------------------------------------------------------------


def test_export_metadata_and_validity(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import export_jsonl, import_jsonl

    src = _write_jsonl(tmp_path / "e.jsonl", [_healthy(1), _healthy(2), _healthy(3)])
    db = tmp_path / "e.db"
    out = tmp_path / "out.jsonl"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        report = export_jsonl(surface.broker, out)
        assert report["exported"] == 3

        lines = [
            line
            for line in out.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(lines) == 3
        for raw in lines:
            obj = json.loads(raw)
            assert obj["authority"] == "ledger"
            assert obj["read_only"] is True
            assert obj["projection"] == "jsonl-shadow/v1"
            assert obj["source"] == "e.jsonl"
            assert obj["hash"]
            assert "id" in obj["original"]

        # 稳定顺序：重复导出字节级一致
        out2 = tmp_path / "out2.jsonl"
        export_jsonl(surface.broker, out2)
        assert out.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")
        # 导出不增长 DB
        assert surface.broker.count() == 3


def test_export_reverse_import_rejected_no_growth(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import export_jsonl, import_jsonl

    src = _write_jsonl(tmp_path / "r.jsonl", [_healthy(1), _healthy(2)])
    db = tmp_path / "rr.db"
    out = tmp_path / "exported.jsonl"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        export_jsonl(surface.broker, out)
        r = import_jsonl(surface.broker, out)
        assert r["imported"] == 0
        assert r["quarantined"] == 2
        assert all(
            e["reason"] == "reverse_write_rejected" for e in r["quarantine_entries"]
        )
        assert surface.broker.count() == 2
        assert surface.broker.verify_chain()["ok"] is True


# ---------------------------------------------------------------------------
# 批次 2b — compare-jsonl：equal / missing / extra / 物理重复 / digest 稳定
# ---------------------------------------------------------------------------


def test_compare_equal(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import compare_jsonl, import_jsonl

    src = _write_jsonl(tmp_path / "c.jsonl", [_healthy(1), _healthy(2), _healthy(3)])
    db = tmp_path / "c.db"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        res = compare_jsonl(surface.broker, src)
        assert res["source_rows"] == 3
        assert res["source_unique"] == 3
        assert res["ledger_rows"] == 3
        assert res["missing"] == 0
        assert res["extra"] == 0
        assert res["duplicate"] == 0
        assert res["ok"] is True
        assert res["source_digest"] == res["ledger_digest"]


def test_compare_missing(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import compare_jsonl, import_jsonl

    # 相同 basename、不同目录：source 推导一致，ledger 只有 2 条 → missing=1
    imported = _write_jsonl(tmp_path / "a" / "m.jsonl", [_healthy(1), _healthy(2)])
    full = _write_jsonl(
        tmp_path / "b" / "m.jsonl", [_healthy(1), _healthy(2), _healthy(3)]
    )
    db = tmp_path / "m.db"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, imported)
        res = compare_jsonl(surface.broker, full)
        assert res["source_rows"] == 3
        assert res["source_unique"] == 3
        assert res["ledger_rows"] == 2
        assert res["missing"] == 1
        assert res["extra"] == 0
        assert res["ok"] is False
        assert res["source_digest"] != res["ledger_digest"]


def test_compare_extra(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import compare_jsonl, import_jsonl

    src = _write_jsonl(
        tmp_path / "extra.jsonl", [_healthy(1), _healthy(2), _healthy(3)]
    )
    db = tmp_path / "extra.db"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        # 删除源中第 3 条后再比较 → ledger 多一条
        _write_jsonl(src, [_healthy(1), _healthy(2)])
        res = compare_jsonl(surface.broker, src)
        assert res["source_unique"] == 2
        assert res["ledger_rows"] == 3
        assert res["missing"] == 0
        assert res["extra"] == 1
        assert res["ok"] is False


def test_compare_physical_duplicate_no_false_missing(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import compare_jsonl, import_jsonl

    lines = [_healthy(1), _healthy(2), _healthy(2)]
    src = _write_jsonl(tmp_path / "dup.jsonl", lines)
    db = tmp_path / "dup.db"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        assert surface.broker.count() == 2  # 物理重复只落一条
        res = compare_jsonl(surface.broker, src)
        assert res["source_rows"] == 3
        assert res["source_unique"] == 2
        assert res["ledger_rows"] == 2
        assert res["missing"] == 0
        assert res["extra"] == 0
        assert res["duplicate"] == 1
        assert res["ok"] is True
        assert res["source_digest"] == res["ledger_digest"]


def test_compare_digest_stable_across_runs(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import compare_jsonl, import_jsonl

    src = _write_jsonl(tmp_path / "d.jsonl", [_healthy(1), _healthy(2)])
    db = tmp_path / "d.db"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        r1 = compare_jsonl(surface.broker, src)
        r2 = compare_jsonl(surface.broker, src)
        assert r1 == r2


# ---------------------------------------------------------------------------
# 批次 2c — 幂等 key 与 content hash 性质
# ---------------------------------------------------------------------------


def test_content_hash_content_based_and_stable() -> None:
    from omo.event_ledger.jsonl_shadow import content_hash

    rec1 = {"b": 2, "a": 1}
    rec2 = {"a": 1, "b": 2}  # 键序不同 → canonical JSON 相同
    rec3 = {"a": 1, "b": 3}
    assert content_hash(rec1) == content_hash(rec2)
    assert content_hash(rec1) != content_hash(rec3)
    assert len(content_hash(rec1)) == 64


def test_idempotency_key_has_no_line_time_or_absolute_path(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import derive_source, idempotency_key

    src = tmp_path / "sub" / "data.jsonl"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(_healthy(1) + "\n", encoding="utf-8")
    source = derive_source(src)
    assert source == "data.jsonl"
    key = idempotency_key(source, "abc123")
    assert str(src) not in key
    assert str(tmp_path) not in key
    assert "line" not in key.lower()
    assert key == idempotency_key(source, "abc123")


# ---------------------------------------------------------------------------
# 批次 2d — CLI：receipt / 错误 / 不支持 --agora
# ---------------------------------------------------------------------------


def _run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "omo.omo_ledger", *args],
        capture_output=True,
        text=True,
        cwd=str(OMO_SRC),
        env={
            **os.environ,
            "PYTHONPATH": str(OMO_SRC),
            "WORKSPACE_ROOT": str(tmp_path),
        },
    )


def test_cli_import_export_compare(tmp_path: Path) -> None:
    src = _write_jsonl(tmp_path / "cli.jsonl", [_healthy(1), _healthy(2)])
    db = tmp_path / "cli.db"

    p = _run_cli(
        tmp_path, "import-jsonl", "--db", str(db), "--file", str(src), "--json"
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert r["ok"] is True and r["imported"] == 2

    out = tmp_path / "cli-out.jsonl"
    p = _run_cli(
        tmp_path, "export-jsonl", "--db", str(db), "--output", str(out), "--json"
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert r["ok"] is True and r["exported"] == 2

    p = _run_cli(
        tmp_path, "compare-jsonl", "--db", str(db), "--file", str(src), "--json"
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert r["ok"] is True and r["missing"] == 0 and r["extra"] == 0

    p = _run_cli(tmp_path, "verify", "--db", str(db), "--json")
    assert p.returncode == 0, p.stderr


def test_cli_import_quarantine_writes_file(tmp_path: Path) -> None:
    src = _write_jsonl(tmp_path / "q.jsonl", [_healthy(1), "{bad"])
    db = tmp_path / "q.db"
    qf = tmp_path / "q.out"
    p = _run_cli(
        tmp_path,
        "import-jsonl",
        "--db",
        str(db),
        "--file",
        str(src),
        "--quarantine",
        str(qf),
        "--json",
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert r["quarantined"] == 1
    entry = json.loads(qf.read_text(encoding="utf-8").splitlines()[0])
    assert entry["source"] == "q.jsonl"
    assert entry["line"] == 2
    assert entry["reason"] == "parse_error"


def test_cli_import_missing_file_nonzero_no_traceback(tmp_path: Path) -> None:
    db = tmp_path / "err.db"
    p = _run_cli(
        tmp_path,
        "import-jsonl",
        "--db",
        str(db),
        "--file",
        str(tmp_path / "nope.jsonl"),
        "--json",
    )
    assert p.returncode != 0
    assert "Traceback" not in p.stderr
    r = json.loads(p.stdout)
    assert r["ok"] is False


def test_cli_import_jsonl_rejects_agora(tmp_path: Path) -> None:
    src = _write_jsonl(tmp_path / "a.jsonl", [_healthy(1)])
    p = _run_cli(
        tmp_path,
        "import-jsonl",
        "--db",
        str(tmp_path / "a.db"),
        "--file",
        str(src),
        "--agora",
    )
    assert p.returncode != 0


def test_full_cycle_verify_chain_ok(tmp_path: Path) -> None:
    from omo.event_ledger.jsonl_shadow import export_jsonl, import_jsonl

    src = _write_jsonl(tmp_path / "f.jsonl", [_healthy(i) for i in range(1, 6)])
    db = tmp_path / "f.db"
    out = tmp_path / "f-out.jsonl"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        export_jsonl(surface.broker, out)
        chain = surface.broker.verify_chain()
        assert chain["ok"] is True and chain["total"] == 5


# ---------------------------------------------------------------------------
# 批次 3 — 独立审查 REQUEST_CHANGES 反例（TDD RED 先行）
# ---------------------------------------------------------------------------


def test_nan_infinity_quarantined_as_parse_error(tmp_path: Path) -> None:
    """json.loads 接受的 NaN/Infinity 必须按 parse_error 隔离，且不污染后续行。"""
    from omo.event_ledger.jsonl_shadow import import_jsonl

    lines = [
        _healthy(1),
        '{"x": NaN}',
        "[NaN]",
        json.dumps({"id": 2, "kind": "health"}),
    ]
    src = _write_jsonl(tmp_path / "nan.jsonl", lines)
    db = tmp_path / "nan.db"
    qf = tmp_path / "nan-q.jsonl"
    with EventLedgerSurface(db_path=db) as surface:
        r = import_jsonl(surface.broker, src, quarantine_path=qf)
        assert r["healthy"] == 2
        assert r["imported"] == 2
        assert r["quarantined"] == 2
        assert all(e["reason"] == "parse_error" for e in r["quarantine_entries"])
        assert surface.broker.count() == 2
    # quarantine 序列化必须不崩（不得含 NaN 原始值）
    entries = [
        json.loads(line)
        for line in qf.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(entries) == 2
    assert all(entry["reason"] == "parse_error" for entry in entries)


def test_jsonl_shadow_error_inherits_ledger_error() -> None:
    from omo.event_ledger.broker import LedgerError
    from omo.event_ledger.jsonl_shadow import JsonlShadowError

    assert issubclass(JsonlShadowError, LedgerError)


def test_import_quarantine_same_as_source_rejected(tmp_path: Path) -> None:
    """quarantine_path 与源 resolve 同路径 → 领域错误，源不变，DB 不增长。"""
    from omo.event_ledger.jsonl_shadow import JsonlShadowError, import_jsonl

    src = _write_jsonl(tmp_path / "same.jsonl", [_healthy(1), _healthy(2)])
    db = tmp_path / "same.db"
    original = src.read_bytes()
    with EventLedgerSurface(db_path=db) as surface:
        with pytest.raises(JsonlShadowError):
            import_jsonl(surface.broker, src, quarantine_path=src)
        assert src.read_bytes() == original  # 源未被改写
        assert surface.broker.count() == 0  # append 前即拒绝


def test_export_rejects_overwrite_of_foreign_jsonl(tmp_path: Path) -> None:
    """既有非本适配器 projection 的 JSONL → 写前拒绝且字节不变。"""
    from omo.event_ledger.jsonl_shadow import (
        JsonlShadowError,
        export_jsonl,
        import_jsonl,
    )

    src = _write_jsonl(tmp_path / "o.jsonl", [_healthy(1), _healthy(2)])
    db = tmp_path / "o.db"
    foreign = tmp_path / "existing.jsonl"
    foreign_bytes = (json.dumps({"a": 1}) + "\n").encode("utf-8")
    foreign.write_bytes(foreign_bytes)
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        with pytest.raises(JsonlShadowError):
            export_jsonl(surface.broker, foreign)
        assert foreign.read_bytes() == foreign_bytes  # 字节不变
        assert surface.broker.count() == 2  # DB 不增长


def test_export_safe_overwrite_of_own_export(tmp_path: Path) -> None:
    """既有合法本适配器 export → 允许安全覆盖。"""
    from omo.event_ledger.jsonl_shadow import export_jsonl, import_jsonl

    src = _write_jsonl(tmp_path / "ow.jsonl", [_healthy(1), _healthy(2)])
    extra = _write_jsonl(tmp_path / "ow2.jsonl", [_healthy(3)])
    db = tmp_path / "ow.db"
    out = tmp_path / "ow-out.jsonl"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        export_jsonl(surface.broker, out)
        first = out.read_text(encoding="utf-8")
        import_jsonl(surface.broker, extra)
        export_jsonl(surface.broker, out)
        second = out.read_text(encoding="utf-8")
        assert second != first
        assert len([ln for ln in second.splitlines() if ln.strip()]) == 3


def test_compare_with_source_id_matches_import(tmp_path: Path) -> None:
    """import --source-id custom 后 compare 传同 custom 必须 ok。"""
    from omo.event_ledger.jsonl_shadow import compare_jsonl, import_jsonl

    src = _write_jsonl(tmp_path / "custom-name.jsonl", [_healthy(1), _healthy(2)])
    db = tmp_path / "sid.db"
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src, source_id="custom")
        res = compare_jsonl(surface.broker, src, source_id="custom")
        assert res["source"] == "custom"
        assert res["ok"] is True
        assert res["ledger_rows"] == 2
        assert res["missing"] == 0 and res["extra"] == 0


def test_cli_compare_source_id(tmp_path: Path) -> None:
    src = _write_jsonl(tmp_path / "cli-sid.jsonl", [_healthy(1), _healthy(2)])
    db = tmp_path / "cli-sid.db"
    p = _run_cli(
        tmp_path,
        "import-jsonl",
        "--db",
        str(db),
        "--file",
        str(src),
        "--source-id",
        "custom",
        "--json",
    )
    assert p.returncode == 0, p.stderr
    p = _run_cli(
        tmp_path,
        "compare-jsonl",
        "--db",
        str(db),
        "--file",
        str(src),
        "--source-id",
        "custom",
        "--json",
    )
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert r["ok"] is True


def test_cli_compare_mismatch_nonzero(tmp_path: Path) -> None:
    imported = _write_jsonl(tmp_path / "a" / "cmp.jsonl", [_healthy(1)])
    full = _write_jsonl(tmp_path / "b" / "cmp.jsonl", [_healthy(1), _healthy(2)])
    db = tmp_path / "cmp.db"
    p = _run_cli(
        tmp_path, "import-jsonl", "--db", str(db), "--file", str(imported), "--json"
    )
    assert p.returncode == 0, p.stderr
    p = _run_cli(
        tmp_path, "compare-jsonl", "--db", str(db), "--file", str(full), "--json"
    )
    assert p.returncode != 0
    assert "Traceback" not in p.stderr
    r = json.loads(p.stdout)
    assert r["ok"] is False and r["missing"] == 1


def test_cli_missing_source_does_not_create_db(tmp_path: Path) -> None:
    db = tmp_path / "nodb.db"
    p = _run_cli(
        tmp_path,
        "import-jsonl",
        "--db",
        str(db),
        "--file",
        str(tmp_path / "missing.jsonl"),
        "--json",
    )
    assert p.returncode != 0
    assert "Traceback" not in p.stderr
    assert not db.exists()  # 缺失源不能创建 DB


def test_cli_export_rejects_foreign_overwrite(tmp_path: Path) -> None:
    src = _write_jsonl(tmp_path / "e.jsonl", [_healthy(1)])
    db = tmp_path / "e.db"
    p = _run_cli(
        tmp_path, "import-jsonl", "--db", str(db), "--file", str(src), "--json"
    )
    assert p.returncode == 0, p.stderr
    out = tmp_path / "existing.jsonl"
    out_bytes = b'{"legacy": true}\n'
    out.write_bytes(out_bytes)
    p = _run_cli(
        tmp_path, "export-jsonl", "--db", str(db), "--output", str(out), "--json"
    )
    assert p.returncode != 0
    assert "Traceback" not in p.stderr
    r = json.loads(p.stdout)
    assert r["ok"] is False
    assert out.read_bytes() == out_bytes  # 字节不变


def test_export_rejects_fake_projection_only_overwrite(tmp_path: Path) -> None:
    """仅伪装 projection 字段的既有文件不是本适配器合法导出 → 拒绝覆盖且字节不变。"""
    from omo.event_ledger.jsonl_shadow import (
        JsonlShadowError,
        export_jsonl,
        import_jsonl,
    )

    src = _write_jsonl(tmp_path / "fp.jsonl", [_healthy(1)])
    db = tmp_path / "fp.db"
    out = tmp_path / "fake.jsonl"
    out_bytes = b'{"projection": "jsonl-shadow/v1", "valuable": "keep"}\n'
    out.write_bytes(out_bytes)
    with EventLedgerSurface(db_path=db) as surface:
        import_jsonl(surface.broker, src)
        with pytest.raises(JsonlShadowError):
            export_jsonl(surface.broker, out)
        assert out.read_bytes() == out_bytes  # 字节不变
