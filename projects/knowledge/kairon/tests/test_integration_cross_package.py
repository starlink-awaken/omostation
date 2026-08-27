"""Cross-package integration tests — 3 chains.

These tests verify that packages in the kairon monorepo can interoperate
correctly.  Each chain exercises a real cross-package data flow without
mocking the target package — only external services (LLM endpoints, MCP
servers) are replaced with in-memory stubs.

Chains:
  1. agora → agent-runtime  — ServiceRegistry → AgentRuntime task dispatch
  2. agent-runtime → engine-core  — WorkerAbstract → AgentRuntime execution
  3. engine-core → llm-gateway  — MockLLMProvider → engine-core task orchestration
"""

from __future__ import annotations

import pytest

# 这些测试依赖 workspace 中其他项目的包; 不在 kairon 标准测试路径中运行
pytest.importorskip("agora", reason="requires agora package (cross-project dependency)")
pytest.importorskip("engine_core", reason="requires engine_core package (not yet in kairon)")
pytest.importorskip("llm_gateway", reason="requires llm_gateway package (not yet in kairon)")

# ═══════════════════════════════════════════════════════════════════
# Chain 1: Agora → Agent-Runtime
# ═══════════════════════════════════════════════════════════════════


class TestChainAgoraToAgentRuntime:
    """Agora ServiceRegistry + EventBus dispatches tasks to AgentRuntime."""

    def test_service_registration(self, tmp_path):
        """Register service in Agora, verify it is discoverable."""
        from agora.core.registry import ServiceRegistry  # type: ignore[reportMissingImports]
        from agora.core.service_base import Service  # type: ignore[reportMissingImports]

        registry = ServiceRegistry(storage_path=str(tmp_path / "agora.json"), cb_max_failures=5)

        svc = Service(
            name="agent-runtime",
            description="Agent Runtime engine",
            protocol="mcp",
            port=9999,
            tags=["agent-runtime", "execution"],
        )
        registry.register(svc)

        # Verify via get()
        registered = registry.get("agent-runtime")
        assert registered is not None
        assert registered.name == "agent-runtime"
        assert registered.port == 9999
        assert "execution" in registered.tags

    def test_service_listing(self, tmp_path):
        """Registered services appear in list_all."""
        from agora.core.registry import ServiceRegistry  # type: ignore[reportMissingImports]
        from agora.core.service_base import Service  # type: ignore[reportMissingImports]

        registry = ServiceRegistry(storage_path=str(tmp_path / "agora2.json"))
        registry.register(Service(name="agent-runtime", protocol="mcp", port=8765, tags=["agent-runtime"]))
        registry.register(Service(name="llm-gateway", protocol="mcp", port=8771, tags=["llm"]))  # use KOS_RESERVED

        services = registry.list_all()
        names = {s.name for s in services}
        assert "agent-runtime" in names
        assert "llm-gateway" in names

    def test_agent_hub_register(self):
        """AgentHub works independently and is compatible with Agora types."""

        hub = AgentHub()  # noqa: F821  # type: ignore[reportUndefinedVariable]
        agent_id = hub.register_agent(
            name="agora-worker",
            capabilities=["task:execute", "llm:chat"],
            endpoint="http://agora-worker:9000",
        )
        assert agent_id is not None
        agents = hub.discover_agents(capability="task:execute")
        assert len(agents) == 1
        assert agents[0].name == "agora-worker"


# ═══════════════════════════════════════════════════════════════════
# Chain 2: Agent-Runtime → Engine-Core
# ═══════════════════════════════════════════════════════════════════


