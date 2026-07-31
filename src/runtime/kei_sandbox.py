"""KEI (Knowledge Engine Integrity) Runtime Sandbox

This module implements runtime permissions enforcement using Python's sys.addaudithook.
It reads rules from kei.yaml, intercepts operations such as file access,
network requests, and sub-process execution, and writes audit records to a JSONL file.
"""

import json
import os
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path


def _load_kei_rules(config_path: str = "kei.yaml", role: str = "default") -> dict:
    path = Path(config_path)
    if not path.exists():
        # Default strict rules if no kei.yaml
        return {
            "version": "1.0",
            "role": role,
            "permissions": {
                "network": {"allow": ["localhost", "127.0.0.1"]},
                "filesystem": {
                    "allow_read": ["/"],
                    "allow_write": [
                        "/tmp",
                        "/private/var/folders",
                        "/var/folders",
                        str(Path.home() / "Workspace"),
                    ],
                },
                "execution": {"allow_subprocess": False},
            },
        }
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}

    # Extract global permissions
    perms = data.get("permissions", {})

    # If a role is specified and exists, merge/override its specific permissions
    if role and role != "default":
        roles_config = data.get("roles", {})
        if role in roles_config:
            role_perms = roles_config[role].get("permissions", {})
            # Merge logic: deep update dicts
            for k, v in role_perms.items():
                if isinstance(v, dict) and k in perms:
                    perms[k].update(v)
                else:
                    perms[k] = v

    return {"version": data.get("version", "1.0"), "role": role, "permissions": perms}


_RULES = _load_kei_rules(
    os.environ.get("KEI_CONFIG_PATH", "kei.yaml"),
    os.environ.get("ECOS_EXECUTION_ROLE", "default"),
)
_workspace_root = (
    Path(__file__).resolve().parents[4]
)  # runtime/src/runtime/kei_sandbox.py → workspace root
_DEFAULT_AUDIT = _workspace_root / "runtime" / "data" / "kei_audit.jsonl"
_AUDIT_FILE = Path(
    os.environ.get("KEI_AUDIT_FILE", str(_DEFAULT_AUDIT))
)  # Set by enable_sandbox()
_IN_AUDIT = False  # Recursion guard


