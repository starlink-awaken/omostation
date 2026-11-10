#!/usr/bin/env python3
"""A 系门禁 detail 契约检查 —— 判「诊断串还带不带信息」，不判门禁本身红绿。

来源：.omo/debt/items/PANORAMA-GATE-DETAIL-UNRELIABLE.yaml 的 decision_needed 第三条。
该债的两种实际死法都在这里有一条断言：A1 的 detail 退化成单字符 `'}'`（裸取美化 JSON 的
末行），A9 点名了 `cockpit_sources` 却不带源状态原因（2026-10-23 已修过一次，今天只在
仓内代码里生效）。

只在平面在位的宿主上判：CI 检出里没有 `~/.local/share/zhixing-dashboard` ⇒ plane=absent
⇒ 不判，退出码 0。仪器故障（文件在但读不出）照判并标 plane=unreadable —— 读不出不等于清白。

跨平面偏斜（发布链跑 2026-09 的冻结副本，见该债 2026-11-10 review 条）只作 advisory：
清掉它需要一次部署面写操作（推进冻结代码根），不是仓库改动能满足的条件，把它做成阻断
等于把 principal 的授权决策换成一个恒红门禁。
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import time
from datetime import UTC
from pathlib import Path
from typing import Any

DEBT_ID = "PANORAMA-GATE-DETAIL-UNRELIABLE"
RULE_ID = "CR-X2-GATE-DETAIL-CONTRACT"
# 限期与 governance-checks.yaml::CR-X2-GATE-DETAIL-CONTRACT.review_before 由单测钉成同源
ENFORCE_AFTER = "2026-12-01"

APP = Path.home() / ".local" / "share" / "zhixing-dashboard"
PUBLISHED = APP / "current.json"
REVISIONS = APP / "revisions"
SKEW_WINDOW_SECONDS = 900

FAIL_MARKERS = ("incomplete", "Traceback", "Error:", "not ok", "non-zero")
BRACKET_ONLY = re.compile(r"^[\s\]\}\)\.,;]+$")
REASON_TOKEN = re.compile(r"\b([a-z][a-z0-9_\-]{1,40})=([A-Za-z_][A-Za-z0-9_]*)")


def _read_plane(path: Path) -> tuple[str, dict | None]:
    """三态读一个平面文件：present / absent / unreadable。"""
    if not path.is_file():
        return "absent", None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 仪器故障不是被检物的清白
        return "unreadable", None
    if not isinstance(payload, dict):
        return "unreadable", None
    return "present", payload


def newest_revision(revisions_dir: Path) -> Path | None:
    """取 generated_at 最新的 revision 快照（目录名是 content digest，不含时间）。"""
    if not revisions_dir.is_dir():
        return None
    best: tuple[float, Path] | None = None
    for child in revisions_dir.iterdir():
        data = child / "data.json"
        if not child.is_dir() or not data.is_file():
            continue
        stamp = data.stat().st_mtime
        if best is None or stamp > best[0]:
            best = (stamp, data)
    return best[1] if best else None


def _gates(payload: dict | None) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    gates = payload.get("gates")
    if not isinstance(gates, list):
        return []
    return [g for g in gates if isinstance(g, dict) and str(g.get("id", "")).startswith("A")]


def _iso_age(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        observed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    return (datetime.datetime.now(UTC) - observed).total_seconds()


def check_detail(gate: dict) -> list[dict]:
    """一条门 detail 的契约违反清单；空列表 = 合格。"""
    gid = str(gate.get("id"))
    detail = gate.get("detail")
    verdict = str(gate.get("verdict") or "")
    violations: list[dict] = []

    def add(kind: str, note: str) -> None:
        violations.append({"id": gid, "kind": kind, "detail": detail if isinstance(detail, str) else repr(detail), "note": note})

    if not isinstance(detail, str) or not detail.strip():
        add("shape", "detail 为空或非字符串：诊断通路没有带出任何内容")
        return violations
    if BRACKET_ONLY.match(detail):
        add("shape", f"detail 只有收尾符 ({detail!r})：这是把美化 JSON 的末行当诊断，无信息量")
        return violations
    if len(detail.strip()) < 2:
        add("shape", f"detail 短到无信息 ({detail!r})")

    if verdict == "PASS" and any(m in detail for m in FAIL_MARKERS):
        add("coherence", "verdict=PASS 但 detail 带失败标记：detail 与 verdict 不同源")
    # 债的原始形状：点名了 cockpit 源却没给源状态，读者仍得人工翻 cockpit current.json
    if "cockpit_sources" in detail and "=" not in detail:
        add("reason_missing", "detail 点名 cockpit_sources 却没有任何 name=STATUS 原因段")
    names = [m.group(1) for m in REASON_TOKEN.finditer(detail)]
    if names and names != sorted(names):
        add("order", f"原因段顺序未固定 {names}：采集侧按 set 迭代，逐字比对会假漂移")
    return violations


def evaluate(
    *,
    published_path: Path = PUBLISHED,
    revisions_dir: Path = REVISIONS,
    published: dict | None | Any = ...,
    revision: dict | None | Any = ...,
    strict: bool = False,
    now: datetime.date | None = None,
) -> dict:
    """两平面各判一遍，再加一条跨平面偏斜 advisory。"""
    if published is ...:
        pub_state, published = _read_plane(published_path)
    else:
        pub_state = "present"
    if revision is ...:
        newest = newest_revision(revisions_dir)
        if newest is None:
            rev_state, revision = "absent", None
        else:
            rev_state, revision = _read_plane(newest)
    else:
        rev_state = "present"

    planes = (("published", published), ("revision", revision))
    violations: list[dict] = []
    counts: dict[str, dict[str, int]] = {}
    for plane, payload in planes:
        gates = _gates(payload)
        found = [v for g in gates for v in check_detail(g)]
        for v in found:
            v["plane"] = plane
        violations.extend(found)
        counts[plane] = {
            "gates_scanned": len(gates),
            "violations": len(found),
            "state": pub_state if plane == "published" else rev_state,
        }
        # 仪器自证：平面读得出、有 gates 列表，却一条 A 系门都解析不到 ⇒ 判据在空转
        if payload is not None and isinstance(payload.get("gates"), list) and payload["gates"] and not gates:
            counts[plane]["parse_suspicious"] = 1

    kinds = sorted({v["kind"] for v in violations})
    blocking = [v for v in violations if v["kind"] != "order"]
    order_violations = [v for v in violations if v["kind"] == "order"]

    skew: list[dict] = []
    pub_gates = {str(g.get("id")): g.get("detail") for g in _gates(published)}
    rev_gates = {str(g.get("id")): g.get("detail") for g in _gates(revision)}
    # 「同一时点」是两份 payload 自己的属性，不看挂钟：只有两条门的读数确实出自同一轮，
    # 它们的差异才是偏斜证据，否则只是先后两轮的正常变化。
    pub_age = _iso_age((published or {}).get("generated_at")) if isinstance(published, dict) else None
    rev_age = _iso_age((revision or {}).get("generated_at")) if isinstance(revision, dict) else None
    same_window = pub_age is not None and rev_age is not None and abs(pub_age - rev_age) <= SKEW_WINDOW_SECONDS
    for gid in sorted(set(pub_gates) & set(rev_gates)):
        if pub_gates[gid] != rev_gates[gid]:
            skew.append(
                {
                    "id": gid,
                    "published": pub_gates[gid],
                    "revision": rev_gates[gid],
                    "same_window": bool(same_window),
                }
            )

    escalated = (now or datetime.datetime.now().date()) >= datetime.date.fromisoformat(ENFORCE_AFTER)
    verdict = "OK"
    if blocking or order_violations or skew:
        verdict = "FAIL" if ((blocking or order_violations) and (escalated or strict)) else "WARN"

    return {
        "debt_id": DEBT_ID,
        "rule_id": RULE_ID,
        "verdict": verdict,
        "enforcement": "blocking" if escalated else "advisory",
        "enforce_after": ENFORCE_AFTER,
        "planes": counts,
        "violations": violations[:60],
        "violation_kinds": kinds,
        "blocking_violations": len(blocking),
        "order_violations": len(order_violations),
        "skew": skew[:20],
        "skew_count": len(skew),
        "skew_same_window": bool(same_window),
        "generated_at": (published or {}).get("generated_at") if isinstance(published, dict) else None,
        "revision_generated_at": (revision or {}).get("generated_at") if isinstance(revision, dict) else None,
    }


def _six_field_record(result: dict, *, started: float, inputs: list[str], basis: list[str]) -> dict:
    """AGENTS.md §14.2：一次自动化运行一条记录，六个键，缺值写 null 不省略键。"""
    return {
        "inputs": inputs,
        "basis": basis,
        "approver": "principal (2026-11-10 授权全面推进；限期见 " + RULE_ID + ")",
        "result": {
            "verdict": result["verdict"],
            "blocking_violations": result["blocking_violations"],
            "order_violations": result["order_violations"],
            "skew_count": result["skew_count"],
            "enforcement": result["enforcement"],
        },
        "duration_ms": int((time.monotonic() - started) * 1000),
        "model_usage": None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--published", default=str(PUBLISHED))
    ap.add_argument("--revisions-dir", default=str(REVISIONS))
    ap.add_argument("--now", default=None, help="判定用的今天 (YYYY-MM-DD)，测试与回溯用")
    ap.add_argument("--strict", action="store_true", help="无视限期，有违反即 FAIL")
    ap.add_argument("--json", action="store_true", help="机器可读输出（含六字段运行记录）")
    args = ap.parse_args(argv)

    started = time.monotonic()
    result = evaluate(
        published_path=Path(args.published),
        revisions_dir=Path(args.revisions_dir),
        now=datetime.date.fromisoformat(args.now) if args.now else None,
        strict=args.strict,
    )
    result["run_record"] = _six_field_record(
        result,
        started=started,
        inputs=[
            f"published={args.published} state={result['planes']['published']['state']} "
            f"扫{result['planes']['published']['gates_scanned']}条",
            f"revisions={args.revisions_dir} state={result['planes']['revision']['state']} "
            f"扫{result['planes']['revision']['gates_scanned']}条",
            f"generated_at={result['generated_at']} revision_generated_at={result['revision_generated_at']}",
        ],
        basis=[
            f".omo/debt/items/{DEBT_ID}.yaml (decision_needed 第三条, 2026-11-10 定论为代码版本偏斜)",
            f".omo/_truth/registry/governance-checks.yaml::{RULE_ID}",
            "bin/gac/gate-health-check.py::_diagnostic (A1 detail 的生产者)",
            "bin/panorama/panorama-collect.py (A 系 detail 的聚合生产者)",
        ],
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"[gate-detail-contract] published={result['planes']['published']['state']}"
            f"({result['planes']['published']['gates_scanned']}) "
            f"revision={result['planes']['revision']['state']}"
            f"({result['planes']['revision']['gates_scanned']}) "
            f"verdict={result['verdict']} 违反={len(result['violations'])}"
            f"(阻断={result['blocking_violations']} 顺序={result['order_violations']}) "
            f"跨平面偏斜={result['skew_count']}"
            f"{'' if result['skew_same_window'] else '(非同一时点, 只作参考)'} "
            f"(enforcement={result['enforcement']}, 限期={ENFORCE_AFTER})"
        )
        for v in result["violations"][:20]:
            print(f"  {v['plane']:9s} {v['id']:3s} {v['kind']:13s} {str(v['detail'])[:60]!r} :: {v['note']}")
        for s in result["skew"][:10]:
            print(f"  SKEW    {s['id']:3s} published={str(s['published'])[:60]!r} revision={str(s['revision'])[:60]!r}")
        for plane, info in result["planes"].items():
            if info.get("parse_suspicious"):
                print(f"  ⚠PARSE  {plane}: gates 非空但解析不到 A 系门 —— 判据在空转，这条绿不可信")
    return 1 if result["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
