import json
import subprocess

CODEGRAPH_CMD = ["npx", "-y", "@colbymchenry/codegraph"]


def _run_codegraph(args: list[str], cwd: str) -> str:
    """Run a codegraph command and return its stdout as a string."""
    try:
        cmd = CODEGRAPH_CMD + args
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error running codegraph: {e.stderr}"
    except FileNotFoundError:
        return "Error: npx not found. Ensure Node.js is installed."


def init_codegraph(cwd: str) -> str:
    """Initialize CodeGraph and build the initial index."""
    return _run_codegraph(["init"], cwd)


def sync_codegraph(cwd: str) -> str:
    """Sync changes since last index."""
    return _run_codegraph(["sync"], cwd)


def get_symbol_graph(symbol: str, cwd: str) -> dict:
    """Get callers and callees for a specific symbol."""
    # To keep it simple, we use the CLI instead of SQLite directly
    callers = _run_codegraph(["callers", symbol, "--json"], cwd)
    callees = _run_codegraph(["callees", symbol, "--json"], cwd)

    res = {}
    try:
        res["callers"] = json.loads(callers) if callers.startswith("[") else callers
    except json.JSONDecodeError:
        res["callers"] = callers

    try:
        res["callees"] = json.loads(callees) if callees.startswith("[") else callees
    except json.JSONDecodeError:
        res["callees"] = callees

    return res


def get_impact_radius(symbol: str, cwd: str) -> str:
    """Analyze what code is affected by changing a symbol (Blast Radius)."""
    return _run_codegraph(["impact", symbol], cwd)


def get_affected_tests(files: list[str], cwd: str) -> str:
    """Find test files affected by changed source files."""
    return _run_codegraph(["affected"] + files, cwd)
