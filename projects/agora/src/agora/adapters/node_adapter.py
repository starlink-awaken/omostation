"""异构节点Adapter模板 — Phase 9 / T133

外部系统接入联邦只需实现4个接口。
"""

from abc import ABC, abstractmethod


class NodeAdapter(ABC):
    """外部节点Adapter基类。"""

    @abstractmethod
    def get_node_info(self) -> dict:
        """返回节点基本信息。"""

    @abstractmethod
    def call_tool(self, tool: str, args: dict) -> dict:
        """调用外部节点的能力。"""

    @abstractmethod
    def submit_task(self, task_data: dict) -> dict:
        """向外部节点提交Task。"""

    @abstractmethod
    def get_task_status(self, task_id: str) -> dict:
        """查询Task状态。"""

    def health_check(self) -> bool:
        return True


class FullNodeAdapter(NodeAdapter):
    """接入完整4+1+3架构节点。"""

    def __init__(self, node_id: str, endpoint: str, a2a_endpoint: str = ""):
        self.node_id = node_id
        self.endpoint = endpoint
        self.a2a_endpoint = a2a_endpoint or f"{endpoint}/mcp"

    def get_node_info(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": "full",
            "capabilities": ["identity", "capability", "task", "event", "knowledge"],
            "endpoint_url": self.endpoint,
            "a2a_endpoint": self.a2a_endpoint,
        }

    def call_tool(self, tool: str, args: dict) -> dict:
        import json
        from urllib import request

        payload = json.dumps({"tool": tool, "arguments": args}).encode()
        req = request.Request(f"{self.endpoint}/api/call", data=payload, headers={"Content-Type": "application/json"})  # noqa: S310
        return json.loads(request.urlopen(req, timeout=30).read().decode())  # noqa: S310

    def submit_task(self, task_data: dict) -> dict:
        return self.call_tool(
            "collab.create_task",
            {
                "title": task_data["title"],
                "goal": task_data.get("goal", ""),
                "creator": task_data.get("creator", "agent:external"),
                "visibility_scope": "public",
                "subtasks": task_data.get("subtasks", []),
            },
        )

    def get_task_status(self, task_id: str) -> dict:
        return self.call_tool("collab.get_task", {"task_id": task_id})


class GitHubActionsAdapter(NodeAdapter):
    """接入GitHub Actions作为外部节点。"""

    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token

    def get_node_info(self) -> dict:
        return {
            "node_id": f"node:github-{self.repo.replace('/', '-')}",
            "node_type": "external",
            "capabilities": ["task", "ci_cd"],
            "endpoint_url": f"https://api.github.com/repos/{self.repo}",
            "owner": "github",
        }

    def call_tool(self, tool: str, args: dict) -> dict:
        import json
        from urllib import request

        if tool == "github.dispatch_workflow":
            url = f"https://api.github.com/repos/{self.repo}/actions/workflows/{args['workflow_id']}/dispatches"
            payload = json.dumps({"ref": args.get("ref", "main")}).encode()
            req = request.Request(  # noqa: S310
                url,
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            request.urlopen(req, timeout=30)  # noqa: S310
            return {"status": "dispatched"}
        return {"error": f"unknown tool: {tool}"}

    def submit_task(self, task_data: dict) -> dict:
        return {"task_id": None, "fallback": "not supported"}

    def get_task_status(self, task_id: str) -> dict:
        return {"status": "unknown"}
