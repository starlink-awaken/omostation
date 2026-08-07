#!/usr/bin/env python3
"""
bin/gac/test-mof-governance-ecosystem.py — 全图架构、运维治理与代谢演进体系全场景集成测试套件

校验 4 大核心场景：
- 场景 A: 债务挖掘 ➔ C2G 升维 ➔ Goal 绑定断言
- 场景 B: agent-workflow start --bet ➔ Objective 自动填充断言
- 场景 C: MOS Belief 记录 ➔ audit.log 审计流落盘断言
- 场景 D: agent-workflow bootstrap ➔ LifeOS 价值观与 MOS 经验渲染断言
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

raw_ws = str(Path(__file__).resolve().parents[2])
if "/Workspace" in raw_ws:
    raw_ws = raw_ws.replace("/Workspace", "/workspace")
WS = Path(raw_ws)

omo_src = str(WS / "projects/omo/src")
if omo_src not in sys.path:
    sys.path.insert(0, omo_src)

from omo.omo_belief import MOSBeliefManager
from omo.omo_paths import WORKSPACE_ROOT


class TestMOFGovernanceEcosystem(unittest.TestCase):

    def test_scenario_a_debt_synthesis_and_goal_binding(self):
        """场景 A: 测试 omo-debt-synthesizer 债务升维与 Goal ID 绑定"""
        gac_dir = str(WS / "bin" / "gac")
        if gac_dir not in sys.path:
            sys.path.insert(0, gac_dir)
        import omo_debt_synthesizer as synth_mod

        debts = synth_mod.load_debts()
        res = synth_mod.synthesize_debts(debts)
        self.assertIn("proposed_bets", res)
        if res["proposed_bets"]:
            first_bet = res["proposed_bets"][0]
            self.assertIn("goal_id", first_bet)
            self.assertTrue(first_bet["goal_id"].startswith("GOAL-"))

    def test_scenario_b_workflow_start_bet_auto_resolution(self):
        """场景 B: 测试 agent-workflow start --bet 参数自动解析 Objective"""
        wf_script = os.path.realpath(str(WS / "bin" / "agent-workflow.py"))
        cmd = [
            sys.executable,
            wf_script,
            "start",
            "project-code-change",
            "--profile",
            "engineering-agent",
            "--bet",
            "BET-Y1Q1-T1-01",
            "--dry-run",
            "--json",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(WS / "projects/omo/src")
        res = subprocess.run(cmd, cwd=os.path.realpath(str(WS)), capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, f"Workflow start --bet failed: {res.stderr}")
        data = json.loads(res.stdout)
        self.assertIn("objective", data)
        self.assertIn("BET-Y1Q1-T1-01", data["objective"])

    def test_scenario_c_mos_belief_and_audit_log(self):
        """场景 C: 测试 MOS Agent Belief 记录与 audit.log 审计流追加"""
        mgr = MOSBeliefManager(root=WS)
        test_topic = f"test_ecosystem_{os.getpid()}"
        b_id = mgr.record_belief(
            topic=test_topic,
            belief_text="Ecosystem integration test belief assertion",
            pitfall="Fragmented governance",
            solution="Integrated 8D Meta-Architecture",
            scope_path="bin/gac/*",
            source_run_id="test-run-ecosystem",
        )
        self.assertTrue(b_id.startswith("belief-"))
        self.assertTrue(mgr.audit_log_file.exists())
        audit_content = mgr.audit_log_file.read_text(encoding="utf-8")
        self.assertIn(f"id={b_id}", audit_content)

    def test_scenario_d_bootstrap_lifeos_and_belief_rendering(self):
        """场景 D: 测试 agent-workflow bootstrap 报告包含 LifeOS 与 MOS 经验渲染"""
        wf_script = os.path.realpath(str(WS / "bin" / "agent-workflow.py"))
        cmd = [
            sys.executable,
            wf_script,
            "bootstrap",
            "--skip-health",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(WS / "projects/omo/src")
        res = subprocess.run(cmd, cwd=os.path.realpath(str(WS)), capture_output=True, text=True, env=env)
        self.assertEqual(res.returncode, 0, f"Bootstrap failed: {res.stderr}")
        self.assertIn("LifeOS values & directives", res.stdout)
        self.assertIn("MOS agent beliefs", res.stdout)


if __name__ == "__main__":
    unittest.main()
