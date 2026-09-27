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
8. --dev-env --profile dev: 打印 dev-profile 端口覆盖 (NAME=PORT), 取值只来自
   protocols/port-registry.yaml 的 dev_ports 显式表 (ADR-0456 B2)

适用原则 (P77-5):
- port-registration-mandatory: 任何 service 端口必须先在 SSOT 注册, 否则 hard fail
- legacy-external-allowlist: 不归本仓管的外部服务 (otel / lm-studio / family-hub) 允许硬编码;
  本仓自己拉起的进程用的端口不算外部工具 (5173 于 2026-09-26 由此改判为已注册自有端口)
- environment-variable-preferred: 优先用 env var, 而不是字面量

数据源:
- ecos port: projects/ecos/port-registry.yaml
- protocols port: protocols/port-registry.yaml
- dev 端口段: protocols/port-registry.yaml 的 dev_band + dev_ports
- 每仓 src/ 代码

豁免 (LEGACY_OK_PORTS): 外部标准 / 外部仓端口 (otel 4318 / lm-studio 1234 / family-hub 3000+3001)。
准入判据是"不归本仓管", 不是"是某个工具的默认值"。dev 端口 (15000-15099) 故意**不**进注册 union:
字面量出现在源码里必须被判为未注册, dev 值只能从 --dev-env 打印的环境变量来。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


# 外部标准 / 工具端口 (允许硬编码, 不算 unregistered)
# rationale: 这些是行业标准或外部服务, 不归我们 SSOT 管
# 准入判据 (ADR-0456 B2): 只有"不归本仓管的端口"才能进这张表。本仓自己拉起的进程
# 用的端口必须进 protocols/port-registry.yaml 的 ports: —— 否则门禁无法表达"谁在听"。
# 5173 (cockpit-ui vite) 曾以此处"工具默认"名义被豁免, 2026-09-26 改判为已注册自有端口。
LEGACY_OK_PORTS = {
    1234,  # LM Studio (本地 LLM)
    3000,  # family-hub dashboard (外部仓)
    3001,  # family-hub api (外部仓)
    4318,  # OpenTelemetry OTLP (行业标准)
}


