"""Tests for kos.task_dispatcher — priority queues, QoS, preemption."""

# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
import time
import unittest

from kos.task_dispatcher import Priority, TaskDispatcher

# ── Fixtures ──


def tick(d: TaskDispatcher):
    """Advance dispatcher internal counter and return next task (like next())."""
    return d.next()


# ═══════════════════════════════════════════════════════════════
# Priority Queue Ordering
# ═══════════════════════════════════════════════════════════════


class TestPriorityOrdering(unittest.TestCase):
    def setUp(self):
        self.d = TaskDispatcher()

    def test_p0_before_p1(self):
        self.d.submit("low", Priority.P1_HIGH)
        self.d.submit("high", Priority.P0_CRITICAL)
        t = self.d.next()
        self.assertEqual(t.description, "high")  # type: ignore[reportOptionalMemberAccess]

    def test_p1_before_p2(self):
        self.d.submit("normal", Priority.P2_NORMAL)
        self.d.submit("high", Priority.P1_HIGH)
        t = self.d.next()
        self.assertEqual(t.description, "high")  # type: ignore[reportOptionalMemberAccess]

    def test_p2_before_p3(self):
        self.d.submit("low", Priority.P3_LOW)
        self.d.submit("normal", Priority.P2_NORMAL)
        t = self.d.next()
        self.assertEqual(t.description, "normal")  # type: ignore[reportOptionalMemberAccess]

    def test_fifo_within_same_priority(self):
        self.d.submit("first", Priority.P2_NORMAL)
        self.d.submit("second", Priority.P2_NORMAL)
        t1 = self.d.next()
        self.assertEqual(t1.description, "first")  # type: ignore[reportOptionalMemberAccess]
        # Complete first task before dequeuing second
        self.d.running = None
        t2 = self.d.next()
        self.assertEqual(t2.description, "second")  # type: ignore[reportOptionalMemberAccess]

    def test_mixed_priority_fifo(self):
        self.d.submit("p3", Priority.P3_LOW)
        self.d.submit("p2", Priority.P2_NORMAL)
        self.d.submit("p1", Priority.P1_HIGH)
        self.d.submit("p0", Priority.P0_CRITICAL)
        self.assertEqual(self.d.next().description, "p0")  # type: ignore[reportOptionalMemberAccess]
        self.d.running = None
        self.assertEqual(self.d.next().description, "p1")  # type: ignore[reportOptionalMemberAccess]
        self.d.running = None
        self.assertEqual(self.d.next().description, "p2")  # type: ignore[reportOptionalMemberAccess]
        self.d.running = None
        self.assertEqual(self.d.next().description, "p3")  # type: ignore[reportOptionalMemberAccess]

    def test_empty_queue_returns_none(self):
        self.assertIsNone(self.d.next())

    def test_submit_returns_task_with_correct_priority(self):
        t = self.d.submit("test", Priority.P0_CRITICAL)
        self.assertEqual(t.priority, Priority.P0_CRITICAL)
        self.assertEqual(t.status, "queued")

    def test_submit_assigns_incremental_ids(self):
        t1 = self.d.submit("a", Priority.P2_NORMAL)
        t2 = self.d.submit("b", Priority.P2_NORMAL)
        self.assertEqual(t1.id, "T0001")
        self.assertEqual(t2.id, "T0002")

    def test_submit_records_timestamp(self):
        now = time.time()
        t = self.d.submit("test", Priority.P2_NORMAL)
        self.assertGreaterEqual(t.submitted_at, now - 1)


# ═══════════════════════════════════════════════════════════════
# Preemption
# ═══════════════════════════════════════════════════════════════


