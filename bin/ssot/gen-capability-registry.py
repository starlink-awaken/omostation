#!/usr/bin/env python3
"""Generate docs/generated/capability-registry.yaml — multi-channel capability SSOT (P2.1).

Sources (read-only discovery):
  - projects/agora/etc/bos-services.yaml
  - cockpit --help top-level commands (or fallback parse of cli.py)
  - agora @mcp.tool definitions under projects/agora/src/agora/server/
  - .agents/skills/*/SKILL.md frontmatter
  - .omo/_truth/registry/agent-workflows.yaml workflows

Usage:
  python3 bin/ssot/gen-capability-registry.py
  python3 bin/ssot/gen-capability-registry.py --stdout
"""
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
OUT = WORKSPACE / "docs/generated/capability-registry.yaml"
BOS_YAML = WORKSPACE / "projects/agora/etc/bos-services.yaml"
AGORA_SERVER = WORKSPACE / "projects/agora/src/agora/server"
SKILLS = WORKSPACE / ".agents/skills"
WORKFLOWS = WORKSPACE / ".omo/_truth/registry/agent-workflows.yaml"
COCKPIT_CLI = WORKSPACE / "projects/cockpit/src/cockpit/cli.py"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_bos() -> list[dict]:
    docs = list(yaml.safe_load_all(BOS_YAML.read_text(encoding="utf-8")))
    for d in docs:
        if isinstance(d, dict) and "services" in d:
            return [
                {
                    "uri": s.get("uri"),
                    "domain": s.get("domain"),
                    "package": s.get("package"),
                    "action": s.get("action"),
                    "status": s.get("status") or "active",
                    "transport": s.get("transport"),
                    "description": (s.get("description") or "")[:200],
                    "channels": ["bos"],
                }
                for s in (d["services"] or [])
                if isinstance(s, dict)
            ]
    return []


def load_mcp_tools() -> list[dict]:
    tools: list[dict] = []
    if not AGORA_SERVER.is_dir():
        return tools
    pat = re.compile(
        r"@mcp\.tool\([^)]*\)\s*(?:\n[ \t]*@[^\n]+)*\s*(?:async\s+)?def\s+(\w+)\s*\(",
        re.M,
    )
    for py in sorted(AGORA_SERVER.rglob("*.py")):
        text = py.read_text(encoding="utf-8", errors="ignore")
        for m in pat.finditer(text):
            tools.append(
                {
                    "id": m.group(1),
                    "source": str(py.relative_to(WORKSPACE)),
                    "channels": ["agora_mcp"],
                }
            )
    # unique by id
    seen: set[str] = set()
    uniq = []
    for t in tools:
        if t["id"] in seen:
            continue
        seen.add(t["id"])
        uniq.append(t)
    return uniq


def load_cockpit_commands() -> list[str]:
    # Prefer live help; fall back to cli.py brace list
    try:
        r = subprocess.run(
            [
                "uv",
                "run",
                "--project",
                str(WORKSPACE / "projects/cockpit"),
                "cockpit",
                "--help",
            ],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        text = r.stdout or ""
        m = re.search(r"\{([^{}]*research[^{}]*c2g)\}", text, re.S)
        if m:
            raw = re.sub(r"\s+", "", m.group(1))
            return [c for c in raw.split(",") if c]
    except Exception:  # noqa: BLE001
        pass
    if COCKPIT_CLI.is_file():
        text = COCKPIT_CLI.read_text(encoding="utf-8", errors="ignore")
        names = re.findall(r'sub\.add_parser\(\s*"([a-z0-9\-]+)"', text)
        # unique preserve order
        seen: set[str] = set()
        out = []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out
    return []


def load_skills() -> list[dict]:
    rows = []
    if not SKILLS.is_dir():
        return rows
    for d in sorted(SKILLS.iterdir()):
        skill = d / "SKILL.md"
        if not d.is_dir() or not skill.is_file():
            continue
        text = skill.read_text(encoding="utf-8", errors="ignore")
        name = d.name
        desc = ""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                    name = meta.get("name") or name
                    desc = (meta.get("description") or "").strip()
                except Exception:  # noqa: BLE001
                    pass
        if not desc:
            for line in text.splitlines():
                if line.startswith("# "):
                    desc = line[2:].strip()
                    break
        rows.append(
            {
                "id": d.name,
                "name": name,
                "description": desc[:240],
                "path": str(skill.relative_to(WORKSPACE)),
                "channels": ["skill"],
            }
        )
    return rows


def load_workflows() -> list[dict]:
    if not WORKFLOWS.is_file():
        return []
    docs = list(yaml.safe_load_all(WORKFLOWS.read_text(encoding="utf-8")))
    data: dict = {}
    for d in docs:
        if isinstance(d, dict):
            data.update(d)
    wfs = data.get("workflows") or []
    rows = []
    if isinstance(wfs, list):
        for w in wfs:
            if not isinstance(w, dict):
                continue
            rows.append(
                {
                    "id": w.get("id"),
                    "description": (w.get("description") or w.get("purpose") or "")[:200],
                    "channels": ["agent_workflow"],
                }
            )
    return rows


def build() -> dict:
    bos = load_bos()
    mcp = load_mcp_tools()
    cli = load_cockpit_commands()
    skills = load_skills()
    workflows = load_workflows()
    status_c: dict[str, int] = {}
    for s in bos:
        st = s.get("status") or "active"
        status_c[st] = status_c.get(st, 0) + 1
    return {
        "version": "1.0.0",
        "generated_at": _now(),
        "generator": "bin/ssot/gen-capability-registry.py",
        "totals": {
            "bos_services": len(bos),
            "bos_by_status": status_c,
            "agora_mcp_tools": len(mcp),
            "cockpit_top_level_commands": len(cli),
            "skills": len(skills),
            "agent_workflows": len(workflows),
        },
        "cockpit_commands": [{"id": c, "channels": ["cockpit_cli"]} for c in cli],
        "agora_mcp_tools": mcp,
        "bos_services": bos,
        "skills": skills,
        "agent_workflows": workflows,
        "notes": [
            "BOS status=unimplemented/deprecated are excluded from agora routing by default "
            "(see projects/agora/src/agora/mcp/resolver/bos_registry.py).",
            "Use cockpit bos list --all to inspect non-routable YAML rows.",
            "Minimum external-agent tool belt: see docs/operations/external-agent-attach-card.md",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args(argv)
    reg = build()
    body = yaml.safe_dump(reg, allow_unicode=True, sort_keys=False)
    if args.stdout:
        print(body)
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(
            "# AUTO-GENERATED by bin/ssot/gen-capability-registry.py — do not edit by hand\n"
            + body,
            encoding="utf-8",
        )
        print(f"✅ wrote {OUT.relative_to(WORKSPACE)}")
        t = reg["totals"]
        print(
            f"   bos={t['bos_services']} mcp={t['agora_mcp_tools']} "
            f"cli={t['cockpit_top_level_commands']} skills={t['skills']} wf={t['agent_workflows']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
