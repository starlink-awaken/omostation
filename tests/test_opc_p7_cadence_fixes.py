#!/usr/bin/env python3
# mock-heavy test: monkeypatch + dynamic attribute setup; pyright cannot follow.
# pyright: reportAttributeAccessIssue=false

"""OPC P7-H1 / P7-H3 cadence + race + mode 透传回归测试.

测试 3 项修复:
  T1: H3 daemon fcntl.flock 防 race - N 并行跑 N 条 entry 全部落盘 (无覆盖)
  T2: H3 5repos.py mode 透传 - OPC_MODE=monthly/pre-release 写对应 mode-specific 文件
  T3: H1 release OPC_GENERATED_AT override - 注入语义时间点形成真实 cadence

设计:
  - 不用 mock, 直接调 daemon / 5repos / release runner
  - T1 用 multiprocessing 真实并行 6 进程
  - T2 跑 3 次不同 mode 验证产物文件名
  - T3 跑 2 次不同时间点验证 interval_days ≥ 7

worker 函数必须在 module 顶层 (multiprocessing pickling 要求):
  - _worker_init 是顶层函数, 接收参数 (worker_id, tmp_path_str, mode)
  - worker 内部 importlib.util.spec_from_file_location 加载 daemon,
    不依赖测试 class 的方法
"""

from __future__ import annotations

import importlib.util
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPTS = WORKSPACE / "scripts"


def _worker_init(worker_id: int, tmp_path_str: str, mode: str) -> dict:
    """multiprocessing 顶层 worker: 加载 daemon + 跑一次 main."""
    tmp_path = Path(tmp_path_str)
    spec = importlib.util.spec_from_file_location(
        "daemon_worker", SCRIPTS / "opc_p7_audit_rollout_daemon.py"
    )
    daemon = importlib.util.module_from_spec(spec)  # type: ignore[reportArgumentType]
    spec.loader.exec_module(daemon)  # type: ignore[reportOptionalMemberAccess]
    daemon.ROOT = tmp_path  # type: ignore[reportAttributeAccessIssue]
    daemon._today = lambda: "2026-06-12"  # type: ignore[reportAttributeAccessIssue]
    daemon._now_iso = lambda: f"2026-06-12T00:00:0{worker_id}Z"  # type: ignore[reportAttributeAccessIssue]
    daemon._trigger_source = lambda: "manual"  # type: ignore[reportAttributeAccessIssue]

    def fake_primary(mode_arg: str) -> dict:
        return {
            "returncode": 1,
            "stdout_tail": ["primary fail"],
            "stderr_tail": ["primary fail"],
            "output_path": None,
            "payload": None,
        }

    def fake_fallback() -> dict:
        out_path = (
            tmp_path
            / "runtime"
            / "omo"
            / "_delivery"
            / "audit-rollout"
            / "2026-06-12-5repos.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "repos": {
                "workspace": {
                    "health_grade": "R3",
                    "total_drift": 0,
                    "total_records": 4,
                }
            }
        }
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return {
            "returncode": 0,
            "stdout_tail": ["fallback ok"],
            "stderr_tail": [],
            "output_path": str(out_path.relative_to(tmp_path)),
            "payload": payload,
        }

    daemon._run_primary_audit_rollout = fake_primary  # type: ignore[reportAttributeAccessIssue]
    daemon._run_fallback_5repos = fake_fallback  # type: ignore[reportAttributeAccessIssue]
    rc = daemon.main()
    return {"worker": worker_id, "rc": rc}


class T01RaceConditionLock(unittest.TestCase):
    """T1: H3 daemon fcntl.flock 防 race - N 并行跑 N 条 entry 全部落盘."""

    def test_six_concurrent_runs_all_persist(self) -> None:
        """6 进程并行跑 (multiprocessing), 验证 index.json 末态 6 entry 全部落盘 (无覆盖)."""
        tmp_path = Path("/tmp/opc-race-test")
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        tmp_path.mkdir(parents=True)

        with multiprocessing.Pool(processes=6) as pool:
            results = pool.starmap(
                _worker_init,
                [(i, str(tmp_path), "weekly") for i in range(6)],
            )

        index_path = (
            tmp_path / "runtime" / "omo" / "_delivery" / "audit-rollout" / "index.json"
        )
        self.assertTrue(index_path.exists(), "index.json 必须存在")
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(
            len(index["runs"]),
            6,
            f"6 并行跑必须有 6 条 entry 落盘, 实际 {len(index['runs'])} 条 (race condition 修复前会少)",
        )
        for r in results:
            self.assertNotIn("error", r, f"worker 出错: {r}")
            self.assertEqual(
                r["rc"], 0, f"worker {r['worker']} rc 应为 0 (fallback 成功)"
            )


