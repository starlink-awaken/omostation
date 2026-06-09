"""omo system inspection — P36-W1 补 GAP 5.

检查 omo daemon, agora 服务, kairon 关键包状态.
"""

from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path


def inspect_omo_daemon() -> dict:
    """检查 omo daemon 状态."""
    try:
        r = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return {"status": "error", "error": r.stderr}
        # 找 com.omo.governance.daemon
        for line in r.stdout.splitlines():
            if "com.omo.governance.daemon" in line:
                parts = line.split()
                if len(parts) >= 3:
                    pid = parts[0]
                    exit_code = parts[1]
                    return {
                        "status": "running" if pid != "-" else "stopped",
                        "pid": pid,
                        "exit_code": exit_code,
                    }
        return {"status": "not_found"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def inspect_agora_routes() -> dict:
    """检查 agora 路由表状态."""
    ws = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
    routes_path = ws / "projects" / "agora" / "src" / "agora-services.json"
    if not routes_path.exists():
        return {"status": "error", "error": f"routes_not_found: {routes_path}"}
    data = json.loads(routes_path.read_text(encoding="utf-8"))
    routes = data.get("routes", {})
    return {
        "status": "ok",
        "total_routes": len(routes),
        "services": sorted(set(routes.values())),
    }


def inspect_kairon_packages() -> dict:
    """检查 kairon 活跃包数."""
    ws = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
    kairon_pkgs = ws / "projects" / "kairon" / "packages"
    if not kairon_pkgs.exists():
        return {"status": "error", "error": "kairon_not_found"}
    packages = [d.name for d in kairon_pkgs.iterdir() if d.is_dir() and not d.name.startswith(".")]
    return {
        "status": "ok",
        "package_count": len(packages),
        "packages": sorted(packages),
    }


def run_full_inspection() -> dict:
    """综合检查."""
    return {
        "omo_daemon": inspect_omo_daemon(),
        "agora_routes": inspect_agora_routes(),
        "kairon_packages": inspect_kairon_packages(),
    }


def main() -> int:
    result = run_full_inspection()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
