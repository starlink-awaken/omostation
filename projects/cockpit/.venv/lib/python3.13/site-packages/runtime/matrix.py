"""Runtime Matrix — read/query the service registry with env-var expansion."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ─── Defaults ──────────────────────────────────────────────────────────────
RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime"))
RUNTIME_MATRIX = Path(os.environ.get("RUNTIME_MATRIX", RUNTIME_HOME / "matrix.yaml"))


@dataclass
class ServiceEntry:
    """A single service entry from the matrix."""
    name: str
    type: str
    status: str
    port: Optional[int] = None
    launchd_label: Optional[str] = None
    deploy_path: Optional[str] = None
    log_path: Optional[str] = None
    start_command: Optional[str] = None
    health_url: Optional[str] = None
    docker_container: Optional[str] = None
    notes: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def _expand_env(s: str) -> str:
    """Expand $VAR references using environment variables."""
    if not s or s == "null":
        return ""
    result = s
    for var, val in os.environ.items():
        result = result.replace(f"${var}", val)
    return result


# ─── Section markers ───────────────────────────────────────────────────────
# Indentation conventions in our matrix.yaml:
#   0 spaces: root keys (runtime_matrix:)
#   2 spaces: 2nd-level (version:, services:, migrations:, groups:)
#   4 spaces: 3rd-level (comments, service entries: "- name:", groups)
#   6 spaces: 4th-level (service fields: "type:", "port:", etc.)
#   8 spaces: continuation text (notes > text)

def load_matrix(path: Optional[Path] = None) -> list[ServiceEntry]:
    """Load and parse the runtime matrix YAML.

    Lightweight line-by-line parser for the specific matrix.yaml format.
    No external YAML dependency required.
    """
    path = path or RUNTIME_MATRIX
    if not path.exists():
        raise FileNotFoundError(f"Runtime matrix not found: {path}")

    services: list[ServiceEntry] = []
    current: dict = {}

    # States
    IN_SERVICES = 1     # Inside the 'services:' block
    IN_SERVICE = 2      # Inside a single service entry
    IN_GROUPS = 3       # Inside 'groups:' or 'migrations:' block — skip
    OUTSIDE = 0         # Before 'services:' or after it

    state = OUTSIDE

    with open(path) as f:
        for line in f:
            s = line.rstrip()

            # ── Detect section transitions ──────────────────────────────────
            # 2-space keys: services:, migrations:, groups:
            if s.startswith("  ") and not s.startswith("    ") and ":" in s:
                key = s.split(":")[0].strip()
                if key == "services":
                    state = IN_SERVICES
                    continue
                elif key in ("migrations", "groups"):
                    state = IN_GROUPS
                    continue
                else:
                    continue

            # Skip blank lines and full-line comments
            if not s or s.startswith("#"):
                continue

            if state == IN_GROUPS:
                # Until we see a non-indented line or next section
                continue

            if state == IN_SERVICES:
                # 4-space service entry: "    - name: ..."
                if s.startswith("    - name:"):
                    # Flush previous service
                    if current:
                        services.append(_parse_entry(current))
                    current = {"name": s.split('"')[1]}
                    continue

                # 4-space comment between services
                if s.startswith("    #"):
                    continue

                # Inside a service: parse 6-space fields
                if current and s.startswith("      "):
                    if ":" in s:
                        key, _, val = s.partition(":")
                        key = key.strip()
                        val_part = val.strip().strip('"')
                        value = _expand_env(val_part) if val_part else ""
                        if key:
                            current[key] = value
                    continue

                # 8-space continuation lines (notes: > text)
                if current and s.startswith("        "):
                    # Append to notes if present
                    if "notes" in current:
                        current["notes"] = current["notes"] + " " + s.strip()
                    continue

                # Anything else — end of services section (e.g., blank line
                # at 0 indent, or next 2-space key)
                if s.strip() and not s.startswith("    "):
                    if current:
                        services.append(_parse_entry(current))
                        current = {}
                    state = OUTSIDE

    # Flush last service
    if current:
        services.append(_parse_entry(current))

    return services


def _parse_entry(raw: dict) -> ServiceEntry:
    port_str = raw.get("port", "")
    port = int(port_str) if port_str and port_str not in ("null", "—") else None
    
    depends_raw = raw.get("depends_on", "")
    depends_on = [d.strip() for d in depends_raw.strip("[]").split(",")] if depends_raw and depends_raw != "null" else []

    return ServiceEntry(
        name=raw.get("name", "unknown"),
        type=raw.get("type", "unknown"),
        status=raw.get("status", "unknown"),
        port=port,
        launchd_label=raw.get("launchd_label"),
        deploy_path=raw.get("deploy_path"),
        log_path=raw.get("log_path"),
        start_command=raw.get("start_command"),
        health_url=raw.get("health_url"),
        docker_container=raw.get("docker_container"),
        notes=raw.get("notes"),
        depends_on=[d for d in depends_on if d],
        raw=raw,
    )


def get_service(name: str, path: Optional[Path] = None) -> Optional[ServiceEntry]:
    """Find a service by name."""
    for svc in load_matrix(path):
        if svc.name == name:
            return svc
    return None


def list_services(path: Optional[Path] = None) -> list[ServiceEntry]:
    """List all services."""
    return load_matrix(path)


def resolve_path(path_str: Optional[str]) -> Optional[str]:
    """Resolve a $VAR path to its actual filesystem path."""
    if not path_str:
        return None
    expanded = _expand_env(path_str)
    return os.path.expanduser(expanded)


def health_check_url(url: Optional[str]) -> str:
    """Quick HTTP health check via curl."""
    if not url:
        return "—"
    import subprocess
    try:
        r = subprocess.run(
            ["curl", "-sf", "-o", "/dev/null", "--max-time", "2", url],
            capture_output=True, timeout=5
        )
        return "healthy" if r.returncode == 0 else "unreachable"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "error"
