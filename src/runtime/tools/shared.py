import json
import os
import subprocess
import uuid
from pathlib import Path

RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime"))
PROJECT_HOME = Path(__file__).parent.parent.parent.parent
SCRIPTS_DIR = PROJECT_HOME / "scripts"

_TASKOBJECT_LOG = RUNTIME_HOME / "taskobject_envelopes.jsonl"
_STATS: dict[str, int] = {}

# ── Cost tracking ───────────────────────────────────────────────────────────
# Approximate cost per 1K tokens (USD), aligned with omo_cost.py
_MODEL_COST_MAP: dict[str, dict[str, float]] = {
    "deepseek-v4-flash": {"input": 0.0005, "output": 0.002},
    "deepseek-v4": {"input": 0.002, "output": 0.008},
    "gpt-4o": {"input": 0.01, "output": 0.03},
    "gpt-4o-mini": {"input": 0.0015, "output": 0.006},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "ollama": {"input": 0.0, "output": 0.0},
}

# Default model used by executor (see executor/config/config.py)
_DEFAULT_MODEL = "deepseek-v4-flash"


def _estimate_cost(tokens_used: int, model: str = _DEFAULT_MODEL) -> float:
    """Estimate LLM cost from total tokens (conservative: 3:1 input/output split)."""
    rates = _MODEL_COST_MAP.get(model) or _MODEL_COST_MAP[_DEFAULT_MODEL]
    # Conservative estimate: 75% input, 25% output
    input_tokens = int(tokens_used * 0.75)
    output_tokens = tokens_used - input_tokens
    cost = (input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates[
        "output"
    ]
    return round(cost, 6)


def _summarize_executor_costs(log_file: Path | None = None) -> dict:
    """Read executor execution_log.jsonl and return token/cost summary."""
    if log_file is None:
        # Runtime executor log (same dir as this file's grandparent / executor)
        log_file = Path(__file__).parent.parent / "executor" / "execution_log.jsonl"
    if not log_file.exists():
        return {
            "total_calls": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "model": _DEFAULT_MODEL,
        }

    total_calls = 0
    total_tokens = 0
    for line in log_file.read_text().strip().splitlines():
        try:
            entry = json.loads(line)
        except Exception:  # noqa: BLE001, S112  # defensive fallback
            continue
        total_calls += 1
        total_tokens += entry.get("tokens_used", 0)

    cost = _estimate_cost(total_tokens)
    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "estimated_cost_usd": cost,
        "model": _DEFAULT_MODEL,
    }


def _record_taskobject_envelope(tool_name: str, params: dict, status: str) -> None:
    try:
        envelope = {
            "id": str(uuid.uuid4()),
            "intent": "query",
            "context": {
                "source": "runtime-mcp",
                "description": f"Tool call: {tool_name}",
            },
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
    except Exception:  # noqa: BLE001, S110, S112  # defensive fallback
        pass  # noqa: S110, BLE001, S112  # defensive fallback


def _run_script(script_name: str, *args: str) -> str:
    script = SCRIPTS_DIR / script_name
    env = os.environ.copy()
    env["RUNTIME_HOME"] = str(RUNTIME_HOME)
    try:
        r = subprocess.run(
            [str(script), *args],
            capture_output=True,
            text=True,
            timeout=30,
            env=env, check=False)
        return (
            r.stdout.strip()
            if r.returncode == 0
            else (
                f"❌ Error (exit={r.returncode}): {r.stderr.strip() or r.stdout.strip()}"
            )
        )
    except subprocess.TimeoutExpired:
        return "❌ Timeout (30s)"
    except FileNotFoundError:
        return f"❌ Script not found: {script}"