class T02ModePassthrough(unittest.TestCase):
    """T2: H3 5repos.py mode 透传 - OPC_MODE=monthly/pre-release 写对应 mode-specific 文件."""

    def _run_5repos(self, mode: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["OPC_MODE"] = mode
        env["OPC_GENERATED_AT"] = (
            "2026-06-12"  # 注入语义时间点 (T3 设计, 匹配硬编码期望)
        )
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "opc_audit_rollout_5repos.py")],
            cwd=str(WORKSPACE),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_weekly_mode_creates_weekly_file(self) -> None:
        result = self._run_5repos("weekly")
        self.assertEqual(result.returncode, 0, f"5repos failed: {result.stderr}")
        self.assertIn(
            "mode-specific",
            result.stderr,
            f"应打印 mode-specific 路径: {result.stderr}",
        )
        self.assertIn(
            "mode=weekly", result.stderr, f"应标 mode=weekly: {result.stderr}"
        )
        weekly_file = (
            WORKSPACE
            / "runtime"
            / "omo"
            / "_delivery"
            / "audit-rollout"
            / "2026-06-12-weekly.json"
        )
        self.assertTrue(weekly_file.exists(), f"{weekly_file} 应存在 (mode 透传)")

    def test_monthly_mode_creates_monthly_file(self) -> None:
        result = self._run_5repos("monthly")
        self.assertEqual(
            result.returncode, 0, f"5repos monthly failed: {result.stderr}"
        )
        self.assertIn(
            "mode=monthly", result.stderr, f"应标 mode=monthly: {result.stderr}"
        )
        monthly_file = (
            WORKSPACE
            / "runtime"
            / "omo"
            / "_delivery"
            / "audit-rollout"
            / "2026-06-12-monthly.json"
        )
        self.assertTrue(
            monthly_file.exists(),
            f"{monthly_file} 应存在 (修复前 5repos.py 写死 weekly, monthly 不可分辨)",
        )

    def test_pre_release_mode_creates_pre_release_file(self) -> None:
        result = self._run_5repos("pre-release")
        self.assertEqual(
            result.returncode, 0, f"5repos pre-release failed: {result.stderr}"
        )
        self.assertIn("mode=pre-release", result.stderr)
        pre_release_file = (
            WORKSPACE
            / "runtime"
            / "omo"
            / "_delivery"
            / "audit-rollout"
            / "2026-06-12-pre-release.json"
        )
        self.assertTrue(
            pre_release_file.exists(), f"{pre_release_file} 应存在 (mode 透传修复)"
        )

    def test_write_outputs_isolated_and_mode_aware(self) -> None:
        """独立验证 5repos.py 自身写盘契约, 不依赖 daemon/fallback/workspace 实盘."""
        spec = importlib.util.spec_from_file_location(
            "audit_5repos_worker", SCRIPTS / "opc_audit_rollout_5repos.py"
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore[reportArgumentType]
        assert spec.loader is not None  # type: ignore[reportOptionalMemberAccess]
        spec.loader.exec_module(module)  # type: ignore[reportOptionalMemberAccess]

        tmp_dir = Path("/tmp/opc-5repos-isolated")
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True)

        payload = {
            "summary": {"total_repos": 5},
            "repos": {"workspace": {"health_grade": "R1"}},
        }
        baseline, monthly = module.write_outputs(
            payload,
            out_dir=tmp_dir,
            today="2026-06-12",
            mode="monthly",
        )
        self.assertEqual(baseline.name, "2026-06-12-5repos.json")
        self.assertEqual(monthly.name, "2026-06-12-monthly.json")
        self.assertEqual(json.loads(baseline.read_text(encoding="utf-8")), payload)
        self.assertEqual(json.loads(monthly.read_text(encoding="utf-8")), payload)

    def test_write_outputs_invalid_mode_falls_back_to_weekly(self) -> None:
        """非法 mode 不得写出脏文件名, 必须回退 weekly."""
        spec = importlib.util.spec_from_file_location(
            "audit_5repos_worker_invalid", SCRIPTS / "opc_audit_rollout_5repos.py"
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore[reportArgumentType]
        assert spec.loader is not None  # type: ignore[reportOptionalMemberAccess]
        spec.loader.exec_module(module)  # type: ignore[reportOptionalMemberAccess]

        tmp_dir = Path("/tmp/opc-5repos-invalid-mode")
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True)

        _, mode_specific = module.write_outputs(
            {"summary": {"total_repos": 5}, "repos": {}},
            out_dir=tmp_dir,
            today="2026-06-12",
            mode="garbage-mode",
        )
        self.assertEqual(mode_specific.name, "2026-06-12-weekly.json")
        self.assertTrue(mode_specific.exists(), "非法 mode 应回退 weekly 文件名")


