from fastmcp import FastMCP
from pathlib import Path
from .bridge import _import_pitch
from .strategy import strategy_audit, strategy_gc

# Create the MCP server for C2G
mcp = FastMCP("c2g")

@mcp.tool()
def c2g_bet(source_file: str, adapter: str = "ecos") -> str:
    """
    Convert a Pitch Markdown file into a tracked Bet and Task.
    
    Args:
        source_file: Absolute path to the Pitch markdown file.
        adapter: Which adapter to use ('ecos' or 'local'). Default is 'ecos'.
    """
    path = Path(source_file)
    if not path.exists():
        return f"Error: Pitch file {source_file} not found."
    
    base_dir = path.parent
    if adapter == "ecos":
        # Attempt to find the .omo directory root by traversing up
        current = path
        while current != current.parent:
            if (current / ".omo").exists():
                base_dir = current / ".omo"
                break
            current = current.parent
            
    try:
        _import_pitch(path, base_dir, adapter)
        return f"Successfully processed pitch: {source_file} using {adapter} adapter."
    except Exception as e:
        return f"Error processing pitch: {str(e)}"

@mcp.tool()
def c2g_radar(workspace_root: str, adapter: str = "ecos") -> str:
    """
    Audit the current strategic alignment vectors (Radar).
    
    Args:
        workspace_root: Path to the workspace root or storage directory.
        adapter: Which adapter to use ('ecos' or 'local').
    """
    import io
    import sys
    
    base_dir = Path(workspace_root)
    if adapter == "ecos" and (base_dir / ".omo").exists():
        base_dir = base_dir / ".omo"

    # Capture stdout since strategy_audit prints directly
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    try:
        strategy_audit(base_dir, adapter)
    except Exception as e:
        sys.stdout = old_stdout
        return f"Error running radar: {str(e)}"
    finally:
        sys.stdout = old_stdout
        
    return new_stdout.getvalue()

@mcp.tool()
def c2g_gc(workspace_root: str, adapter: str = "ecos") -> str:
    """
    Run Garbage Collection to clear out decayed Sandbox pitches.
    
    Args:
        workspace_root: Path to the workspace root or storage directory.
        adapter: Which adapter to use ('ecos' or 'local').
    """
    import io
    import sys
    
    base_dir = Path(workspace_root)
    if adapter == "ecos" and (base_dir / ".omo").exists():
        base_dir = base_dir / ".omo"

    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    try:
        strategy_gc(base_dir, adapter)
    except Exception as e:
        sys.stdout = old_stdout
        return f"Error running GC: {str(e)}"
    finally:
        sys.stdout = old_stdout
        
    return new_stdout.getvalue()

if __name__ == "__main__":
    mcp.run()
