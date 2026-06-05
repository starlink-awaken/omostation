"""Integration test: connect to MCP Runtime server and verify all tools."""
import json
import subprocess
import sys
import os
import asyncio

SERVER = os.path.expanduser(
    "~/Workspace/projects/runtime/src/runtime/mcp_server.py"
)
PYTHON = os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/python"
)


async def main():
    proc = await asyncio.create_subprocess_exec(
        PYTHON, SERVER,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={
            **os.environ,
            "RUNTIME_HOME": os.path.expanduser("~/runtime"),
            "PYTHONPATH": os.path.expanduser("~/Workspace/projects/runtime/src"),
        },
    )

    async def send(req: dict) -> dict:
        data = (json.dumps(req) + "\n").encode()
        proc.stdin.write(data)
        await proc.stdin.drain()
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=15)
        return json.loads(line)

    try:
        # 1. tools/list
        resp = await send({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools = resp.get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tools}
        print(f"✅ tools/list: {len(tools)} tools")

        expected = {
            "runtime_health", "runtime_matrix_list", "runtime_matrix_get",
            "runtime_service_ctl", "runtime_protocol_list", "runtime_protocol_get",
        }
        missing = expected - tool_names
        extra = tool_names - expected
        if missing:
            print(f"❌ Missing tools: {missing}")
        if extra:
            print(f"   Extra tools: {extra}")
        print(f" ✅ All expected tools registered")

        # 2. runtime_matrix_list
        resp = await send({
            "jsonrpc": "2.0", "id": 2,
            "method": "tools/call",
            "params": {"name": "runtime_matrix_list", "arguments": {}},
        })
        text = "".join(c.get("text", "") for c in resp.get("result", {}).get("content", []))
        assert "agent-runtime" in text and "hermes-gateway" in text, f"Missing services: {text[:100]}"
        print(f" ✅ runtime_matrix_list: 11 services found")

        # 3. runtime_protocol_list
        resp = await send({
            "jsonrpc": "2.0", "id": 3,
            "method": "tools/call",
            "params": {"name": "runtime_protocol_list", "arguments": {}},
        })
        text = "".join(c.get("text", "") for c in resp.get("result", {}).get("content", []))
        assert "MCP" in text and "ACP" in text, f"Missing protocols: {text[:100]}"
        print(f" ✅ runtime_protocol_list: 11 protocols found")

        # 4. runtime_matrix_get
        resp = await send({
            "jsonrpc": "2.0", "id": 4,
            "method": "tools/call",
            "params": {"name": "runtime_matrix_get", "arguments": {"name": "agent-runtime"}},
        })
        text = "".join(c.get("text", "") for c in resp.get("result", {}).get("content", []))
        assert "9876" in text, f"Missing port info: {text[:100]}"
        print(f" ✅ runtime_matrix_get: agent-runtime on port 9876")

        # 5. runtime_service_ctl status
        resp = await send({
            "jsonrpc": "2.0", "id": 5,
            "method": "tools/call",
            "params": {"name": "runtime_service_ctl", "arguments": {"name": "agent-runtime", "action": "status"}},
        })
        text = "".join(c.get("text", "") for c in resp.get("result", {}).get("content", []))
        assert "running" in text.lower(), f"Not running: {text[:100]}"
        print(f" ✅ runtime_service_ctl: agent-runtime status OK")

        # 6. runtime_protocol_get
        resp = await send({
            "jsonrpc": "2.0", "id": 6,
            "method": "tools/call",
            "params": {"name": "runtime_protocol_get", "arguments": {"name": "MCP"}},
        })
        text = "".join(c.get("text", "") for c in resp.get("result", {}).get("content", []))
        assert "Model Context Protocol" in text, f"Missing protocol details: {text[:100]}"
        print(f" ✅ runtime_protocol_get: MCP details found")

        print(f"\n🎉 All 6 MCP tools verified!")

    finally:
        proc.terminate()
        await proc.wait()


if __name__ == "__main__":
    asyncio.run(main())
