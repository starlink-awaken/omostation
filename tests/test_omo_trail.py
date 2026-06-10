"""Tests for omo trail (Round 12 P0+P1 — AppendOnlyLog 第 7 个 consumer).

覆盖:
  1. record_step 走 AppendOnlyLog 写 .jsonl (含 7 字段, Z-suffix ts)
  2. read_trail 倒序 + actor/action 过滤
  3. Pydantic schema 校验 (status enum, 字段非空)
  4. CLI `omo trail record` / `omo trail show` 子进程可调
  5. 默认路径 = .omo/_knowledge/omo-trail.jsonl
  6. 第 7 个 schema 在 SCHEMA_REGISTRY 中
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


# ── 1. record_step 基础: AppendOnlyLog + Z-suffix ts + 7 字段 ──────


def test_record_step_writes_seven_fields(tmp_path):
    """record_step 走 AppendOnlyLog, 写 1 条含 7 字段 (ts, actor, action, target, status, duration_ms, parent_step_id) 的 record."""
    from omo.omo_trail import record_step

    log_path = tmp_path / "trail.jsonl"
    rec = record_step(
        actor="user",
        action="edit",
        target="omo_trail.py",
        status="ok",
        duration_ms=120,
        parent_step_id=None,
        log_path=log_path,
    )

    # record dict 含 7 字段
    assert rec["actor"] == "user"
    assert rec["action"] == "edit"
    assert rec["target"] == "omo_trail.py"
    assert rec["status"] == "ok"
    assert rec["duration_ms"] == 120
    assert rec["parent_step_id"] == ""  # None → ""
    assert rec["ts"].endswith("Z"), "ts must end with Z (omo_audit convention)"

    # 落盘: 1 行 JSONL
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    on_disk = json.loads(lines[0])
    assert on_disk == rec, "落盘内容与返回 record 一致"


# ── 2. read_trail 倒序 + 过滤 ──────────────────────────────


def test_read_trail_reverse_and_filters(tmp_path):
    """read_trail 默认倒序 (最新在前), 支持 actor / action 过滤."""
    from omo.omo_trail import record_step, read_trail

    log_path = tmp_path / "trail.jsonl"

    # 写 5 条 (混合 actor/action)
    record_step(actor="user", action="edit", target="a.py", log_path=log_path)
    record_step(actor="agent:foo", action="exec", target="git status", log_path=log_path)
    record_step(actor="user", action="read", target="b.py", log_path=log_path)
    record_step(actor="agent:foo", action="edit", target="c.py", log_path=log_path)
    record_step(actor="user", action="edit", target="d.py", log_path=log_path)

    # 全读 (倒序): 5 条, 最新 (target=d.py) 在前
    all_steps = read_trail(log_path=log_path)
    assert len(all_steps) == 5
    assert all_steps[0]["target"] == "d.py", "最新应在最前"
    assert all_steps[-1]["target"] == "a.py", "最旧应在最后"

    # actor=user 过滤: 3 条
    user_steps = read_trail(log_path=log_path, actor="user")
    assert len(user_steps) == 3
    assert all(s["actor"] == "user" for s in user_steps)
    # 倒序: d.py → b.py → a.py
    assert [s["target"] for s in user_steps] == ["d.py", "b.py", "a.py"]

    # actor=agent:foo + action=edit: 1 条 (target=c.py)
    agent_edits = read_trail(log_path=log_path, actor="agent:foo", action="edit")
    assert len(agent_edits) == 1
    assert agent_edits[0]["target"] == "c.py"

    # limit=2: 仅前 2 条
    limited = read_trail(log_path=log_path, limit=2)
    assert len(limited) == 2
    assert limited[0]["target"] == "d.py"
    assert limited[1]["target"] == "c.py"


# ── 3. Pydantic schema 校验 ────────────────────────────────


def test_pydantic_schema_in_registry_and_validates():
    """OmoTrailRecord 在 SCHEMA_REGISTRY, 且能 model_validate."""
    from omo.omo_io_schemas import SCHEMA_REGISTRY, OmoTrailRecord

    # 第 7 个
    assert "omo_trail" in SCHEMA_REGISTRY
    assert SCHEMA_REGISTRY["omo_trail"] is OmoTrailRecord

    # 合法 record
    rec = OmoTrailRecord(
        ts="2026-06-09T12:00:00Z",
        actor="user",
        action="edit",
        target="x.py",
        status="ok",
        duration_ms=42,
    )
    assert rec.actor == "user"
    assert rec.parent_step_id == ""  # 默认值

    # 非法 status 抛 ValidationError
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        OmoTrailRecord(
            ts="2026-06-09T12:00:00Z",
            actor="user",
            action="edit",
            target="x.py",
            status="unknown",  # type: ignore[arg-type]
        )

    # 非 Z 结尾 ts 抛 (ZTimestampModel 校验)
    with pytest.raises(pydantic.ValidationError):
        OmoTrailRecord(
            ts="2026-06-09T12:00:00+00:00",  # 缺 Z
            actor="user",
            action="edit",
            target="x.py",
            status="ok",
        )


def test_append_only_log_writes_via_schema_rejects_drift(tmp_path):
    """AppendOnlyLog.append(..., schema=OmoTrailRecord) 拒 drift record."""
    from omo.omo_io import AppendOnlyLog
    from omo.omo_io_schemas import OmoTrailRecord
    import pydantic

    log_path = tmp_path / "trail.jsonl"
    log = AppendOnlyLog(log_path)

    # 合法: schema 校验通过
    good = {"ts": "2026-06-09T01:00:00Z", "actor": "u", "action": "a", "target": "t", "status": "ok", "duration_ms": 0, "parent_step_id": ""}
    log.append(good, schema=OmoTrailRecord)

    # 非法: status 不在 enum → 抛 ValidationError
    bad = {"ts": "2026-06-09T01:00:00Z", "actor": "u", "action": "a", "target": "t", "status": "wrong", "duration_ms": 0, "parent_step_id": ""}
    with pytest.raises(pydantic.ValidationError):
        log.append(bad, schema=OmoTrailRecord)

    # 落盘: 仅 1 条 (good)
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1


# ── 4. CLI 子进程调用 ────────────────────────────────────────


def test_cli_record_subprocess(tmp_path):
    """`python -m omo.omo_trail record` 子进程可调, 写 1 条结构化 trail step."""
    log_path = tmp_path / "cli-trail.jsonl"
    r = subprocess.run(
        [
            sys.executable, "-m", "omo.omo_trail", "record",
            "--actor", "user",
            "--action", "edit",
            "--target", "omo_trail.py",
            "--status", "ok",
            "--duration-ms", "250",
            "--log", str(log_path),
        ],
        capture_output=True, text=True, timeout=15,
        cwd=str(OMO_SRC.parent.parent),
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "✅ trail step recorded" in r.stdout

    # 验证 log 写 1 条 7-字段 record
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["actor"] == "user"
    assert rec["action"] == "edit"
    assert rec["target"] == "omo_trail.py"
    assert rec["status"] == "ok"
    assert rec["duration_ms"] == 250
    assert rec["parent_step_id"] == ""
    assert rec["ts"].endswith("Z")


def test_cli_show_subprocess(tmp_path):
    """`python -m omo.omo_trail show` 倒序显示 trail."""
    log_path = tmp_path / "cli-show.jsonl"
    # 先写 3 条
    for tgt in ("alpha.py", "beta.py", "gamma.py"):
        subprocess.run(
            [
                sys.executable, "-m", "omo.omo_trail", "record",
                "--actor", "user",
                "--action", "edit",
                "--target", tgt,
                "--log", str(log_path),
            ],
            check=True, capture_output=True, text=True, timeout=10,
            cwd=str(OMO_SRC.parent.parent),
        )

    # show --limit 2
    r = subprocess.run(
        [
            sys.executable, "-m", "omo.omo_trail", "show",
            "--limit", "2",
            "--log", str(log_path),
        ],
        capture_output=True, text=True, timeout=10,
        cwd=str(OMO_SRC.parent.parent),
    )
    assert r.returncode == 0
    assert "gamma.py" in r.stdout  # 最新在前
    assert "beta.py" in r.stdout
    # alpha.py 在 limit=2 截断外, 不在表里
    assert "alpha.py" not in r.stdout
    assert "Total: 2 steps" in r.stdout


def test_cli_help_renders():
    """omo trail --help 应列出 record + show 子命令."""
    r = subprocess.run(
        [sys.executable, "-m", "omo.omo_trail", "--help"],
        capture_output=True, text=True, timeout=10,
        cwd=str(OMO_SRC.parent.parent),
    )
    assert r.returncode == 0
    assert "record" in r.stdout
    assert "show" in r.stdout


# ── 5. 默认路径 + 第 7 个 consumer 拓扑 ─────────────────────


def test_default_trail_path():
    """不传 --log 时落 .omo/_knowledge/omo-trail.jsonl (默认)."""
    from omo.omo_trail import DEFAULT_TRAIL_PATH
    assert ".omo" in str(DEFAULT_TRAIL_PATH)
    assert "_knowledge" in str(DEFAULT_TRAIL_PATH)
    assert DEFAULT_TRAIL_PATH.name == "omo-trail.jsonl"


def test_trail_uses_append_only_log():
    """验证 record_step 内部用 AppendOnlyLog (而非直接 open+write)."""
    from omo.omo_trail import record_step
    import inspect

    src = inspect.getsource(record_step)
    assert "AppendOnlyLog" in src, "record_step should use AppendOnlyLog abstraction"
    assert "schema=OmoTrailRecord" in src, "record_step should pass schema= for Pydantic 校验"


def test_seventh_consumer_registered():
    """验证 omo_trail 是 SCHEMA_REGISTRY 第 7 个 key (Round 12 P0 拓扑)."""
    from omo.omo_io_schemas import SCHEMA_REGISTRY

    expected_keys = {
        "omo_audit", "omo_bos_metrics", "omo_sync", "omo_alert",
        "omo_event", "omo_history", "omo_trail",
    }
    actual_keys = set(SCHEMA_REGISTRY.keys())
    assert expected_keys.issubset(actual_keys), (
        f"missing: {expected_keys - actual_keys}"
    )
    assert len(SCHEMA_REGISTRY) >= 7, f"expected ≥ 7 consumers, got {len(SCHEMA_REGISTRY)}"
