"""Documents 域变更留痕 —— 让「谁在什么时候动了这个域」进事件账本。

⚠⚠⚥⚠▣ **为什么有这个东西**（§5.165 · USER-ACTIONS #117）——
⚠ 知识域的存量变动**没有账** ⇒ ⇒ ⚠ 事后追查只能靠【快照 / 时间戳 / 目录 mtime】反推
⚠ ⇒ ⇒ ⚠ §5.159 实测两次作业改了 `~/Documents/@工作文档`（⚠ 20 个目录 mtime 变更）
⚠ ⇒ ⇒ ⚠ **事件账本 0 行** ⇒ ⇒ ⚠ **那些改动一笔都没进账**
⇒ ⇒ ✅ **⇒ 本模块把账放回产生它的地方**：⚠ **作业跑完 ⇒ ⇒ 往事件账本写一条**

⚠⚠⚥⚠▣ **三条纪律**——
① ⚠ **失败不许挡住作业**（⚠ 留痕是旁路 ⇒ ⇒ 写不进去只报，不抛）
② ⚠ **只记【声明过的写入面】＋ 作业身份**（⚠ 不许在这里做目录 diff ⇒ ⇒ 那太贵）
③ ⚠ **一条作业一条事件**（⚠ 幂等键＝作业身份 ＋ 开始时刻 ⇒ ⇒ 重跑不重复记）

⚠ **它记什么、不记什么**——
⚠ **记**：⚠ `job_id` · ⚠ `domain_id` · ⚠ **声明的写入面**（`writes`）· ⚠ 状态 · ⚠ 退出码 · ⚠ 起止时刻
⚠ **不记**：⚠ **具体哪些文件变了**（⚠ 那由【逐文件基线】那一侧负责 ⇒ ⇒ 两侧并排才「逐条对得上」）

用法：
    from lib.documents_change_ledger import record_domain_change
    record_domain_change(job_id=..., domain_id=..., writes=[...],
                          status="succeeded", exit_code=0)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]

#: ⚠ **事件类型**（⚠ 独立的事件类型 ⇒ ⇒ 读者能只取这一族）
EVENT_TYPE = "Documents.DomainChange.v1"

#: ⚠ **生产者标识**（⚠ 写进 `producer` 列 ⇒ ⇒ 可按它筛）
PRODUCER = "omo-documents-domain-owner-job"

#: ⚠ **默认 principal**（⚠ 与 `omo` 侧那条 canonicalizer 同源）
DEFAULT_PRINCIPAL_ID = "xiamingxing"


def _omo_src() -> str:
    return str(ROOT / "projects" / "omo" / "src")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_principal_id() -> str:
    """⚠ **principal 走仓内那条 canonicalizer**（⚠ 不许自己拼）。"""
    try:
        ssot_dir = str(ROOT / "bin" / "ssot")
        if ssot_dir not in sys.path:
            sys.path.insert(0, ssot_dir)
        from _principal_id import principal_id_from_env  # type: ignore

        return str(principal_id_from_env(os.environ.get("OMO_PRINCIPAL_ID", DEFAULT_PRINCIPAL_ID)))
    except Exception:  # noqa: BLE001 —— 留痕是旁路 ⇒ ⇒ 取不到就退回默认值
        return os.environ.get("OMO_PRINCIPAL_ID", DEFAULT_PRINCIPAL_ID)


def build_payload(
    *,
    job_id: str,
    domain_id: str,
    writes: Iterable[str] | None,
    status: str,
    exit_code: int | None,
    started_at: str | None = None,
    finished_at: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """⚠ **事件载荷**（⚠ 形状显式 ⇒ ⇒ 读者能按字段判，不必猜）。"""
    payload: dict[str, Any] = {
        "job_id": job_id,
        "domain_id": domain_id,
        "writes": sorted(str(w) for w in (writes or [])),
        "status": status,
        "exit_code": exit_code,
        "started_at": started_at,
        "finished_at": finished_at or _now_iso(),
    }
    if detail:
        payload["detail"] = detail
    return payload


def record_domain_change(
    *,
    job_id: str,
    domain_id: str,
    writes: Iterable[str] | None = None,
    status: str = "succeeded",
    exit_code: int | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    detail: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """⚠ **写一条变更事件**（⚠ **失败只报不抛** —— ⚠ 留痕不许挡住作业）。

    :returns: ⚠ `{"recorded": bool, ...}`（⚠ 写没写进去**必须说清** ⇒ ⇒ 不许折成「没有变化」）
    """
    payload = build_payload(
        job_id=job_id,
        domain_id=domain_id,
        writes=writes,
        status=status,
        exit_code=exit_code,
        started_at=started_at,
        finished_at=finished_at,
        detail=detail,
    )
    receipt: dict[str, Any] = {"recorded": False, "payload": payload}
    try:
        omo_src = _omo_src()
        if omo_src not in sys.path:
            sys.path.insert(0, omo_src)
        from omo.event_ledger.surface import EventLedgerSurface

        surface = EventLedgerSurface(db_path=db_path) if db_path else EventLedgerSurface()
        # ⚠ **幂等键**＝作业身份 ＋ 开始时刻 ⇒ ⇒ 同一次作业重跑不会重复记
        idem = "domchange-%s-%s-%s" % (
            domain_id,
            job_id,
            (started_at or "").replace(":", "").replace("-", ""),
        )
        result = surface.append(
            event_type=EVENT_TYPE,
            producer=PRODUCER,
            principal_id=canonical_principal_id(),
            correlation_id="domchange-%s" % domain_id,
            idempotency_key=idem,
            payload=payload,
            evidence_uri="documents-domain-owner-job://%s" % job_id,
        )
        receipt["recorded"] = True
        receipt["sequence"] = result.sequence
        receipt["event_id"] = result.event_id
        receipt["db_path"] = result.db_path
    except Exception as exc:  # noqa: BLE001 —— ⚠ 留痕是旁路 ⇒ ⇒ 写不进去只报
        receipt["error"] = "%s: %s" % (type(exc).__name__, exc)
    return receipt


def main(argv: list[str] | None = None) -> int:
    """⚠ **命令行入口**（⚠ 手动补记一条 ⇒ ⇒ 作业自己没留痕时可以人工兜底）。"""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--domain-id", required=True)
    parser.add_argument("--status", default="succeeded")
    parser.add_argument("--exit-code", type=int, default=None)
    parser.add_argument("--write", action="append", dest="writes", default=[])
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)

    receipt = record_domain_change(
        job_id=args.job_id,
        domain_id=args.domain_id,
        writes=args.writes,
        status=args.status,
        exit_code=args.exit_code,
        db_path=args.db,
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt.get("recorded") else 1


if __name__ == "__main__":
    raise SystemExit(main())