def record_audit(action: str, extension_id: str, status: str, details: str) -> None:
    """Append a KEI audit record to the audit file (JSONL format).

    Args:
        action:     One of 'validate', 'execute', 'reject'.
        extension_id: Identifier of the extension (e.g. 'ecos.kernel.sandbox').
        status:     One of 'pass', 'fail', 'blocked'.
        details:    Human-readable description of the operation.
    """
    global _AUDIT_FILE, _IN_AUDIT
    if _AUDIT_FILE is None or _IN_AUDIT:
        return  # Audit not configured or re-entrant — skip logging

    _IN_AUDIT = True
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "extension_id": extension_id,
        "status": status,
        "details": details,
    }

    try:
        _AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Use low-level I/O to avoid triggering the 'open' audit hook
        line = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(str(_AUDIT_FILE), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except OSError:
        pass  # Best-effort audit; don't crash the sandbox
    finally:
        _IN_AUDIT = False


def _audit_hook(event: str, args: tuple):
    if _IN_AUDIT:
        return
    perms = _RULES.get("permissions", {})

    if event == "subprocess.Popen":
        cmd = " ".join(str(a) for a in args[0]) if args else "unknown"
        if not perms.get("execution", {}).get("allow_subprocess", True):
            record_audit(
                "reject", "ecos.kernel.sandbox", "blocked", f"Subprocess blocked: {cmd}"
            )
            raise PermissionError("KEI Sandbox: subprocess execution is blocked.")
        record_audit(
            "execute", "ecos.kernel.sandbox", "pass", f"Subprocess allowed: {cmd}"
        )

    elif event == "socket.connect":
        # args[0] is socket, args[1] is address (host, port)
        if len(args) >= 2 and isinstance(args[1], tuple) and len(args[1]) >= 2:
            host = args[1][0]
            allowed_hosts = perms.get("network", {}).get("allow", ["*"])
            if "*" not in allowed_hosts and host not in allowed_hosts:
                record_audit(
                    "reject",
                    "ecos.kernel.sandbox",
                    "blocked",
                    f"Network connection blocked to {host}",
                )
                raise PermissionError(
                    f"KEI Sandbox: Network connection to {host} is blocked."
                )
            record_audit(
                "execute",
                "ecos.kernel.sandbox",
                "pass",
                f"Network connection allowed to {host}",
            )

    elif event == "open":
        if isinstance(args[0], int):
            return  # Allow file descriptors
        file_path = os.path.abspath(str(args[0]))
        mode = str(args[1]) if len(args) > 1 else "r"

        if "w" in mode or "a" in mode or "+" in mode:
            allowed_writes = perms.get("filesystem", {}).get("allow_write", ["*"])
            if "*" not in allowed_writes:
                allowed_writes = [os.path.expandvars(p) for p in allowed_writes]
                allowed = any(file_path.startswith(prefix) for prefix in allowed_writes)
                if not allowed:
                    record_audit(
                        "reject",
                        "ecos.kernel.sandbox",
                        "blocked",
                        f"Write blocked: {file_path} (mode={mode})",
                    )
                    raise PermissionError(
                        f"KEI Sandbox: Write access to {file_path} is blocked."
                    )
            record_audit(
                "execute",
                "ecos.kernel.sandbox",
                "pass",
                f"Write allowed: {file_path} (mode={mode})",
            )
        else:
            allowed_reads = perms.get("filesystem", {}).get("allow_read", ["*"])
            if "*" not in allowed_reads:
                allowed_reads = [os.path.expandvars(p) for p in allowed_reads]
                allowed = any(file_path.startswith(prefix) for prefix in allowed_reads)
                if not allowed:
                    record_audit(
                        "reject",
                        "ecos.kernel.sandbox",
                        "blocked",
                        f"Read blocked: {file_path}",
                    )
                    raise PermissionError(
                        f"KEI Sandbox: Read access to {file_path} is blocked."
                    )
            record_audit(
                "validate", "ecos.kernel.sandbox", "pass", f"Read allowed: {file_path}"
            )

    elif event == "os.system":
        cmd = str(args[0]) if args else "unknown"
        if not perms.get("execution", {}).get("allow_subprocess", True):
            record_audit(
                "reject", "ecos.kernel.sandbox", "blocked", f"os.system blocked: {cmd}"
            )
            raise PermissionError("KEI Sandbox: os.system execution is blocked.")
        record_audit(
            "execute", "ecos.kernel.sandbox", "pass", f"os.system allowed: {cmd}"
        )

    elif event == "os.exec":
        cmd = " ".join(str(a) for a in args) if args else "unknown"
        if not perms.get("execution", {}).get("allow_subprocess", True):
            record_audit(
                "reject", "ecos.kernel.sandbox", "blocked", f"os.exec blocked: {cmd}"
            )
            raise PermissionError("KEI Sandbox: os.exec execution is blocked.")
        record_audit(
            "execute", "ecos.kernel.sandbox", "pass", f"os.exec allowed: {cmd}"
        )

    elif event == "urllib.Request":
        url = str(args[0]) if args else "unknown"
        allowed_hosts = perms.get("network", {}).get("allow", ["*"])
        if "*" not in allowed_hosts:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            host = parsed.hostname or url
            if host not in allowed_hosts:
                record_audit(
                    "reject",
                    "ecos.kernel.sandbox",
                    "blocked",
                    f"urllib request blocked: {url}",
                )
                raise PermissionError(f"KEI Sandbox: HTTP request to {url} is blocked.")
        record_audit(
            "execute", "ecos.kernel.sandbox", "pass", f"urllib request allowed: {url}"
        )

    elif event == "http.client":
        # args[0] is (host, port) tuple for http.client connections
        if args and len(args) >= 1 and isinstance(args[0], tuple) and len(args[0]) >= 2:
            host = args[0][0]
            allowed_hosts = perms.get("network", {}).get("allow", ["*"])
            if "*" not in allowed_hosts and host not in allowed_hosts:
                record_audit(
                    "reject",
                    "ecos.kernel.sandbox",
                    "blocked",
                    f"http.client blocked: {host}",
                )
                raise PermissionError(
                    f"KEI Sandbox: HTTP connection to {host} is blocked."
                )
            record_audit(
                "execute", "ecos.kernel.sandbox", "pass", f"http.client allowed: {host}"
            )

    # ── Phase 15: Deep FS Mutation Interception ──
    elif event in ("os.remove", "os.unlink", "os.rename", "os.mkdir", "os.rmdir"):
        # Audit hooks include extra non-path args (mode, dir_fd). Only inspect path args.
        if event == "os.rename":
            if len(args) < 2:
                record_audit(
                    "reject",
                    "ecos.kernel.sandbox",
                    "blocked",
                    f"FS mutation blocked: {event} missing destination",
                )
                raise PermissionError(
                    f"KEI Sandbox: {event} missing destination argument."
                )
            paths = [os.path.abspath(str(args[0])), os.path.abspath(str(args[1]))]
        else:
            paths = [os.path.abspath(str(args[0]))]

        allowed_writes = perms.get("filesystem", {}).get("allow_write", ["*"])
        if "*" not in allowed_writes:
            allowed_writes = [os.path.expandvars(p) for p in allowed_writes]
            blocked = [
                p
                for p in paths
                if not any(p.startswith(prefix) for prefix in allowed_writes)
            ]
            if blocked:
                detail = ", ".join(blocked)
                record_audit(
                    "reject",
                    "ecos.kernel.sandbox",
                    "blocked",
                    f"FS mutation blocked: {event} on {detail}",
                )
                raise PermissionError(
                    f"KEI Sandbox: {event} access to {detail} is blocked."
                )
        record_audit(
            "execute",
            "ecos.kernel.sandbox",
            "pass",
            f"FS mutation allowed: {event} on {', '.join(paths)}",
        )


def enable_sandbox(
    config_path: str = "kei.yaml", audit_file: str | None = None, role: str = "default"
) -> None:
    """Enable the KEI Sandbox.

    Args:
        config_path: Path to kei.yaml rules file.
        audit_file:  Path where audit records are written (JSONL).
                     Falls back to $AUDIT_FILE_PATH env var, then
                     $HOME/runtime/audit/kei-audit.jsonl.
        role:        The execution role (e.g. 'generator', 'evaluator') used to load
                     role-specific rules from the 'roles' section of kei.yaml.
    """
    global _RULES, _AUDIT_FILE

    # If passed via env var, override the argument
    env_role = os.environ.get("ECOS_EXECUTION_ROLE")
    if env_role and role == "default":
        role = env_role

    _RULES = _load_kei_rules(config_path, role)

    if audit_file is None:
        audit_file = os.environ.get("AUDIT_FILE_PATH", str(_DEFAULT_AUDIT))
    _AUDIT_FILE = Path(audit_file)
    _AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)

    sys.addaudithook(_audit_hook)
    record_audit(
        "validate",
        "ecos.kernel.sandbox",
        "pass",
        f"KEI Sandbox enabled (rules={config_path}, role={role}, audit={audit_file})",
    )
    import sys as _sys

    print(f"KEI Sandbox enabled [Role: {role}]", file=_sys.stderr)


if __name__ == "__main__":
    # Test script behavior
    enable_sandbox()
    try:
        import subprocess

        subprocess.run(["echo", "hello"], check=False)
        print("Subprocess succeeded (should not happen if allow_subprocess=False)")
    except PermissionError as e:
        print(f"Blocked as expected: {e}")
