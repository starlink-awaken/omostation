"""Run Oh My Pi as a bounded, no-tools local worker via AetherForge."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import stat
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

try:
    import yaml as _yaml
except ImportError:  # pragma: no cover - exercised by deployment dependency check
    _yaml = None

OMP_EXECUTABLE = str(Path.home() / ".bun" / "bin" / "omp")
EXPECTED_OMP_VERSION = "16.1.16"
EXPECTED_OMP_SHA256 = "0b690fc3cbf940aa86723f029c0206ddfba152dfa6aa180b891b8923c35f5c96"
HEALTH_URL = "http://127.0.0.1:9290/health"
ROUTE_REF = "bos://compute/aetherforge/infer"
PROVIDER = "omlxc"
MODEL = "coding"
MODEL_REF = f"{PROVIDER}/{MODEL}"
MAX_TIMEOUT_SECONDS = 120
SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
KEYCHAIN_REFERENCE = "!security find-generic-password -s aetherforge-gateway -w"
AETHERFORGE_ENV_IDENTITY = "AETHERFORGE_API_KEY"


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


def fixed_argv(prompt: str, *, timeout_seconds: int = 120) -> list[str]:
    """Return the only command shape the admitted OMP worker may execute."""
    return [
        OMP_EXECUTABLE,
        "--print",
        "--mode",
        "text",
        "--no-session",
        "--no-tools",
        "--no-lsp",
        "--no-pty",
        "--no-extensions",
        "--no-skills",
        "--no-rules",
        "--no-title",
        "--approval-mode",
        "always-ask",
        "--model",
        MODEL_REF,
        "--max-time",
        str(timeout_seconds),
        prompt,
    ]


def _system_temp_roots() -> tuple[Path, ...]:
    return tuple(
        dict.fromkeys(
            path.resolve()
            for path in (
                Path(tempfile.gettempdir()),
                Path("/tmp"),
                Path("/private/tmp"),
            )
        )
    )


def validate_receipt_path(receipt_path: Path | str, *, user_home: Path) -> Path:
    receipt = Path(receipt_path).expanduser().resolve()
    if (
        receipt.exists()
        or not receipt.parent.is_dir()
        or _is_within(receipt, user_home.resolve())
    ):
        raise AdapterError("unsafe_receipt")
    if not any(_is_within(receipt, root) for root in _system_temp_roots()):
        raise AdapterError("unsafe_receipt")
    return receipt


def validate_config_root(user_home: Path) -> Path:
    """Require OMP's user configuration root to be a real directory."""
    config_root = user_home / ".omp" / "agent"
    try:
        mode = os.lstat(config_root).st_mode
    except OSError as exc:
        raise AdapterError("config_root_rejected") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise AdapterError("config_root_rejected")
    return config_root


def _safe_keychain_reference(value: object) -> bool:
    return value == KEYCHAIN_REFERENCE


def _safe_credential_identity(value: object) -> bool:
    return value == AETHERFORGE_ENV_IDENTITY or _safe_keychain_reference(value)


def _resolve_keychain_api_key(reference: str) -> str:
    if not _safe_credential_identity(reference):
        raise AdapterError("models_config_rejected")
    if reference == AETHERFORGE_ENV_IDENTITY:
        api_key = os.environ.get(AETHERFORGE_ENV_IDENTITY, "")
        if api_key.strip():
            if len(api_key) > 4096 or "\x00" in api_key:
                raise AdapterError("credential_unavailable")
            return api_key
        reference = KEYCHAIN_REFERENCE
    argv = shlex.split(reference[1:])
    argv[0] = "/usr/bin/security"
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
            env={"HOME": str(Path.home()), "LANG": "C.UTF-8", "PATH": SAFE_PATH},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AdapterError("credential_unavailable") from exc
    api_key = completed.stdout.strip()
    if (
        completed.returncode != 0
        or not api_key
        or len(api_key) > 4096
        or "\x00" in api_key
    ):
        raise AdapterError("credential_unavailable")
    return api_key


