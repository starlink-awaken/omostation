"""Agent Runtime 工具层 — 路径沙箱 + MCP 调用封装。"""

import ipaddress
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from runtime.executor.config import (
    ALLOWED_PATHS,
    ECOS_DIR,
    ILINK_SEND_URL,
    MCP_ENDPOINTS,
    log,
    sanitize_for_log,
)

# ── Agora degrade state ────────────────────────────────────────────────────
# After 2 consecutive Agora failures, auto-switch to direct MCP mode
# for 5 minutes (300 seconds).
_agora_failure_count = 0
_agora_direct_mode_until = 0.0  # timestamp when direct mode expires
_AGORA_DIRECT_MODE_DURATION = 300  # 5 minutes
_AGORA_MAX_FAILURES = 2


def _check_path_sandbox(path: Path) -> Path:
    """检查路径是否在沙箱白名单内，防止任意文件读写。"""
    p = path.expanduser().resolve()
    allowed = False
    for allowed_dir in ALLOWED_PATHS:
        allowed_dir_resolved = allowed_dir.expanduser().resolve()
        if p == allowed_dir_resolved or allowed_dir_resolved in p.parents:
            allowed = True
            break
    if not allowed:
        allowed_names = [str(d) for d in ALLOWED_PATHS]
        raise PermissionError(f"Access denied: {p} is outside allowed paths ({', '.join(allowed_names)})")
    return p


# ── Agora degrade helpers ─────────────────────────────────────────────────


def _is_agora_direct_mode() -> bool:
    """Check if we are currently in direct MCP mode (bypassing Agora)."""
    global _agora_direct_mode_until
    if time.monotonic() > _agora_direct_mode_until:
        return False
    return True


def _enter_agora_direct_mode():
    """Switch to direct MCP mode for the configured duration."""
    global _agora_failure_count, _agora_direct_mode_until
    _agora_direct_mode_until = time.monotonic() + _AGORA_DIRECT_MODE_DURATION
    log.warning(
        f"⚠️  Agora direct mode activated for {_AGORA_DIRECT_MODE_DURATION}s (until t={_agora_direct_mode_until:.0f})"
    )


def _record_agora_failure():
    """Increment the consecutive Agora failure counter.

    Auto-switches to direct mode when the threshold is reached.
    """
    global _agora_failure_count
    _agora_failure_count += 1
    log.warning(f"  ⚠️  Agora failure #{_agora_failure_count}/{_AGORA_MAX_FAILURES}")
    if _agora_failure_count >= _AGORA_MAX_FAILURES:
        _enter_agora_direct_mode()


def _record_agora_success():
    """Reset the consecutive Agora failure counter on success."""
    global _agora_failure_count
    if _agora_failure_count > 0:
        _agora_failure_count = 0
        log.info("  ✅ Agora recovered — failure counter reset")


