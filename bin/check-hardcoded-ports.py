#!/usr/bin/env python3
"""check-hardcoded-ports.py — P77 Phase 5/7 跨仓端口硬编码扫描 + env var 检验

按 STRAT-P77 § 2 Phase 5/7 设计:

1. 读 projects/ecos/port-registry.yaml + protocols/port-registry.yaml → 已注册 union set
2. 扫 projects/*/src/ 真**代码** (非 test, 非 docstring) 中 port=NNNN / :NNNN / PORT = NNNN 模式
3. 找 hardcoded_unregistered (在代码里硬编码但未在 SSOT 注册)
4. 找 registered_usages 并分类: env_fallback (P77-7-2 OK) vs bare_hardcoded (需迁移)
5. 读 env_vars SSOT, 为 bare_hardcoded 显示建议的 env var
6. --env-var-check: env-only 类型端口 (7422/7456/8090) 裸硬编码 → warning
7. 输出 violations table + threshold (默认 0) + exit code

适用原则 (P77-5):
- port-registration-mandatory: 任何 service 端口必须先在 SSOT 注册, 否则 hard fail
- legacy-external-allowlist: 外部服务 (otel/vite/lm-studio/family-hub) 允许硬编码
- environment-variable-preferred: 优先用 env var, 而不是字面量

数据源:
- ecos port: projects/ecos/port-registry.yaml
- protocols port: protocols/port-registry.yaml
- 每仓 src/ 代码

豁免 (LEGACY_OK_PORTS): 外部标准 / 工具端口 (otel 4318 / vite 5173 / lm-studio 1234)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]


# 外部标准 / 工具端口 (允许硬编码, 不算 unregistered)
# rationale: 这些是行业标准或外部服务, 不归我们 SSOT 管
LEGACY_OK_PORTS = {
    1234,    # LM Studio (本地 LLM)
    3000,    # family-hub dashboard (外部仓)
    3001,    # family-hub api (外部仓)
    4318,    # OpenTelemetry OTLP (行业标准)
    5173,    # Vite dev server (工具默认)
}


# 检测模式: port-context (4-5 digit number)
# 严格定义: PORT = NNNN / port=NNNN / --port NNNN / host:port[/path]
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
    except yaml.YAMLError as exc:
        print(f"⚠️ parse error: {p}: {exc}", file=sys.stderr)
        return None


def _strip_yaml_comment(value: str) -> str:
    """YAML parser 不会 strip inline comment ('value # comment')."""
    if "  #" in value:
        return value.split("  #", 1)[0].strip()
    if "\t#" in value:
        return value.split("\t#", 1)[0].strip()
    return value.strip()


def load_registered_ports() -> set[int]:
    """Union of ecos + protocols port-registry."""
    ports: set[int] = set()
    for f in [
        WORKSPACE / "projects" / "ecos" / "port-registry.yaml",
        WORKSPACE / "protocols" / "port-registry.yaml",
    ]:
        data = load_yaml(f) or {}
        if isinstance(data, dict):
            for k in (data.get("ports") or {}).keys():
                if str(k).isdigit():
                    ports.add(int(k))
    return ports


def load_env_vars() -> dict[int, str]:
    """Load env_var mapping from port-registry.yaml."""
    env_vars: dict[int, str] = {}
    for f in [
        WORKSPACE / "projects" / "ecos" / "port-registry.yaml",
        WORKSPACE / "protocols" / "port-registry.yaml",
    ]:
        data = load_yaml(f) or {}
        if isinstance(data, dict):
            for k, v in (data.get("env_vars") or {}).items():
                try:
                    env_vars[int(k)] = str(v)
                except (ValueError, TypeError):
                    pass
    return env_vars


def collect_hardcoded_ports() -> dict[int, list[dict]]:
    """扫 projects/*/src/ 真代码 (非 test, 非 docstring) 中硬编码 port."""
    found: dict[int, list[dict]] = {}
    for proj_dir in (WORKSPACE / "projects").iterdir():
        if not (proj_dir / "src").is_dir():
            continue
        if proj_dir.name in ("venv",) or proj_dir.name.startswith("."):
            continue
        for f in (proj_dir / "src").rglob("*.py"):
            parts = f.parts
            if "test" in parts or "tests" in parts or "__pycache__" in parts:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pat, pat_name in PORT_PATTERNS:
                for m in pat.finditer(text):
                    port = int(m.group(1))
                    if not (1000 < port < 65536):
                        continue
                    line_no = text[:m.start()].count("\n") + 1
                    # 检查是否是 env var fallback (os.environ.get("X", "PORT"))
                    line_start = max(0, m.start() - 120)
                    line_end = min(len(text), m.end() + 30)
                    context = text[line_start:line_end]
                    is_env_fallback = "os.environ.get(" in context or "os.environ.get (" in context
                    found.setdefault(port, []).append({
                        "file": str(f.relative_to(WORKSPACE)),
                        "line": line_no,
                        "pattern": pat_name,
                        "env_fallback": is_env_fallback,
                    })
    return found


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--threshold", type=int, default=0,
                   help="unregistered port 阈值 (默认 0, hard)")
    p.add_argument("--env-var-check", action="store_true",
                   help="env-only 端口检查: 标记需要 env var 的 bare 硬编码")
    args = p.parse_args()

    registered = load_registered_ports()
    env_vars = load_env_vars()
    hardcoded = collect_hardcoded_ports()

    # unregistered (硬编码但未注册) = hardcoded keys - registered - legacy_ok
    unregistered_ports = set(hardcoded.keys()) - registered - LEGACY_OK_PORTS
    # 按代码使用数排序
    unregistered_list = sorted(
        [{"port": port, "count": len(hardcoded[port]), "sites": hardcoded[port][:5]}
         for port in unregistered_ports],
        key=lambda x: -x["count"],
    )

    # 分类 registered: env_fallback vs bare_hardcoded
    registered_usages = []
    env_fallback_usages = []
    bare_hardcoded_usages = []
    for port in sorted(hardcoded.keys() & registered):
        entries = hardcoded[port]
        env_fb = [e for e in entries if e.get("env_fallback")]
        bare = [e for e in entries if not e.get("env_fallback")]
        total = len(entries)
        registered_usages.append({"port": port, "count": total})
        env_fallback_usages.append({"port": port, "count": len(env_fb), "env_var": env_vars.get(port)})
        bare_hardcoded_usages.append({"port": port, "count": len(bare), "env_var": env_vars.get(port)})
        # 输出 env-only 端口 bare 硬编码 warning
        if args.env_var_check and bare and port in (7422, 7456, 8090):
            for e in bare[:3]:
                print(f"  ⚠️  env-only port {port} bare hardcoded: {e['file']}:{e['line']} ({e['pattern']})")

    # legacy usages (外部标准 / 工具) — 算豁免
    legacy_usages = [
        {"port": port, "count": len(hardcoded.get(port, []))}
        for port in sorted(LEGACY_OK_PORTS & set(hardcoded.keys()))
    ]

    fc = sum(x["count"] for x in env_fallback_usages)
    bc = sum(x["count"] for x in bare_hardcoded_usages)
    summary = {
        "registered_total": len(registered),
        "hardcoded_distinct_ports": len(hardcoded),
        "unregistered": len(unregistered_list),
        "env_fallback_usages_count": fc,
        "bare_hardcoded_usages_count": bc,
        "registered_usages_count": fc + bc,
        "legacy_usages_count": sum(x["count"] for x in legacy_usages),
        "env_vars_defined": len(env_vars),
        "threshold": args.threshold,
        "ok": len(unregistered_list) <= args.threshold,
        "unregistered_list": unregistered_list,
        "registered_usages": registered_usages,
        "env_fallback_usages": env_fallback_usages,
        "bare_hardcoded_usages": bare_hardcoded_usages,
        "legacy_usages": legacy_usages,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"=== hardcoded-port-detector (P77 Phase 5) ===")
        print(f"  registered (union ecos+protocols): {summary['registered_total']}")
        print(f"  hardcoded distinct ports (in code): {summary['hardcoded_distinct_ports']}")
        print(f"  unregistered (hardcoded but NOT in SSOT): {summary['unregistered']}")
        print(f"  env var fallback (P77-7-2 OK): {summary['env_fallback_usages_count']}")
        print(f"  bare hardcoded (修真修真, should use env var): {summary['bare_hardcoded_usages_count']}")
        print(f"  env vars defined in SSOT: {summary['env_vars_defined']}")
        print(f"  legacy usages (external/standard, 豁免): {summary['legacy_usages_count']}")
        print()
        if summary["bare_hardcoded_usages_count"] > 0:
            print(f"📋 需要迁移的硬编码端口:")
            for u in bare_hardcoded_usages:
                if u["count"] > 0:
                    ev = u["env_var"] or "(no env var defined)"
                    print(f"  port {u['port']} ({u['count']} sites, env: {ev})")
        if summary["unregistered"] > args.threshold:
            print(f"❌ {summary['unregistered']} hardcoded port(s) 未在 SSOT 注册:")
            for u in unregistered_list:
                print(f"  port {u['port']} ({u['count']} sites):")
                for s in u["sites"][:3]:
                    print(f"    {s['file']}:{s['line']} ({s['pattern']})")
        else:
            print(f"✅ hardcoded ports {summary['unregistered']} ≤ threshold {args.threshold}")

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
