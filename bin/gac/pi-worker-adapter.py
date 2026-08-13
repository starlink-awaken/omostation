"""Run Pi as a bounded, no-tools local reasoning worker via AetherForge."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PI_EXECUTABLE = "/opt/homebrew/bin/pi"
HEALTH_URL = "http://127.0.0.1:9290/health"
ROUTE_REF = "bos://compute/aetherforge/infer"
PROVIDER = "omlxc"
MODEL = "coding"
MAX_TIMEOUT_SECONDS = 120
SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
USER_CONFIG_NAMES = ("models.json", "settings.json", "auth.json", "trust.json")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


class AdapterError(RuntimeError):
    """A stable failure code for the bounded worker contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def fixed_argv(prompt: str) -> list[str]:
    """Return the only command shape the admitted L0 worker may execute."""
    return [
        PI_EXECUTABLE,
        "--print",
        "--mode",
        "text",
        "--no-session",
        "--no-tools",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--no-approve",
        "--offline",
        "--provider",
        PROVIDER,
        "--model",
        MODEL,
        prompt,
    ]


def _system_temp_roots() -> tuple[Path, ...]:
    return tuple(dict.fromkeys(path.resolve() for path in (Path(tempfile.gettempdir()), Path("/tmp"), Path("/private/tmp"))))


def validate_receipt_path(receipt_path: Path | str, *, user_home: Path) -> Path:
    receipt = Path(receipt_path).expanduser().resolve()
    if receipt.exists() or not receipt.parent.is_dir() or _is_within(receipt, user_home.resolve()):
        raise AdapterError("unsafe_receipt")
    if not any(_is_within(receipt, root) for root in _system_temp_roots()):
        raise AdapterError("unsafe_receipt")
    return receipt


def _user_config_digests(user_home: Path) -> dict[str, str]:
    config_dir = user_home / ".pi" / "agent"
    result: dict[str, str] = {}
    for name in USER_CONFIG_NAMES:
        path = config_dir / name
        result[name] = digest_bytes(path.read_bytes()) if path.is_file() else "missing"
    return result


def _copy_omlxc_provider(user_home: Path, agent_dir: Path) -> None:
    source = user_home / ".pi" / "agent" / "models.json"
    try:
        source_data = json.loads(source.read_text(encoding="utf-8"))
        provider = source_data["providers"][PROVIDER]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AdapterError("models_config_rejected") from exc
    if not _is_audited_omlxc_provider(provider):
        raise AdapterError("models_config_rejected")
    agent_dir.mkdir(mode=0o700)
    models = agent_dir / "models.json"
    models.write_text(json.dumps({"providers": {PROVIDER: provider}}, separators=(",", ":")), encoding="utf-8")
    models.chmod(0o600)
    auth = agent_dir / "auth.json"
    auth.write_text("{}", encoding="utf-8")
    auth.chmod(0o600)


def _is_audited_omlxc_provider(provider: object) -> bool:
    """Allow only the local AetherForge provider and one non-shell Keychain form."""
    if not isinstance(provider, dict):
        return False
    if provider.get("baseUrl") != "http://127.0.0.1:9290/v1":
        return False
    if provider.get("api") != "openai-completions" or provider.get("authHeader") is not True:
        return False
    models = provider.get("models")
    if not isinstance(models, list) or not any(isinstance(model, dict) and model.get("id") == MODEL for model in models):
        return False
    api_key = provider.get("apiKey")
    if not isinstance(api_key, str) or not api_key.startswith("!"):
        return False
    try:
        keychain_argv = shlex.split(api_key[1:])
    except ValueError:
        return False
    return (
        len(keychain_argv) == 5
        and keychain_argv[0] in {"security", "/usr/bin/security"}
        and keychain_argv[1] == "find-generic-password"
        and keychain_argv[2] == "-s"
        and bool(re.fullmatch(r"[A-Za-z0-9_.-]+", keychain_argv[3]))
        and keychain_argv[4] == "-w"
    )


def _trial_tree_digest(trial_dir: Path) -> str:
    entries: list[tuple[str, str]] = []
    for path in sorted(trial_dir.rglob("*")):
        if path.is_file():
            entries.append((str(path.relative_to(trial_dir)), digest_bytes(path.read_bytes())))
        elif path.is_symlink():
            entries.append((str(path.relative_to(trial_dir)), "symlink:" + os.readlink(path)))
    return digest_bytes(json.dumps(entries, separators=(",", ":")).encode("utf-8"))


