"""Documents 域变更留痕的合同测试（§5.165 · USER-ACTIONS #117）。

⚠⚠⚥ **这个模块在防什么**——
⚠ 知识域的存量变动**没有账** ⇒ ⇒ ⚠ §5.159 实测两次作业改了 `~/Documents/@工作文档`
⇒ ⇒ ⚠ **事件账本 0 行** ⇒ ⇒ ⚠ 那些改动一笔都没进账
⇒ ⇒ ⚠ 本模块让作业跑完就写一条 ⇒ ⇒ **下一次变动可追查**

⚠⚠⚥⚠▣ **三条纪律**（⚠ 本测试逐条钉住）——
① ⚠ **失败不许挡住作业**（⚠ 留痕是旁路 ⇒ ⇒ 写不进去只报，不抛）
② ⚠ **一条作业一条事件**（⚠ 幂等键＝域 ＋ 作业 ＋ 开始时刻）
③ ⚠ **自检只写临时库**（⚠ **真账本是 append-only ⇒ ⇒ 往里面塞测试行就是编造事实**）
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.documents_change_ledger import (  # noqa: E402
    EVENT_TYPE,
    PRODUCER,
    build_payload,
    record_domain_change,
)


def _rows(db_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute("SELECT * FROM event_log ORDER BY sequence"))
    finally:
        conn.close()


def test_record_domain_change_writes_one_row(tmp_path: Path) -> None:
    """⚠ **一条作业 ⇒ ⇒ 一条事件**。"""
    db = tmp_path / "ledger.sqlite3"
    receipt = record_domain_change(
        job_id="documents-weijian-controller-shadow",
        domain_id="work-weijian",
        writes=["@工作文档/卫健委/_control"],
        status="succeeded",
        exit_code=0,
        db_path=db,
    )
    assert receipt["recorded"] is True
    rows = _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["event_type"] == EVENT_TYPE
    assert row["producer"] == PRODUCER
    payload = json.loads(row["payload_json"])
    assert payload["job_id"] == "documents-weijian-controller-shadow"
    assert payload["domain_id"] == "work-weijian"
    assert payload["status"] == "succeeded"
    assert payload["exit_code"] == 0


def test_the_payload_carries_the_declared_write_surface(tmp_path: Path) -> None:
    """⚠ **声明过的写入面必须进账**（⚠ 那是「动了什么」的声明侧）。"""
    db = tmp_path / "ledger.sqlite3"
    record_domain_change(
        job_id="job-a",
        domain_id="work-docs",
        writes=["@工作文档/_control", "@工作文档/_runtime"],
        status="succeeded",
        exit_code=0,
        db_path=db,
    )
    payload = json.loads(_rows(db)[0]["payload_json"])
    assert payload["writes"] == ["@工作文档/_control", "@工作文档/_runtime"]


def test_a_failing_write_is_reported_but_never_raises(tmp_path: Path) -> None:
    """⚠ **失败不许挡住作业**（⚠ 留痕是旁路）。"""
    # ⚠ **父路径是一个【文件】** ⇒ ⇒ 建不出目录 ⇒ ⇒ 写必然失败（⚠ 真实失败形状）
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    receipt = record_domain_change(
        job_id="job-b",
        domain_id="work-docs",
        status="succeeded",
        exit_code=0,
        db_path=blocker / "ledger.sqlite3",
    )
    assert receipt["recorded"] is False
    assert receipt.get("error")


def test_the_idempotency_key_is_derived_from_the_job_identity(tmp_path: Path) -> None:
    """⚠ **同一次作业重跑不重复记**（⚠ 幂等键＝域 ＋ 作业 ＋ 开始时刻）。"""
    db = tmp_path / "ledger.sqlite3"
    for _ in range(2):
        record_domain_change(
            job_id="job-c",
            domain_id="work-docs",
            status="succeeded",
            exit_code=0,
            started_at="2026-10-31T08:52:13+00:00",
            db_path=db,
        )
    rows = _rows(db)
    assert len(rows) == 1
    assert rows[0]["idempotency_key"] == "domchange-work-docs-job-c-20261031T085213+0000"


def test_the_writes_are_sorted(tmp_path: Path) -> None:
    """⚠ **写入面排序**（⚠ 两次同一次作业的载荷必须逐字相同）。"""
    payload = build_payload(
        job_id="job-d",
        domain_id="work-docs",
        writes=["b", "a"],
        status="succeeded",
        exit_code=0,
    )
    assert payload["writes"] == ["a", "b"]


def test_an_unknown_domain_is_still_recorded(tmp_path: Path) -> None:
    """⚠ **域归属拿不到 ⇒ ⇒ 也要写**（⚠ 不许因为「不知道」就整条丢掉）。"""
    db = tmp_path / "ledger.sqlite3"
    receipt = record_domain_change(
        job_id="job-e",
        domain_id="unknown-domain",
        status="failed",
        exit_code=2,
        db_path=db,
    )
    assert receipt["recorded"] is True
    payload = json.loads(_rows(db)[0]["payload_json"])
    assert payload["domain_id"] == "unknown-domain"
    assert payload["status"] == "failed"


def test_the_real_ledger_is_never_touched_by_this_module() -> None:
    """⚠ **自检只写临时库**（⚠ 真账本是 append-only ⇒ ⇒ 塞测试行＝编造事实）。"""
    source = (ROOT / "lib" / "documents_change_ledger.py").read_text(encoding="utf-8")
    # ⚠ 模块里不许出现「默认写真账本」的路径拼接（⚠ 调用方必须显式给 db_path 或走 surface 的解析）
    assert "event-ledger.sqlite3" not in source, (
        "⚠⚠ 模块里不许硬写真账本路径 —— ⚠ 真账本是 append-only ⇒ ⇒ 塞测试行就是编造事实"
    )