def _audited_model(provider: dict[str, Any]) -> dict[str, Any] | None:
    models = provider.get("models")
    if not isinstance(models, list):
        return None
    model = next(
        (item for item in models if isinstance(item, dict) and item.get("id") == MODEL),
        None,
    )
    if not isinstance(model, dict):
        return None
    if not isinstance(model.get("name"), str) or not model["name"].strip():
        return None
    inputs = model.get("input")
    if (
        not isinstance(inputs, list)
        or "text" not in inputs
        or any(not isinstance(item, str) or not item for item in inputs)
    ):
        return None
    if not isinstance(model.get("reasoning"), bool) or not isinstance(
        model.get("supportsTools"), bool
    ):
        return None
    return model


def _audited_compat(provider: dict[str, Any]) -> dict[str, bool] | None:
    compat = provider.get("compat")
    expected = {"supportsDeveloperRole", "supportsReasoningEffort"}
    if (
        not isinstance(compat, dict)
        or set(compat) != expected
        or any(not isinstance(compat[key], bool) for key in expected)
    ):
        return None
    return {key: compat[key] for key in sorted(expected)}


def _audited_provider(provider: object) -> dict[str, Any] | None:
    if not isinstance(provider, dict):
        return None
    if (
        provider.get("baseUrl") != "http://127.0.0.1:9290/v1"
        or provider.get("api") != "openai-completions"
        or provider.get("authHeader") is not True
        or not _safe_credential_identity(provider.get("apiKey"))
    ):
        return None
    model = _audited_model(provider)
    compat = _audited_compat(provider)
    if model is None or compat is None:
        return None
    return {
        "api": provider["api"],
        "apiKey": provider["apiKey"],
        "authHeader": provider["authHeader"],
        "baseUrl": provider["baseUrl"],
        "compat": compat,
        "models": [
            {
                "id": MODEL,
                "name": model["name"],
                "input": ["text"],
                "reasoning": model["reasoning"],
                "supportsTools": model["supportsTools"],
            }
        ],
    }


def _load_authoritative_provider(config_root: Path) -> dict[str, Any]:
    if _yaml is None:
        raise AdapterError("models_config_rejected")
    try:
        source_data = _yaml.safe_load(
            (config_root / "models.yml").read_text(encoding="utf-8")
        )
        provider = source_data["providers"][PROVIDER]
    except Exception as exc:
        raise AdapterError("models_config_rejected") from exc
    audited = _audited_provider(provider)
    if audited is None:
        raise AdapterError("models_config_rejected")
    return audited


def _assert_json_consistent(config_root: Path, authoritative: dict[str, Any]) -> None:
    source = config_root / "models.json"
    if not source.exists():
        return
    try:
        source_data = json.loads(source.read_text(encoding="utf-8"))
        provider = source_data["providers"][PROVIDER]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AdapterError("models_config_rejected") from exc
    if _audited_provider(provider) != authoritative:
        raise AdapterError("models_config_rejected")


