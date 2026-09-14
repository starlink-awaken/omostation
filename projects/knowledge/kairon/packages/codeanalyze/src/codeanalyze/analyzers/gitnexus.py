"""GitNexus 分析器 — 依赖图与调用链"""

import subprocess
from pathlib import Path

from codeanalyze.core.registry import ToolInfo  # type: ignore[import-not-found]


def gitnexus_available() -> bool:
    try:
        import shutil

        return shutil.which("gitnexus") is not None
    except Exception:
        return False


def analyze(repo_path: str = ".", tool: ToolInfo | None = None) -> dict:
    """运行 gitnexus analyze，返回索引状态。"""
    if tool and not tool.available:
        return {"error": "gitnexus not installed", "status": "unavailable"}
    if not gitnexus_available():
        return {"error": "gitnexus CLI not found on PATH", "status": "unavailable"}

    try:
        result = subprocess.run(
            ["gitnexus", "analyze", repo_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "status": "ok" if result.returncode == 0 else "failed",
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "gitnexus analyze timed out (300s)", "status": "timeout"}
    except FileNotFoundError:
        return {"error": "gitnexus CLI not found", "status": "unavailable"}
    except Exception as e:
        return {"error": str(e), "status": "error"}


def status(repo_path: str = ".") -> dict:
    """查询 GitNexus 索引状态。"""
    if not gitnexus_available():
        return {"status": "unavailable"}
    try:
        result = subprocess.run(
            ["gitnexus", "status"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=repo_path,
        )
        return {
            "status": "indexed" if result.returncode == 0 else "not_indexed",
            "message": (result.stdout or result.stderr).strip()[:500],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def has_index(repo_path: str = ".") -> bool:
    return (Path(repo_path).resolve() / ".gitnexus").exists()


def serve_mcp() -> dict:
    """启动 GitNexus MCP server（stdio 模式，用于开发调试）。"""
    if not gitnexus_available():
        return {"error": "gitnexus not installed"}
    try:
        result = subprocess.run(
            ["gitnexus", "setup"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "status": "ok" if result.returncode == 0 else "failed",
            "message": (result.stdout or result.stderr).strip()[:1000],
        }
    except Exception as e:
        return {"error": str(e)}
