import os
import urllib.parse
from pathlib import Path
from fastmcp import FastMCP
from pydantic import BaseModel
from ecos.protocol.ssb.ssb_client import SSBClient  # type: ignore[import-not-found]

# Define the base workspace and documents paths
WORKSPACE_ROOT = Path(
    os.environ.get("WORKSPACE_ROOT", "/Users/xiamingxing/Workspace")
).resolve()
HOME_DIR = Path.home()
DOCS_ROOT = HOME_DIR / "Documents"

mcp = FastMCP("ecos-bos-mounter")


@mcp.resource("bos://memory/{path}")
def read_memory_resource(path: str) -> str:
    """
    Map bos://memory/* URIs to local documents/workspace files.
    """
    try:
        path = urllib.parse.unquote(path)
        target_path = None

        # Routing logic
        if path.startswith("cards/"):
            sub_path = path[len("cards/") :]
            target_path = DOCS_ROOT / "驾驶舱" / "CARDS" / sub_path
        elif path.startswith("learning/"):
            sub_path = path[len("learning/") :]
            target_path = DOCS_ROOT / "学习进化" / sub_path
        elif path.startswith("workspace/"):
            sub_path = path[len("workspace/") :]
            target_path = WORKSPACE_ROOT / sub_path
        else:
            return f"Error: Unknown memory namespace bos://memory/{path}"

        target_path = target_path.resolve()

        # Security: Prevent path traversal
        if "CARDS" in str(target_path) and not str(target_path).startswith(
            str(DOCS_ROOT / "驾驶舱" / "CARDS")
        ):
            return "Error: Path traversal detected."
        elif "学习进化" in str(target_path) and not str(target_path).startswith(
            str(DOCS_ROOT / "学习进化")
        ):
            return "Error: Path traversal detected."
        elif "workspace" in path and not str(target_path).startswith(
            str(WORKSPACE_ROOT)
        ):
            return "Error: Path traversal detected."

        if not target_path.exists() or not target_path.is_file():
            return f"Error: Resource not found or is a directory at {path}"

        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading resource: {str(e)}"


class WriteMemoryRequest(BaseModel):
    uri: str
    content: str
    create_dirs: bool = True


@mcp.tool()
async def write_memory_resource(req: WriteMemoryRequest) -> str:
    """
    Write to a bos://memory/* URI.
    Supports bos://memory/cards/*, bos://memory/learning/*, bos://memory/workspace/*
    """
    try:
        if not req.uri.startswith("bos://memory/"):
            return "Error: URI must start with bos://memory/"

        path = req.uri[len("bos://memory/") :]
        path = urllib.parse.unquote(path)
        target_path = None

        # Routing logic
        if path.startswith("cards/"):
            sub_path = path[len("cards/") :]
            target_path = DOCS_ROOT / "驾驶舱" / "CARDS" / sub_path
        elif path.startswith("learning/"):
            sub_path = path[len("learning/") :]
            target_path = DOCS_ROOT / "学习进化" / sub_path
        elif path.startswith("workspace/"):
            sub_path = path[len("workspace/") :]
            target_path = WORKSPACE_ROOT / sub_path
        else:
            return f"Error: Unknown memory namespace bos://memory/{path}"

        target_path = target_path.resolve()

        # Security: Prevent path traversal
        if "CARDS" in str(target_path) and not str(target_path).startswith(
            str(DOCS_ROOT / "驾驶舱" / "CARDS")
        ):
            return "Error: Path traversal detected."
        elif "学习进化" in str(target_path) and not str(target_path).startswith(
            str(DOCS_ROOT / "学习进化")
        ):
            return "Error: Path traversal detected."
        elif "workspace" in path and not str(target_path).startswith(
            str(WORKSPACE_ROOT)
        ):
            return "Error: Path traversal detected."

        if req.create_dirs:
            target_path.parent.mkdir(parents=True, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(req.content)

        return f"Successfully wrote to {req.uri}"
    except Exception as e:
        return f"Error writing resource: {str(e)}"


@mcp.resource("bos://omo/{path}")
def read_omo_resource(path: str) -> str:
    """
    Map bos://omo/* URIs to .omo governance files.
    """
    try:
        path = urllib.parse.unquote(path)
        omo_root = WORKSPACE_ROOT / ".omo"
        target_path = (omo_root / path).resolve()

        if not str(target_path).startswith(str(omo_root)):
            return "Error: Path traversal detected."

        if not target_path.exists() or not target_path.is_file():
            return f"Error: OMO resource not found at {path}"

        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading OMO resource: {str(e)}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()

class SSBLogRequest(BaseModel):
    event_type: str
    agent_name: str
    summary: str
    detail: str = ""

@mcp.tool()
async def append_ssb_log(req: SSBLogRequest) -> str:
    """
    Write a critical event or decision to the L0 ecos SSB Immutable Log.
    Use this for high-level governance, circuit breaking, sandboxing decisions, etc.
    """
    try:
        ssb = SSBClient()
        event = {
            "event": {"type": req.event_type},
            "source": {"agent": req.agent_name, "instance": "mcp-vfs"},
            "payload": {"summary": req.summary, "detail": req.detail}
        }
        event_id = ssb.publish(event)
        return f"Successfully anchored event {event_id} to L0 SSB Log."
    except Exception as e:
        return f"Error appending to SSB log: {str(e)}"
