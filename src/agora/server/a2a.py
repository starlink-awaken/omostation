from __future__ import annotations

import json
import logging
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

async def a2a_send_endpoint(request):
    """[Phase 9] Network A2A Receiver with Signature Verification."""
    try:
        raw_body = await request.body()
        body = json.loads(raw_body)
        target_agent_id = body.get("target_agent_id")
        message = body.get("message")
        sender_node_id = body.get("sender_node_id")
        
        # 1. Identity Check
        signature = request.headers.get("X-Swarm-Signature")
        if signature:
            from agora.mcp.swarm import get_swarm  # type: ignore[import-not-found]
            from agora.auth.node_identity import NodeIdentity  # type: ignore[import-not-found]
            
            swarm = get_swarm()
            sender_node = swarm._nodes.get(sender_node_id)
            if sender_node and sender_node.public_key:
                # Verify signature directly against raw received bytes
                is_valid = NodeIdentity.verify(
                    raw_body,
                    signature,
                    sender_node.public_key
                )
                if not is_valid:
                    logger.warning("a2a_auth_failed", node_id=sender_node_id)
                    return JSONResponse({"status": "error", "error": "invalid_signature"}, status_code=401)
                
                logger.debug("a2a_auth_success", node_id=sender_node_id)
        
        # 2. Local Delivery
        from agora.a2a.transport import A2ATransport  # type: ignore[import-not-found]
        transport = A2ATransport()
        res = transport.send_message(target_agent_id, message)
        return JSONResponse(res)
        
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