class TestPreemption(unittest.TestCase):
    def setUp(self):
        self.d = TaskDispatcher()

    def test_p0_preempts_p2(self):
        self.d.submit("normal", Priority.P2_NORMAL)
        self.d.next()  # start running P2
        self.assertEqual(self.d.running.description, "normal")  # type: ignore[reportOptionalMemberAccess]
        self.d.submit("critical", Priority.P0_CRITICAL)
        t = self.d.next()
        self.assertEqual(t.description, "critical")  # type: ignore[reportOptionalMemberAccess]
        # Running task should have been preempted back to queue
        self.assertEqual(self.d.running.description, "critical")  # type: ignore[reportOptionalMemberAccess]
        # P2 should be back in queue
        self.assertEqual(len(self.d.queues[Priority.P2_NORMAL]), 1)

    def test_p0_preempts_p3(self):
        self.d.submit("low", Priority.P3_LOW)
        self.d.next()
        self.d.submit("critical", Priority.P0_CRITICAL)
        t = self.d.next()
        self.assertEqual(t.description, "critical")  # type: ignore[reportOptionalMemberAccess]

    def test_p1_does_not_preempt_p0(self):
        self.d.submit("critical", Priority.P0_CRITICAL)
        self.d.next()
        self.d.submit("high", Priority.P1_HIGH)
        t = self.d.next()
        # P0 still running, P1 stays queued since P0 is higher
        self.assertIsNone(t)

    def test_p2_does_not_preempt_p1(self):
        self.d.submit("high", Priority.P1_HIGH)
        self.d.next()
        self.d.submit("normal", Priority.P2_NORMAL)
        t = self.d.next()
        self.assertIsNone(t)

    def test_preempted_task_back_to_queued_status(self):
        self.d.submit("normal", Priority.P2_NORMAL)
        self.d.next()
        self.d.submit("critical", Priority.P0_CRITICAL)
        self.d.next()
        # P2 should be in queued status again
        preempted = self.d.queues[Priority.P2_NORMAL][0]
        self.assertEqual(preempted.status, "queued")

    def test_preempted_task_preserves_priority(self):
        self.d.submit("normal", Priority.P2_NORMAL)
        self.d.next()
        self.d.submit("critical", Priority.P0_CRITICAL)
        self.d.next()  # P0 starts
        preempted = self.d.queues[Priority.P2_NORMAL][0]
        self.assertEqual(preempted.priority, Priority.P2_NORMAL)
        self.assertEqual(preempted.description, "normal")

    def test_multiple_p0_cascading_preemptions(self):
        """Multiple P0 tasks — each starts after previous completes (no preempt same priority)."""
        self.d.submit("p3", Priority.P3_LOW)
        self.d.next()
        for i in range(3):
            self.d.submit(f"p0-{i}", Priority.P0_CRITICAL)
            # P0 preempts P3 (lower priority)
            t = self.d.next()
            self.assertEqual(t.description, f"p0-{i}")  # type: ignore[reportOptionalMemberAccess]
            # Complete this P0 before next one can start
            self.d.running = None

    def test_after_p0_completes_resume_p2(self):
        self.d.submit("normal", Priority.P2_NORMAL)
        self.d.next()  # P2 running
        self.d.submit("critical", Priority.P0_CRITICAL)
        self.d.next()  # P0 preempts
        # Manually "complete" P0 — set running = None
        self.d.running = None
        t = self.d.next()  # Should get P2 back
        self.assertEqual(t.description, "normal")  # type: ignore[reportOptionalMemberAccess]


# ═══════════════════════════════════════════════════════════════
# QoS
# ═══════════════════════════════════════════════════════════════


