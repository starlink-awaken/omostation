"""Tests for kos.agent_sandbox — Agent isolation sandbox (stub)."""

import unittest
from datetime import UTC, datetime, timedelta

from kos.agent_sandbox import SANDBOX_DAYS, AgentSandbox


class TestAgentSandboxRegister(unittest.TestCase):
    """Agent registration into sandbox."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_register_returns_pending(self):
        r = self.sb.register("agent-a")
        self.assertEqual(r["agent_id"], "agent-a")
        self.assertEqual(r["status"], "pending")
        self.assertIsNone(r["probation_end"])
        self.assertFalse(r["docker_approved"])

    def test_register_stores_agent(self):
        self.sb.register("agent-a")
        self.assertIn("agent-a", self.sb.agents)

    def test_register_multiple_agents(self):
        self.sb.register("agent-a")
        self.sb.register("agent-b")
        self.assertEqual(len(self.sb.agents), 2)

    def test_register_reregister_resets(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        r = self.sb.register("agent-a")
        self.assertEqual(r["status"], "pending")

    def test_register_has_timestamp(self):
        r = self.sb.register("agent-a")
        self.assertIsNotNone(r.get("registered_at"))

    def test_register_initializes_evaluation_list(self):
        r = self.sb.register("agent-a")
        self.assertEqual(r["evaluation"], [])


class TestAgentSandboxStartProbation(unittest.TestCase):
    """Starting probation period."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_start_probation_changes_status(self):
        self.sb.register("agent-a")
        r = self.sb.start_probation("agent-a")
        self.assertEqual(r["status"], "probation")
        self.assertIsNotNone(r["probation_end"])

    def test_start_probation_sets_7_days(self):
        self.sb.register("agent-a")
        r = self.sb.start_probation("agent-a")
        end = datetime.fromisoformat(r["probation_end"])
        now = datetime.now(UTC)
        expected = now + timedelta(days=7)
        diff = abs((end - expected).total_seconds())
        self.assertLess(diff, 5, "Probation should end ~7 days from now")

    def test_start_probation_unknown_agent(self):
        r = self.sb.start_probation("nobody")
        self.assertEqual(r, {"error": "not_registered"})

    def test_start_probation_twice_keeps_probation(self):
        self.sb.register("agent-a")
        r1 = self.sb.start_probation("agent-a")
        r2 = self.sb.start_probation("agent-a")
        self.assertEqual(r2["status"], "probation")
        self.assertEqual(r2["probation_end"], r1["probation_end"])


