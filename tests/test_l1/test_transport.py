"""L1 Transport 测试 — WireMessage 编解码 + TCPNode 真实网络"""

import asyncio
import struct
import time

from ecos.l1.transport import TCPNode, WireMessage, ChannelState


class TestWireMessage:
    """WireMessage 编解码测试"""

    def test_encode_decode_roundtrip(self):
        msg = WireMessage(
            msg_id="test-1", msg_type="sync",
            source="node-a", target="node-b",
            payload={"key": "value", "num": 42},
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)

        assert decoded.msg_id == "test-1"
        assert decoded.msg_type == "sync"
        assert decoded.source == "node-a"
        assert decoded.target == "node-b"
        assert decoded.payload["key"] == "value"
        assert decoded.payload["num"] == 42

    def test_encode_length_prefix(self):
        msg = WireMessage(
            msg_id="t", msg_type="ping",
            source="a", target="b", payload={},
        )
        encoded = msg.encode()
        length = struct.unpack("!I", encoded[:4])[0]
        assert length == len(encoded) - 4

    def test_large_payload(self):
        large_payload = {"data": "x" * 10000}
        msg = WireMessage(
            msg_id="big", msg_type="data",
            source="a", target="b", payload=large_payload,
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)
        assert len(decoded.payload["data"]) == 10000

    def test_unicode_payload(self):
        msg = WireMessage(
            msg_id="u", msg_type="text",
            source="a", target="b", payload={"text": "你好世界"},
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)
        assert decoded.payload["text"] == "你好世界"

    def test_nested_payload(self):
        msg = WireMessage(
            msg_id="n", msg_type="complex",
            source="a", target="b",
            payload={"level1": {"level2": [1, 2, 3]}},
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)
        assert decoded.payload["level1"]["level2"] == [1, 2, 3]

    def test_empty_payload(self):
        msg = WireMessage(
            msg_id="e", msg_type="empty",
            source="a", target="b", payload={},
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)
        assert decoded.payload == {}


class TestTCPNodeBasic:
    """TCPNode 基础测试"""

    def test_create_node(self):
        node = TCPNode("test-node", "127.0.0.1", 8080)
        assert node.node_id == "test-node"
        assert node.host == "127.0.0.1"
        assert node.port == 8080
        assert node.state == ChannelState.DISCONNECTED

    def test_handler_registration(self):
        handled = []
        node = TCPNode("test", "127.0.0.1", 0)
        node.on("custom", lambda msg: handled.append(msg))

        msg = WireMessage(
            msg_id="t", msg_type="custom",
            source="x", target="test", payload={"data": 1},
        )
        node._on_receive(msg)

        assert len(handled) == 1
        assert handled[0].payload["data"] == 1

    def test_ack_handling(self):
        pending_acks = {}
        node = TCPNode("test", "127.0.0.1", 0)
        node._pending_acks = pending_acks

        event = asyncio.Event()
        pending_acks["msg-1"] = event

        ack_msg = WireMessage(
            msg_id="ack-1", msg_type="ack",
            source="server", target="test",
            payload={"ack_for": "msg-1"},
        )
        node._on_receive(ack_msg)

        assert "msg-1" not in pending_acks

    def test_get_stats(self):
        node = TCPNode("test", "127.0.0.1", 9999)
        stats = node.get_stats()
        assert stats["node_id"] == "test"
        assert stats["port"] == 9999
        assert stats["state"] == "disconnected"
        assert stats["peer_count"] == 0

    def test_get_peers_empty(self):
        node = TCPNode("test", "127.0.0.1", 0)
        assert node.get_peers() == []

    def test_multiple_handlers(self):
        results = []
        node = TCPNode("test", "127.0.0.1", 0)
        node.on("type_a", lambda msg: results.append("a"))
        node.on("type_b", lambda msg: results.append("b"))

        msg_a = WireMessage(msg_id="1", msg_type="type_a", source="x", target="test", payload={})
        msg_b = WireMessage(msg_id="2", msg_type="type_b", source="x", target="test", payload={})

        node._on_receive(msg_a)
        node._on_receive(msg_b)

        assert results == ["a", "b"]


