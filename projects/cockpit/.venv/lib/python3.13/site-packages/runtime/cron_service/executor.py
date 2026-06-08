"""Script executor — runs cron job scripts in subprocess.

Supports:
  - .sh → bash
  - .py / no-ext → python3
  - Timeout per job
  - Workdir support
  - Environment variable injection
"""

import logging
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────


def _resolve_script(path_str: str | None) -> Path | None:
    """Resolve script path. Accepts relative (→ ~/.hermes/scripts/) or absolute."""
    if not path_str or not path_str.strip():
        return None
    raw = Path(path_str.strip()).expanduser()
    if raw.is_absolute():
        if raw.exists():
            return raw.resolve()
        return None

    # relative → check ~/.hermes/scripts/
    hermes_scripts = Path.home() / ".hermes" / "scripts"
    candidate = (hermes_scripts / str(raw)).resolve()
    if candidate.exists():
        return candidate

    # also check the script directly as-is
    if raw.exists():
        return raw.resolve()

    return None


def _get_interpreter(script_path: Path) -> str:
    """Choose interpreter based on extension."""
    ext = script_path.suffix
    if ext in (".sh", ".bash"):
        return "/bin/bash"
    # .py or no extension → Python
    shebang = _read_shebang(script_path)
    if shebang and "python" in shebang.lower():
        return sys.executable
    if ext == ".py" or not ext:
        return sys.executable
    return "/bin/bash"


def _read_shebang(path: Path) -> str | None:
    try:
        with open(path) as f:
            first = f.readline().strip()
        return first
    except Exception:
        return None


# ── Executor ───────────────────────────────────────────────────────


class ExecutionResult:
    """Result of a script execution."""

    def __init__(self, success: bool, output: str, error: str = "", timed_out: bool = False):
        self.success = success
        self.output = output
        self.error = error
        self.timed_out = timed_out


class Executor:
    """Compatibility wrapper around module-level execute()."""

    def execute(
        self, script_path_str: str | None, timeout: int = 120, workdir: str | None = None, env: dict | None = None
    ) -> ExecutionResult:
        return execute(script_path_str, timeout=timeout, workdir=workdir, env=env)


def execute_script(
    script_path_str: str | None, timeout: int = 120, workdir: str | None = None, env: dict | None = None
) -> ExecutionResult:
    return execute(script_path_str, timeout=timeout, workdir=workdir, env=env)


def execute(
    script_path_str: str | None, timeout: int = 120, workdir: str | None = None, env: dict | None = None
) -> ExecutionResult:
    """Run a script and return the result.

    Handles:
      - Script resolution (relative → ~/.hermes/scripts/)
      - Interpreter selection
      - Timeout with process kill
      - Working directory change
    """
    script_path = _resolve_script(script_path_str)
    if script_path is None:
        return ExecutionResult(
            False, "", f"Script not found: {script_path_str!r} (resolved under {Path.home() / '.hermes' / 'scripts'})"
        )

    interpreter = _get_interpreter(script_path)
    cmd = [interpreter, str(script_path)]

    # Build environment
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    # Apply workdir
    cwd = None
    prior_cwd = None
    if workdir:
        wd = Path(workdir).expanduser()
        if wd.is_dir():
            cwd = str(wd)
            prior_cwd = os.getcwd()
        else:
            logger.warning("Workdir %s does not exist, ignoring", workdir)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=run_env,
            text=True,
        )

        # Timeout handling
        timer = threading.Timer(timeout, _kill_process, [proc])
        timer.daemon = True
        timer.start()

        stdout, stderr = proc.communicate()
        timer.cancel()

        exit_code = proc.returncode
        if exit_code == -signal.SIGTERM or exit_code == -signal.SIGKILL:
            return ExecutionResult(False, "", "Script timed out", timed_out=True)

        success = exit_code == 0
        return ExecutionResult(success, stdout, stderr)

    except FileNotFoundError as e:
        return ExecutionResult(False, "", f"Interpreter not found: {interpreter} — {e}")
    except Exception as e:
        return ExecutionResult(False, "", str(e))

    finally:
        if prior_cwd is not None:
            try:
                os.chdir(prior_cwd)
            except OSError:
                pass


def _kill_process(proc: subprocess.Popen):
    """Force-kill the process group."""
    try:
        if proc.poll() is None:
            if hasattr(os, "killpg"):
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            else:
                proc.kill()
    except Exception:
        pass
