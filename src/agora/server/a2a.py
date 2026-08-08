from __future__ import annotations

import json
import logging
import time

from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── Phase 15: Replay Protection Cache ──
_SEEN_SIGNATURES: set[str] = set()
_LAST_CLEANUP = 0.0


async def a2a_send_endpoint(request):
    """[Phase 9/15] Network A2A Receiver with Signature & Replay Verification."""
    global _LAST_CLEANUP
    try:
        raw_body = await request.body()
        body = json.loads(raw_body)
        target_agent_id = body.get("target_agent_id")
        message = body.get("message")
        sender_node_id = body.get("sender_node_id")
        msg_ts = body.get("timestamp", 0)

        # 1. Identity Check
        signature = request.headers.get("X-Swarm-Signature")
        if signature:
            # ── Phase 15: TTL Check (5 mins) ──
            now = time.time()
            if abs(now - msg_ts) > 300:
                logger.warning(
                    "a2a_replay_blocked: timestamp_out_of_window",
                    extra={"node_id": sender_node_id, "ts": msg_ts},
                )
                return JSONResponse(
                    {"status": "error", "error": "timestamp_out_of_window"},
                    status_code=401,
                )

            # ── Phase 15: Replay Check ──
            if signature in _SEEN_SIGNATURES:
                logger.warning(
                    "a2a_replay_blocked: signature_already_seen",
                    extra={"node_id": sender_node_id},
                )
                return JSONResponse(
                    {"status": "error", "error": "replay_detected"}, status_code=401
                )

            from agora.auth.node_identity import (
                NodeIdentity,  # type: ignore[import-not-found]
            )
            from agora.mcp.swarm import get_swarm  # type: ignore[import-not-found]

            swarm = get_swarm()
            sender_node = swarm._nodes.get(sender_node_id)
            if sender_node and sender_node.public_key:  # type: ignore[reportAttributeAccessIssue]
                # Verify signature directly against raw received bytes
                is_valid = NodeIdentity.verify(
                    raw_body,
                    signature,
                    sender_node.public_key,  # type: ignore[reportAttributeAccessIssue]
                )
                if not is_valid:
                    logger.warning("a2a_auth_failed", extra={"node_id": sender_node_id})
                    return JSONResponse(
                        {"status": "error", "error": "invalid_signature"},
                        status_code=401,
                    )

                # Record signature to prevent replay
                _SEEN_SIGNATURES.add(signature)
                logger.debug("a2a_auth_success", extra={"node_id": sender_node_id})

                # Simple cleanup every hour
                if now - _LAST_CLEANUP > 3600:
                    _SEEN_SIGNATURES.clear()
                    _LAST_CLEANUP = now

        # 2. Local Delivery
        from agora.a2a.transport import A2ATransport  # type: ignore[import-not-found]

        transport = A2ATransport()
        res = transport.send_message(target_agent_id, message)
        return JSONResponse(res)

    except Exception as e:  # defensive fallback
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