class TestQoS(unittest.TestCase):
    def setUp(self):
        self.d = TaskDispatcher()

    def test_qos_check_p0_immediate(self):
        """P0 task just submitted — should be within 5min QoS."""
        self.d.submit("critical", Priority.P0_CRITICAL)
        report = self.d.check_qos()
        self.assertIn("P0", report)

    def test_qos_check_p1_immediate(self):
        self.d.submit("high", Priority.P1_HIGH)
        report = self.d.check_qos()
        self.assertIn("P1", report)

    def test_qos_no_violations_immediately(self):
        self.d.submit("critical", Priority.P0_CRITICAL)
        self.d.submit("high", Priority.P1_HIGH)
        report = self.d.check_qos()
        for prio in ("P0", "P1"):
            self.assertLessEqual(report[prio]["max_wait_seconds"], 300, f"{prio} should have zero violations")

    def test_qos_empty_queues(self):
        report = self.d.check_qos()
        self.assertEqual(report, {})

    def test_qos_returns_wait_times(self):
        self.d.submit("critical", Priority.P0_CRITICAL)
        self.d.submit("high", Priority.P1_HIGH)
        self.d.submit("normal", Priority.P2_NORMAL)
        report = self.d.check_qos()
        for prio in ("P0", "P1", "P2"):
            self.assertIn(prio, report)
        # P3 queue empty — not in report
        self.assertNotIn("P3", report)


# ═══════════════════════════════════════════════════════════════
# Agent Match
# ═══════════════════════════════════════════════════════════════


class TestAgentMatch(unittest.TestCase):
    def setUp(self):
        self.d = TaskDispatcher()

    def test_find_agent_by_capability(self):
        agents = [
            {"id": "agent-a", "capabilities": ["read", "write"]},
            {"id": "agent-b", "capabilities": ["search"]},
        ]
        matches = self.d.find_agent("search", agents)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], "agent-b")

    def test_find_agent_missing_capability(self):
        agents = [
            {"id": "agent-a", "capabilities": ["read"]},
        ]
        matches = self.d.find_agent("exec", agents)
        self.assertEqual(matches, [])

    def test_find_agent_empty_registry(self):
        matches = self.d.find_agent("read", [])
        self.assertEqual(matches, [])

    def test_find_agent_no_capabilities_field(self):
        agents = [{"id": "agent-a"}]
        matches = self.d.find_agent("read", agents)
        self.assertEqual(matches, [])

    def test_find_agent_multiple_matches(self):
        agents = [
            {"id": "agent-a", "capabilities": ["read", "search"]},
            {"id": "agent-b", "capabilities": ["search", "write"]},
            {"id": "agent-c", "capabilities": ["exec"]},
        ]
        matches = self.d.find_agent("search", agents)
        self.assertEqual(len(matches), 2)
        self.assertIn("agent-a", [m["id"] for m in matches])
        self.assertIn("agent-b", [m["id"] for m in matches])

    def test_find_agent_case_sensitive(self):
        agents = [
            {"id": "agent-a", "capabilities": ["Search"]},
        ]
        matches = self.d.find_agent("search", agents)
        self.assertEqual(matches, [])

    def test_find_agent_task_with_required_capability(self):
        """Method that accepts a Task object and finds matching agents."""
        self.d.submit("do research", Priority.P2_NORMAL)
        # Attach required capability — tasks don't have it by default
        # For this test, we use the generic method
        agents = [{"id": "agent-a", "capabilities": ["research"]}]
        matches = self.d.find_agent("research", agents)
        self.assertEqual(len(matches), 1)


# ═══════════════════════════════════════════════════════════════
# Status Query
# ═══════════════════════════════════════════════════════════════


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.d = TaskDispatcher()

    def test_status_queued(self):
        t = self.d.submit("test")
        self.assertEqual(self.d.status(t.id), "queued")

    def test_status_running(self):
        self.d.submit("test")
        self.d.next()
        self.assertEqual(self.d.status("T0001"), "running")

    def test_status_unknown(self):
        self.assertIsNone(self.d.status("NONEXIST"))

    def test_status_after_preempted(self):
        self.d.submit("normal", Priority.P2_NORMAL)
        self.d.next()
        self.d.submit("critical", Priority.P0_CRITICAL)
        self.d.next()
        self.assertEqual(self.d.status("T0001"), "queued")

    def test_status_running_preserved(self):
        self.d.submit("p0", Priority.P0_CRITICAL)
        self.d.submit("p1", Priority.P1_HIGH)
        self.d.next()  # P0 starts
        self.d.next()  # P0 still running, P1 stays queued
        self.assertEqual(self.d.status("T0001"), "running")


