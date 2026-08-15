#!/usr/bin/env python3
"""test_coordination_layer.py — BET-Y1Q1-T1-05A 协调层测试 (可重跑).

四套件 (台账 verify 引用):
  --suite concurrency  两进程并发认领同一 resource → 恰 1 成功 (fencing token 单调)
  --suite fencing      释放→重认领→旧 token 校验必须 reject
  --suite schema       ensure_ready 幂等 / WAL 生效 / maybe_backup 产出
  --suite runtime      agent_health runtime attestation 写入并通过 status 暴露

用法:
  OMO_COORDINATION_DB=/tmp/x.sqlite3 python3 bin/gac/test_coordination_layer.py --suite all
  python3 bin/gac/test_coordination_layer.py --suite concurrency --repeat 20

DB 路径: 优先 env OMO_COORDINATION_DB; 否则用临时目录 (测试不污染真实共享 DB).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordination_store as cs


def _prep_db(tag: str) -> Path:
    """测试 DB: env 覆盖或临时目录; 每次全新."""
    env_db = os.environ.get(cs.ENV_DB_PATH)
    if env_db:
        path = Path(env_db)
        for candidate in (
            path,
            Path(env_db + "-wal"),
            Path(env_db + "-shm"),
            path.parent / f"{path.name}.last-backup",
            *(path.parent.glob(f"{path.name}.bak.*")),
        ):
            candidate.unlink(missing_ok=True)
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
    import multiprocessing as mp

    ok_rounds = 0
    for i in range(repeat):
        db = _prep_db(f"conc-{i}")
        cs.ensure_ready()
        rid = f"work/conc-{i}"
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
    expiry_db = _prep_db("expired-concurrency")
    cs.ensure_ready()
    expired_rid = "work/expired-concurrency"
    stale = cs.claim_resource("branch", expired_rid, owner="stale", ttl_hours=1)
    assert stale and stale.token == 1
    conn = sqlite3.connect(str(expiry_db))
    conn.execute(
        "UPDATE claims SET expires_at='2000-01-01T00:00:00Z' "
        "WHERE resource_type='branch' AND resource_id=? AND state='active'",
        (expired_rid,),
    )
    conn.commit()
    conn.close()
    procs = [
        mp.Process(target=_claim_worker, args=(str(expiry_db), expired_rid, owner, 0.05))
        for owner in ("a", "b")
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=30)
    expiry_results = [
        json.loads((expiry_db.parent / f"worker-{owner}.result").read_text())
        for owner in ("a", "b")
    ]
    expiry_winners = [result for result in expiry_results if result["ok"]]
    assert len(expiry_winners) == 1 and expiry_winners[0]["token"] == 2, expiry_results
    print(f"concurrency: {ok_rounds}/{repeat} rounds → exactly one winner")
    print("concurrency: expired active claim 原子回收后 exactly one token=2 winner")
    return ok_rounds == repeat


# ── fencing ──────────────────────────────────────────────────────────


def suite_fencing() -> bool:
    _prep_db("fencing")
    cs.ensure_ready()
    rid = "work/fencing"
    c1 = cs.claim_resource("branch", rid, owner="a", ttl_hours=1)
    assert c1 and c1.token == 1
    # same-owner 幂等重取 (drift 修复): token 不变, TTL 顺延, 不产生新行
    c1_re = cs.claim_resource("branch", rid, owner="a", ttl_hours=2)
    assert c1_re and c1_re.token == 1, f"same-owner 重取应幂等返回 token=1, 实际={c1_re.token if c1_re else None}"
    conn0 = sqlite3.connect(str(cs.db_path()))
    rows0 = conn0.execute(
        "SELECT COUNT(*) FROM claims WHERE resource_id=? AND state='active'", (rid,)
    ).fetchone()[0]
    conn0.close()
    assert rows0 == 1, f"same-owner 重取不应新增 active 行, 实际={rows0}"
    assert c1_re.expires_at > c1.expires_at, "same-owner 重取应顺延 TTL"
    assert cs.check_fencing("branch", rid, "a", c1.token).ok, "active owner/token 应通过"
    wrong_owner = cs.check_fencing("branch", rid, "intruder", c1.token)
    assert not wrong_owner.ok and "owner" in wrong_owner.reason, "错误 owner 必须 reject"
    assert cs.release_resource("branch", rid, "a"), "owner 匹配释放"
    released = cs.check_fencing("branch", rid, "a", c1.token)
    assert not released.ok and "released" in released.reason, "released token 必须 reject"
    c2 = cs.claim_resource("branch", rid, owner="b", ttl_hours=1)
    assert c2 and c2.token == 2, f"reclaim token 应=2 实际={c2.token if c2 else None}"
    old = cs.check_fencing("branch", rid, "a", c1.token)
    assert not old.ok, "旧 token 必须 reject"
    assert cs.current_token("branch", rid) == 2
    # 非 owner 不能释放
    assert not cs.release_resource("branch", rid, "intruder")
    conn = sqlite3.connect(str(cs.db_path()))
    conn.execute(
        "UPDATE claims SET expires_at='2000-01-01T00:00:00Z' "
        "WHERE resource_type='branch' AND resource_id=? AND state='active'",
        (rid,),
    )
    conn.commit()
    conn.close()
    expired = cs.check_fencing("branch", rid, "b", c2.token)
    assert not expired.ok and "expired" in expired.reason, "过期 active token 必须 reject"
    c3 = cs.claim_resource("branch", rid, owner="c", ttl_hours=1)
    assert c3 and c3.token == 3, "过期 claim 应在同一认领事务内回收并递增 token"
    conn = sqlite3.connect(str(cs.db_path()))
    old_state = conn.execute(
        "SELECT state FROM claims WHERE resource_type='branch' AND resource_id=? AND token=2",
        (rid,),
    ).fetchone()[0]
    conn.close()
    assert old_state == "expired", f"过期 claim state 应为 expired, 实际={old_state}"

    cli = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("swarm-discipline-cli.py")),
            "token-check", "--resource-type", "branch", "--resource-id", rid,
            "--owner", "c", "--token", str(c3.token),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    cli_payload = json.loads(cli.stdout)
    assert cli.returncode == 0 and cli_payload["ok"], cli.stdout + cli.stderr
    shadow_reject = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("swarm-discipline-cli.py")),
            "token-check", "--resource-type", "branch", "--resource-id", rid,
            "--owner", "intruder", "--token", str(c3.token),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    reject_payload = json.loads(shadow_reject.stdout)
    assert shadow_reject.returncode == 0, "shadow reject 仍不得阻断调用方"
    assert not reject_payload["ok"] and "owner" in reject_payload["reason"]

    missing_token = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("swarm-discipline-cli.py")),
            "token-check", "--resource-type", "branch", "--resource-id", rid,
            "--owner", "legacy", "--token", "0", "--missing-token",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    missing_payload = json.loads(missing_token.stdout)
    assert missing_token.returncode == 0, "legacy missing-token 在 shadow 阶段不阻断"
    assert not missing_payload["ok"] and missing_payload["reason"] == "missing local fencing token"

    mirror_missing = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("swarm-discipline-cli.py")),
            "token-check", "--resource-type", "branch", "--resource-id", "work/mirror-missing",
            "--owner", "mirror-owner", "--token", "7",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    mirror_payload = json.loads(mirror_missing.stdout)
    assert mirror_missing.returncode == 0, "SQLite 镜像缺 claim 在 shadow 阶段不阻断"
    assert not mirror_payload["ok"] and "missing" in mirror_payload["reason"]

    broken_db = Path(tempfile.mkdtemp(prefix="coord-broken-db-"))
    broken_env = os.environ.copy()
    broken_env[cs.ENV_DB_PATH] = str(broken_db)
    unrecordable = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("swarm-discipline-cli.py")),
            "token-check", "--resource-type", "branch", "--resource-id", "work/broken-mirror",
            "--owner", "broken-owner", "--token", "0", "--missing-token",
        ],
        env=broken_env,
        capture_output=True,
        text=True,
        check=False,
    )
    unrecordable_payload = json.loads(unrecordable.stdout)
    assert unrecordable.returncode == 2, "shadow verdict 无法落事件时必须 fail-closed"
    assert unrecordable_payload["fail_closed"] and not unrecordable_payload["event_recorded"]

    conn = sqlite3.connect(str(cs.db_path()))
    event_rows = conn.execute(
        "SELECT kind, resource_id, detail_json FROM shadow_events "
        "WHERE kind IN ('token_missing_legacy', 'token_stale_rejected')"
    ).fetchall()
    events = {
        (row[0], row[1]): json.loads(row[2])
        for row in event_rows
    }
    conn.close()
    legacy_detail = events[("token_missing_legacy", rid)]
    assert legacy_detail["owner"] == "legacy" and legacy_detail["local_token"] == 0
    mirror_detail = events[("token_stale_rejected", "work/mirror-missing")]
    assert mirror_detail["owner"] == "mirror-owner" and mirror_detail["local_token"] == 7
    worktree_script = Path(__file__).with_name("gac-worktree.sh").read_text()
    assert '--owner "$session"' in worktree_script, "submit token-check 必须传 claim owner"
    assert 'if [ -n "$_t05a_token" ]; then' not in worktree_script, "missing token 不得静默跳过"
    assert '--missing-token' in worktree_script
    assert '--token "${_t05a_token:-0}"' in worktree_script
    print("fencing: 正常/旧 claim missing-token/镜像缺失均进入可审计 shadow verdict")
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
    bak.unlink()
    (db.parent / f"{db.name}.last-backup").unlink()
    cs.heartbeat("backup-fallback", "ok")
    fallback = db.parent / f"{db.name}.bak.1"
    assert fallback.exists(), "普通 store access 应触发 24h backup fallback"
    backup_conn = sqlite3.connect(str(fallback))
    backup_integrity = backup_conn.execute("PRAGMA integrity_check").fetchone()[0]
    backup_conn.close()
    assert backup_integrity == "ok", f"fallback backup integrity={backup_integrity}"
    print(f"schema: WAL={journal}, user_version={version}, 四表齐, 自动 backup fallback OK")
    return True


def suite_runtime() -> bool:
    db = _prep_db("runtime")
    cs.ensure_ready()
    ssot_dir = Path(__file__).resolve().parents[1] / "ssot"
    sys.path.insert(0, str(ssot_dir))
    daemon_path = ssot_dir / "agent-tick-daemon.py"
    spec = importlib.util.spec_from_file_location("agent_tick_daemon", daemon_path)
    assert spec and spec.loader
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    original_workspace_root = os.environ.get("WORKSPACE_ROOT")
    original_code_root = os.environ.get("WORKSPACE_CODE_ROOT")
    runtime_root = Path(tempfile.mkdtemp(prefix="coord-runtime-root-")).resolve()
    (runtime_root / ".omo" / "state").mkdir(parents=True)
    try:
        configured_root = daemon._configure_runtime_workspace(runtime_root)
        assert configured_root == runtime_root.resolve()
        assert os.environ["WORKSPACE_ROOT"] == str(runtime_root.resolve())
        assert os.environ["WORKSPACE_CODE_ROOT"] == str(daemon.CODE_ROOT)
        daemon._heartbeat({"type": "runtime-root-probe"})
        heartbeat_path = runtime_root / ".omo" / "state" / "agent-tick-daemon.jsonl"
        assert heartbeat_path.exists(), (
            "heartbeat 必须写 runtime root，不得写 code root"
        )
        heartbeat_entry = json.loads(
            heartbeat_path.read_text().strip().splitlines()[-1]
        )
        assert heartbeat_entry["type"] == "runtime-root-probe"

        expected_root_digest = (
            __import__("hashlib")
            .sha256(str(runtime_root.resolve()).encode())
            .hexdigest()
        )
        daemon._coordination_heartbeat(
            {"results": [{"agent_id": "runtime-agent", "ok": True, "action": "noop"}]}
        )
        observed_root: dict[str, str] = {}
        original_load_omo = daemon._load_omo
        original_coordination_heartbeat = daemon._coordination_heartbeat

        def fake_load_omo():
            observed_root["before_import"] = os.environ["WORKSPACE_ROOT"]
            observed_root["code_before_import"] = os.environ["WORKSPACE_CODE_ROOT"]
            return lambda: {
                "agent_count": 0,
                "ok_count": 0,
                "failed_count": 0,
                "results": [],
            }

        daemon._load_omo = fake_load_omo
        daemon._coordination_heartbeat = lambda _result: None
        try:
            assert daemon.main(["--once", "--workspace-root", str(runtime_root)]) == 0
        finally:
            daemon._load_omo = original_load_omo
            daemon._coordination_heartbeat = original_coordination_heartbeat
        assert observed_root["before_import"] == str(runtime_root.resolve())
        assert observed_root["code_before_import"] == str(daemon.CODE_ROOT)

        code_status_cmd = [
            "git",
            "-C",
            str(daemon.CODE_ROOT),
            "status",
            "--porcelain=v2",
            "--ignored=matching",
        ]
        code_status_before = subprocess.run(
            code_status_cmd, capture_output=True, text=True, check=True
        ).stdout
        subprocess_env = os.environ.copy()
        subprocess_env["PYTHONDONTWRITEBYTECODE"] = "1"
        subprocess_env[cs.ENV_DB_PATH] = str(runtime_root / "coordination.sqlite3")
        isolated_tick = subprocess.run(
            [
                sys.executable,
                str(daemon_path),
                "--once",
                "--workspace-root",
                str(runtime_root),
            ],
            env=subprocess_env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert isolated_tick.returncode == 0, (
            isolated_tick.stdout + isolated_tick.stderr
        )
        isolated_result = json.loads(isolated_tick.stdout)
        expected_agent_ids = {
            "health-monitor",
            "knowledge-curator",
            "journey-runner",
            "governor",
            "advisor",
            "autonomy-assessment",
        }
        assert isolated_result["mode"] == "once"
        assert isolated_result["agent_count"] == len(expected_agent_ids)
        assert isolated_result["ok_count"] == len(expected_agent_ids)
        assert isolated_result["failed_count"] == 0
        assert {item["agent_id"] for item in isolated_result["results"]} == (
            expected_agent_ids
        )
        code_status_after = subprocess.run(
            code_status_cmd, capture_output=True, text=True, check=True
        ).stdout
        assert code_status_after == code_status_before, (
            "isolated --once must not mutate the code checkout\n"
            f"before={code_status_before!r}\nafter={code_status_after!r}"
        )
    finally:
        if original_workspace_root is None:
            os.environ.pop("WORKSPACE_ROOT", None)
        else:
            os.environ["WORKSPACE_ROOT"] = original_workspace_root
        if original_code_root is None:
            os.environ.pop("WORKSPACE_CODE_ROOT", None)
        else:
            os.environ["WORKSPACE_CODE_ROOT"] = original_code_root
    conn = sqlite3.connect(str(db))
    detail_json = conn.execute(
        "SELECT detail_json FROM agent_health WHERE agent_id='runtime-agent'"
    ).fetchone()[0]
    conn.close()
    detail = json.loads(detail_json)
    attestation = detail["runtime_attestation"]
    assert set(attestation) == {
        "component",
        "code_sha256",
        "workspace_revision",
        "python_version",
        "runtime_root_digest",
    }
    assert len(attestation["code_sha256"]) == 64
    assert attestation["workspace_revision"]
    assert attestation["runtime_root_digest"] == expected_root_digest
    assert "/Users/" not in json.dumps(attestation), "attestation 不得泄露本机路径"
    snap_health = cs.snapshot()["agent_health"]
    visible = next(h for h in snap_health if h["agent_id"] == "runtime-agent")
    assert visible["runtime_attestation"] == attestation, "status 快照必须暴露部署指纹"

    unsafe_link_root = Path(tempfile.mkdtemp(prefix="coord-runtime-link-parent-"))
    link_path = unsafe_link_root / "workspace-link"
    link_path.symlink_to(runtime_root, target_is_directory=True)
    try:
        daemon._configure_runtime_workspace(link_path)
    except ValueError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("runtime workspace symlink 必须 fail closed")

    parent_link = unsafe_link_root / "parent-link"
    parent_link.symlink_to(runtime_root.parent, target_is_directory=True)
    nested_link_path = parent_link / runtime_root.name
    assert not nested_link_path.is_symlink()
    try:
        daemon._configure_runtime_workspace(nested_link_path)
    except ValueError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("runtime workspace symlink parent 必须 fail closed")

    dotdot_link_path = f"{parent_link}/../{runtime_root.name}"
    try:
        daemon._configure_runtime_workspace(dotdot_link_path)
    except ValueError as exc:
        assert "canonical" in str(exc)
    else:
        raise AssertionError("含 symlink/.. 的 runtime workspace 必须 fail closed")

    print("runtime: code/runtime root 分离 + privacy-safe attestation OK")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--suite",
        choices=["concurrency", "fencing", "schema", "runtime", "all"],
        default="all",
    )
    ap.add_argument("--repeat", type=int, default=20, help="concurrency 轮数")
    args = ap.parse_args(argv)

    results: dict[str, bool] = {}
    if args.suite in ("concurrency", "all"):
        results["concurrency"] = suite_concurrency(args.repeat)
    if args.suite in ("fencing", "all"):
        results["fencing"] = suite_fencing()
    if args.suite in ("schema", "all"):
        results["schema"] = suite_schema()
    if args.suite in ("runtime", "all"):
        results["runtime"] = suite_runtime()

    print("\n── RESULTS ──")
    all_ok = True
    for name, ok in results.items():
        print(f"  {name:<14} {'PASS' if ok else 'FAIL'}")
        all_ok = all_ok and ok
    print("ALL PASS" if all_ok else "SOME FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
