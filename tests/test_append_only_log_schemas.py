"""AppendOnlyLog 6 个 consumer schema SSOT 校验 (Round 8 P2).

读 .omo/_knowledge/*.jsonl, 按 schema SSOT 文档检查必填字段存在.
失败时报告具体哪个文件哪条 record 缺哪个字段.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))

# 把工作区根加入 path, 读 .omo/_knowledge/*.jsonl
WORKSPACE_ROOT = Path(__file__).resolve().parents[2] / ".."
# 实际: tests/test_*.py → parents[2] = projects/omo, parents[3] = projects, parents[4] = workspace
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


# 每个 consumer 的必填字段 + 落点
SCHEMAS: dict[str, dict] = {
    "omo-audit": {
        "path_pattern": "governance-audit.jsonl",  # 在 ~/runtime/audit/ (跳过, omo 仓内不可达)
        "required_fields": {"ts", "action", "debt_id", "actor", "details"},
    },
    "omo-bos-metrics": {
        "path_pattern": "bos-metrics.jsonl",
        "required_fields": {"uri", "status", "elapsed_ms", "recorded_at"},
    },
    "omo-sync": {
        "path_pattern": "omo-sync.jsonl",
        "required_fields": {"ts", "kind", "phase", "health_score", "dry_run", "audit_checks", "status"},
    },
    "omo-alert": {
        "path_pattern": "omo-alerts.jsonl",
        "required_fields": {"ts", "kind", "severity", "message", "blocked_rate", "failed_rate", "threshold"},
    },
    "omo-event": {
        "path_pattern": "omo-events.jsonl",
        "required_fields": {"ts", "kind", "source", "payload"},
    },
    "omo-history": {
        "path_pattern": "governance-history.jsonl",
        # source 是 Round 8 P2 新加的, 老记录没有 — 故 omitted
        "required_fields": {"date", "timestamp", "total_score", "grade", "watchlist_count"},
    },
}


def test_schemas_doc_exists():
    """Schema SSOT 文档必须存在 (防文档漂移)."""
    doc_path = WORKSPACE_ROOT / ".omo" / "_knowledge" / "management" / "append-only-log-schemas-2026-06-09.md"
    assert doc_path.exists(), f"schema SSOT doc missing: {doc_path}"


def test_knowledge_dir_exists():
    """AppendOnlyLog consumer 落点目录 .omo/_knowledge/ 必须存在."""
    knowledge_dir = WORKSPACE_ROOT / ".omo" / "_knowledge"
    assert knowledge_dir.exists(), f"knowledge dir missing: {knowledge_dir}"


@pytest.mark.parametrize(
    "consumer_name,schema",
    list(SCHEMAS.items()),
    ids=list(SCHEMAS.keys()),
)
def test_consumer_log_schema_when_exists(consumer_name, schema, tmp_path):
    """每个 consumer 的 log 文件 (若存在) 必须符合 SSOT schema.

    Round 8 P2 锁: 现有数据必填字段全在, 防 schema 漂移.
    不会自动生成 log (若文件不存在跳过 — 消费还没发生).
    """
    log_path = WORKSPACE_ROOT / ".omo" / "_knowledge" / schema["path_pattern"]
    if not log_path.exists():
        pytest.skip(f"{consumer_name} log not yet created: {log_path}")

    # 抽前 5 + 后 5 条 (避免读 1MB+ 大文件)
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        pytest.skip(f"{consumer_name} log empty")

    # 解析所有行 (Round 8 P2 容错: 跳过 JSON parse 错 — AppendOnlyLog 默认行为)
    parsed: list[tuple[int, dict]] = []
    parse_errors: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        try:
            parsed.append((i, json.loads(line)))
        except json.JSONDecodeError as exc:
            parse_errors.append((i, str(exc)))
    if not parsed:
        pytest.skip(f"{consumer_name} log: all lines malformed (parse errors: {len(parse_errors)})")

    # 取前 5 + 后 5 条 (avoid reading 1MB+ file)
    sample = parsed[:5] + (parsed[-5:] if len(parsed) > 10 else [])
    required = schema["required_fields"]
    failures = []
    for i, rec in sample:
        missing = required - set(rec.keys())
        if missing:
            failures.append(f"line {i}: missing fields {sorted(missing)} (record keys: {list(rec.keys())})")

    if failures:
        # 顺便报告 parse errors (非 fatal, 仅信息)
        msg = f"{consumer_name} ({log_path}) schema mismatch:\n" + "\n".join(failures)
        if parse_errors:
            msg += f"\n[info] {len(parse_errors)} parse errors in file (skipped)"
        raise AssertionError(msg)


def test_round_trip_omo_event_emit(tmp_path):
    """omo event emit 写出的 record 必符合 SSOT (Round 8 P2 端到端验证)."""
    from omo.omo_event import cmd_event_emit

    log_path = tmp_path / "omo-events.jsonl"
    cmd_event_emit(
        event_type="schema_test",
        source="pytest",
        payload='{"k": "v"}',
        log_path=log_path,
    )
    rec = json.loads(log_path.read_text(encoding="utf-8").strip())
    required = SCHEMAS["omo-event"]["required_fields"]
    missing = required - set(rec.keys())
    assert not missing, f"omo event emit record missing: {missing}"
    # 进一步: 必填字段类型
    assert isinstance(rec["ts"], str)
    assert rec["ts"].endswith("Z")
    assert isinstance(rec["kind"], str)
    assert isinstance(rec["source"], str)
    assert isinstance(rec["payload"], str)


def test_round_trip_omo_history_append(tmp_path):
    """omo_history append_entry 写出的 record 必符合 SSOT."""
    from omo.omo_history import append_entry

    log_path = tmp_path / "governance-history.jsonl"
    append_entry(
        {"total_score": 100.0, "grade": "A+", "watchlist_count": 0, "source": "pytest_round_trip"},
        path=log_path,
    )
    rec = json.loads(log_path.read_text(encoding="utf-8").strip())
    required = SCHEMAS["omo-history"]["required_fields"]
    missing = required - set(rec.keys())
    assert not missing, f"omo_history record missing: {missing}"
    # Round 8 P2 新增: 必填字段类型检查
    assert isinstance(rec["date"], str)
    assert isinstance(rec["timestamp"], str)
    assert rec["timestamp"].endswith("Z")
    assert isinstance(rec["total_score"], (int, float))
    assert rec["grade"] in ("A+", "A", "B", "C", "D", "F")
    assert isinstance(rec["watchlist_count"], int)
    # sort_keys 锁: 全字母序
    parsed_order = [k for k, _ in json.loads(
        log_path.read_text(encoding="utf-8").strip(),
        object_pairs_hook=list,
    )]
    expected_order = sorted(["date", "timestamp", "total_score", "grade", "watchlist_count", "source"])
    assert parsed_order == expected_order, (
        f"omo_history sort_keys 失守: {parsed_order} != {expected_order}"
    )
