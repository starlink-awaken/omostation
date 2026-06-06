import os
import urllib.parse
from pathlib import Path
from fastmcp import FastMCP

# Define the base workspace and documents paths
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/Users/xiamingxing/Workspace")).resolve()
HOME_DIR = Path.home()
DOCS_ROOT = HOME_DIR / "Documents"

mcp = FastMCP("ecos-bos-mounter", description="BOS Virtual File System Mounter")

@mcp.resource("bos://memory/{path:path}")
def read_memory_resource(path: str) -> str:
    """
    Map bos://memory/* URIs to local documents/workspace files.
    """
    try:
        path = urllib.parse.unquote(path)
        target_path = None
        
        # Routing logic
        if path.startswith("cards/"):
            sub_path = path[len("cards/"):]
            target_path = DOCS_ROOT / "驾驶舱" / "CARDS" / sub_path
        elif path.startswith("learning/"):
            sub_path = path[len("learning/"):]
            target_path = DOCS_ROOT / "学习进化" / sub_path
        elif path.startswith("workspace/"):
            sub_path = path[len("workspace/"):]
            target_path = WORKSPACE_ROOT / sub_path
        else:
            return f"Error: Unknown memory namespace bos://memory/{path}"
            
        target_path = target_path.resolve()
        
        # Security: Prevent path traversal
        if "CARDS" in str(target_path) and not str(target_path).startswith(str(DOCS_ROOT / "驾驶舱" / "CARDS")):
            return "Error: Path traversal detected."
        elif "学习进化" in str(target_path) and not str(target_path).startswith(str(DOCS_ROOT / "学习进化")):
            return "Error: Path traversal detected."
        elif "workspace" in path and not str(target_path).startswith(str(WORKSPACE_ROOT)):
            return "Error: Path traversal detected."

        if not target_path.exists() or not target_path.is_file():
            return f"Error: Resource not found or is a directory at {path}"
            
        with open(target_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading resource: {str(e)}"

@mcp.resource("bos://omo/{path:path}")
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
            
        with open(target_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading OMO resource: {str(e)}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()
