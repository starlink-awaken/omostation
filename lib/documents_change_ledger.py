"""Documents 域变更留痕 —— 让「谁在什么时候动了这个域」进事件账本。

⚠⚠⚥⚠▣ **为什么有这个东西**（§5.165 · USER-ACTIONS #117）——
⚠ 知识域的存量变动**没有账** ⇒ ⇒ ⚠ 事后追查只能靠【快照 / 时间戳 / 目录 mtime】反推
⚠ ⇒ ⇒ ⚠ §5.159 实测两次作业改了 `~/Documents/@工作文档`（⚠ 20 个目录 mtime 变更）
⚠ ⇒ ⇒ ⚠ **事件账本 0 行** ⇒ ⇒ ⚠ **那些改动一笔都没进账**
⇒ ⇒ ✅ **⇒ 本模块把账放回产生它的地方**：⚠ **作业跑完 ⇒ ⇒ 往事件账本写一条**

⚠⚠⚥⚠▣ **四条纪律**——
① ⚠ **失败不许挡住作业**（⚠ 留痕是旁路 ⇒ ⇒ 写不进去只报，不抛）
② ⚠ **只记【声明过的写入面】＋ 作业身份**（⚠ 不许在这里做目录 diff ⇒ ⇒ 那太贵）
③ ⚠ **一条作业一条事件**（⚠ 幂等键＝作业身份 ＋ 开始时刻 ⇒ ⇒ 重跑不重复记）
④ ⚠⚠⚥ **账本路径必须【显式给】**（⚠ `db_path` 是**必填** ⇒ ⇒ 不许有「默认落点」）
   ⇒ ⇒ ⚠ **「默认落点」就是往真账本塞测试行的入口**（⚠ 真账本是 append-only
   ⇒ ⇒ ⚠ 塞进去的行 = 编造的事实 ⇒ ⇒ ⚠ 且**删不掉**）

⚠⚠⚥⚠▣ **④ 这条纪律是怎么来的**（⚠ §5.165 的实测自踩）——
   ⚠ 既有测试（`tests/test_documents_domain_owner_job.py`）**以子进程调作业**
   ⇒ ⇒ ⚠ 而作业若自己解析账本落点 ⇒ ⇒ ⚠ **它解析到的是真账本**
   ⇒ ⇒ ⚠ 实测：**跑一次测试 ⇒ ⇒ 真账本多了 5 条测试留痕**（⚠ 4 个用例，其中一个跑两次）
   ⇒ ⇒ ⚠ **那 5 条是编造的事实**（⚠ 没有任何作业真的动过那些域）
   ⇒ ⇒ ✅ **⇒ 账本落点由【调用方】点名**（⚠ `db_path` 必填 ＋ `OMO_EVENT_LEDGER_DB` 是隔离面）

⚠ **它记什么、不记什么**——
⚠ **记**：⚠ `job_id` · ⚠ `domain_id` · ⚠ **声明的写入面**（`writes`）· ⚠ 状态 · ⚠ 退出码 · ⚠ 起止时刻
⚠ **不记**：⚠ **具体哪些文件变了**（⚠ 那由【逐文件基线】那一侧负责 ⇒ ⇒ 两侧并排才「逐条对得上」）

用法：
    from lib.documents_change_ledger import record_domain_change, resolve_ledger_path
    record_domain_change(job_id=..., domain_id=..., writes=[...],
                          status="succeeded", exit_code=0,
                          db_path=resolve_ledger_path())
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: ⚠ **事件类型**（⚠ 独立的事件类型 ⇒ ⇒ 读者能只取这一族）
EVENT_TYPE = "Documents.DomainChange.v1"

#: ⚠ **生产者标识**（⚠ 写进 `producer` 列 ⇒ ⇒ 可按它筛）
PRODUCER = "omo-documents-domain-owner-job"

#: ⚠ **默认 principal**（⚠ 与 `omo` 侧那条 canonicalizer 同源）
DEFAULT_PRINCIPAL_ID = "xiamingxing"


def _omo_src() -> str:
    return str(ROOT / "projects" / "omo" / "src")


def _omo_paths():
    """⚠ **仓内那一份路径真源**（⚠ 不许自己拼 `runtime/omo/…`）。

    ⚠ **为什么必须引它**：⚠ 账本相对路径（`LEDGER_RELATIVE`）与那个 env 名
    （`LEDGER_DB_ENV`）在 `omo_paths` 里是**唯一一份** ⇒ ⇒ 手抄一份就会漂
    ⇒ ⇒ ⚠ 而漂了的后果是「写去另一个账本」（⚠ 静默 ⇒ ⇒ 事实没进账）。
    """
    omo_src = _omo_src()
    if omo_src not in sys.path:
        sys.path.insert(0, omo_src)
    import omo.omo_paths as paths  # type: ignore

    return paths


def resolve_ledger_path(explicit=None, environ=None) -> Path:
    """⚠ **账本落点**（⚠ 三级优先级 ⇒ ⇒ 每一级都有明确理由）。

    ⚠ ① `explicit`（⚠ 调用方点名给的那个 ⇒ ⇒ 最高优先）
    ⚠ ② `OMO_EVENT_LEDGER_DB`（⚠ 仓内那一条 env 面 ⇒ ⇒ **测试的隔离面**）
    ⚠ ③ `<state root>` ＋ 仓内那一份 `LEDGER_RELATIVE`
       （⚠ `state root` ＝ `OMOSTATION_STATE_ROOT` env ⇒ ⇒ 未声明时＝仓根
       ⇒ ⇒ **与仓内 `event_ledger_path()` 逐字同契约**）

    ⚠⚠⚥ **为什么要有 ②**：⚠ 真账本是 **append-only** ⇒ ⇒ **往里面塞测试行就是编造事实**
    ⇒ ⇒ ⚠ 而既有测试**以子进程调作业** ⇒ ⇒ ⚠ 作业不留痕时测试是绿的
    ⇒ ⇒ ⚠ 留痕时测试**污染真账本**（⚠ 实测 5 条）
    ⇒ ⇒ ✅ **⇒ 落点由调用方点名**（⚠ ② 就是那个点名 ⇒ ⇒ **测试面**）

    :param environ: ⚠ **可注入的环境**（⚠ 给了它 ⇒ ⇒ **只认它** ⇒ ⇒ 不许回落去读真环境）
    """
    env = environ if environ is not None else os.environ
    if explicit:
        return Path(explicit).expanduser().absolute()
    paths = _omo_paths()
    declared = env.get(paths.LEDGER_DB_ENV)
    if declared:
        return Path(declared).expanduser().absolute()
    state_root = env.get(paths.STATE_ROOT_ENV)
    base = Path(state_root).expanduser().absolute() if state_root else paths.WORKSPACE_ROOT
    return base / paths.LEDGER_RELATIVE


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
    db_path: str | Path,
    writes: Iterable[str] | None = None,
    status: str = "succeeded",
    exit_code: int | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """⚠ **写一条变更事件**（⚠ **失败只报不抛** —— ⚠ 留痕不许挡住作业）。

    ⚠⚠⚥ **`db_path` 是【必填】**（⚠ 纪律 ④）⇒ ⇒ **没有默认落点**
    ⇒ ⇒ ⚠ 调用方必须自己点名那个账本（⚠ `resolve_ledger_path()` 或直接给路径）
    ⇒ ⇒ ⚠ **不许在这里回落**（⚠ 回落＝真账本 ⇒ ⇒ 塞测试行＝编造事实）

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

        surface = EventLedgerSurface(db_path=Path(db_path).expanduser().absolute())
        # ⚠ **幂等键**＝作业身份 ＋ 开始时刻 ⇒ ⇒ 同一次作业重跑不会重复记
        #   ⚠⚠⚥ **那行 f-string 必须单行**（⚠ 多行表达式要 Python 3.12+ ⇒ ⇒ 仓里还有 3.9 面）
        stamp = (started_at or "").replace(":", "").replace("-", "")
        idem = f"domchange-{domain_id}-{job_id}-{stamp}"
        result = surface.append(
            event_type=EVENT_TYPE,
            producer=PRODUCER,
            principal_id=canonical_principal_id(),
            correlation_id=f"domchange-{domain_id}",
            idempotency_key=idem,
            payload=payload,
            evidence_uri=f"documents-domain-owner-job://{job_id}",
        )
        receipt["recorded"] = True
        receipt["sequence"] = result.sequence
        receipt["event_id"] = result.event_id
        receipt["db_path"] = result.db_path
    except Exception as exc:  # noqa: BLE001 —— ⚠ 留痕是旁路 ⇒ ⇒ 写不进去只报
        receipt["error"] = f"{type(exc).__name__}: {exc}"
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
    parser.add_argument("--db", required=True,
                        help="⚠ 账本路径（⚠ 必填 ⇒ ⇒ 不许有默认落点 ⇒ ⇒ 那是往真账本塞行的入口）")
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