def _direct_mcp_call(server: str, tool_name: str, args: dict) -> dict:
    """Call an MCP tool directly, bypassing Agora.

    Uses the hardcoded MCP_ENDPOINTS from config.py for direct access to
    kos/minerva/agora services.
    """
    base = MCP_ENDPOINTS.get(server)
    if not base:
        return {"error": f"Unknown MCP server (direct): {server}"}

    payload = json.dumps({"name": tool_name, "arguments": args}).encode()
    req = urllib.request.Request(  # noqa: S310
        f"{base}/tools/call",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            data = json.loads(resp.read())
        result = data.get("result", {})
        content = result.get("content", [])
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return {"content": "\n".join(texts), "raw": result, "direct": True}
    except Exception as e:
        return {"error": f"Direct MCP call failed: {e}", "direct": True}


def reset_agora_degrade_state():
    """Reset the Agora degrade state (for testing / recovery)."""
    global _agora_failure_count, _agora_direct_mode_until
    _agora_failure_count = 0
    _agora_direct_mode_until = 0.0
    log.info("  🔄 Agora degrade state reset")


def _is_safe_url(url: str) -> bool:
    """检查 URL 是否安全，阻止 SSRF 攻击。

    阻止对内网/私有地址、localhost 的请求。
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
    except Exception:
        return False

    # 禁止 localhost / 0.0.0.0
    if hostname in ("localhost", "0.0.0.0", "127.0.0.1", "127.1", "::1"):  # noqa: S104
        log.warning(f"  ⛔ SSRF blocked: localhost URL {url}")
        return False

    # 禁止纯 IP 格式的 localhost
    if hostname.startswith("127."):
        log.warning(f"  ⛔ SSRF blocked: loopback URL {url}")
        return False

    # 解析并检查私有 IP
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            log.warning(f"  ⛔ SSRF blocked: private/internal IP URL {url}")
            return False
    except ValueError:
        # 不是 IP 地址（域名），放行
        pass

    return True


class Tools:
    """Agent Runtime 可用的工具集合。所有文件操作受路径沙箱约束。"""

    @staticmethod
    def terminal_run(command: str, cwd: str | None = None, timeout: int = 120, _confirmed: bool = False) -> dict:
        """执行终端命令。返回 {exit_code, stdout, stderr}

        L2 操作: 需要 _confirmed=True 才能执行。
        使用 shlex.split 解析命令参数，避免 shell 注入。
        """
        # L2 确认检查
        if not _confirmed:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "L2 operation 'terminal_run' requires explicit confirmation. Re-run with `_confirmed: true`.",
                "operation_level": "L2",
                "status": "denied",
            }
        log.info(f"  🔧 terminal_run: {sanitize_for_log(command, 100)}")
        try:
            # 使用 shlex.split 而不是 shell=True / sh -c，防止注入
            import shlex

            args = shlex.split(command)
            r = subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=cwd or str(ECOS_DIR),
                timeout=timeout,
            )
            return {"exit_code": r.returncode, "stdout": r.stdout[:5000], "stderr": r.stderr[:2000]}
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": f"Timed out after {timeout}s"}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}

    @staticmethod
    def file_read(path: str) -> dict:
        """读取文件内容（受路径沙箱限制）。"""
        try:
            p = _check_path_sandbox(Path(path))
            if not p.exists():
                return {"error": f"File not found: {path}"}
            return {"content": p.read_text(encoding="utf-8")[:10000]}
        except PermissionError as e:
            log.warning(f"  ⛔ file_read blocked: {e}")
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def file_write(path: str, content: str) -> dict:
        """写入文件（受路径沙箱限制）。"""
        try:
            p = _check_path_sandbox(Path(path))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {"success": True, "path": str(p)}
        except PermissionError as e:
            log.warning(f"  ⛔ file_write blocked: {e}")
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def sqlite_query(db_path: str, query: str) -> dict:
        """执行 SQLite 查询（受路径沙箱限制）。"""
        import sqlite3

        try:
            p = _check_path_sandbox(Path(db_path))
            if not p.exists():
                return {"error": f"DB not found: {db_path}"}
            conn = sqlite3.connect(str(p))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
            conn.close()
            result = [dict(r) for r in rows]
            return {"rows": result, "count": len(result)}
        except PermissionError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def mcp_call(server: str, tool_name: str, args: dict | None = None) -> dict:
        """调用 MCP 工具的 HTTP 端点，带 Agora 降级回退。

        正常路径：通过 Agora 路由调用。
        降级路径：Agora 不可用时，直连 MCP 端点（HARDCODED in config.py）。
        自动降级：连续 2 次 Agora 失败后，自动切换直连模式 5 分钟。
        """
        # ── Check if we're in direct mode ──────────────────────────────
        if _is_agora_direct_mode():
            log.info(f"  🔧 mcp_call (direct mode): {server}.{tool_name}")
            return _direct_mcp_call(server, tool_name, args or {})

        # ── Normal path: route through Agora ───────────────────────────
        base = MCP_ENDPOINTS.get("agora")
        if not base:
            # No Agora configured at all — go direct immediately
            log.info(f"  🔧 mcp_call (no Agora configured): {server}.{tool_name}")
            return _direct_mcp_call(server, tool_name, args or {})

        payload = json.dumps(
            {
                "name": tool_name,
                "server": server,
                "arguments": args or {},
            }
        ).encode()
        req = urllib.request.Request(  # noqa: S310
            f"{base}/tools/call",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                data = json.loads(resp.read())
            result = data.get("result", {})
            content = result.get("content", [])
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            _record_agora_success()
            return {"content": "\n".join(texts), "raw": result}
        except Exception as e:
            log.warning(f"  ⚠️  Agora MCP call failed for {server}.{tool_name}: {e}")
            _record_agora_failure()
            # Fallback: try direct MCP endpoint for this server
            log.info(f"  🔧 mcp_call (Agora fallback): {server}.{tool_name}")
            return _direct_mcp_call(server, tool_name, args or {})

    @staticmethod
    def http_get(url: str, timeout: int = 30) -> dict:
        """HTTP GET 请求。"""
        if not _is_safe_url(url):
            return {"error": f"URL rejected: {url} (blocked by SSRF protection)"}
        import urllib.request

        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")[:5000]
                return {"status": resp.status, "body": body}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def http_post(url: str, data: dict | None = None, timeout: int = 30) -> dict:
        """HTTP POST 请求。"""
        if not _is_safe_url(url):
            return {"error": f"URL rejected: {url} (blocked by SSRF protection)"}
        payload = json.dumps(data or {}).encode()
        try:
            req = urllib.request.Request(  # noqa: S310
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                body = resp.read().decode("utf-8")[:5000]
                return {"status": resp.status, "body": body}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def send_message(platform: str = "weixin", text: str = "") -> dict:
        """通过 iLink 发送消息到用户。"""
        if not text:
            return {"error": "text is required"}
        receiver = os.environ.get(
            "ILINK_RECEIVER",
            "o9cq800tslBgu_e2s6YBCvkmHc2U@im.wechat",
        )
        payload = json.dumps(
            {
                "platform": platform,
                "receiver": receiver,
                "content": text,
            }
        ).encode()
        try:
            req = urllib.request.Request(  # noqa: S310
                ILINK_SEND_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = resp.read().decode()[:500]
            return {"status": resp.status, "body": body}
        except Exception as e:
            return {"error": str(e)}

    def build_tool_registry(self) -> dict:
        """构建 LLM 可用的工具注册表。"""
        return {
            "terminal_run": {
                "fn": self.terminal_run,
                "description": "Execute a shell command (L2 — requires _confirmed=true). ALL file paths with ~/ must be expanded to absolute path first.",
                "params": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run. Expand ~/ to full path.",
                        "required": True,
                    },
                    "cwd": {"type": "string", "description": "Working directory (optional)"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds"},
                    "_confirmed": {
                        "type": "boolean",
                        "description": "Must be true for L2 operations",
                        "required": False,
                    },
                },
            },
            "file_read": {
                "fn": self.file_read,
                "description": "Read a file from disk (sandboxed to Workspace/.hermes/.kos/.omo)",
                "params": {"path": {"type": "string", "description": "File path (use full path)", "required": True}},
            },
            "file_write": {
                "fn": self.file_write,
                "description": "Write content to a file (sandboxed to Workspace/.hermes/.kos/.omo)",
                "params": {
                    "path": {"type": "string", "required": True},
                    "content": {"type": "string", "required": True},
                },
            },
            "sqlite_query": {
                "fn": self.sqlite_query,
                "description": "Query a SQLite database (sandboxed)",
                "params": {
                    "db_path": {"type": "string", "required": True},
                    "query": {"type": "string", "required": True},
                },
            },
            "mcp_kos_run_indexer": {
                "fn": lambda **kw: self.mcp_call("kos", "run_indexer", kw),
                "description": "Run KOS incremental indexer",
                "params": {"incremental": {"type": "boolean"}},
            },
            "mcp_kos_get_system_status": {
                "fn": lambda **kw: self.mcp_call("kos", "get_system_status", kw),
                "description": "Get KOS system health",
                "params": {},
            },
            "mcp_kos_research_now": {
                "fn": lambda **kw: self.mcp_call("kos", "research_now", kw),
                "description": "Execute deep research via KOS/Minerva",
                "params": {"query": {"type": "string", "required": True}, "level": {"type": "string"}},
            },
            "http_get": {
                "fn": self.http_get,
                "description": "HTTP GET request",
                "params": {"url": {"type": "string", "required": True}},
            },
            "http_post": {
                "fn": self.http_post,
                "description": "HTTP POST request",
                "params": {"url": {"type": "string", "required": True}, "data": {"type": "object"}},
            },
            "send_message": {
                "fn": self.send_message,
                "description": "Send a message to the user via WeChat",
                "params": {"text": {"type": "string", "required": True}, "platform": {"type": "string"}},
            },
        }

    def build_tool_schemas(self) -> list[dict[str, Any]]:
        """构建 OpenAI 格式的 tool schemas。"""
        registry = self.build_tool_registry()
        schemas: list[dict[str, Any]] = []
        for name, info in registry.items():
            props = {}
            required_params = []
            for pname, pinfo in info.get("params", {}).items():
                ptype = pinfo.get("type", "string")
                props[pname] = {"type": ptype, "description": pinfo.get("description", "")}
                if pinfo.get("required"):
                    required_params.append(pname)
                if ptype == "object":
                    props[pname]["properties"] = {}
            parameters: dict[str, Any] = {"type": "object", "properties": props}
            if required_params:
                parameters["required"] = required_params
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": parameters,
                },
            }
            schemas.append(schema)
        return schemas
