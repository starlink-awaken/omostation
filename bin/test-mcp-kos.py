#!/usr/bin/env python3
"""TDD test script for validation of mcp-server-kos.py protocol compliance."""
import sys
import json
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
MCP_SERVER = WORKSPACE / "bin" / "mcp-server-kos.py"
KOS_DB = WORKSPACE / "kos" / "kos-index.sqlite"


def run_mcp_query(request_payloads: list[dict]) -> list[dict]:
    # 启动 MCP Server 进程
    proc = subprocess.Popen(
        [sys.executable, str(MCP_SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    responses = []
    try:
        for req in request_payloads:
            # 写入一行请求
            proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            proc.stdin.flush()
            # 读取一行回复
            line = proc.stdout.readline()
            if line:
                responses.append(json.loads(line.strip()))
    finally:
        proc.terminate()
        proc.wait()
        
    return responses


def main() -> int:
    print("🧪 Running TDD tests for mcp-server-kos.py...")
    
    if not MCP_SERVER.is_file():
        print(f"❌ Error: MCP Server target not found at: {MCP_SERVER}")
        return 1

    if not KOS_DB.is_file():
        print(f"⏭️  Skip: KOS database not found at {KOS_DB} (runtime artifact, not in git)")
        return 0

    # 测试 Payload 1: initialize
    reqs = [
        {"jsonrpc": "2.0", "method": "initialize", "id": 1},
        {"jsonrpc": "2.0", "method": "tools/list", "id": 2},
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_custom_sql",
                "arguments": {"sql": "SELECT COUNT(*) as cnt FROM documents"}
            },
            "id": 3
        },
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_custom_sql",
                "arguments": {"sql": "DROP TABLE documents"}
            },
            "id": 4
        }
    ]
    
    try:
        res = run_mcp_query(reqs)
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        return 1
        
    if len(res) < 4:
        print(f"❌ Error: Expected 4 responses, got {len(res)}: {res}")
        return 1
        
    # 1. 验证 initialize
    init_res = res[0]
    if init_res.get("result", {}).get("serverInfo", {}).get("name") != "mcp-server-kos":
        print(f"❌ Error: Initialize validation failed: {init_res}")
        return 1
    print("✅ Initialize handshake PASS.")
    
    # 2. 验证 tools/list
    list_res = res[1]
    tools = list_res.get("result", {}).get("tools", [])
    tool_names = {t["name"] for t in tools}
    expected_tools = {"search_kos", "get_document", "list_entities", "query_custom_sql"}
    if not expected_tools.issubset(tool_names):
        print(f"❌ Error: Tools list validation failed. Found: {tool_names}")
        return 1
    print("✅ Tools listing schema PASS.")
    
    # 3. 验证 query_custom_sql (只读读取行数)
    query_res = res[2]
    content = query_res.get("result", {}).get("content", [{}])[0].get("text", "")
    try:
        data = json.loads(content)
        cnt = data[0]["cnt"]
        print(f"✅ Database query PASS. KOS document count: {cnt}")
    except Exception as e:
        print(f"❌ Error: Database query result parsing failed: {content}, err={e}")
        return 1
        
    # 4. 验证安全拦截 (DROP TABLE)
    sec_res = res[3]
    is_error = sec_res.get("result", {}).get("isError")
    sec_text = sec_res.get("result", {}).get("content", [{}])[0].get("text", "")
    if not is_error or "prohibited" not in sec_text:
        print(f"❌ Error: Security protection failed to intercept write command: {sec_res}")
        return 1
    print("✅ Write interception security PASS.")
    
    print("\n🏁 ALL KOS MCP SERVER TESTS PASSED SUCCESSFULLY! (4/4 PASS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
