"""L1 运行时层测试"""

from ecos.l1.runtime import (
    CommunicationProtocol,
    ProtocolType,
    MessageType,
    Message,
    StateSyncService,
    FailoverExecutor,
    LoadBalancerExecutor,
)


class TestCommunicationProtocol:
    """通信协议测试"""
    
    def test_send_message(self):
        protocol = CommunicationProtocol("node-1", ProtocolType.TCP)
        
        message = Message(
            message_id="msg-1",
            message_type=MessageType.SYNC,
            source="node-1",
            target="node-2",
            payload={"key": "value"},
        )
        
        result = protocol.send("node-2", message)
        assert result is True
        assert "node-2" in protocol.get_connections()
    
    def test_broadcast(self):
        protocol = CommunicationProtocol("node-1")
        protocol.connections = {"node-2": [], "node-3": []}
        
        message = Message(
            message_id="msg-1",
            message_type=MessageType.HEARTBEAT,
            source="node-1",
            target="all",
            payload={"status": "alive"},
        )
        
        result = protocol.broadcast(message)
        assert result is True


class TestStateSyncService:
    """状态同步服务测试"""
    
    def test_set_and_get_state(self):
        service = StateSyncService("node-1")
        
        service.set_state("key1", "value1")
        value = service.get_state("key1")
        assert value == "value1"
    
    def test_sync_from(self):
        service = StateSyncService("node-1")
        service.set_state("key1", "old_value")
        
        remote_state = {"key1": "new_value", "key2": "value2"}
        changes = service.sync_from(remote_state)
        
        assert "key1" in changes
        assert "key2" in changes
        assert service.get_state("key1") == "new_value"
        assert service.get_state("key2") == "value2"


class TestFailoverExecutor:
    """故障转移执行器测试"""
    
    def test_execute(self):
        executor = FailoverExecutor()
        
        result = executor.execute("node-1", "node-2")
        assert result is True
        assert executor.failover_count == 1
        assert executor.last_failover is not None


class TestLoadBalancerExecutor:
    """负载均衡执行器测试"""
    
    def test_route(self):
        executor = LoadBalancerExecutor()
        
        target = executor.route("node-1")
        assert target == "node-1"
        assert executor.request_count == 1
        assert executor.node_requests["node-1"] == 1