class TestTCPNodeAsync:
    """TCPNode 异步网络测试"""

    async def test_start_and_stop(self):
        node = TCPNode("server", "127.0.0.1", 0)
        port = await node.start()
        assert port > 0
        assert node.state == ChannelState.CONNECTED
        await node.stop()
        assert node.state == ChannelState.CLOSED

    async def test_two_nodes_connect(self):
        server = TCPNode("server", "127.0.0.1", 0)
        client = TCPNode("client", "127.0.0.1", 0)

        server_port = await server.start()
        await client.start()

        connected = await client.connect_to("127.0.0.1", server_port, "server")
        assert connected
        assert "server" in client.get_peers()

        await server.stop()
        await client.stop()

    async def test_send_receive_message(self):
        received = []

        server = TCPNode("server", "127.0.0.1", 0)
        server.on("test_msg", lambda msg: received.append(msg))

        client = TCPNode("client", "127.0.0.1", 0)

        server_port = await server.start()
        await client.start()
        await client.connect_to("127.0.0.1", server_port, "server")

        await asyncio.sleep(0.1)

        sent = await client.send("server", "test_msg", {"hello": "world"})
        assert sent

        await asyncio.sleep(0.3)

        assert len(received) >= 1
        assert received[0].payload["hello"] == "world"

        await server.stop()
        await client.stop()

    async def test_broadcast(self):
        received_a = []
        received_b = []

        node_a = TCPNode("a", "127.0.0.1", 0)
        node_b = TCPNode("b", "127.0.0.1", 0)
        hub = TCPNode("hub", "127.0.0.1", 0)

        node_a.on("broadcast_msg", lambda msg: received_a.append(msg))
        node_b.on("broadcast_msg", lambda msg: received_b.append(msg))

        await hub.start()
        a_port = await node_a.start()
        b_port = await node_b.start()

        await hub.connect_to("127.0.0.1", a_port, "a")
        await hub.connect_to("127.0.0.1", b_port, "b")

        await asyncio.sleep(0.1)

        hub.broadcast("broadcast_msg", {"announcement": "hello all"})

        await asyncio.sleep(0.3)

        assert len(received_a) >= 1
        assert len(received_b) >= 1

        await hub.stop()
        await node_a.stop()
        await node_b.stop()

    async def test_node_stats_after_start(self):
        node = TCPNode("test", "127.0.0.1", 0)
        await node.start()

        stats = node.get_stats()
        assert stats["node_id"] == "test"
        assert stats["state"] == "connected"
        assert stats["port"] > 0

        await node.stop()

    async def test_multi_node_star_topology(self):
        """星型拓扑: hub 连接 3 个节点"""
        hub = TCPNode("hub", "127.0.0.1", 0)
        nodes = [TCPNode(f"node-{i}", "127.0.0.1", 0) for i in range(3)]

        await hub.start()
        node_ports = []
        for n in nodes:
            port = await n.start()
            node_ports.append(port)

        for i, n in enumerate(nodes):
            await hub.connect_to("127.0.0.1", node_ports[i], f"node-{i}")

        await asyncio.sleep(0.1)

        assert len(hub.get_peers()) == 3

        received = {f"node-{i}": [] for i in range(3)}
        for i, n in enumerate(nodes):
            n.on("test", lambda msg, idx=i: received[f"node-{idx}"].append(msg))

        hub.broadcast("test", {"from": "hub"})

        await asyncio.sleep(0.3)

        for i in range(3):
            assert len(received[f"node-{i}"]) >= 1

        await hub.stop()
        for n in nodes:
            await n.stop()

    async def test_message_latency(self):
        """消息延迟测量"""
        received = []
        server = TCPNode("server", "127.0.0.1", 0)
        server.on("bench", lambda msg: received.append((time.monotonic(), msg)))

        client = TCPNode("client", "127.0.0.1", 0)

        server_port = await server.start()
        await client.start()
        await client.connect_to("127.0.0.1", server_port, "server")
        await asyncio.sleep(0.1)

        latencies = []
        for _ in range(20):
            start = time.monotonic()
            await client.send("server", "bench", {"ts": start})
            await asyncio.sleep(0.05)
            if received:
                recv_time, msg = received[-1]
                latency = (recv_time - msg.payload["ts"]) * 1000
                latencies.append(latency)

        if latencies:
            avg = sum(latencies) / len(latencies)
            assert avg < 100, f"平均延迟 {avg:.1f}ms 超过 100ms"

        await server.stop()
        await client.stop()
