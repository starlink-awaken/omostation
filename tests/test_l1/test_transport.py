"""L1 Transport 测试 — WireMessage 编解码 + TCPNode 基础"""

import struct
import asyncio

from ecos.l1.transport import TCPNode, WireMessage, ChannelState, MessageProtocol


class TestWireMessage:
    """WireMessage 编解码测试"""

    def test_encode_decode_roundtrip(self):
        msg = WireMessage(
            msg_id="test-1",
            msg_type="sync",
            source="node-a",
            target="node-b",
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
            msg_id="t",
            msg_type="ping",
            source="a",
            target="b",
            payload={},
        )
        encoded = msg.encode()
        length = struct.unpack("!I", encoded[:4])[0]
        assert length == len(encoded) - 4

    def test_large_payload(self):
        large_payload = {"data": "x" * 10000}
        msg = WireMessage(
            msg_id="big",
            msg_type="data",
            source="a",
            target="b",
            payload=large_payload,
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)
        assert len(decoded.payload["data"]) == 10000

    def test_unicode_payload(self):
        msg = WireMessage(
            msg_id="u",
            msg_type="text",
            source="a",
            target="b",
            payload={"text": "你好世界"},
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)
        assert decoded.payload["text"] == "你好世界"

    def test_nested_payload(self):
        msg = WireMessage(
            msg_id="n",
            msg_type="complex",
            source="a",
            target="b",
            payload={"level1": {"level2": [1, 2, 3]}},
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)
        assert decoded.payload["level1"]["level2"] == [1, 2, 3]

    def test_empty_payload(self):
        msg = WireMessage(
            msg_id="e",
            msg_type="empty",
            source="a",
            target="b",
            payload={},
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)
        assert decoded.payload == {}

    def test_multiple_messages(self):
        messages = []
        for i in range(10):
            msg = WireMessage(
                msg_id=f"m-{i}",
                msg_type="seq",
                source="a",
                target="b",
                payload={"i": i},
            )
            encoded = msg.encode()
            decoded = WireMessage.decode(encoded)
            messages.append(decoded)

        assert len(messages) == 10
        for i, msg in enumerate(messages):
            assert msg.payload["i"] == i

    def test_binary_data(self):
        binary = bytes(range(256))
        msg = WireMessage(
            msg_id="bin",
            msg_type="binary",
            source="a",
            target="b",
            payload={"data": list(binary)},
        )
        encoded = msg.encode()
        decoded = WireMessage.decode(encoded)
        assert decoded.payload["data"] == list(binary)


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
            msg_id="t",
            msg_type="custom",
            source="x",
            target="test",
            payload={"data": 1},
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
            msg_id="ack-1",
            msg_type="ack",
            source="server",
            target="test",
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

        msg_a = WireMessage(
            msg_id="1", msg_type="type_a", source="x", target="test", payload={}
        )
        msg_b = WireMessage(
            msg_id="2", msg_type="type_b", source="x", target="test", payload={}
        )

        node._on_receive(msg_a)
        node._on_receive(msg_b)

        assert results == ["a", "b"]

    def test_handler_not_found(self):
        node = TCPNode("test", "127.0.0.1", 0)
        msg = WireMessage(
            msg_id="1", msg_type="unknown", source="x", target="test", payload={}
        )
        node._on_receive(msg)
        assert len(node._message_log) == 1

    def test_create_server_protocol(self):
        node = TCPNode("test", "127.0.0.1", 0)
        protocol = node._create_server_protocol()
        assert isinstance(protocol, MessageProtocol)

    def test_send_without_connection(self):
        async def _test():
            node = TCPNode("test", "127.0.0.1", 0)
            result = await node.send("ghost", "test", {})
            assert result is False

        asyncio.run(_test())

    def test_connect_to_nonexistent(self):
        async def _test():
            node = TCPNode("test", "127.0.0.1", 0)
            result = await node.connect_to("127.0.0.1", 99999, "ghost")
            assert result is False

        asyncio.run(_test())

    def test_broadcast_without_peers(self):
        node = TCPNode("test", "127.0.0.1", 0)
        results = node.broadcast("test", {})
        assert results == {}