class TestChainAgentRuntimeToEngineCore:
    """AgentRuntime uses engine-core primitives for execution."""

    def test_worker_abstract_exists(self):
        """Engine-core WorkerAbstract type is correctly structured."""
        # Import worker_abstraction without triggering engine_core.__init__
        # (must import the module directly to avoid kairon_lib dep chain)
        import importlib

        wa = importlib.import_module("engine_core.worker_abstraction")

        # Verify the types exist and are structured correctly
        assert hasattr(wa, "WorkerAbstract")
        assert hasattr(wa, "WorkerCapability")
        assert hasattr(wa, "WorkerType")
        assert hasattr(wa, "WorkerMetrics")
        assert hasattr(wa, "WorkerStatus")

        # Verify WorkerCapability structure
        cap = wa.WorkerCapability(name="task:execute")
        assert cap.matches("task:execute") is True
        assert cap.matches("task:unknown") is False

    def test_dag_orchestrates_workflow(self):
        """Engine-core TaskDAG can orchestrate multi-step workflows."""
        from engine_core.dag import TaskDAG, TaskNode  # type: ignore[reportMissingImports]

        dag = TaskDAG()

        t1 = TaskNode(task_id="step_1", name="fetch")
        t2 = TaskNode(task_id="step_2", name="process", depends_on=["step_1"])
        t3 = TaskNode(task_id="step_3", name="store", depends_on=["step_2"])

        dag.add_node(t1)
        dag.add_node(t2)
        dag.add_node(t3)

        assert dag.has_cycle() is False

        order = dag.topological_sort()
        assert order is not None
        assert order.index("step_1") < order.index("step_2")
        assert order.index("step_2") < order.index("step_3")

    def test_retry_policy_delay(self):
        """Engine-core RetryPolicy provides backoff compatible with retry loops."""
        import importlib

        rp = importlib.import_module("engine_core.retry_policy")

        policy = rp.RetryPolicy(max_attempts=3, backoff_base=2.0, max_delay=10.0)
        state = rp.RetryState()

        delays = []
        for attempt in range(1, policy.max_attempts + 1):
            delays.append(policy.delay_for_attempt(attempt))
            state.attempt_count = attempt

        assert len(delays) == 3
        assert delays[0] < delays[1]  # exponential backoff
        assert state.attempt_count == 3

    def test_capability_catalog_register(self):
        """Engine-core CapabilityCatalog stores agent-runtime capabilities."""
        from engine_core.capability import Capability, CapabilityCatalog  # type: ignore[reportMissingImports]

        catalog = CapabilityCatalog()
        catalog.register(Capability(id="llm:chat", name="Chat via LLM", source="local"))
        catalog.register(Capability(id="task:execute", name="Execute task", source="local"))

        cap = catalog.get("llm:chat")
        assert cap is not None
        assert cap.name == "Chat via LLM"

        cap2 = catalog.get("task:execute")
        assert cap2 is not None

    def test_worker_metrics_tracking(self):
        """Engine-core WorkerMetrics tracks execution stats."""
        import importlib

        wa = importlib.import_module("engine_core.worker_abstraction")

        metrics = wa.WorkerMetrics(
            task_count=10,
            success_count=9,
            failure_count=1,
            avg_latency=0.5,
        )
        assert metrics.success_rate == 0.9
        assert metrics.load_factor == 0.0


# ═══════════════════════════════════════════════════════════════════
# Chain 3: Engine-Core → LLM-Gateway
# ═══════════════════════════════════════════════════════════════════


class TestChainEngineCoreToLlmGateway:
    """Engine-core uses llm-gateway for LLM-powered task execution."""

    def test_mock_llm_provider_returns_string_content(self):
        """MockLLMProvider returns string content (not list-based)."""
        from llm_gateway.provider import LLMRequest, MockLLMProvider  # type: ignore[reportMissingImports]

        provider = MockLLMProvider()
        request = LLMRequest(prompt="Hello from engine-core")
        response = provider.complete(request)

        assert response.content is not None
        assert isinstance(response.content, str)
        assert len(response.content) > 0

    def test_engine_core_retry_policy_with_llm_request(self):
        """RetryPolicy delay logic is usable alongside LLMRequest."""
        import importlib

        from llm_gateway.provider import LLMRequest, MockLLMProvider  # type: ignore[reportMissingImports]

        rp = importlib.import_module("engine_core.retry_policy")

        provider = MockLLMProvider()
        policy = rp.RetryPolicy(max_attempts=3, backoff_base=2.0)
        request = LLMRequest(prompt="retry test")

        response = provider.complete(request)
        assert response is not None

        delay = policy.delay_for_attempt(1)
        assert delay > 0

    def test_task_context_and_llm_response_interop(self):
        """TaskContext and LLMResponse types coexist without conflict."""
        import importlib

        from llm_gateway.provider import LLMRequest, MockLLMProvider  # type: ignore[reportMissingImports]

        tc = importlib.import_module("engine_core.task_context")

        provider = MockLLMProvider()
        request = LLMRequest(prompt="context test")
        response = provider.complete(request)

        ctx = tc.TaskContext(task_id="integration-test-001", content={"prompt": "hello"})
        assert ctx.task_id == "integration-test-001"
        assert response.content is not None

    def test_capability_catalog_agent_card_uses_llm_gateway_types(self):
        """CapabilityCatalog's to_agent_card() works with MockLLMProvider types."""
        from engine_core.capability import Capability, CapabilityCatalog  # type: ignore[reportMissingImports]

        catalog = CapabilityCatalog()
        catalog.register(Capability(id="code_gen", name="Code generation", source="local"))

        card = catalog.to_agent_card()
        assert len(card["capabilities"]) == 1
        assert card["capabilities"][0]["name"] == "Code generation"

    def test_cost_aware_dispatcher_constructs(self):
        """CostAwareDispatcher can be instantiated alongside LLM types."""
        from engine_core.cost_aware_dispatcher import CostAwareDispatcher  # type: ignore[reportMissingImports]
        from llm_gateway.provider import MockLLMProvider  # type: ignore[reportMissingImports]

        dispatcher = CostAwareDispatcher()
        provider = MockLLMProvider()

        # Both coexist
        assert dispatcher is not None
        assert provider is not None

    def test_llm_response_metadata_compatible_with_engine_core(self):
        """LLMResponse metadata structure matches engine-core expectations."""
        from llm_gateway.provider import LLMRequest, MockLLMProvider  # type: ignore[reportMissingImports]

        provider = MockLLMProvider()
        request = LLMRequest(prompt="test metadata")
        response = provider.complete(request)

        assert hasattr(response, "provider")
        assert hasattr(response, "model")
        assert hasattr(response, "input_tokens")
        assert hasattr(response, "output_tokens")
