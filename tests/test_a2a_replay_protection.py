"""Tests for A2A network replay protection."""

import json
import time
from unittest.mock import MagicMock, patch

import agora.server.a2a as a2a_mod


class _FakeRequest:
    def __init__(self, body_dict, headers=None):
        self._body = json.dumps(body_dict).encode("utf-8")
        self.headers = headers or {}

    async def body(self):
        return self._body


def setup_module():
    a2a_mod._SEEN_SIGNATURES.clear()


def teardown_module():
    a2a_mod._SEEN_SIGNATURES.clear()


async def test_a2a_rejects_outdated_timestamp():
    """Messages outside the 300s TTL window should be rejected."""
    payload = {
        "target_agent_id": "agent-1",
        "message": {"text": "hello"},
        "sender_node_id": "node-a",
        "timestamp": time.time() - 400,
    }
    request = _FakeRequest(payload, {"X-Swarm-Signature": "sig-old"})

    response = await a2a_mod.a2a_send_endpoint(request)
    assert response.status_code == 401
    body = json.loads(response.body)  # type: ignore[reportArgumentType]
    assert body["error"] == "timestamp_out_of_window"


async def test_a2a_rejects_replayed_signature():
    """Duplicate signatures within the TTL window should be rejected."""
    a2a_mod._SEEN_SIGNATURES.clear()
    now = time.time()
    payload = {
        "target_agent_id": "agent-1",
        "message": {"text": "hello"},
        "sender_node_id": "node-a",
        "timestamp": now,
    }

    fake_node = MagicMock()
    fake_node.public_key = "pubkey"
    fake_swarm = MagicMock()
    fake_swarm._nodes = {"node-a": fake_node}

    with (
        patch("agora.mcp.swarm.get_swarm", return_value=fake_swarm),
        patch("agora.auth.node_identity.NodeIdentity.verify", return_value=True),
        patch(
            "agora.a2a.transport.A2ATransport.send_message",
            return_value={"status": "delivered", "msg_id": "m1", "target": "agent-1"},
        ),
    ):
        # Manually seed the module-level cache to exercise replay detection
        a2a_mod._SEEN_SIGNATURES.add("sig-replay")

        request2 = _FakeRequest(payload, {"X-Swarm-Signature": "sig-replay"})
        response2 = await a2a_mod.a2a_send_endpoint(request2)
        assert response2.status_code == 401, json.loads(response2.body)  # type: ignore[reportArgumentType]
        body = json.loads(response2.body)  # type: ignore[reportArgumentType]
        assert body["error"] == "replay_detected"