class T03ReleaseCycleGeneratedAtOverride(unittest.TestCase):
    """T3: H1 release OPC_GENERATED_AT override - 注入语义时间点形成真实 cadence."""

    def test_opc_generated_at_overrides_now(self) -> None:
        """OPC_GENERATED_AT 注入后, index entry 的 generated_at 用注入值."""
        for generated_at in ["2026-06-08T23:00:00Z", "2026-06-15T23:00:00Z"]:
            env = os.environ.copy()
            env["OPC_TRIGGER"] = "cron"
            env["OPC_GENERATED_AT"] = generated_at
            env["OPC_RELEASE_CUTOFF"] = "7 days ago"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "opc_p7_release_cycle.py")],
                cwd=str(WORKSPACE),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                result.returncode, 0, f"release cycle failed: {result.stderr}"
            )

        index = json.loads(
            (WORKSPACE / ".omo" / "_delivery" / "release" / "index.json").read_text(
                encoding="utf-8"
            )
        )
        all_gens = [r["generated_at"] for r in index["releases"]]
        self.assertIn(
            "2026-06-08T23:00:00Z",
            all_gens,
            f"应至少 1 条 entry 标记 2026-06-08T23:00:00Z, 实际 latest 5: {sorted(all_gens, reverse=True)[:5]}",
        )
        self.assertIn(
            "2026-06-15T23:00:00Z",
            all_gens,
            f"应至少 1 条 entry 标记 2026-06-15T23:00:00Z, 实际 latest 5: {sorted(all_gens, reverse=True)[:5]}",
        )

        # 验证 interval_days: 找 06-15 entry 紧邻 06-08 entry
        all_sorted = sorted(index["releases"], key=lambda r: r["generated_at"])
        for i, r in enumerate(all_sorted):
            if r["generated_at"] == "2026-06-15T23:00:00Z" and i > 0:
                prev = all_sorted[i - 1]
                if prev["generated_at"] == "2026-06-08T23:00:00Z":
                    self.assertEqual(
                        r.get("interval_days_from_previous"),
                        7,
                        f"06-15 entry 紧邻 06-08 entry 应有 interval=7, 实际 {r.get('interval_days_from_previous')}",
                    )
                    break

    def test_opc_today_overrides_today(self) -> None:
        """OPC_TODAY 注入后, version 命名用注入日期."""
        unique_today = "2026-06-09"
        env = os.environ.copy()
        env["OPC_TRIGGER"] = "cron"
        env["OPC_TODAY"] = unique_today
        env["OPC_GENERATED_AT"] = f"{unique_today}T23:00:00Z"
        env["OPC_RELEASE_CUTOFF"] = "7 days ago"
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "opc_p7_release_cycle.py")],
            cwd=str(WORKSPACE),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, f"release cycle failed: {result.stderr}")
        index = json.loads(
            (WORKSPACE / ".omo" / "_delivery" / "release" / "index.json").read_text(
                encoding="utf-8"
            )
        )
        found = any(r["version"] == f"v{unique_today}-r1" for r in index["releases"])
        self.assertTrue(found, f"应有 v{unique_today}-r1 entry (OPC_TODAY override)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
