"""Tests for swarm_engine._compat — agent communication and event functions."""

from __future__ import annotations


class TestAgentSendReceive:
    def test_agent_send(self):
        from swarm_engine._compat import agent_send

        result = agent_send("agent-b", "hello")
        assert result is True

    def test_agent_send_and_receive(self):
        from swarm_engine._compat import agent_receive, agent_send

        # Clear any leftover messages for target
        agent_receive("test-agent")

        agent_send("test-agent", "message-1")
        agent_send("test-agent", "message-2")

        messages = agent_receive("test-agent")
        assert messages == ["message-1", "message-2"]

        # Second receive should be empty
        messages = agent_receive("test-agent")
        assert messages == []

    def test_agent_ack(self):
        from swarm_engine._compat import agent_ack

        result = agent_ack("msg-123")
        assert result is True


class TestEmitFunctions:
    def test_emit_worker_hatched(self):
        from swarm_engine._compat import emit_worker_hatched

        # Should not raise even without bus-foundation
        emit_worker_hatched(worker_id="w1", task_type="CODE", pid=12345)

    def test_emit_worker_terminated(self):
        from swarm_engine._compat import emit_worker_terminated

        emit_worker_terminated(worker_id="w1", reason="done", eu_consumed=10.0)


class TestBuildFunctions:
    def test_build_active_worker_handle(self):
        from swarm_engine._compat import build_active_worker_handle

        result = build_active_worker_handle()
        assert result is None

    def test_build_agent_cli_handle(self):
        from swarm_engine._compat import build_agent_cli_handle

        result = build_agent_cli_handle()
        assert result is None

    def test_inject_soul_env(self):
        from swarm_engine._compat import inject_soul_env

        result = inject_soul_env()
        assert result == {}

    def test_prepare_agent_cli_bootstrap(self):
        from swarm_engine._compat import prepare_agent_cli_bootstrap

        result = prepare_agent_cli_bootstrap()
        assert result is None

    def test_resolve_agent_cli_command(self):
        from swarm_engine._compat import resolve_agent_cli_command

        result = resolve_agent_cli_command()
        assert result == []

    def test_spawn_agent_cli_process(self):
        from swarm_engine._compat import spawn_agent_cli_process

        result = spawn_agent_cli_process()
        assert result is None

    def test_spawn_worker_process(self):
        from swarm_engine._compat import spawn_worker_process

        result = spawn_worker_process()
        assert result is None

    def test_wait_for_worker_process_start(self):
        from swarm_engine._compat import wait_for_worker_process_start

        result = wait_for_worker_process_start()
        assert result is None

    def test_get_worker_profile(self):
        from swarm_engine._compat import get_worker_profile

        result = get_worker_profile("w1")
        assert result is not None
        assert result.to_dict() == {}
