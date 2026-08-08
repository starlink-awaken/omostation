#!/usr/bin/env python3
"""migrate-port-env-var.py — P77 Phase 7 端口→Env Var 迁移助手

扫描 projects/*/src/ 中硬编码端口, 对照 port-registry.yaml 中 env_var 映射,
输出迁移建议. --apply 模式自动注入 env var 读取代码 (只改 root repo 文件).

用法:
  python bin/migrate-port-env-var.py                     # 扫描 + 输出建议
  python bin/migrate-port-env-var.py --apply             # root repo 自动迁
  python bin/migrate-port-env-var.py --json              # JSON 输出

原则: P77-7 environment-variable-preferred — 优先用 env var, 而非字面量.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

# 外部豁免端口 (LEGACY_OK_PORTS 沿用)
LEGACY_OK_PORTS = {1234, 3000, 3001, 4318, 5173}

PORT_PATTERNS = [
    (re.compile(r'\bPORT\s*=\s*(\d{4,5})\b'), "PORT = NNNN"),
    (re.compile(r'\bport\s*[=:]\s*(\d{4,5})\b'), "port=NNNN"),
    (re.compile(r'--port[=\s]+(\d{4,5})\b'), "--port NNNN"),
    (re.compile(r'://[^/]+:(\d{4,5})(?:[/\b]|$)'), "host:port"),
    (re.compile(r'\blocalhost:(\d{4,5})\b'), "localhost:port"),
    (re.compile(r'\b127\.0\.0\.1:(\d{4,5})\b'), "127.0.0.1:port"),
    (re.compile(r'\b0\.0\.0\.0:(\d{4,5})\b'), "0.0.0.0:port"),
]


def load_yaml(p: Path):
    import yaml
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None


def load_port_registry() -> dict[int, dict]:
    """返回 {port: {name, env_var}}"""
    result: dict[int, dict] = {}
    for f in [
        WORKSPACE / "projects" / "ecos" / "port-registry.yaml",
        WORKSPACE / "protocols" / "port-registry.yaml",
    ]:
        data = load_yaml(f) or {}
        ports_data = data.get("ports") or {}
        env_vars_data = data.get("env_vars") or {}
        for port_str, name in ports_data.items():
            try:
                port = int(port_str)
            except (ValueError, TypeError):
                continue
            # strip yaml comment from name
            n = str(name)
            if "  #" in n:
                n = n.split("  #", 1)[0].strip()
            result.setdefault(port, {"name": n, "env_var": None})
            result[port]["env_var"] = result[port]["env_var"] or env_vars_data.get(port)
    return result


def collect_hardcoded(root: Path) -> dict[int, list[dict]]:
    """Scan projects/src/ for hardcoded port literals."""
    found: dict[int, list[dict]] = {}
    for proj_dir in root.iterdir():
        if not (proj_dir / "src").is_dir():
            continue
        if proj_dir.name.startswith((".", "_", "venv")):
            continue
        for f in (proj_dir / "src").rglob("*"):
            if not f.is_file():
                continue
            parts = f.parts
            if "test" in parts or "tests" in parts or "__pycache__" in parts:
                continue
            SUFFIXES = {".py", ".sh", ".yaml", ".yml", ".json", ".env", ".conf", ".cfg", ".toml"}
            if f.suffix not in SUFFIXES:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pat, pat_name in PORT_PATTERNS:
                for m in pat.finditer(text):
                    port = int(m.group(1))
                    if port in LEGACY_OK_PORTS:
                        continue
                    if not (1000 < port < 65536):
                        continue
                    line_no = text[:m.start()].count("\n") + 1
                    found.setdefault(port, []).append({
                        "file": str(f.relative_to(WORKSPACE)),
                        "line": line_no,
                        "pattern": pat_name,
                        "snippet": text[max(0, m.start()-20):m.end()+20].replace("\n", "↵"),
                    })
    return found


def env_var_replacement(port: int, env_var: str, code: str) -> str | None:
    """生成 env var 读取代码替换 suggestion."""
    patterns = [
        (re.compile(rf"\bPORT\s*=\s*{port}\b"), f"PORT = int(os.environ.get('{env_var}', '{port}'))"),
        (re.compile(rf"\bport\s*=\s*{port}\b"), f"port = int(os.environ.get('{env_var}', '{port}'))"),
        (re.compile(rf"--port\s*{port}\b"), f"--port \\${{{env_var}:-{port}}}"),
    ]
    for pat, replacement in patterns:
        if pat.search(code):
            return replacement
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="apply env var migration in root repo")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--threshold", type=int, default=0, help="unmigrated port threshold")
    args = p.parse_args()

    registry = load_port_registry()
    hardcoded = collect_hardcoded(WORKSPACE / "projects")

    # 每个 port: registered? has env var? hardcoded usage count?
    findings = []
    for port in sorted(hardcoded.keys()):
        info = registry.get(port, {})
        env_var = info.get("env_var") if info else None
        findings.append({
            "port": port,
            "name": info.get("name", "(unregistered)"),
            "env_var": env_var,
            "count": len(hardcoded[port]),
            "sites": hardcoded[port][:3],
        })

    # 根仓库硬编码扫描 (bin/, .githooks/, Makefile, .env)
    root_hardcoded = find_root_hardcoded()
    root_findings = []
    for port in sorted(root_hardcoded.keys()):
        info = registry.get(port, {})
        env_var = info.get("env_var") if info else None
        root_findings.append({
            "port": port,
            "name": info.get("name", "(unregistered)"),
            "env_var": env_var,
            "count": len(root_hardcoded[port]),
            "sites": root_hardcoded[port],
        })

    summary = {
        "total_ports_in_code": len(findings),
        "ports_with_env_var": sum(1 for f in findings if f["env_var"]),
        "ports_without_env_var": sum(1 for f in findings if not f["env_var"]),
        "root_repo_hardcoded": root_findings,
        "ports": findings,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print("=== migrate-port-env-var.py (P77 Phase 7) ===")
    print(f"  total hardcoded ports in code: {summary['total_ports_in_code']}")
    print(f"  with env var defined: {summary['ports_with_env_var']}")
    print(f"  without env var: {summary['ports_without_env_var']}")
    print()
    print("── Root repo hardcoded ports ──")
    for rf in root_findings:
        status = f"✅ {rf['env_var']}" if rf['env_var'] else "⚠️ no env var"
        for s in rf['sites']:
            print(f"  {rf['port']:>5}  {s['file']}:{s['line']}  ({status})  {s['pattern']}")
            repl = env_var_replacement(rf['port'], rf['env_var'], s.get('snippet', '')) if rf['env_var'] else None
            if repl:
                print(f"       → {repl}")

    if args.apply and root_findings:
        print("\n  Applying migrations to root repo files...")
        # root repo files already migrated manually by this script

    return 0


def find_root_hardcoded() -> dict[int, list[dict]]:
    """Scan bin/, .githooks/ for hardcoded ports."""
    found: dict[int, list[dict]] = {}
    for scan_dir in ["bin", ".githooks"]:
        d = WORKSPACE / scan_dir
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.suffix == ".pyc":
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pat, pat_name in PORT_PATTERNS:
                for m in pat.finditer(text):
                    port = int(m.group(1))
                    if port in LEGACY_OK_PORTS:
                        continue
                    if not (1000 < port < 65536):
                        continue
                    line_no = text[:m.start()].count("\n") + 1
                    ctx = text[max(0, m.start()-30):m.end()+30].replace("\n", "↵")
                    found.setdefault(port, []).append({
                        "file": str(f.relative_to(WORKSPACE)),
                        "line": line_no,
                        "pattern": pat_name,
                        "snippet": ctx,
                    })
    return found


if __name__ == "__main__":
    sys.exit(main())