# ═══════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════


class TestStats(unittest.TestCase):
    def setUp(self):
        self.d = TaskDispatcher()

    def test_stats_empty(self):
        s = self.d.stats()
        self.assertEqual(s["queued"], 0)
        self.assertEqual(s["running"], 0)

    def test_stats_with_tasks(self):
        self.d.submit("a", Priority.P0_CRITICAL)
        self.d.submit("b", Priority.P2_NORMAL)
        self.d.submit("c", Priority.P2_NORMAL)
        self.d.submit("d", Priority.P3_LOW)
        s = self.d.stats()
        self.assertEqual(s["queued"], 4)
        self.assertEqual(s["running"], 0)

    def test_stats_with_running(self):
        self.d.submit("a", Priority.P0_CRITICAL)
        self.d.next()
        s = self.d.stats()
        self.assertEqual(s["queued"], 0)
        self.assertEqual(s["running"], 1)

    def test_stats_queue_breakdown(self):
        self.d.submit("a", Priority.P0_CRITICAL)
        self.d.submit("b", Priority.P1_HIGH)
        self.d.submit("c", Priority.P2_NORMAL)
        self.d.submit("d", Priority.P3_LOW)
        s = self.d.stats()
        self.assertEqual(s["queues"]["P0_CRITICAL"], 1)
        self.assertEqual(s["queues"]["P1_HIGH"], 1)
        self.assertEqual(s["queues"]["P2_NORMAL"], 1)
        self.assertEqual(s["queues"]["P3_LOW"], 1)

    def test_stats_after_dequeue(self):
        self.d.submit("a", Priority.P0_CRITICAL)
        self.d.submit("b", Priority.P2_NORMAL)
        self.d.next()
        s = self.d.stats()
        self.assertEqual(s["queued"], 1)


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.d = TaskDispatcher()

    def test_default_priority_is_p2(self):
        t = self.d.submit("test")
        self.assertEqual(t.priority, Priority.P2_NORMAL)

    def test_none_running_when_empty(self):
        self.assertIsNone(self.d.running)

    def test_task_id_monotonic(self):
        t1 = self.d.submit("a")
        t2 = self.d.submit("b")
        t3 = self.d.submit("c")
        self.assertEqual(t1.id, "T0001")
        self.assertEqual(t2.id, "T0002")
        self.assertEqual(t3.id, "T0003")

    def test_queues_are_separate_lists(self):
        self.d.submit("p0", Priority.P0_CRITICAL)
        self.d.submit("p1", Priority.P1_HIGH)
        self.d.next()
        self.assertEqual(len(self.d.queues[Priority.P0_CRITICAL]), 0)
        self.assertEqual(len(self.d.queues[Priority.P1_HIGH]), 1)

    def test_running_task_started_at_set(self):
        self.d.submit("test", Priority.P0_CRITICAL)
        t = self.d.next()
        self.assertIsNotNone(t.started_at)  # type: ignore[reportOptionalMemberAccess]

    def test_running_task_status_is_running(self):
        self.d.submit("test", Priority.P0_CRITICAL)
        t = self.d.next()
        self.assertEqual(t.status, "running")  # type: ignore[reportOptionalMemberAccess]

    def test_submit_many_then_drain(self):
        for i in range(10):
            self.d.submit(f"task-{i}", Priority.P3_LOW)
        for i in range(5):
            self.d.submit(f"high-{i}", Priority.P1_HIGH)
        # Should get all P1 first, then P3
        self.d.running = None
        for i in range(5):
            t = self.d.next()
            self.assertIn(t.description, [f"high-{j}" for j in range(5)])  # type: ignore[reportOptionalMemberAccess]
            self.d.running = None
        for i in range(10):
            self.d.running = None
            t = self.d.next()
            self.assertIn(t.description, [f"task-{j}" for j in range(10)])  # type: ignore[reportOptionalMemberAccess]


