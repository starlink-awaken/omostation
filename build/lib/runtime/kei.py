"""Kernel Extension Interface (KEI) Sandbox Specification.

This module defines the permission schema and sandbox rules for
external Skills/Plugins connecting to the eCOS v5 Kernel.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import yaml

@dataclass
class SandboxPermissions:
    """Permissions requested by an extension."""
    fs_read: List[str] = field(default_factory=list)
    fs_write: List[str] = field(default_factory=list)
    network_hosts: List[str] = field(default_factory=list)
    shell_exec: bool = False
    env_vars: List[str] = field(default_factory=list)

@dataclass
class KEIManifest:
    """Kernel Extension Interface Manifest (kei.yaml)."""
    name: str
    version: str
    description: str
    entrypoint: str
    permissions: SandboxPermissions
    status: str = "active"

def load_manifest(path: str | Path) -> KEIManifest:
    """Load and validate a KEI manifest from a yaml file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"KEI manifest not found at {p}")
    
    with p.open() as f:
        data = yaml.safe_load(f)
    
    perms_data = data.get("permissions", {})
    perms = SandboxPermissions(
        fs_read=perms_data.get("fs_read", []),
        fs_write=perms_data.get("fs_write", []),
        network_hosts=perms_data.get("network_hosts", []),
        shell_exec=perms_data.get("shell_exec", False),
        env_vars=perms_data.get("env_vars", [])
    )
    
    return KEIManifest(
        name=data.get("name", "unknown"),
        version=data.get("version", "0.0.0"),
        description=data.get("description", ""),
        entrypoint=data.get("entrypoint", ""),
        permissions=perms,
        status=data.get("status", "active")
    )

def validate_action(manifest: KEIManifest, action_type: str, target: str) -> bool:
    """Basic validation logic for sandbox enforcement.
    
    In a real runtime, this is checked before executing adapter commands.
    """
    if action_type == "read":
        # Simplified: Check if target starts with any allowed path
        return any(target.startswith(p) for p in manifest.permissions.fs_read)
    elif action_type == "write":
        return any(target.startswith(p) for p in manifest.permissions.fs_write)
    elif action_type == "network":
        return any(target in host or host == "*" for host in manifest.permissions.network_hosts)
    elif action_type == "exec":
        return manifest.permissions.shell_exec
    
    return False