def _copy_omlxc_provider(
    user_home: Path,
    agent_dir: Path,
    *,
    api_key_resolver: Callable[[str], str] = _resolve_keychain_api_key,
) -> str:
    config_root = user_home / ".omp" / "agent"
    provider = _load_authoritative_provider(config_root)
    _assert_json_consistent(config_root, provider)
    api_key = api_key_resolver(str(provider["apiKey"]))
    if not api_key or "\x00" in api_key or len(api_key) > 4096:
        raise AdapterError("credential_unavailable")

    agent_dir.mkdir(mode=0o700)
    projected = dict(provider)
    projected["apiKey"] = "OMP_OMLXC_API_KEY"
    destination = agent_dir / "models.json"
    destination.write_text(
        json.dumps(
            {"providers": {PROVIDER: projected}},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    destination.chmod(0o600)
    return api_key


def _node_type(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "regular"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character"
    if stat.S_ISBLK(mode):
        return "block"
    return "other"


def _tree_digest(root: Path) -> str:
    entries: list[tuple[str, str, str]] = []

    def visit(path: Path, relative: Path) -> None:
        node = os.lstat(path)
        node_type = _node_type(node.st_mode)
        payload = ""
        if node_type == "regular":
            payload = digest_bytes(path.read_bytes())
        elif node_type == "symlink":
            payload = os.readlink(path)
        entries.append((relative.as_posix(), node_type, payload))
        if node_type == "directory":
            with os.scandir(path) as children:
                for child in sorted(children, key=lambda item: item.name):
                    visit(Path(child.path), relative / child.name)

    try:
        visit(root, Path("."))
    except FileNotFoundError:
        entries.append((".", "missing", ""))
    return digest_bytes(json.dumps(entries, separators=(",", ":")).encode("utf-8"))


def _minimal_environment(
    trial_dir: Path, marker: str, *, api_key: str
) -> dict[str, str]:
    locale = os.environ.get("LC_ALL") or os.environ.get("LANG") or "C.UTF-8"
    isolated_home = trial_dir / "home"
    agent_dir = trial_dir / "agent"
    session_dir = trial_dir / "sessions"
    isolated_home.mkdir(mode=0o700)
    session_dir.mkdir(mode=0o700)
    return {
        "HOME": str(isolated_home),
        "LANG": locale,
        "PATH": SAFE_PATH,
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "PI_CODING_AGENT_SESSION_DIR": str(session_dir),
        "OMO_OMP_TRIAL_ID": marker.removeprefix("OMO_OMP_TRIAL_ID="),
        "OMP_OMLXC_API_KEY": api_key,
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
    return (
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and payload.get("service") == "aetherforge-openai-proxy"
    )


def _default_marker_probe(marker: str) -> dict[int, int] | None:
    try:
        completed = subprocess.run(
            ["/bin/ps", "eww", "-axo", "pid=,pgid=,command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    token = re.compile(rf"(?<!\S){re.escape(marker)}(?!\S)")
    found: dict[int, int] = {}
    for line in completed.stdout.splitlines():
        parts = line.split(maxsplit=2)
        if (
            len(parts) == 3
            and parts[0].isdigit()
            and parts[1].isdigit()
            and token.search(parts[2])
        ):
            found[int(parts[0])] = int(parts[1])
    return found


def _default_group_terminator(group_id: int, value: signal.Signals) -> None:
    if group_id <= 1 or group_id == os.getpgrp():
        return
    try:
        os.killpg(group_id, value)
    except ProcessLookupError:
        return


def _reap(
    process: Any,
    *,
    marker: str,
    timeout_seconds: float,
    marker_probe: Callable[[str], dict[int, int] | None] = _default_marker_probe,
    group_terminator: Callable[[int, signal.Signals], None] = _default_group_terminator,
) -> bool:
    current_group = os.getpgrp()

    def safe_group(group: object) -> bool:
        return isinstance(group, int) and group > 1 and group != current_group

    def probe() -> dict[int, int] | None:
        try:
            return marker_probe(marker)
        except Exception:  # noqa: BLE001 - probe failure is explicit and fail-closed
            return None

    initial = probe()
    groups = {process.pid} if safe_group(process.pid) else set()
    if initial is not None:
        groups.update(group for group in initial.values() if safe_group(group))
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
    leaked = probe()
    if leaked is None:
        return False
    if leaked:
        for group in sorted({group for group in leaked.values() if safe_group(group)}):
            group_terminator(group, signal.SIGTERM)
        time.sleep(0.05)
        leaked = probe()
        if leaked is None:
            return False
        if leaked:
            for group in sorted(
                {group for group in leaked.values() if safe_group(group)}
            ):
                group_terminator(group, signal.SIGKILL)
            time.sleep(0.05)
    final = probe()
    return final == {}


def _binary_digest(path: Path) -> str:
    try:
        return digest_bytes(path.read_bytes())
    except OSError as exc:
        raise AdapterError("version_unavailable") from exc


def _default_version_reader() -> str:
    executable = Path(OMP_EXECUTABLE)
    try:
        resolved = executable.resolve(strict=True)
    except OSError as exc:
        raise AdapterError("version_unavailable") from exc
    if not _is_within(resolved, (Path.home() / ".bun").resolve()):
        raise AdapterError("version_unavailable")
    if _binary_digest(executable) != EXPECTED_OMP_SHA256:
        raise AdapterError("version_unavailable")
    try:
        completed = subprocess.run(
            [OMP_EXECUTABLE, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env={"HOME": str(Path.home()), "LANG": "C.UTF-8", "PATH": SAFE_PATH},
        )
    except OSError as exc:
        raise AdapterError("version_unavailable") from exc
    expected = f"omp/{EXPECTED_OMP_VERSION}"
    if completed.returncode != 0 or completed.stdout.strip() != expected:
        raise AdapterError("version_unavailable")
    return EXPECTED_OMP_VERSION


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )


def _session_persisted(session_dir: Path) -> bool:
    return any(path.is_file() or path.is_symlink() for path in session_dir.rglob("*"))


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
    marker_probe: Callable[[str], dict[int, int] | None] = _default_marker_probe,
    group_terminator: Callable[[int, signal.Signals], None] = _default_group_terminator,
    version_reader: Callable[[], str] = _default_version_reader,
    api_key_resolver: Callable[[str], str] = _resolve_keychain_api_key,
) -> dict[str, Any]:
    """Execute one bounded OMP call without persisting prompt or output text."""
    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise AdapterError("timeout_rejected")
    if not execute:
        return {
            "command": fixed_argv(prompt, timeout_seconds=timeout_seconds),
            "mode": "dry-run",
            "tools_enabled": False,
        }
    home = (
        Path.home() if user_home is None else Path(user_home).expanduser()
    ).resolve()
    receipt_file = (
        validate_receipt_path(receipt_path, user_home=home)
        if receipt_path is not None
        else None
    )
    config_root = validate_config_root(home)
    marker = f"OMO_OMP_TRIAL_ID={uuid.uuid4()}"
    started_at = _utc_now()
    started = time.monotonic()
    before_config = _tree_digest(config_root)
    receipt: dict[str, Any] = {
        "checks": {
            "aetherforge_health": False,
            "child_reaped": False,
            "session_persisted": False,
            "temp_removed": False,
            "tools_enabled": False,
            "user_config_unchanged": False,
        },
        "model": MODEL,
        "outcome": "failed",
        "provider": PROVIDER,
        "route_ref": ROUTE_REF,
        "schema_version": 1,
        "started_at": started_at,
        "worker": "oh-my-pi",
    }
    process: Any | None = None
    trial_dir: Path | None = None
    session_dir: Path | None = None
    error_code: str | None = None
    output = ""
    try:
        receipt["omp_version"] = version_reader()
        if not _health_is_expected(health_probe()):
            raise AdapterError("health_rejected")
        receipt["checks"]["aetherforge_health"] = True
        trial_dir = Path(tempfile.mkdtemp(prefix="omo-omp-trial-"))
        api_key = _copy_omlxc_provider(
            home,
            trial_dir / "agent",
            api_key_resolver=api_key_resolver,
        )
        environment = _minimal_environment(trial_dir, marker, api_key=api_key)
        session_dir = Path(environment["PI_CODING_AGENT_SESSION_DIR"])
        try:
            process = popen_factory(
                fixed_argv(prompt, timeout_seconds=timeout_seconds),
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
        if before_config != _tree_digest(config_root):
            raise AdapterError("config_drift")
        receipt["checks"]["user_config_unchanged"] = True
        if _session_persisted(session_dir):
            receipt["checks"]["session_persisted"] = True
            raise AdapterError("session_persisted")
        receipt["output_bytes"] = len(output.encode("utf-8"))
        receipt["output_digest"] = digest_bytes(output.encode("utf-8"))
    except AdapterError as exc:
        error_code = exc.code
    except Exception:  # noqa: BLE001 - keep dependency text and secrets out of errors
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
            try:
                residual = marker_probe(marker)
            except Exception:  # noqa: BLE001 - probe failure must fail closed
                residual = None
            receipt["checks"]["child_reaped"] = residual == {}
        if before_config != _tree_digest(config_root) and error_code is None:
            error_code = "config_drift"
        if session_dir is not None and _session_persisted(session_dir):
            receipt["checks"]["session_persisted"] = True
            if error_code is None:
                error_code = "session_persisted"
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
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "run", help="dry-run by default; --execute performs one bounded call"
    )
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
        print(
            json.dumps(
                {"error_code": exc.code, "outcome": "failed"},
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    if args.execute:
        sys.stdout.write(result["output"])
    else:
        print(
            json.dumps(
                result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
