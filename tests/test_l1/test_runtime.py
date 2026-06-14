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

    def test_ack(self):
        protocol = CommunicationProtocol("node-1")
        protocol.connect("node-2")
        message = Message.create(MessageType.SYNC, "node-1", "node-2", {"data": 1})
        protocol.send("node-2", message)
        # send succeeds immediately, message is not in _in_flight after success
        # verify it was processed by checking stats
        stats = protocol.get_stats()
        assert stats["in_flight_count"] == 0

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
        assert first.priority == MessagePriority.HIGH

    def test_purge_expired(self):
        queue = MessageQueue()
        from datetime import datetime, timezone, timedelta
        msg = Message(
            message_id="old", message_type=MessageType.SYNC,
            source="a", target="b", payload={},
            timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
            ttl_seconds=10,
        )
        queue.enqueue(msg)
        purged = queue.purge_expired()
        assert purged == 1
        assert queue.size() == 0


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
        changes = service.sync_from(remote_state)

        assert "key1" in changes
        assert "key2" in changes
        assert service.get("key1") == "new_value"
        assert service.get("key2") == "value2"

    def test_versioning(self):
        service = StateSyncService("node-1")
        v1 = service.set("k", "v1")
        v2 = service.set("k", "v2")
        assert v2 > v1
        assert service.get_version("k") == v2

    def test_delta(self):
        service = StateSyncService("node-1")
        service.set("k1", "v1")
        service.set("k2", "v2")

        delta = service.get_delta(0)
        assert len(delta) == 2

    def test_stats(self):
        service = StateSyncService("node-1")
        service.set("k", "v")
        stats = service.to_dict()
        assert stats["key_count"] == 1


class TestFailoverExecutor:
    """故障转移执行器测试"""

    def test_execute(self):
        executor = FailoverExecutor()

        result = executor.execute("node-1", "node-2")
        assert result is True
        assert executor.failover_count == 1
        assert executor.last_failover is not None

    def test_health_tracking(self):
        executor = FailoverExecutor()
        executor.execute("node-1", "node-2")
        assert executor.get_node_health("node-1") == NodeHealth.UNHEALTHY
        assert executor.get_node_health("node-2") == NodeHealth.HEALTHY

    def test_recovery(self):
        executor = FailoverExecutor()
        executor.register_recovery("node-1", lambda: True)
        assert executor.attempt_recovery("node-1")

    def test_stats(self):
        executor = FailoverExecutor()
        executor.execute("n1", "n2")
        stats = executor.get_stats()
        assert stats["failover_count"] == 1


class TestLoadBalancerExecutor:
    """负载均衡执行器测试"""

    def test_route(self):
        executor = LoadBalancerExecutor()

        target = executor.route("node-1")
        assert target == "node-1"
        assert executor.request_count == 1
        assert executor.node_requests["node-1"] == 1

    def test_latency_tracking(self):
        executor = LoadBalancerExecutor()
        executor.record_latency("node-1", 10.0)
        executor.record_latency("node-1", 20.0)
        assert executor.get_avg_latency("node-1") == 15.0

    def test_select_best_node(self):
        executor = LoadBalancerExecutor()
        executor.record_latency("node-1", 50.0)
        executor.record_latency("node-2", 10.0)
        best = executor.select_best_node(["node-1", "node-2"])
        assert best == "node-2"

    def test_stats(self):
        executor = LoadBalancerExecutor()
        executor.route("n1")
        stats = executor.get_stats()
        assert stats["total_requests"] == 1
