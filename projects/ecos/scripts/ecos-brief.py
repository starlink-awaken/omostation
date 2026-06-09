#!/usr/bin/env python3
"""
ecos-brief.py — 系统简报生成器

生成 eCOS 系统运行简报，包含：
- daemon 周期统计
- 健康检查结果
- 协议衰减状态
- model-driven 自反验证结果

用法:
    python3 ecos-brief.py          # 生成简报
    python3 ecos-brief.py --json   # JSON 输出
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_brief(json_output: bool = False) -> dict:
    """生成系统简报"""
    ws = Path.home() / "Workspace"
    brief = {
        "generated_at": now(),
        "system": "eCOS v5",
        "sections": {},
    }

    # 1. Daemon 状态
    daemon_state = ws / ".ecos" / "daemon-state.db"
    if daemon_state.exists():
        import sqlite3
        try:
            conn = sqlite3.connect(str(daemon_state))
            cursor = conn.execute("SELECT COUNT(*) FROM cycles")
            cycles = cursor.fetchone()[0]
            conn.close()
            brief["sections"]["daemon"] = {"cycles": cycles, "status": "active"}
        except Exception:
            brief["sections"]["daemon"] = {"status": "error"}
    else:
        brief["sections"]["daemon"] = {"status": "not_initialized"}

    # 2. M0 快照
    m0_path = ws / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m0" / "snapshot.yaml"
    if m0_path.exists():
        import yaml
        try:
            with open(m0_path) as f:
                m0 = yaml.safe_load(f)
            brief["sections"]["m0_snapshot"] = {
                "daemon_cycles": m0.get("daemon", {}).get("cycles", 0),
                "protocols": list(m0.get("protocols", {}).keys()),
            }
        except Exception:
            brief["sections"]["m0_snapshot"] = {"error": "parse_failed"}
    else:
        brief["sections"]["m0_snapshot"] = {"status": "not_available"}

    # 3. model-driven 自反验证
    md_dir = ws / "projects" / "model-driven"
    if md_dir.exists() and (md_dir / "pyproject.toml").exists():
        try:
            import subprocess
            result = subprocess.run(
                ["uv", "run", "python3", "-c",
                 "from model_driven.toolchain.tools import tool_validate; "
                 "import yaml; from pathlib import Path; "
                 "m1 = Path.home() / 'Workspace/projects/ecos/src/ecos/ssot/mof/m1'; "
                 "nodes = [yaml.safe_load(open(f)) for d in sorted(m1.iterdir()) if d.is_dir() for f in sorted(d.glob('*.yaml')) if (yaml.safe_load(open(f)) or {}).get('type')]; "
                 "r = tool_validate(models=nodes); "
                 "print(r['models_checked'], r['error_count'], r['warning_count'])",
                 ],
                cwd=str(md_dir), capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split()
                if len(parts) == 3:
                    brief["sections"]["model_driven"] = {
                        "nodes": int(parts[0]),
                        "errors": int(parts[1]),
                        "warnings": int(parts[2]),
                    }
        except Exception:
            brief["sections"]["model_driven"] = {"status": "unavailable"}

    return brief


def main():
    json_output = "--json" in sys.argv
    brief = generate_brief(json_output)

    if json_output:
        print(json.dumps(brief, indent=2, ensure_ascii=False))
    else:
        print(f"eCOS v5 系统简报 — {brief['generated_at']}")
        for section, data in brief["sections"].items():
            print(f"  [{section}]: {data}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
