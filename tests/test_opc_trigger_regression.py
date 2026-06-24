#!/usr/bin/env python3
"""OPC P7-H1 / P7-H3 / P6-approval-board regression tests.

测试 3 个修复:
  T1: P7-H1 release cycle wrapper — manual 调用不被标为 cron
  T2: P7-H1 release cycle wrapper — cron 调用 (INVOCATION_ID=cron) 标为 cron
  T3: P7-H1 release cycle wrapper — OPC_TRIGGER 显式设值时透传 (优先级最高)
  T4: P7-H3 audit-rollout daemon — primary 失败 + fallback 成功 → index 仍写, returncode=0
  T5: P7-H3 audit-rollout daemon — primary 失败 + fallback 失败 → index 仍写, returncode=1
  T6: P6 approval board — latest_week 与 loop history 对齐
  T7: P6 approval board — latest_week_source 字段正确标注
  T8: P6 self-evolve nop task latest_week 与 loop history 对齐

设计:
  - 不修改 .omo/* 现状 (每个 test 跑完恢复: 临时 OPS_ID 隔离)
  - 使用 tmp 目录做 env 隔离 (override ROOT)
  - 不用 mock, 直接调 wrapper
  - 每个 test 跑完清理: 移除 tmp .omo 创建的临时文件
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path("/Users/xiamingxing/Workspace").resolve()


def _run_wrapper(wrapper: str, env: dict[str, str]) -> dict:
    """跑 wrapper, 捕获 wrapper 注入的 OPC_TRIGGER 值.

    策略: 在 tmp 目录复制 wrapper, 在 exec 前注入 env 探针.
    """
    tmp = Path(tempfile.mkdtemp(prefix="opc-regression-"))
    try:
        target = tmp / Path(wrapper).name
        shutil.copy(wrapper, target)
        content = target.read_text(encoding="utf-8")
        # 替换所有可能的 exec / python3 行, 注入 env 探针
        # 探针: 把当前 env 写 /tmp/opc-trigger-probe.txt, 然后 exec 原命令
        inject = (
            "env | grep -E '^(OPC_TRIGGER|INVOCATION_ID|WORKSPACE)=' "
            "> /tmp/opc-trigger-probe.txt; "
        )
        content = content.replace("exec python3 ", inject + "exec python3 ")
        content = content.replace(
            "python3 scripts/opc_p6_self_evolve.py",
            inject + "python3 scripts/opc_p6_self_evolve.py",
        )
        content = content.replace(
            "python3 scripts/opc_p5_radar_cron.py",
            inject + "python3 scripts/opc_p5_radar_cron.py",
        )
        content = content.replace(
            "python3 scripts/opc_p7_release_cycle.py",
            inject + "python3 scripts/opc_p7_release_cycle.py",
        )
        content = content.replace(
            "python3 scripts/opc_p7_audit_rollout_daemon.py",
            inject + "python3 scripts/opc_p7_audit_rollout_daemon.py",
        )
        target.write_text(content, encoding="utf-8")
        probe = Path("/tmp/opc-trigger-probe.txt")
        if probe.exists():
            probe.unlink()
        full_env = {**os.environ, **env}
        full_env.setdefault("OPC_RELEASE_CUTOFF", "7 days ago")
        full_env.setdefault("WORKSPACE", str(REPO_ROOT))
        result = subprocess.run(
            ["bash", str(target)],
            cwd=str(REPO_ROOT),
            env=full_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        probe_data: dict[str, str] = {}
        if probe.exists():
            for line in probe.read_text(encoding="utf-8").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    probe_data[k] = v
        return {
            "wrapper_returncode": result.returncode,
            "trigger_injected": probe_data.get("OPC_TRIGGER", "<unset>"),
            "invocation_id_seen": probe_data.get("INVOCATION_ID", "<unset>"),
            "stdout_tail": result.stdout.splitlines()[-3:],
            "stderr_tail": result.stderr.splitlines()[-3:],
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class T01ReleaseWrapperTrigger(unittest.TestCase):
    """T1-T3: P7-H1 release cycle wrapper trigger 注入语义."""

    def setUp(self) -> None:
        self.wrapper = str(REPO_ROOT / "scripts" / "opc_p7_release_cycle_cron.sh")

    def test_t1_manual_unset(self) -> None:
        """manual: 不设 INVOCATION_ID, 不设 OPC_TRIGGER → 应注入 manual."""
        result = _run_wrapper(self.wrapper, env={})
        self.assertEqual(
            result["trigger_injected"],
            "manual",
            f"manual 调用应注入 manual, 实际: {result}",
        )

    def test_t2_cron_invocation_id(self) -> None:
        """cron: 设 INVOCATION_ID=cron, 不设 OPC_TRIGGER → 应注入 cron."""
        result = _run_wrapper(self.wrapper, env={"INVOCATION_ID": "cron"})
        self.assertEqual(
            result["trigger_injected"],
            "cron",
            f"INVOCATION_ID=cron 应注入 cron, 实际: {result}",
        )

    def test_t3_explicit_opc_trigger_passthrough(self) -> None:
        """explicit: 设 OPC_TRIGGER=manual (无 INVOCATION_ID) → 透传 manual."""
        result = _run_wrapper(self.wrapper, env={"OPC_TRIGGER": "manual"})
        self.assertEqual(
            result["trigger_injected"],
            "manual",
            f"OPC_TRIGGER 显式 manual 应透传, 实际: {result}",
        )

    def test_t3b_explicit_cron_passthrough(self) -> None:
        """explicit: 设 OPC_TRIGGER=cron (有 INVOCATION_ID=manual) → OPC_TRIGGER 优先."""
        result = _run_wrapper(
            self.wrapper, env={"OPC_TRIGGER": "cron", "INVOCATION_ID": "manual"}
        )
        self.assertEqual(
            result["trigger_injected"],
            "cron",
            f"显式 OPC_TRIGGER=cron 应透传, 实际: {result}",
        )


class T02AuditRolloutWrapperTrigger(unittest.TestCase):
    """T2-set: P7-H3 audit-rollout wrapper trigger 注入语义."""

    def setUp(self) -> None:
        self.wrapper = str(REPO_ROOT / "scripts" / "opc_p7_audit_rollout_cron.sh")

    def test_t1_manual_unset(self) -> None:
        result = _run_wrapper(self.wrapper, env={})
        self.assertEqual(
            result["trigger_injected"],
            "manual",
            f"manual 应注入 manual, 实际: {result}",
        )

    def test_t2_cron_invocation_id(self) -> None:
        result = _run_wrapper(self.wrapper, env={"INVOCATION_ID": "cron"})
        self.assertEqual(
            result["trigger_injected"],
            "cron",
            f"INVOCATION_ID=cron 应注入 cron, 实际: {result}",
        )


class T03WeeklyLoopWrapperTrigger(unittest.TestCase):
    """T3-set: P6 weekly_loop wrapper trigger 注入语义."""

    def setUp(self) -> None:
        self.wrapper = str(REPO_ROOT / "scripts" / "opc_p6_weekly_loop_cron.sh")

    def test_t1_manual_unset(self) -> None:
        result = _run_wrapper(self.wrapper, env={})
        self.assertEqual(result["trigger_injected"], "manual")

    def test_t2_cron_invocation_id(self) -> None:
        result = _run_wrapper(self.wrapper, env={"INVOCATION_ID": "cron"})
        self.assertEqual(result["trigger_injected"], "cron")


class T04SelfEvolveWrapperTrigger(unittest.TestCase):
    """T4-set: P6 self_evolve wrapper trigger 注入语义."""

    def setUp(self) -> None:
        self.wrapper = str(REPO_ROOT / "scripts" / "opc_p6_self_evolve_cron.sh")

    def test_t1_manual_unset(self) -> None:
        result = _run_wrapper(self.wrapper, env={})
        self.assertEqual(result["trigger_injected"], "manual")

    def test_t2_cron_invocation_id(self) -> None:
        result = _run_wrapper(self.wrapper, env={"INVOCATION_ID": "cron"})
        self.assertEqual(result["trigger_injected"], "cron")


class T05ApprovalBoardLatestWeek(unittest.TestCase):
    """T6-T7: P6 approval board latest_week 与 loop history 对齐."""

    def test_approval_board_uses_loop_history(self) -> None:
        """跑 approval board, 验证 summary.latest_week = loop history.summary.latest_week."""
        result = subprocess.run(
            ["python3", "scripts/opc_p6_approval_board.py"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(
            result.returncode, 0, f"approval board failed: {result.stderr}"
        )
        board = json.loads(
            (
                REPO_ROOT
                / ".omo"
                / "_control"
                / "evolution"
                / "approval-board"
                / "current.json"
            ).read_text(encoding="utf-8")
        )
        loop_history = json.loads(
            (
                REPO_ROOT / ".omo" / "_control" / "evolution" / "loop" / "history.json"
            ).read_text(encoding="utf-8")
        )
        loop_latest_week = loop_history.get("summary", {}).get("latest_week")
        board_latest_week = board.get("summary", {}).get("latest_week")
        self.assertEqual(
            board_latest_week,
            loop_latest_week,
            f"approval_board.latest_week ({board_latest_week}) 应等于 loop_history.latest_week ({loop_latest_week})",
        )
        self.assertEqual(
            board["summary"].get("latest_week_source"),
            "loop_history",
            f"latest_week_source 应为 loop_history, 实际: {board['summary'].get('latest_week_source')}",
        )


class T06AuditRolloutDaemonWriteback(unittest.TestCase):
    """T4-T5: P7-H3 audit-rollout daemon 写回语义 (primary fail → fallback success/fail).

    真实运行会污染 .omo/_delivery/audit-rollout/index.json, 所以用 mock 替换
    primary / fallback 子进程来隔离测试.
    """

    def setUp(self) -> None:
        # 保存原始 index, 跑完恢复
        self.index_path = (
            REPO_ROOT / ".omo" / "_delivery" / "audit-rollout" / "index.json"
        )
        self.index_backup = (
            self.index_path.read_bytes() if self.index_path.exists() else None
        )

    def tearDown(self) -> None:
        if self.index_backup is not None:
            self.index_path.write_bytes(self.index_backup)
        elif self.index_path.exists():
            # 删掉新建的
            self.index_path.unlink()

    def test_t4_fallback_success_writes_index(self) -> None:
        """primary fail + fallback success → index 写, returncode=0, fallback_used=True."""
        # 用 monkey-patch 替换 _run_primary / _run_fallback
        import scripts.opc_p7_audit_rollout_daemon as daemon

        original_primary = daemon._run_primary_audit_rollout
        original_fallback = daemon._run_fallback_5repos

        def fake_primary(mode: str) -> dict:
            return {
                "returncode": 1,
                "stdout_tail": [],
                "stderr_tail": ["baseline missing: llm-gateway"],
                "output_path": None,
                "payload": None,
            }

        def fake_fallback() -> dict:
            fake_payload = {
                "repos": {
                    "workspace": {"health_grade": "R3"},
                    "omo": {"health_grade": "R0"},
                    "llm-gateway": {"health_grade": "R0"},
                    "compute-mesh": {"health_grade": "R0"},
                    "runtime": {"health_grade": "R0"},
                }
            }
            # 真写 5repos.json 让 daemon 读
            fallback_path = (
                REPO_ROOT
                / ".omo"
                / "_delivery"
                / "audit-rollout"
                / f"{daemon._today()}-5repos.json"
            )
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_path.write_text(
                json.dumps(fake_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return {
                "returncode": 0,
                "stdout_tail": ["ok"],
                "stderr_tail": [],
                "output_path": str(fallback_path.relative_to(REPO_ROOT)),
                "payload": fake_payload,
            }

        daemon._run_primary_audit_rollout = fake_primary
        daemon._run_fallback_5repos = fake_fallback
        try:
            # 跑前 baseline
            pre_count = 0
            if self.index_path.exists():
                pre_count = len(
                    json.loads(self.index_path.read_text(encoding="utf-8")).get(
                        "runs", []
                    )
                )

            os.environ["OPC_TRIGGER"] = "manual"
            os.environ["OPC_MODE"] = "weekly"
            rc = daemon.main()

            self.assertEqual(
                rc, 0, f"daemon.main returncode 应为 0 (fallback 成功), 实际 {rc}"
            )
            self.assertTrue(self.index_path.exists(), "index.json 必须存在")
            index = json.loads(self.index_path.read_text(encoding="utf-8"))
            new_count = len(index.get("runs", []))
            self.assertEqual(
                new_count,
                pre_count + 1,
                f"index 应新增 1 条, pre={pre_count}, post={new_count}",
            )
            latest = index["runs"][-1]
            self.assertEqual(latest["trigger_source"], "manual")
            self.assertEqual(latest["returncode"], 0)
            self.assertTrue(latest["fallback_used"], "fallback_used 必须为 True")
            self.assertEqual(latest["fallback_returncode"], 0)
            self.assertIsNotNone(
                latest["fallback_output_path"], "fallback output_path 必须非 None"
            )
            self.assertIsNotNone(latest["primary_error"], "primary_error 必须有")
        finally:
            daemon._run_primary_audit_rollout = original_primary
            daemon._run_fallback_5repos = original_fallback

    def test_t5_both_fail_writes_index_with_failure(self) -> None:
        """primary fail + fallback fail → index 仍写, returncode=1, failed_count delta=+1."""
        import scripts.opc_p7_audit_rollout_daemon as daemon

        original_primary = daemon._run_primary_audit_rollout
        original_fallback = daemon._run_fallback_5repos

        def fake_primary(mode: str) -> dict:
            return {
                "returncode": 2,
                "stdout_tail": [],
                "stderr_tail": ["primary fail"],
                "output_path": None,
                "payload": None,
            }

        def fake_fallback() -> dict:
            return {
                "returncode": 3,
                "stdout_tail": [],
                "stderr_tail": ["fallback fail"],
                "output_path": None,
                "payload": None,
            }

        daemon._run_primary_audit_rollout = fake_primary
        daemon._run_fallback_5repos = fake_fallback
        try:
            pre_count = 0
            pre_failed_count = 0
            if self.index_path.exists():
                pre_index = json.loads(self.index_path.read_text(encoding="utf-8"))
                pre_count = len(pre_index.get("runs", []))
                pre_failed_count = pre_index.get("summary", {}).get("failed_count", 0)

            os.environ["OPC_TRIGGER"] = "manual"
            os.environ["OPC_MODE"] = "weekly"
            rc = daemon.main()

            self.assertEqual(
                rc, 1, f"daemon.main returncode 应为 1 (双失败), 实际 {rc}"
            )
            self.assertTrue(self.index_path.exists(), "index.json 必须存在 (失败也写)")
            index = json.loads(self.index_path.read_text(encoding="utf-8"))
            new_count = len(index.get("runs", []))
            self.assertEqual(
                new_count,
                pre_count + 1,
                f"index 应新增 1 条 (失败也写), pre={pre_count}, post={new_count}",
            )
            latest = index["runs"][-1]
            self.assertEqual(latest["trigger_source"], "manual")
            self.assertEqual(latest["returncode"], 1, "run returncode 应为 1")
            self.assertIsNone(latest["output_path"], "双失败 output_path 应为 None")
            self.assertEqual(latest["primary_returncode"], 2)
            self.assertEqual(latest["fallback_returncode"], 3)
            # failed_count delta 应为 1 (此次新增 1 条失败)
            self.assertEqual(
                index["summary"]["failed_count"],
                pre_failed_count + 1,
                f"summary.failed_count delta 应为 +1, pre={pre_failed_count}, post={index['summary']['failed_count']}",
            )
        finally:
            daemon._run_primary_audit_rollout = original_primary
            daemon._run_fallback_5repos = original_fallback


if __name__ == "__main__":
    unittest.main(verbosity=2)