# 检测模式: port-context (4-5 digit number)
# 严格定义: PORT = NNNN / port=NNNN / --port NNNN / host:port[/path]
PORT_PATTERNS = [
    (re.compile(r"\bPORT\s*=\s*(\d{4,5})\b"), "PORT = NNNN"),
    (re.compile(r"\bport\s*[=:]\s*(\d{4,5})\b"), "port=NNNN"),
    (re.compile(r"--port[=\s]+(\d{4,5})\b"), "--port NNNN"),
    (re.compile(r"://[^/]+:(\d{4,5})(?:[/\b]|$)"), "host:port"),
    (re.compile(r"\blocalhost:(\d{4,5})\b"), "localhost:port"),
    (re.compile(r"\b127\.0\.0\.1:(\d{4,5})\b"), "127.0.0.1:port"),
    (re.compile(r"\b0\.0\.0\.0:(\d{4,5})\b"), "0.0.0.0:port"),
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


def load_dev_ports() -> tuple[dict[str, dict], tuple[int, int]]:
    """Read the dev-profile port band + explicit dev_ports table (ADR-0456 B2).

    Returns ({service_name: {env, port, prod_port}}, (band_from, band_to)).
    dev_ports is intentionally NOT merged into the registered union: a dev port
    written as a literal in source must still count as unregistered.
    """
    data = load_yaml(WORKSPACE / "protocols" / "port-registry.yaml") or {}
    band = data.get("dev_band") or {}
    try:
        edges = (int(band["from"]), int(band["to"]))
    except (KeyError, TypeError, ValueError):
        raise SystemExit("protocols/port-registry.yaml 缺 dev_band.from/to") from None
    table: dict[str, dict] = {}
    for name, entry in (data.get("dev_ports") or {}).items():
        if not isinstance(entry, dict):
            raise SystemExit(f"dev_ports.{name} 必须是 mapping")
        try:
            table[str(name)] = {
                "env": str(entry["env"]),
                "port": int(entry["port"]),
                "prod_port": int(entry["prod_port"]),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit(f"dev_ports.{name} 缺 env/port/prod_port: {exc}") from None
    return table, edges


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
                    line_no = text[: m.start()].count("\n") + 1
                    # 检查是否是 env var fallback (os.environ.get("X", "PORT"))
                    line_start = max(0, m.start() - 120)
                    line_end = min(len(text), m.end() + 30)
                    context = text[line_start:line_end]
                    is_env_fallback = "os.environ.get(" in context or "os.environ.get (" in context
                    found.setdefault(port, []).append(
                        {
                            "file": str(f.relative_to(WORKSPACE)),
                            "line": line_no,
                            "pattern": pat_name,
                            "env_fallback": is_env_fallback,
                        }
                    )
    return found


def render_dev_env(profile: str, registered: set[int]) -> int:
    """Print the dev-profile port overlay as NAME=PORT lines (one per dev_ports entry).

    prod prints nothing: production takes its ports from the registry defaults.
    dev re-asserts the C3 invariants before emitting, so an overlay that would
    collide with a live production port fails here instead of silently binding it.
    """
    if profile != "dev":
        return 0
    table, (band_from, band_to) = load_dev_ports()
    if not table:
        raise SystemExit("dev_ports 表为空 — 无法为 dev profile 生成端口覆盖")
    dev_ports = [entry["port"] for entry in table.values()]
    errors = []
    for name, entry in sorted(table.items()):
        if not band_from <= entry["port"] <= band_to:
            errors.append(f"dev_ports.{name}.port {entry['port']} 不在 dev_band {band_from}-{band_to}")
        if entry["prod_port"] not in registered:
            errors.append(f"dev_ports.{name}.prod_port {entry['prod_port']} 未在 ports: 注册")
    if len(set(dev_ports)) != len(dev_ports):
        errors.append(f"dev_ports 端口不唯一 (非单射): {sorted(dev_ports)}")
    clash = set(dev_ports) & (registered | LEGACY_OK_PORTS)
    if clash:
        errors.append(f"dev 端口与已注册/豁免端口重叠: {sorted(clash)}")
    if errors:
        for err in errors:
            print(f"❌ {err}", file=sys.stderr)
        return 1
    for name, entry in sorted(table.items()):
        print(f"{entry['env']}={entry['port']}  # dev 覆盖 {entry['prod_port']} ({name})")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--threshold", type=int, default=0, help="unregistered port 阈值 (默认 0, hard)")
    p.add_argument(
        "--env-var-check",
        action="store_true",
        help="env-only 端口检查: 标记需要 env var 的 bare 硬编码",
    )
    p.add_argument(
        "--dev-env",
        action="store_true",
        help="打印 dev-profile 端口覆盖 (NAME=PORT), 取值只来自 protocols/port-registry.yaml dev_ports",
    )
    p.add_argument(
        "--profile",
        choices=["dev", "prod"],
        help="配合 --dev-env 使用。故意不读 OMOSTATION_PROFILE: 该 env 的首个消费者是 B3 服务注册 "
        "(ADR-0456 §契约面), 端口打印不抢这个顺序",
    )
    args = p.parse_args()

    registered = load_registered_ports()
    if args.dev_env:
        if not args.profile:
            p.error("--dev-env 需要显式 --profile dev|prod")
        return render_dev_env(args.profile, registered)

    env_vars = load_env_vars()
    hardcoded = collect_hardcoded_ports()

    # unregistered (硬编码但未注册) = hardcoded keys - registered - legacy_ok
    unregistered_ports = set(hardcoded.keys()) - registered - LEGACY_OK_PORTS
    # 按代码使用数排序
    unregistered_list = sorted(
        [{"port": port, "count": len(hardcoded[port]), "sites": hardcoded[port][:5]} for port in unregistered_ports],
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
    dev_table, dev_band = load_dev_ports()
    summary = {
        "registered_total": len(registered),
        "dev_band": list(dev_band),
        "dev_ports": {name: entry["port"] for name, entry in sorted(dev_table.items())},
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
        print("=== hardcoded-port-detector (P77 Phase 5) ===")
        print(f"  registered (union ecos+protocols): {summary['registered_total']}")
        print(f"  hardcoded distinct ports (in code): {summary['hardcoded_distinct_ports']}")
        print(f"  unregistered (hardcoded but NOT in SSOT): {summary['unregistered']}")
        print(f"  env var fallback (P77-7-2 OK): {summary['env_fallback_usages_count']}")
        print(f"  bare hardcoded (修真修真, should use env var): {summary['bare_hardcoded_usages_count']}")
        print(f"  env vars defined in SSOT: {summary['env_vars_defined']}")
        print(f"  legacy usages (external/standard, 豁免): {summary['legacy_usages_count']}")
        print(f"  dev band {summary['dev_band'][0]}-{summary['dev_band'][1]}: {summary['dev_ports']}")
        print("  (dev 取值: --dev-env --profile dev; dev 端口不进注册 union, 写字面量仍算未注册)")
        print()
        if summary["bare_hardcoded_usages_count"] > 0:
            print("📋 需要迁移的硬编码端口:")
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
