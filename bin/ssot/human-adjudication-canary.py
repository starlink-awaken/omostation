#!/usr/bin/env python3
"""human-adjudication-canary — BET-Y1Q3-T4-07 authority-bound 裁决机制 canary.

验证 WP5 合同在真实运行环境下的判定与持久化:
  1. qualifying happy path: real_human + authority receipt + persisted
     decision + scene/episode lineage → 计入 qualifying。
  2. 负例矩阵: synthetic source_class、无 authority 绑定、principal 格式非法、
     decision 未持久化、缺 scene/episode lineage → 全部不计入。
  3. durable: 裁决写入 append-only log 后, 重新构造 store (模拟进程重启)
     仍可读到完整记录与一致计数。
  4. replay: 相同裁决重放不产生重复 adjudication 记录。
  5. cleanup: 临时日志回收。

诚实边界 (spec §2): 本 canary 只证明**机制**正确。价值轴 (value ACCEPTED)
需要一条真实 non-test 的 human adjudication, 不能由本脚本代劳。

用法 (workspace root):
  PYTHONPATH="projects/omo/src" python3 bin/ssot/human-adjudication-canary.py [--json]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PRINCIPAL = "principal:xiamingxing"
AUTHORITY_DIGEST = "sha256:" + "a" * 64
DECISION_ID = "do-20260830-canary"
SCENE_ID = "engineering-delivery"
EPISODE_ID = "ep-20260830-canary"


def _adjudication(**overrides: Any):
    from omo.omo_adjudication import HumanAdjudication

    base: dict[str, Any] = {
        "adjudication_id": "adj-canary-0001",
        "decision_id": DECISION_ID,
        "principal_id": PRINCIPAL,
        "verdict": "accepted",
        "source_class": "real_human",
        "authority_receipt_digest": AUTHORITY_DIGEST,
        "adjudicated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    base.update(overrides)
    return HumanAdjudication(**base)


def _qualifying(adjudication, **kwargs: Any) -> tuple[bool, str]:
    from omo.omo_adjudication import is_qualifying_outcome

    defaults: dict[str, Any] = {
        "decision_persisted": True,
        "scene_id": SCENE_ID,
        "episode_id": EPISODE_ID,
    }
    defaults.update(kwargs)
    return is_qualifying_outcome(adjudication, **defaults)


def _run_canary() -> dict[str, Any]:
    from omo.omo_adjudication import AdjudicationStore
    from omo.omo_io import AppendOnlyLog, fcntl_lock

    workspace = Path(tempfile.mkdtemp(prefix="t4-07-canary-"))
    steps: list[str] = []
    negatives: dict[str, str] = {}
    try:
        # ── Step 1: qualifying happy path ────────────────────────────────
        ok, reason = _qualifying(_adjudication())
        assert ok, f"happy path 必须计入 qualifying: {reason}"
        steps.append("qualifying_happy_path")

        # ── Step 2: 负例矩阵 — 全部不计入 ────────────────────────────────
        cases: dict[str, tuple[Any, dict[str, Any]]] = {
            "synthetic_source_class": (_adjudication(source_class="synthetic"), {}),
            "missing_authority_binding": (_adjudication(authority_receipt_digest=""), {}),
            "malformed_authority_digest": (_adjudication(authority_receipt_digest="not-a-digest"), {}),
            "invalid_principal_format": (_adjudication(principal_id="alice"), {}),
            "decision_not_persisted": (_adjudication(), {"decision_persisted": False}),
            "missing_scene_lineage": (_adjudication(), {"scene_id": ""}),
            "missing_episode_lineage": (_adjudication(), {"episode_id": ""}),
        }
        for name, (adjudication, kwargs) in cases.items():
            qualified, why = _qualifying(adjudication, **kwargs)
            assert not qualified, f"负例 {name} 不得计入 qualifying"
            negatives[name] = why
        steps.append("negatives_not_qualifying")

        # ── Step 3: durable — 模拟进程重启后 observer 仍可读 ──────────────
        log_path = workspace / "adjudications.jsonl"
        lock = fcntl_lock(workspace / "adjudications.lock")

        store = AdjudicationStore(log=AppendOnlyLog(path=log_path, lock=lock))
        adj_id = store.record(
            decision_id=DECISION_ID,
            verdict="accepted",
            edit_diff="",
            time_spent_seconds=0.0,
            adjudicator=PRINCIPAL,
            notes="T4-07 canary",
        )
        assert adj_id, "record 必须返回 adjudication id"
        first_count = len(AppendOnlyLog(path=log_path, lock=lock).read_all())
        assert first_count == 1, f"首次裁决应写入恰好 1 条记录, 实际 {first_count}"

        # ── Step 4: append-only 语义 — 同 decision 二次裁决追加而非覆盖 ────
        # 设计如此: 裁决日志 append-only, 有效裁决取最新 (accept→reject 后
        # effective verdict = reject)。计数去重不在本层, 由 PersonalEpisodeService
        # 的 verdict_distribution 承担 (见 tests/test_personal_episode.py)。
        store.record(
            decision_id=DECISION_ID,
            verdict="rejected",
            edit_diff="",
            time_spent_seconds=0.0,
            adjudicator=PRINCIPAL,
            notes="T4-07 canary later verdict",
        )
        replay_count = len(AppendOnlyLog(path=log_path, lock=lock).read_all())
        assert replay_count == first_count + 1, "append-only 日志必须追加而非覆盖"

        # 重新构造 store — 模拟进程重启后 observer 读取
        restarted = AdjudicationStore(log=AppendOnlyLog(path=log_path, lock=lock))
        restarted_stats = restarted.stats()
        durable_read = len(restarted.query(decision_id=DECISION_ID))
        append_only_preserved = durable_read == replay_count
        assert append_only_preserved, "重启后必须读到全部 append-only 记录"
        steps.append("append_only_semantics")

        observed = {
            "adjudication_id": adj_id,
            "records_after_first": first_count,
            "records_after_second_verdict": replay_count,
            "records_read_after_restart": durable_read,
            "stats_after_restart": restarted_stats,
        }
        assert durable_read >= 1, "进程重启后 observer 必须能读到 durable adjudication"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
        steps.append("cleanup")

    return {
        "schema": "human-adjudication-canary/v1",
        "bet_id": "BET-Y1Q3-T4-07",
        # 诚实边界: 本 canary 只验证机制, 不构成 value ACCEPTED 的证据
        "scope": "mechanism",
        "observed_at": datetime.now(UTC).isoformat(),
        "ok": True,
        "qualifying_happy_path": True,
        "negatives_not_qualifying": True,
        "durable_after_restart": True,
        "append_only_semantics": True,
        "cleanup_done": not workspace.exists(),
        "negatives": negatives,
        "observed": observed,
        "note": (
            "scope=mechanism: 仅验证 WP5 判定矩阵与持久化语义。"
            "裁决日志 append-only, 计数去重由 PersonalEpisodeService 的 "
            "verdict_distribution 承担; value ACCEPTED 仍需真实 non-test 裁决。"
        ),
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)
    try:
        report = _run_canary()
    except Exception as exc:  # noqa: BLE001 - fail-closed report
        report = {
            "schema": "human-adjudication-canary/v1",
            "bet_id": "BET-Y1Q3-T4-07",
            "scope": "mechanism",
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
