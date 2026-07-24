from __future__ import annotations

import logging
import time

from agora.tools.base import (
    JSONDict,
    ToolContext,
    _get_synapse_link,
    _json_object,
    _synapse_hello_handler,
)

_log = logging.getLogger(__name__)


def tool_synapse_hello(params: JSONDict, ctx: ToolContext) -> JSONDict:
    link = _get_synapse_link()
    if link is None:
        return {"error": "SynapseLink not available"}
    if _synapse_hello_handler is None:
        return {"error": "Synapse hello handler not available"}
    response = _json_object(_synapse_hello_handler(link, params))
    if response is None:
        return {"error": "Synapse hello handler returned invalid payload"}
    return response


def tool_synapse_ping(params: JSONDict, ctx: ToolContext) -> JSONDict:
    link = _get_synapse_link()
    if link is None:
        return {"pong": True, "node_id": "unknown", "timestamp": time.time()}
    remote_id = params.get("node_id", "unknown")
    node = link.get_node(remote_id)
    if node is not None:
        from datetime import UTC, datetime

        node.last_seen = datetime.now(UTC)
    return {"pong": True, "node_id": link._identity.node_id, "timestamp": time.time()}
