import os
import subprocess
import uuid
from pathlib import Path

RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime"))
PROJECT_HOME = Path(__file__).parent.parent.parent.parent
SCRIPTS_DIR = PROJECT_HOME / "scripts"

_TASKOBJECT_LOG = RUNTIME_HOME / "taskobject_envelopes.jsonl"
_STATS: dict[str, int] = {}

def _record_taskobject_envelope(tool_name: str, params: dict, status: str) -> None:
    try:
        envelope = {
            "id": str(uuid.uuid4()),
            "intent": "query",
            "context": {"source": "runtime-mcp", "description": f"Tool call: {tool_name}"},
            "target": {"service": "runtime", "tool": tool_name, "params": params},
            "status": status,
            "callback": {"channel": "stdout", "format": "text"},
            "ttl": 60,
            "priority": 2,
        }
        _TASKOBJECT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_TASKOBJECT_LOG, "a") as f:
            import json
            f.write(json.dumps(envelope) + "\n")
    except Exception:
        pass

def _run_script(script_name: str, *args: str) -> str:
    script = SCRIPTS_DIR / script_name
    env = os.environ.copy()
    env["RUNTIME_HOME"] = str(RUNTIME_HOME)
    try:
        r = subprocess.run(
            [str(script), *args],
            capture_output=True, text=True, timeout=30, env=env,
        )
        return r.stdout.strip() if r.returncode == 0 else (
            f"❌ Error (exit={r.returncode}): {r.stderr.strip() or r.stdout.strip()}")
    except subprocess.TimeoutExpired:
        return "❌ Timeout (30s)"
    except FileNotFoundError:
        return f"❌ Script not found: {script}"