def _minimal_environment(user_home: Path, trial_dir: Path, marker: str) -> dict[str, str]:
    locale = os.environ.get("LC_ALL") or os.environ.get("LANG") or "C.UTF-8"
    agent_dir = trial_dir / "agent"
    session_dir = trial_dir / "sessions"
    session_dir.mkdir(mode=0o700)
    return {
        "HOME": str(user_home),
        "LANG": locale,
        "PATH": SAFE_PATH,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "PI_CODING_AGENT_SESSION_DIR": str(session_dir),
        "OMO_PI_TRIAL_ID": marker.removeprefix("OMO_PI_TRIAL_ID="),
        "TMPDIR": str(trial_dir),
    }


def _default_health_probe() -> dict[str, Any] | None:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(HEALTH_URL, timeout=2) as response:
            if response.status != 200:
                return None
            decoded = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _health_is_expected(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and payload.get("status") == "ok" and payload.get("service") == "aetherforge-openai-proxy"


def _default_marker_probe(marker: str) -> dict[int, int]:
    try:
        completed = subprocess.run(
            ["/bin/ps", "eww", "-axo", "pid=,pgid=,command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {0: 0}
    token = re.compile(rf"(?<!\S){re.escape(marker)}(?!\S)")
    found: dict[int, int] = {}
    for line in completed.stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() and token.search(parts[2]):
            found[int(parts[0])] = int(parts[1])
    return found


def _default_group_terminator(group_id: int, value: signal.Signals) -> None:
    try:
        os.killpg(group_id, value)
    except ProcessLookupError:
        return


def _reap(
    process: Any,
    *,
    marker: str,
    timeout_seconds: float,
    marker_probe: Callable[[str], dict[int, int]] = _default_marker_probe,
    group_terminator: Callable[[int, signal.Signals], None] = _default_group_terminator,
) -> bool:
    """Terminate root and marker-bearing descendants, then prove the marker disappeared."""
    groups = {process.pid}
    groups.update(marker_probe(marker).values())
    if process.poll() is None:
        for group in sorted(groups):
            group_terminator(group, signal.SIGTERM)
        try:
            process.wait(timeout=min(timeout_seconds, 2))
        except subprocess.TimeoutExpired:
            for group in sorted(groups):
                group_terminator(group, signal.SIGKILL)
            try:
                process.wait(timeout=min(timeout_seconds, 2))
            except subprocess.TimeoutExpired:
                return False
    leaked = marker_probe(marker)
    if leaked:
        for group in sorted(set(leaked.values())):
            group_terminator(group, signal.SIGTERM)
        time.sleep(0.05)
        leaked = marker_probe(marker)
        if leaked:
            for group in sorted(set(leaked.values())):
                group_terminator(group, signal.SIGKILL)
            time.sleep(0.05)
    return not marker_probe(marker)


def _default_version_reader() -> str:
    try:
        completed = subprocess.run(
            [PI_EXECUTABLE, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env={"HOME": str(Path.home()), "LANG": "C.UTF-8", "PATH": SAFE_PATH},
        )
    except OSError as exc:
        raise AdapterError("version_unavailable") from exc
    version = completed.stdout.strip()
    if completed.returncode != 0 or not VERSION_RE.fullmatch(version):
        raise AdapterError("version_unavailable")
    return version


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def run_worker(
    *,
    prompt: str,
    execute: bool,
    receipt_path: Path | str | None = None,
    timeout_seconds: int = 120,
    expect_exact: str | None = None,
    user_home: Path | str | None = None,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    health_probe: Callable[[], dict[str, Any] | None] = _default_health_probe,
    marker_probe: Callable[[str], dict[int, int]] = _default_marker_probe,
    group_terminator: Callable[[int, signal.Signals], None] = _default_group_terminator,
    version_reader: Callable[[], str] = _default_version_reader,
) -> dict[str, Any]:
    """Execute one bounded worker call; returned model text is intentionally not receipt data."""
    if not execute:
        return {"command": fixed_argv(prompt), "mode": "dry-run", "tools_enabled": False}
    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise AdapterError("timeout_rejected")
    home = (Path.home() if user_home is None else Path(user_home).expanduser()).resolve()
    receipt_file = validate_receipt_path(receipt_path, user_home=home) if receipt_path is not None else None
    marker = f"OMO_PI_TRIAL_ID={uuid.uuid4()}"
    started_at = _utc_now()
    started = time.monotonic()
    before_config = _user_config_digests(home)
    receipt: dict[str, Any] = {
        "checks": {
            "aetherforge_health": False,
            "child_reaped": False,
            "session_persisted": False,
            "temp_removed": False,
            "temp_cwd_unchanged": False,
            "tools_enabled": False,
            "user_config_unchanged": False,
        },
        "model": MODEL,
        "outcome": "failed",
        "provider": PROVIDER,
        "route_ref": ROUTE_REF,
        "schema_version": 1,
        "started_at": started_at,
        "worker": "pi",
    }
    process: Any | None = None
    trial_dir: Path | None = None
    error_code: str | None = None
    output = ""
    try:
        receipt["pi_version"] = version_reader()
        if not _health_is_expected(health_probe()):
            raise AdapterError("health_rejected")
        receipt["checks"]["aetherforge_health"] = True
        trial_dir = Path(tempfile.mkdtemp(prefix="omo-pi-trial-"))
        agent_dir = trial_dir / "agent"
        _copy_omlxc_provider(home, agent_dir)
        environment = _minimal_environment(home, trial_dir, marker)
        before_trial = _trial_tree_digest(trial_dir)
        try:
            process = popen_factory(
                fixed_argv(prompt),
                cwd=str(trial_dir),
                env=environment,
                shell=False,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise AdapterError("launch_failed") from exc
        try:
            output, _stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            raise AdapterError("timed_out")
        if process.returncode != 0:
            raise AdapterError("nonzero_exit")
        if not output.strip():
            raise AdapterError("empty_output")
        if expect_exact is not None and output.strip() != expect_exact:
            raise AdapterError("output_mismatch")
        if before_config != _user_config_digests(home):
            raise AdapterError("config_drift")
        receipt["checks"]["user_config_unchanged"] = True
        receipt["checks"]["temp_cwd_unchanged"] = before_trial == _trial_tree_digest(trial_dir)
        if not receipt["checks"]["temp_cwd_unchanged"]:
            raise AdapterError("temp_write_detected")
        receipt["output_bytes"] = len(output.encode("utf-8"))
        receipt["output_digest"] = digest_bytes(output.encode("utf-8"))
    except AdapterError as exc:
        error_code = exc.code
    except Exception:  # noqa: BLE001 - retain no dependency text or secrets
        error_code = "adapter_failed"
    finally:
        if process is not None:
            receipt["checks"]["child_reaped"] = _reap(
                process,
                marker=marker,
                timeout_seconds=timeout_seconds,
                marker_probe=marker_probe,
                group_terminator=group_terminator,
            )
            if not receipt["checks"]["child_reaped"] and error_code is None:
                error_code = "process_leaked"
        else:
            receipt["checks"]["child_reaped"] = not marker_probe(marker)
        if before_config != _user_config_digests(home) and error_code is None:
            error_code = "config_drift"
        if trial_dir is not None:
            try:
                shutil.rmtree(trial_dir)
            except OSError:
                pass
            receipt["checks"]["temp_removed"] = not trial_dir.exists()
            if not receipt["checks"]["temp_removed"]:
                error_code = "cleanup_unconfirmed"
        else:
            receipt["checks"]["temp_removed"] = True
        if error_code is None:
            receipt["outcome"] = "succeeded"
        else:
            receipt["error_code"] = error_code
        receipt["completed_at"] = _utc_now()
        receipt["duration_seconds"] = round(max(0.0, time.monotonic() - started), 3)
        if receipt_file is not None:
            try:
                _write_receipt(receipt_file, receipt)
            except OSError:
                error_code = "receipt_write_failed"
    if error_code is not None:
        raise AdapterError(error_code)
    return {"output": output, "receipt": receipt if receipt_file is not None else None}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    run = command.add_parser("run", help="dry-run by default; --execute performs one bounded call")
    run.add_argument("--prompt", required=True)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--receipt")
    run.add_argument("--timeout-seconds", type=int, default=120)
    run.add_argument("--expect-exact")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_worker(
            prompt=args.prompt,
            execute=args.execute,
            receipt_path=args.receipt,
            timeout_seconds=args.timeout_seconds,
            expect_exact=args.expect_exact,
        )
    except AdapterError as exc:
        print(json.dumps({"error_code": exc.code, "outcome": "failed"}, separators=(",", ":")), file=sys.stderr)
        return 2
    if args.execute:
        sys.stdout.write(result["output"])
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