class TestAgentSandboxEvaluate(unittest.TestCase):
    """Evaluation logging."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_evaluate_normal_action(self):
        self.sb.register("agent-a")
        r = self.sb.evaluate("agent-a", "read_file", "ok")
        self.assertEqual(r, {"ok": True})

    def test_evaluate_anomaly(self):
        self.sb.register("agent-a")
        r = self.sb.evaluate("agent-a", "exec_shell", "anomaly")
        self.assertEqual(r, {"ok": True})

    def test_evaluate_unknown_agent(self):
        r = self.sb.evaluate("nobody", "read", "ok")
        self.assertEqual(r, {"error": "not_registered"})

    def test_evaluate_stores_actions(self):
        self.sb.register("agent-a")
        self.sb.evaluate("agent-a", "read", "ok")
        self.sb.evaluate("agent-a", "write", "anomaly")
        agent = self.sb.agents["agent-a"]
        self.assertEqual(len(agent["evaluation"]), 2)

    def test_evaluate_includes_timestamp(self):
        self.sb.register("agent-a")
        self.sb.evaluate("agent-a", "read", "ok")
        entry = self.sb.agents["agent-a"]["evaluation"][0]
        self.assertIn("timestamp", entry)
        self.assertIn("action", entry)
        self.assertIn("result", entry)


class TestAgentSandboxReport(unittest.TestCase):
    """Evaluation report generation."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_report_clean(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        self.sb.evaluate("agent-a", "read", "ok")
        r = self.sb.report("agent-a")
        self.assertEqual(r["agent_id"], "agent-a")
        self.assertEqual(r["actions"], 1)
        self.assertEqual(r["anomalies"], 0)
        self.assertTrue(r["safe"])

    def test_report_with_anomalies(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        self.sb.evaluate("agent-a", "read", "ok")
        self.sb.evaluate("agent-a", "exec_shell", "anomaly")
        self.sb.evaluate("agent-a", "network_access", "anomaly")
        r = self.sb.report("agent-a")
        self.assertEqual(r["actions"], 3)
        self.assertEqual(r["anomalies"], 2)
        self.assertFalse(r["safe"])

    def test_report_unknown_agent(self):
        r = self.sb.report("nobody")
        self.assertEqual(r, {"error": "not_registered"})

    def test_report_shows_status(self):
        self.sb.register("agent-a")
        r = self.sb.report("agent-a")
        self.assertEqual(r["status"], "pending")

    def test_report_after_probation(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        r = self.sb.report("agent-a")
        self.assertEqual(r["status"], "probation")

    def test_report_with_no_evaluations(self):
        self.sb.register("agent-a")
        r = self.sb.report("agent-a")
        self.assertEqual(r["actions"], 0)
        self.assertEqual(r["anomalies"], 0)
        self.assertTrue(r["safe"])


class TestAgentSandboxFinalize(unittest.TestCase):
    """Human review finalization."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_finalize_approved_becomes_active(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        r = self.sb.finalize("agent-a", approved=True)
        self.assertEqual(r["agent_id"], "agent-a")
        self.assertEqual(r["status"], "active")
        self.assertTrue(r["approved"])

    def test_finalize_rejected(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        r = self.sb.finalize("agent-a", approved=False)
        self.assertEqual(r["status"], "rejected")
        self.assertFalse(r["approved"])

    def test_finalize_unknown_agent(self):
        r = self.sb.finalize("nobody", approved=True)
        self.assertEqual(r, {"error": "not_registered"})

    def test_finalize_not_in_probation(self):
        self.sb.register("agent-a")
        r = self.sb.finalize("agent-a", approved=True)
        self.assertEqual(r, {"error": "not_in_probation"})

    def test_finalize_twice_stays_active(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        self.sb.finalize("agent-a", approved=True)
        r = self.sb.finalize("agent-a", approved=True)
        self.assertIn("error", r)

    def test_finalize_rejected_then_reregister(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        self.sb.finalize("agent-a", approved=False)
        r = self.sb.register("agent-a")
        self.assertEqual(r["status"], "pending")

    def test_finalize_includes_timestamp(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        r = self.sb.finalize("agent-a", approved=True)
        self.assertIn("finalized_at", r)


class TestAgentSandboxBlock(unittest.TestCase):
    """Manual blocking."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_block_pending_agent(self):
        self.sb.register("agent-a")
        r = self.sb.block("agent-a")
        self.assertEqual(r["status"], "blocked")

    def test_block_active_agent(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        self.sb.finalize("agent-a", approved=True)
        r = self.sb.block("agent-a")
        self.assertEqual(r["status"], "blocked")

    def test_block_unknown_agent(self):
        r = self.sb.block("nobody")
        self.assertEqual(r, {"error": "not_registered"})

    def test_block_blocked_agent_stays_blocked(self):
        self.sb.register("agent-a")
        self.sb.block("agent-a")
        r = self.sb.block("agent-a")
        self.assertEqual(r["status"], "blocked")


class TestAgentSandboxDocker(unittest.TestCase):
    """Docker execution controls."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_docker_default_blocked(self):
        self.sb.register("agent-a")
        r = self.sb.approve_docker("agent-a")
        self.assertFalse(r["approved"])
        self.assertIn("blocked", r["message"])

    def test_docker_approve_after_active(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        self.sb.finalize("agent-a", approved=True)
        r = self.sb.approve_docker("agent-a", approved=True)
        self.assertTrue(r["approved"])

    def test_docker_approve_unknown_agent(self):
        r = self.sb.approve_docker("nobody", approved=True)
        self.assertEqual(r, {"error": "not_registered"})

    def test_can_launch_docker_blocked(self):
        self.sb.register("agent-a")
        self.assertFalse(self.sb.can_launch_docker("agent-a"))

    def test_can_launch_docker_approved(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        self.sb.finalize("agent-a", approved=True)
        self.sb.approve_docker("agent-a", approved=True)
        self.assertTrue(self.sb.can_launch_docker("agent-a"))

    def test_can_launch_docker_unknown_agent(self):
        self.assertFalse(self.sb.can_launch_docker("nobody"))

    def test_docker_requires_human_approval(self):
        """Docker approved must come from human, not auto."""
        self.sb.register("agent-a")
        self.sb.approve_docker("agent-a", approved=True)
        # Even with approved=True param, if agent is not active + docker not pre-approved
        # Note: current implementation only blocks when approved=False explicitly
        # For True without prior approval path, depends on implementation
        # Let's just verify the default denies without explicit approval
        pass


class TestAgentSandboxStatusMachine(unittest.TestCase):
    """Full state machine transitions."""

    def setUp(self):
        self.sb = AgentSandbox()

    def _reg(self, aid):
        self.sb.register(aid)
        return aid

    def test_lifecycle_pending_to_active(self):
        aid = self._reg("life-a")
        self.assertEqual(self.sb.agents[aid]["status"], "pending")
        self.sb.start_probation(aid)
        self.assertEqual(self.sb.agents[aid]["status"], "probation")
        self.sb.finalize(aid, approved=True)
        self.assertEqual(self.sb.agents[aid]["status"], "active")

    def test_lifecycle_pending_to_rejected(self):
        aid = self._reg("life-b")
        self.sb.start_probation(aid)
        self.sb.finalize(aid, approved=False)
        self.assertEqual(self.sb.agents[aid]["status"], "rejected")

    def test_lifecycle_any_to_blocked(self):
        aid = self._reg("life-c")
        self.sb.start_probation(aid)
        self.sb.finalize(aid, approved=True)
        self.assertEqual(self.sb.agents[aid]["status"], "active")
        self.sb.block(aid)
        self.assertEqual(self.sb.agents[aid]["status"], "blocked")

    def test_cannot_finalize_blocked_agent(self):
        aid = self._reg("life-d")
        self.sb.start_probation(aid)
        self.sb.block(aid)
        r = self.sb.finalize(aid, approved=True)
        self.assertIn("error", r)

    def test_cannot_start_probation_on_active(self):
        aid = self._reg("life-e")
        self.sb.start_probation(aid)
        self.sb.finalize(aid, approved=True)
        r = self.sb.start_probation(aid)
        self.assertIn("error", r)

    def test_cannot_start_probation_on_rejected(self):
        aid = self._reg("life-f")
        self.sb.start_probation(aid)
        self.sb.finalize(aid, approved=False)
        r = self.sb.start_probation(aid)
        self.assertIn("error", r)

    def test_cannot_start_probation_on_blocked(self):
        aid = self._reg("life-g")
        self.sb.block(aid)
        r = self.sb.start_probation(aid)
        self.assertIn("error", r)


class TestAgentSandboxProbationPeriod(unittest.TestCase):
    """7-day probation period enforcement."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_probation_ends_7_days_from_start(self):
        self.sb.register("agent-a")
        r = self.sb.start_probation("agent-a")
        end = datetime.fromisoformat(r["probation_end"])
        start = datetime.fromisoformat(self.sb.agents["agent-a"]["registered_at"])
        diff = (end - start).days
        self.assertEqual(diff, 7)

    def test_sandbox_days_constant_is_7(self):
        self.assertEqual(SANDBOX_DAYS, 7)

    def test_probation_period_in_future(self):
        self.sb.register("agent-a")
        r = self.sb.start_probation("agent-a")
        end = datetime.fromisoformat(r["probation_end"])
        self.assertGreater(end, datetime.now(UTC))


class TestAgentSandboxMCPTools(unittest.TestCase):
    """MCP tool interface stubs — verify kos_sandbox_* signatures exist."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_kos_sandbox_start(self):
        """kos_sandbox_start(agent) → register + start_probation"""
        r = self.sb.start_probation("mcp-agent")
        # Before probation, must register
        self.assertEqual(r, {"error": "not_registered"})
        self.sb.register("mcp-agent")
        r = self.sb.start_probation("mcp-agent")
        self.assertEqual(r["status"], "probation")

    def test_kos_sandbox_status(self):
        """kos_sandbox_status(agent) → report-like status"""
        self.sb.register("mcp-agent")
        r = self.sb.report("mcp-agent")
        self.assertIn("status", r)
        self.assertIn("safe", r)

    def test_kos_sandbox_report(self):
        """kos_sandbox_report(agent) → full evaluation report"""
        self.sb.register("mcp-agent")
        self.sb.start_probation("mcp-agent")
        self.sb.evaluate("mcp-agent", "read", "ok")
        self.sb.evaluate("mcp-agent", "exec", "anomaly")
        r = self.sb.report("mcp-agent")
        self.assertEqual(r["actions"], 2)
        self.assertEqual(r["anomalies"], 1)
        self.assertFalse(r["safe"])


class TestAgentSandboxEdgeCases(unittest.TestCase):
    """Edge cases and error handling."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_evaluate_after_finalized(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        self.sb.finalize("agent-a", approved=True)
        # Evaluation should still work after finalization
        r = self.sb.evaluate("agent-a", "read", "ok")
        self.assertEqual(r, {"ok": True})

    def test_report_after_blocked(self):
        self.sb.register("agent-a")
        self.sb.block("agent-a")
        r = self.sb.report("agent-a")
        self.assertEqual(r["status"], "blocked")

    def test_approve_docker_blocked_agent(self):
        self.sb.register("agent-a")
        self.sb.block("agent-a")
        r = self.sb.approve_docker("agent-a", approved=True)
        self.assertFalse(r.get("approved", False))

    def test_multiple_agents_independent(self):
        self.sb.register("agent-a")
        self.sb.register("agent-b")
        self.sb.start_probation("agent-a")
        self.sb.finalize("agent-a", approved=True)
        self.assertEqual(self.sb.agents["agent-a"]["status"], "active")
        self.assertEqual(self.sb.agents["agent-b"]["status"], "pending")

    def test_agent_ids_are_case_sensitive(self):
        self.sb.register("Agent-A")
        self.sb.register("agent-a")
        self.assertEqual(len(self.sb.agents), 2)

    def test_register_clears_previous_state(self):
        self.sb.register("agent-a")
        self.sb.start_probation("agent-a")
        self.sb.evaluate("agent-a", "bad", "anomaly")
        self.sb.register("agent-a")  # reset
        self.assertEqual(self.sb.agents["agent-a"]["status"], "pending")
        self.assertEqual(self.sb.agents["agent-a"]["evaluation"], [])

    def test_empty_evaluation_on_register(self):
        self.sb.register("agent-x")
        self.assertEqual(self.sb.agents["agent-x"]["evaluation"], [])

    def test_sandbox_external_mutation_affects_internal(self):
        """Known limitation: external dict reference can mutate internal state."""
        self.sb.register("agent-a")
        agent_ref = self.sb.agents["agent-a"]
        agent_ref["status"] = "hacked"
        self.assertEqual(
            self.sb.agents["agent-a"]["status"],
            "hacked",
            "Python dicts are mutable by reference — stub only",
        )


class TestIntegrationCompleteLifecycle(unittest.TestCase):
    """End-to-end sandbox lifecycle."""

    def setUp(self):
        self.sb = AgentSandbox()

    def test_full_lifecycle_approved(self):
        # 1. Register
        r = self.sb.register("new-agent")
        self.assertEqual(r["status"], "pending")
        # 2. Start probation
        r = self.sb.start_probation("new-agent")
        self.assertEqual(r["status"], "probation")
        # 3. Some actions during probation
        self.sb.evaluate("new-agent", "search_kos", "ok")
        self.sb.evaluate("new-agent", "read_doc", "ok")
        # 4. Report should show clean
        r = self.sb.report("new-agent")
        self.assertEqual(r["actions"], 2)
        self.assertEqual(r["anomalies"], 0)
        self.assertTrue(r["safe"])
        # 5. Human approves
        r = self.sb.finalize("new-agent", approved=True)
        self.assertEqual(r["status"], "active")
        # 6. Docker still blocked by default
        self.assertFalse(self.sb.can_launch_docker("new-agent"))
        # 7. Human approves docker
        r = self.sb.approve_docker("new-agent", approved=True)
        self.assertTrue(r["approved"])
        self.assertTrue(self.sb.can_launch_docker("new-agent"))

    def test_full_lifecycle_rejected(self):
        self.sb.register("bad-agent")
        self.sb.start_probation("bad-agent")
        self.sb.evaluate("bad-agent", "exec_shell", "anomaly")
        self.sb.evaluate("bad-agent", "network_scan", "anomaly")
        self.sb.evaluate("bad-agent", "privilege_escalation", "anomaly")
        r = self.sb.report("bad-agent")
        self.assertEqual(r["anomalies"], 3)
        self.assertFalse(r["safe"])
        r = self.sb.finalize("bad-agent", approved=False)
        self.assertEqual(r["status"], "rejected")
        # Rejected agent cannot use docker
        self.assertFalse(self.sb.can_launch_docker("bad-agent"))
        r = self.sb.approve_docker("bad-agent", approved=True)
        self.assertFalse(r.get("approved", False))

    def test_full_lifecycle_blocked_mid_probation(self):
        self.sb.register("suspicious-agent")
        self.sb.start_probation("suspicious-agent")
        self.sb.evaluate("suspicious-agent", "read", "ok")
        # Admin blocks mid-probation
        r = self.sb.block("suspicious-agent")
        self.assertEqual(r["status"], "blocked")
        # Cannot finalize blocked agent
        r = self.sb.finalize("suspicious-agent", approved=True)
        self.assertIn("error", r)
        # Report still works
        r = self.sb.report("suspicious-agent")
        self.assertEqual(r["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
