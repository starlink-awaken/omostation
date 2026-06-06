#!/usr/bin/env python3
"""
E2E test: Verify all 7 new MCP services through agora-mcp proxy.
"""

import fcntl
import json
import os
import select
import subprocess
import sys
import time


def send_message(proc: subprocess.Popen, msg: dict) -> None:
    payload = json.dumps(msg)
    data = (payload + "\n").encode("utf-8")
    proc.stdin.write(data)
    proc.stdin.flush()


class LineReader:
    """Line-oriented reader with proper buffering for subprocess stdout."""

    def __init__(self, proc: subprocess.Popen):
        self._proc = proc
        self._buf = b""

    def read_line(self, timeout: float = 30.0) -> str | None:
        start = time.time()
        while time.time() - start < timeout:
            remaining = timeout - (time.time() - start)
            if remaining <= 0:
                break
            if b"\n" in self._buf:
                idx = self._buf.index(b"\n")
                line = self._buf[:idx].decode("utf-8", errors="replace")
                self._buf = self._buf[idx + 1 :]
                return line
            if select.select([self._proc.stdout], [], [], min(remaining, 1.0))[0]:
                try:
                    data = os.read(self._proc.stdout.fileno(), 65536)
                except Exception:
                    break
                if not data:
                    break
                self._buf += data
            else:
                ret = self._proc.poll()
                if ret is not None:
                    break
        if self._buf:
            line = self._buf.decode("utf-8", errors="replace")
            self._buf = b""
            return line
        return None

    def read_json_response(self, timeout: float = 30.0) -> dict | None:
        start = time.time()
        while time.time() - start < timeout:
            remaining = timeout - (time.time() - start)
            if remaining <= 0:
                return None
            line = self.read_line(timeout=remaining)
            if line is None:
                return None
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict) and "jsonrpc" in obj:
                    return obj
            except json.JSONDecodeError:
                pass
        return None


def do_call(
    reader: LineReader, proc: subprocess.Popen, msg_id: int, tool: str, args: dict, timeout: float = 30.0
) -> dict | None:
    call_msg = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }
    send_message(proc, call_msg)
    return reader.read_json_response(timeout=timeout)


def _set_nonblocking(fd: int) -> None:
    """Set a file descriptor to non-blocking mode."""
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def drain_stderr(proc: subprocess.Popen, echo: bool = False) -> None:
    """Non-blocking drain of stderr to prevent pipe buffer from filling up.

    Uses O_NONBLOCK + os.read instead of select.select to avoid:
    - ValueError on macOS when fd exceeds FD_SETSIZE (1024)
    - Race conditions between select() and read()
    - Silent failures swallowed by bare except
    """
    try:
        fd = proc.stderr.fileno()
        _set_nonblocking(fd)
        while True:
            try:
                data = os.read(fd, 65536)
            except BlockingIOError:
                break
            if not data:
                break
            if echo:
                sys.stderr.write(data.decode("utf-8", errors="replace"))
                sys.stderr.flush()
    except (AttributeError, OSError, ValueError):
        pass


