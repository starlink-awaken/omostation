"""KEI (Knowledge Engine Integrity) Runtime Sandbox

This module implements runtime permissions enforcement using Python's sys.addaudithook.
It reads rules from kei.yaml and intercepts operations such as file access,
network requests, and sub-process execution.
"""

import os
import sys
import yaml
from pathlib import Path

def _load_kei_rules(config_path: str = "kei.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        # Default strict rules if no kei.yaml
        return {
            "version": "1.0",
            "permissions": {
                "network": {"allow": ["localhost", "127.0.0.1"]},
                "filesystem": {"allow_read": ["/"], "allow_write": ["/tmp", str(Path.home() / "Workspace")]},
                "execution": {"allow_subprocess": False}
            }
        }
    with open(path, "r") as f:
        return yaml.safe_load(f)

_RULES = _load_kei_rules(os.environ.get("KEI_CONFIG_PATH", "kei.yaml"))

def _audit_hook(event: str, args: tuple):
    perms = _RULES.get("permissions", {})
    
    if event == "subprocess.Popen":
        if not perms.get("execution", {}).get("allow_subprocess", True):
            raise PermissionError("KEI Sandbox: subprocess execution is blocked.")

    elif event == "socket.connect":
        # args[0] is address (host, port)
        if isinstance(args[0], tuple) and len(args[0]) >= 2:
            host = args[0][0]
            allowed_hosts = perms.get("network", {}).get("allow", ["*"])
            if "*" not in allowed_hosts and host not in allowed_hosts:
                raise PermissionError(f"KEI Sandbox: Network connection to {host} is blocked.")
                
    elif event == "open":
        file_path = str(args[0])
        mode = str(args[1]) if len(args) > 1 else "r"
        
        # Simplify checking
        if "w" in mode or "a" in mode or "+" in mode:
            allowed_writes = perms.get("filesystem", {}).get("allow_write", ["*"])
            if "*" not in allowed_writes:
                allowed = any(file_path.startswith(prefix) for prefix in allowed_writes)
                if not allowed:
                    raise PermissionError(f"KEI Sandbox: Write access to {file_path} is blocked.")
        else:
            allowed_reads = perms.get("filesystem", {}).get("allow_read", ["*"])
            if "*" not in allowed_reads:
                allowed = any(file_path.startswith(prefix) for prefix in allowed_reads)
                if not allowed:
                    raise PermissionError(f"KEI Sandbox: Read access to {file_path} is blocked.")

def enable_sandbox(config_path: str = "kei.yaml"):
    """Enable the KEI Sandbox."""
    global _RULES
    _RULES = _load_kei_rules(config_path)
    sys.addaudithook(_audit_hook)
    print(f"🛡️ KEI Sandbox enabled (Rules loaded from {config_path})")

if __name__ == "__main__":
    # Test script behavior
    enable_sandbox()
    try:
        import subprocess
        subprocess.run(["echo", "hello"])
        print("Subprocess succeeded (should not happen if allow_subprocess=False)")
    except PermissionError as e:
        print(f"Blocked as expected: {e}")
