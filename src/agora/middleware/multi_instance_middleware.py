"""Multi-Instance Middleware — 在Router中隔离不同实例的服务注册和路由。"""

from __future__ import annotations

from agora.instance import AgoraInstance, InstanceManager  # type: ignore[import-not-found]

# 路由隔离规则:
# 1. service.register → 只注册到当前实例
# 2. tool.list → 只返回当前实例的工具 (除非跨实例请求)
# 3. route.call → 只在当前实例路由 (除非显式指定目标实例)
# 4. cross-instance call → 通过A2A转发到目标实例


class InstanceRouter:
    def __init__(self, instance_manager: InstanceManager):
        self.im = instance_manager

    def should_handle(self, tool_name: str, target_instance: str = "") -> bool:
        """判断当前实例是否应该处理此调用。"""
        if not target_instance:
            return True  # 无目标=当前实例
        local = self.im.get_local()
        return target_instance == local.instance_id

    def get_peer_for_tool(self, tool_name: str) -> AgoraInstance | None:
        """找到能处理此工具的远程实例。"""
        for inst in self.im.list():
            for svc in inst.services:
                if tool_name.startswith(svc):
                    return inst
        return None

    def route_to_peer(self, peer: AgoraInstance, tool: str, args: dict) -> dict:
        """通过A2A转发到对等实例。"""
        import json
        from urllib import request

        payload = json.dumps({"tool": tool, "arguments": args}).encode()
        req = request.Request(  # noqa: S310
            f"{peer.a2a_endpoint}/api/call",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Instance-Id": peer.instance_id,
            },
        )
        resp = request.urlopen(req, timeout=30)  # noqa: S310
        return json.loads(resp.read().decode())