# ═══════════════════════════════════════════════════════════════
# MCP Tool Stubs
# ═══════════════════════════════════════════════════════════════


class TestMCPTools(unittest.TestCase):
    """Verify kos_task_submit / kos_task_status signatures exist."""

    def setUp(self):
        self.d = TaskDispatcher()

    def test_kos_task_submit(self):
        """kos_task_submit(priority, task) → submit + task_id."""
        t = self.d.submit("user request", Priority.P1_HIGH)
        self.assertEqual(t.status, "queued")
        self.assertIn("T", t.id)

    def test_kos_task_status_lookup(self):
        """kos_task_status(task_id) → status string."""
        t = self.d.submit("test", Priority.P2_NORMAL)
        self.assertEqual(self.d.status(t.id), "queued")

    def test_kos_task_status_running(self):
        t = self.d.submit("test", Priority.P2_NORMAL)
        self.d.next()
        self.assertEqual(self.d.status(t.id), "running")

    def test_kos_task_status_nonexistent(self):
        self.assertIsNone(self.d.status("T9999"))


# ═══════════════════════════════════════════════════════════════
# Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.d = TaskDispatcher()

    def test_full_lifecycle_simple(self):
        # Submit P2 task
        t = self.d.submit("simple task", Priority.P2_NORMAL)
        self.assertEqual(t.status, "queued")
        # Start it
        t = self.d.next()
        self.assertEqual(t.status, "running")  # type: ignore[reportOptionalMemberAccess]
        self.assertEqual(t.description, "simple task")  # type: ignore[reportOptionalMemberAccess]
        # Query status
        self.assertEqual(self.d.status(t.id), "running")  # type: ignore[reportOptionalMemberAccess]

    def test_complex_preemption_scenario(self):
        """Submit P3, P2, then P0 — verify proper ordering."""
        self.d.submit("p3-1", Priority.P3_LOW)
        self.d.submit("p2-1", Priority.P2_NORMAL)
        self.d.submit("p3-2", Priority.P3_LOW)
        # P2 should start first
        t = self.d.next()
        self.assertEqual(t.description, "p2-1")  # type: ignore[reportOptionalMemberAccess]
        # Now submit P0
        self.d.submit("p0-1", Priority.P0_CRITICAL)
        # P0 preempts
        t = self.d.next()
        self.assertEqual(t.description, "p0-1")  # type: ignore[reportOptionalMemberAccess]
        # When P0 completes, P2 should resume, then P3s in order
        self.d.running = None
        t = self.d.next()
        self.assertEqual(t.description, "p2-1")  # type: ignore[reportOptionalMemberAccess]
        self.d.running = None
        t = self.d.next()
        self.assertEqual(t.description, "p3-1")  # type: ignore[reportOptionalMemberAccess]
        self.d.running = None
        t = self.d.next()
        self.assertEqual(t.description, "p3-2")  # type: ignore[reportOptionalMemberAccess]

    def test_qos_and_agent_match_stubs(self):
        """QoS check + agent match both work independently."""
        self.d.submit("critical task", Priority.P0_CRITICAL)
        self.d.submit("normal task", Priority.P2_NORMAL)
        # QoS check
        report = self.d.check_qos()
        self.assertIn("P0", report)
        self.assertIn("P2", report)
        # Agent match
        agents = [
            {"id": "worker-a", "capabilities": ["critical"]},
            {"id": "worker-b", "capabilities": ["normal"]},
        ]
        matches = self.d.find_agent("critical", agents)
        self.assertEqual(len(matches), 1)

    def test_empty_queues_give_no_task(self):
        self.assertIsNone(self.d.next())
        self.assertIsNone(self.d.next())

    def test_submit_new_dispatcher_instance(self):
        d2 = TaskDispatcher()
        t = d2.submit("fresh", Priority.P0_CRITICAL)
        self.assertEqual(t.id, "T0001")


if __name__ == "__main__":
    unittest.main()
