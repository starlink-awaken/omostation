"""L1 运行时层测试"""

from ecos.l1.runtime import (
    CommunicationProtocol,
    ProtocolType,
    MessageType,
    Message,
    MessagePriority,
    MessageQueue,
    StateSyncService,
    FailoverExecutor,
    LoadBalancerExecutor,
    NodeHealth,
)


class TestCommunicationProtocol:
    """通信协议测试"""

    def test_send_message(self):
        protocol = CommunicationProtocol("node-1", ProtocolType.IN_PROCESS)
        protocol.connect("node-2")

        message = Message(
            message_id="msg-1",
            message_type=MessageType.SYNC,
            source="node-1",
            target="node-2",
            payload={"key": "value"},
        )

        result = protocol.send("node-2", message)
        assert result is True
        assert "node-2" in protocol.connected_nodes

    def test_broadcast(self):
        protocol = CommunicationProtocol("node-1")
        protocol.connect("node-2")
        protocol.connect("node-3")

        message = Message(
            message_id="msg-1",
            message_type=MessageType.HEARTBEAT,
            source="node-1",
            target="all",
            payload={"status": "alive"},
        )

        result = protocol.broadcast(message)
        assert isinstance(result, dict)
        assert result.get("node-2") is True
        assert result.get("node-3") is True

    def test_send_without_connect(self):
        protocol = CommunicationProtocol("node-1")
        message = Message.create(MessageType.SYNC, "node-1", "node-2", {"data": 1})
        result = protocol.send("node-2", message)
        assert result is False

    def test_dispatch(self):
        protocol = CommunicationProtocol("node-1")
        received = []
        protocol.register_handler(MessageType.SYNC, lambda m: received.append(m))

        message = Message.create(MessageType.SYNC, "node-1", "node-1", {"data": 1})
        protocol.dispatch(message)
        assert len(received) == 1

    def test_health_check(self):
        protocol = CommunicationProtocol("node-1")
        protocol.connect("node-2")
        health = protocol.check_health("node-2")
        assert health.status == NodeHealth.HEALTHY

    def test_stats(self):
        protocol = CommunicationProtocol("node-1")
        protocol.connect("node-2")
        stats = protocol.get_stats()
        assert stats["connected_nodes"] == 1
        assert stats["node_id"] == "node-1"


class TestMessageQueue:
    """消息队列测试"""

    def test_enqueue_dequeue(self):
        queue = MessageQueue()
        msg = Message.create(MessageType.SYNC, "a", "b", {})
        queue.enqueue(msg)
        assert queue.size() == 1
        dequeued = queue.dequeue()
        assert dequeued is not None
        assert dequeued.message_id == msg.message_id
        assert queue.size() == 0

    def test_priority_ordering(self):
        queue = MessageQueue()
        low = Message.create(MessageType.SYNC, "a", "b", {}, MessagePriority.LOW)
        high = Message.create(MessageType.SYNC, "a", "b", {}, MessagePriority.HIGH)
        queue.enqueue(low)
        queue.enqueue(high)
        first = queue.dequeue()
        assert first.priority == MessagePriority.HIGH  # type: ignore[reportOptionalMemberAccess]


class TestStateSyncService:
    """状态同步服务测试"""

    def test_set_and_get_state(self):
        service = StateSyncService("node-1")

        service.set("key1", "value1")
        value = service.get("key1")
        assert value == "value1"

    def test_sync_from(self):
        service = StateSyncService("node-1")
        service.set("key1", "old_value")

        remote_state = {"key1": ("new_value", 10), "key2": ("value2", 5)}
        service.sync_from(remote_state)

        assert service.get("key1") == "new_value"
        assert service.get("key2") == "value2"

    def test_versioning(self):
        service = StateSyncService("node-1")
        v1 = service.set("k", "v1")
        v2 = service.set("k", "v2")
        assert v2 > v1

    def test_stats(self):
        service = StateSyncService("node-1")
        service.set("k", "v")
        stats = service.to_dict()
        assert stats["key_count"] == 1


class TestFailoverExecutor:
    """故障转移执行器测试 — 委托 L0"""

    def test_register_and_execute(self):
        executor = FailoverExecutor()
        executor.register_node("n1")
        executor.register_node("n2")
        executor.register_node("n3")

        executor.add_rule("r1", "n1", ["n2", "n3"], "round_robin")

        target = executor.execute("n1")
        assert target in ["n2", "n3"]

    def test_round_robin_rotation(self):
        executor = FailoverExecutor()
        for i in range(4):
            executor.register_node(f"n{i}")

        executor.add_rule("r1", "n0", ["n1", "n2", "n3"], "round_robin")

        targets = set()
        for _ in range(6):
            t = executor.execute("n0")
            targets.add(t)

        assert targets == {"n1", "n2", "n3"}

    def test_health_check(self):
        executor = FailoverExecutor()
        executor.register_node("n1")

        health = executor.get_node_health("n1")
        assert health in (NodeHealth.HEALTHY, NodeHealth.UNKNOWN)

    def test_recovery(self):
        executor = FailoverExecutor()
        executor.register_node("n1")
        executor.register_recovery("n1", lambda: True)

        assert executor.attempt_recovery("n1")

    def test_stats(self):
        executor = FailoverExecutor()
        executor.register_node("n1")
        executor.register_node("n2")

        stats = executor.get_stats()
        assert stats["node_count"] == 2

    def test_failover_history(self):
        executor = FailoverExecutor()
        for i in range(4):
            executor.register_node(f"n{i}")
        executor.add_rule("r1", "n0", ["n1", "n2", "n3"], "round_robin")

        executor.execute("n0")
        executor.execute("n0")

        history = executor.get_failover_history()
        assert len(history) == 2


class TestLoadBalancerExecutor:
    """负载均衡执行器测试 — 委托 L0"""

    def test_register_and_route(self):
        executor = LoadBalancerExecutor()
        executor.register_node("n1")
        executor.register_node("n2")

        target = executor.route_auto()
        assert target in ["n1", "n2"]

    def test_round_robin(self):
        executor = LoadBalancerExecutor("round_robin")
        executor.register_node("n1")
        executor.register_node("n2")

        targets = set()
        for _ in range(4):
            t = executor.route_auto()
            targets.add(t)

        assert targets == {"n1", "n2"}

    def test_least_connections(self):
        executor = LoadBalancerExecutor("least_connections")
        executor.register_node("n1")
        executor.register_node("n2")

        executor.route("n1")
        executor.route("n1")
        executor.route("n2")

        target = executor.route_auto()
        assert target == "n2"

    def test_latency_tracking(self):
        executor = LoadBalancerExecutor()
        executor.record_latency("n1", 10.0)
        executor.record_latency("n1", 20.0)
        assert executor.get_avg_latency("n1") == 15.0

    def test_stats(self):
        executor = LoadBalancerExecutor()
        executor.register_node("n1")
        stats = executor.get_stats()
        assert stats["node_count"] == 1
        assert stats["strategy"] == "round_robin"