def _cleanup(proc: subprocess.Popen) -> None:
    """Clean up subprocess: drain stderr, terminate, close pipes."""
    sys.stderr.write("\n--- stderr (remaining) ---\n")
    drain_stderr(proc, echo=True)
    # Close stderr pipe to prevent lingering writes
    try:
        proc.stderr.close()
    except Exception:
        pass
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def main():
    tests_passed = 0
    tests_failed = 0
    failures = []

    NEW_SERVICES = [  # noqa: N806
        "docker-mcp-gateway",
        "gitnexus",
        "zai-mcp-server",
        "claude-mcp-serve",
        "codex-mcp-server",
        "serena",
        "chrome-devtools-mcp",
    ]

    cwd = os.path.expanduser("~/Workspace/projects/kairon")
    sys.stderr.write("=" * 60 + "\n")
    sys.stderr.write("Starting agora-mcp subprocess...\n")
    sys.stderr.write("=" * 60 + "\n")

    proc = subprocess.Popen(
        ["uv", "run", "--package", "agora", "agora-mcp"],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # ── 2. Wait for lifespan boot + service connections ──────────────
    # The lifespan starts all 19 services in parallel.
    # Most services connect within ~10s, docker-mcp-gateway takes up to 30s.
    # We wait 20s to ensure lifespan completes before sending JSON-RPC,
    # so structlog messages don't interleave with MCP responses.
    sys.stderr.write("\n[STEP] Waiting 20s for proxy bootstrap + service connections...\n")
    for i in range(20):
        time.sleep(1)
        drain_stderr(proc, echo=True)  # drain stderr every second to prevent pipe blocking
        if i % 5 == 4:
            sys.stderr.write(f"  ... waited {i + 1}s\n")

    # ── 3. MCP Initialize ────────────────────────────────────────────
    sys.stderr.write("\n[STEP] MCP Initialize\n")
    reader = LineReader(proc)
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }
    send_message(proc, init_msg)
    init_resp = reader.read_json_response(timeout=20.0)
    if not init_resp:
        sys.stderr.write("[FATAL] No initialize response\n")
        _cleanup(proc)
        sys.exit(1)
    sys.stderr.write(f"  [OK] Initialize: serverInfo={init_resp.get('result', {}).get('serverInfo', {})}\n")
    send_message(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    sys.stderr.write("  [OK] notifications/initialized sent\n")

    # ── 4. Give extra time for slow services ─────────────────────────
    sys.stderr.write("\n[STEP] Waiting 30s for slow services (docker-mcp-gateway)...\n")
    for i in range(30):
        time.sleep(1)
        drain_stderr(proc, echo=True)  # drain stderr every second to prevent pipe blocking
        if i % 10 == 9:
            sys.stderr.write(f"  ... waited {i + 1}s\n")

    # ── PHASE 1: proxy_status ────────────────────────────────────────
    sys.stderr.write(f"\n{'=' * 60}\n[PHASE 1] proxy_status\n{'=' * 60}\n")
    resp = do_call(reader, proc, 10, "proxy_status", {}, timeout=15.0)

    if not resp:
        sys.stderr.write("[FATAL] proxy_status: no response\n")
        _cleanup(proc)
        sys.exit(1)
    if "error" in resp:
        sys.stderr.write(f"[FATAL] proxy_status error: {json.dumps(resp['error'])}\n")
        _cleanup(proc)
        sys.exit(1)

    raw_result = resp.get("result", {})

    # proxy_status 返回 MCP CallToolResult {content: [{type:"text", text:"..."}]}
    # text 中是 _ok() 包装的 JSON：{"status":"ok","data":{"format_version":"2.0","data":{...}}}
    # 因此需要先解 content，再解 _ok 包装，再解 format_version 中的 data
    if isinstance(raw_result, dict) and "content" in raw_result:
        content_list = raw_result["content"]
        if isinstance(content_list, list) and content_list:
            text = content_list[0].get("text", "{}")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = {}
            # 解 _ok() 包装：{"status":"ok","data":{...}}
            payload = parsed.get("data", parsed) if isinstance(parsed, dict) else parsed
            # 解 format_version 层：{"format_version":"2.0","data":{...}}
            if isinstance(payload, dict) and "data" in payload:
                status_data = payload["data"]
            else:
                status_data = payload
        else:
            status_data = raw_result
    else:
        status_data = raw_result

    if isinstance(status_data, dict):
        connected = status_data.get("connected_services", [])
        services_info = status_data.get("services", {})
        total_tools = status_data.get("tools", 0)
    else:
        connected = []
        services_info = {}
        total_tools = 0

    sys.stderr.write(f"  Status: {total_tools} total tools across {len(connected)} services\n")
    for svc_name in sorted(connected):
        info = services_info.get(svc_name, {})
        sys.stderr.write(f"    {svc_name}: connected={info.get('connected', False)}, tools={info.get('tools', '?')}\n")

    all_ok = len(connected) >= 18  # serena may fail occasionally
    sys.stderr.write(f"\n  Total services: {len(connected)}/19 {'[PASS]' if all_ok else '[FAIL]'}\n")

    new_connected = [s for s in NEW_SERVICES if s in connected]
    new_missing = [s for s in NEW_SERVICES if s not in connected]
    if new_missing:
        sys.stderr.write(f"  [PARTIAL] Missing new services: {new_missing}\n")
        for s in new_missing:
            tests_failed += 1
            failures.append(f"{s}: not connected")
    else:
        sys.stderr.write("  [PASS] All 7 new services connected\n")

    # ── PHASE 2: Tool call tests ────────────────────────────────────
    sys.stderr.write(f"\n{'=' * 60}\n[PHASE 2] Tool Call Tests\n{'=' * 60}\n")

    tool_tests = [
        ("docker-mcp-gateway", "fetch", {"url": "https://example.com"}, 60.0),
    ]

    for svc, tool, args, timeout in tool_tests:
        if svc not in connected:
            sys.stderr.write(f"  [SKIP] {svc}.{tool}: service not connected\n")
            continue
        full_tool = f"{svc}.{tool}"
        sys.stderr.write(f"\n[TEST] {full_tool}...\n")
        resp = do_call(
            reader, proc, 100 + tool_tests.index((svc, tool, args, timeout)), full_tool, args, timeout=timeout
        )
        if resp is None:
            sys.stderr.write("  [FAIL] No response (timeout)\n")
            tests_failed += 1
            failures.append(f"{full_tool}: timeout")
        elif "error" in resp:
            err = json.dumps(resp.get("error"))
            sys.stderr.write(f"  [FAIL] Error: {err[:300]}\n")
            tests_failed += 1
            failures.append(f"{full_tool}: {err[:200]}")
        else:
            result = resp.get("result", {})
            sys.stderr.write(f"  [PASS] {json.dumps(result)[:300]}\n")
            tests_passed += 1

    # ── Summary ──
    sys.stderr.write(f"\n{'=' * 60}\n")
    sys.stderr.write("RESULTS:\n")
    sys.stderr.write(f"  New services connected: {len(new_connected)}/7\n")
    sys.stderr.write(f"  Total connected: {len(connected)}/19\n")
    sys.stderr.write(f"  Tool calls: {tests_passed} passed, {tests_failed} failed\n")
    if failures:
        sys.stderr.write("  Notes:\n")
        for f in failures:
            sys.stderr.write(f"    - {f}\n")
    sys.stderr.write(f"{'=' * 60}\n")

    _cleanup(proc)
    sys.exit(0 if tests_failed == 0 else 1)


if __name__ == "__main__":
    main()
