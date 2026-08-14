#!/usr/bin/env python3
"""test_coordination_layer.py — BET-Y1Q1-T1-05A 协调层测试 (可重跑).

三套件 (台账 verify 引用):
  --suite concurrency  两进程并发认领同一 resource → 恰 1 成功 (fencing token 单调)
  --suite fencing      释放→重认领→旧 token 校验必须 reject
  --suite schema       ensure_ready 幂等 / WAL 生效 / maybe_backup 产出

用法:
  OMO_COORDINATION_DB=/tmp/x.sqlite3 python3 bin/gac/test_coordination_layer.py --suite all
  python3 bin/gac/test_coordination_layer.py --suite concurrency --repeat 20

DB 路径: 优先 env OMO_COORDINATION_DB; 否则用临时目录 (测试不污染真实共享 DB).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordination_store as cs  # noqa: E402


def _prep_db(tag: str) -> Path:
    """测试 DB: env 覆盖或临时目录; 每次全新."""
    env_db = os.environ.get(cs.ENV_DB_PATH)
    if env_db:
        for suffix in ("", "-wal", "-shm"):
            Path(env_db + suffix).unlink(missing_ok=True)
        return Path(env_db)
    tmp = Path(tempfile.mkdtemp(prefix=f"coord-test-{tag}-"))
    os.environ[cs.ENV_DB_PATH] = str(tmp / "coordination.sqlite3")
    return Path(os.environ[cs.ENV_DB_PATH])


# ── concurrency: multiprocessing 两 worker 抢同一 resource ───────────


def _claim_worker(tmp_db: str, resource_id: str, owner: str, delay: float) -> None:
    """子进程入口: 直接对同一 DB 文件做原子认领, 结果写 owner 命名文件."""
    os.environ[cs.ENV_DB_PATH] = tmp_db
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import coordination_store as w

    time.sleep(delay)  # 放大竞态窗口 (两 worker 尽量同时起跑)
    claim = w.claim_resource("branch", resource_id, owner=owner, ttl_hours=1)
    out = Path(tmp_db).parent / f"worker-{owner}.result"
    out.write_text(json.dumps({"ok": claim is not None, "token": claim.token if claim else None}))


def suite_concurrency(repeat: int = 20) -> bool:
    ok_rounds = 0
    for i in range(repeat):
        db = _prep_db(f"conc-{i}")
        cs.ensure_ready()
        rid = f"work/conc-{i}"
        import multiprocessing as mp

        procs = [
            mp.Process(target=_claim_worker, args=(str(db), rid, "a", 0.05)),
            mp.Process(target=_claim_worker, args=(str(db), rid, "b", 0.05)),
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)
        results = []
        for owner in ("a", "b"):
            rf = db.parent / f"worker-{owner}.result"
            results.append(json.loads(rf.read_text()))
        winners = [r for r in results if r["ok"]]
        tokens = [r["token"] for r in winners]
        if len(winners) == 1 and tokens == [1]:
            ok_rounds += 1
        else:
            print(f"  FAIL round {i}: winners={len(winners)} results={results}")
    print(f"concurrency: {ok_rounds}/{repeat} rounds → exactly one winner")
    return ok_rounds == repeat


# ── fencing ──────────────────────────────────────────────────────────


def suite_fencing() -> bool:
    _prep_db("fencing")
    cs.ensure_ready()
    rid = "work/fencing"
    c1 = cs.claim_resource("branch", rid, owner="a", ttl_hours=1)
    assert c1 and c1.token == 1
    assert cs.check_fencing("branch", rid, c1.token).ok, "新 token 应通过"
    assert cs.release_resource("branch", rid, "a"), "owner 匹配释放"
    c2 = cs.claim_resource("branch", rid, owner="b", ttl_hours=1)
    assert c2 and c2.token == 2, f"reclaim token 应=2 实际={c2.token if c2 else None}"
    old = cs.check_fencing("branch", rid, c1.token)
    assert not old.ok, "旧 token 必须 reject"
    assert cs.current_token("branch", rid) == 2
    # 非 owner 不能释放
    assert not cs.release_resource("branch", rid, "intruder")
    print(f"fencing: release→reclaim token=2, 旧 token={c1.token} reject, 非法释放拒绝 OK")
    return True


# ── schema ───────────────────────────────────────────────────────────


def suite_schema() -> bool:
    db = _prep_db("schema")
    cs.ensure_ready()
    cs.ensure_ready()  # 幂等
    conn = sqlite3.connect(str(db))
    journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert journal.lower() == "wal", f"journal_mode={journal}"
    assert version == cs.SCHEMA_VERSION
    expected = {"claims", "agent_health", "messages", "shadow_events"}
    assert expected <= tables, f"缺表: {expected - tables}"
    bak = cs.maybe_backup(max_age_h=0)
    assert bak and bak.exists()
    assert cs.maybe_backup(max_age_h=24) is None, "24h 内应跳过"
    assert cs.integrity_check() == "ok"
    print(f"schema: WAL={journal}, user_version={version}, 四表齐, backup 轮转 OK")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite", choices=["concurrency", "fencing", "schema", "all"], default="all")
    ap.add_argument("--repeat", type=int, default=20, help="concurrency 轮数")
    args = ap.parse_args(argv)

    results: dict[str, bool] = {}
    if args.suite in ("concurrency", "all"):
        results["concurrency"] = suite_concurrency(args.repeat)
    if args.suite in ("fencing", "all"):
        results["fencing"] = suite_fencing()
    if args.suite in ("schema", "all"):
        results["schema"] = suite_schema()

    print("\n── RESULTS ──")
    all_ok = True
    for name, ok in results.items():
        print(f"  {name:<14} {'PASS' if ok else 'FAIL'}")
        all_ok = all_ok and ok
    print("ALL PASS" if all_ok else "SOME FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
