"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Gateway/AGENTS.md
Layer: L3
Domain: D-Gateway
Summary: "Kademlia DHT node for decentralized discovery and fact relay."
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Dht Node ≡ Module
# 内涵 ≝ {Dht, Node}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, DhtNode)}
# 功能 ⊢ {Dht_Node, Init_Dht, Validate_Node}
# =============================================================================

import asyncio
import json
import logging
from typing import Any

from agora.dht_routing import DHTRoutingTable  # type: ignore[import-not-found]

_log = logging.getLogger(__name__)


class DHTNode:
    """
    [PB-5] Kademlia DHT Node implementation for decentralized discovery.
    Provides Ping, Store, Find_Node, Find_Value RPCs.
    """

    def __init__(self, node_id: str, host: str, port: int, k: int = 20) -> None:
        self.node_id = node_id
        self.host = host
        self.port = port
        self.routing_table = DHTRoutingTable(node_id, k=k)
        self.data_store: dict[str, Any] = {}
        self.server: asyncio.AbstractServer | None = None
        self.running: bool = False

    async def start(self) -> None:
        """Start the DHT RPC server (TCP-based for reliability in this prototype)."""
        self.server = await asyncio.start_server(self._handle_rpc, self.host, self.port)
        self.running = True
        _log.info(
            f"🌐 [DHT] Node {self.node_id[:8]} listening on {self.host}:{self.port}"
        )
        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle_rpc(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming RPC requests."""
        data = await reader.read(4096)
        if not data:
            writer.close()
            return

        try:
            request = json.loads(data.decode())
            rpc_type = request.get("rpc")
            sender_id = request.get("sender_id")
            sender_host = request.get("sender_host")
            sender_port = request.get("sender_port")

            # Update routing table with sender info (Kademlia requirement)
            if sender_id and sender_host and sender_port:
                self.routing_table.add_peer(sender_id, sender_host, sender_port)

            response: dict[str, Any] = {"status": "error", "message": "Unknown RPC"}

            if rpc_type == "PING":
                response = {
                    "status": "success",
                    "echo": "PONG",
                    "node_id": self.node_id,
                }

            elif rpc_type == "STORE":
                key = request.get("key")
                value = request.get("value")
                if key:
                    self.data_store[key] = value
                    response = {"status": "success"}

            elif rpc_type == "FIND_NODE":
                target_id = request.get("target_id")
                closest = self.routing_table.find_closest(target_id)
                response = {"status": "success", "nodes": closest}

            elif rpc_type == "FIND_VALUE":
                key = request.get("key")
                if key in self.data_store:
                    response = {"status": "success", "value": self.data_store[key]}
                else:
                    closest = self.routing_table.find_closest(key)
                    response = {"status": "success", "nodes": closest}

            elif rpc_type == "SYNC_FACTS":
                facts = request.get("facts", [])
                # [PB-5] Canonical implementation: Write facts to D-Memory (Phase 2 Task 1 Cleanup)
                from nucleus.Z_Microkernel.organs.uri_router import Router  # type: ignore[import-not-found]

                success_count = 0
                for fact in facts:
                    try:
                        # Convert back to triple format for add_fact
                        await Router.call(
                            "bos://memory/fact/write",
                            {
                                "sub": fact.get("sub"),
                                "pred": fact.get("pred"),
                                "obj": fact.get("obj"),
                                "metadata": fact.get("metadata"),
                                "vector_clock": fact.get("vector_clock"),
                                "_remote_sync": True,  # Avoid recursive broadcast
                            },
                        )
                        success_count += 1
                    except (
                        AttributeError,
                        TypeError,
                        ValueError,
                        OSError,
                        RuntimeError,
                        TimeoutError,
                        ConnectionError,
                    ) as exc:
                        _log.debug(f"[DHT] Failed to relay fact to memory: {exc}")

                response = {
                    "status": "success",
                    "received": len(facts),
                    "persisted": success_count,
                }

            elif rpc_type == "QUERY_FACTS":
                params = request.get("query", {})
                from nucleus.Z_Microkernel.organs.uri_router import Router

                try:
                    params["_local_only"] = True
                    # Retrieve local results to serve back to requester
                    res = await Router.call("bos://memory/fact/query", params)
                    results = res.get("results", []) if isinstance(res, dict) else []
                    response = {"status": "success", "facts": results}
                except (
                    AttributeError,
                    TypeError,
                    ValueError,
                    OSError,
                    RuntimeError,
                    TimeoutError,
                    ConnectionError,
                ) as exc:
                    _log.debug(f"[DHT] Failed to query local facts: {exc}")
                    response = {"status": "error", "message": str(exc)}

            writer.write(json.dumps(response).encode())
            await writer.drain()
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            ConnectionError,
            OSError,
            KeyError,
            TypeError,
            ValueError,
        ) as e:
            _log.error(f"[DHT] RPC Error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def call_rpc(self, host: str, port: int, rpc_data: dict) -> dict | None:
        """Client-side helper to call a remote RPC."""
        try:
            # Inject local info
            rpc_data["sender_id"] = self.node_id
            rpc_data["sender_host"] = self.host
            rpc_data["sender_port"] = self.port

            reader, writer = await asyncio.open_connection(host, port)
            writer.write(json.dumps(rpc_data).encode())
            await writer.drain()

            data = await reader.read(4096)
            writer.close()
            await writer.wait_closed()

            return json.loads(data.decode()) if data else None
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            ConnectionError,
            OSError,
            TypeError,
            ValueError,
        ) as e:
            _log.debug(
                f"[DHT] Failed to call RPC {rpc_data.get('rpc')} on {host}:{port}: {e}"
            )
            return None

    async def bootstrap(self, seeds: list[dict[str, Any]]) -> bool:
        """Join the network by bootstrapping from seed nodes and performing recursive lookup."""
        success = False
        for seed in seeds:
            res = await self.call_rpc(seed["host"], seed["port"], {"rpc": "PING"})
            if res and res.get("status") == "success":
                # Contacted a node, add it
                self.routing_table.add_peer(res["node_id"], seed["host"], seed["port"])
                success = True

        if success:
            # Perform recursive FIND_NODE for ourselves to populate routing table
            await self.recursive_find_node(self.node_id)
            _log.info("✅ [DHT] Bootstrapped and populated routing table.")

        return success

    async def recursive_find_node(self, target_id: str) -> list[dict[str, Any]]:
        """[PB-5] Recursive Kademlia node discovery."""
        closest = self.routing_table.find_closest(target_id)
        visited = {self.node_id}

        while True:
            added_any = False
            # Pick top 3 closest nodes we haven't visited
            to_query = [n for n in closest if n["peer_id"] not in visited][:3]
            if not to_query:
                break

            tasks = []
            for node in to_query:
                visited.add(node["peer_id"])
                tasks.append(
                    self.call_rpc(
                        node["address"],
                        node["port"],
                        {"rpc": "FIND_NODE", "target_id": target_id},
                    )
                )

            responses = await asyncio.gather(*tasks)
            for res in responses:
                if res and res.get("status") == "success":
                    for new_node in res.get("nodes", []):
                        if new_node["peer_id"] != self.node_id:
                            self.routing_table.add_peer(
                                new_node["peer_id"],
                                new_node["address"],
                                new_node["port"],
                            )
                            added_any = True

            if not added_any:
                break
            # Refresh closest list
            closest = self.routing_table.find_closest(target_id)

        return closest

    async def broadcast_facts(self, facts: list[dict[str, Any]]) -> None:
        """[PB-5] Broadcast facts to known neighbors."""
        peers = self.routing_table.get_all_peers()
        if not peers:
            return

        tasks = []
        for peer in peers:
            tasks.append(
                self.call_rpc(
                    peer["address"], peer["port"], {"rpc": "SYNC_FACTS", "facts": facts}
                )
            )

        if tasks:
            await asyncio.gather(*tasks)
            _log.info(f"📤 [DHT] Broadcasted {len(facts)} facts to {len(peers)} peers.")

    async def query_facts(self, query_params: dict[str, Any]) -> list[dict[str, Any]]:
        """[PB-5] Query facts from known neighbors."""
        peers = self.routing_table.get_all_peers()
        if not peers:
            return []

        tasks = []
        for peer in peers:
            tasks.append(
                self.call_rpc(
                    peer["address"],
                    peer["port"],
                    {"rpc": "QUERY_FACTS", "query": query_params},
                )
            )

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        all_facts = []
        for res in responses:
            if isinstance(res, dict) and res.get("status") == "success":
                all_facts.extend(res.get("facts", []))

        _log.info(
            f"🔍 [DHT] Queried {len(peers)} peers, found {len(all_facts)} remote facts."
        )
        return all_facts
