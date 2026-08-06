"""Cockpit agent onboarding command - guided setup for new agents."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[5]


def _check(label: str, ok: bool, detail: str = "") -> bool:
    status = "✅" if ok else "❌"
    suffix = f" ({detail})" if detail else ""
    print(f"  {status} {label}{suffix}")
    return ok


def _check_memory_os_surfaces(results: dict[str, bool]) -> None:
    """Phase: Memory OS cold-start surfaces (skill, SSOT, light gate, CLI entry)."""
    print("Phase 6: Memory OS (cold start)")
    skill = WORKSPACE / ".agents" / "skills" / "memory-recall" / "SKILL.md"
    ok_skill = skill.is_file()
    results["skill_memory-recall"] = ok_skill
    _check("skill 'memory-recall'", ok_skill)

    registry = WORKSPACE / ".omo" / "_truth" / "registry" / "memory-os.yaml"
    ops = WORKSPACE / ".omo" / "standards" / "memory-os-ops.md"
    ok_ssot = registry.is_file() and ops.is_file()
    results["memory_os_ssot"] = ok_ssot
    _check("memory-os registry + ops contract", ok_ssot)

    # Light gate (blocking SSOT; no Neo4j required)
    check_script = WORKSPACE / "bin" / "gac" / "check-memory-os-surfaces.py"
    if check_script.is_file():
        try:
            r = subprocess.run(
                ["python3", str(check_script)],
                capture_output=True,
                text=True,
                cwd=str(WORKSPACE),
                timeout=60,
            )
            gate_ok = r.returncode == 0
            results["memory_os_light_gate"] = gate_ok
            detail = "make memory-os-check" if gate_ok else (r.stdout or r.stderr or "exit!=0")[:80]
            _check("memory-os light gate", gate_ok, detail if not gate_ok else "ok")
        except Exception as e:
            results["memory_os_light_gate"] = False
            _check("memory-os light gate", False, str(e))
    else:
        results["memory_os_light_gate"] = False
        _check("memory-os light gate", False, "check-memory-os-surfaces.py missing")

    # CLI entry present in help_map / cli (static — no live Neo4j)
    help_map = WORKSPACE / "projects" / "cockpit" / "src" / "cockpit" / "commands" / "help_map.py"
    cli_py = WORKSPACE / "projects" / "cockpit" / "src" / "cockpit" / "cli.py"
    has_cli = False
    if help_map.is_file():
        t = help_map.read_text(encoding="utf-8", errors="replace")
        has_cli = "memory" in t
    if cli_py.is_file() and not has_cli:
        has_cli = 'add_parser(\n        "memory"' in cli_py.read_text(encoding="utf-8", errors="replace") or (
            '"memory"' in cli_py.read_text(encoding="utf-8", errors="replace")
        )
    results["memory_cli_entry"] = has_cli
    _check("cockpit memory CLI catalogued", has_cli)

    print("  next: source bin/memory-os-env.sh && cockpit memory status --json")
    print("        make memory-os-smoke · make memory-os-asof-seed")
    print()


def cmd_agent_onboard(args) -> int:
    """Run the agent onboarding checklist."""
    profile = getattr(args, "profile", None)
    json_output = getattr(args, "json", False)

    results: dict[str, bool] = {}

    print("╔══════════════════════════════════════════════╗")
    print("║     Agent Onboarding Checklist               ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    # 1. Agent profiles registered
    print("Phase 1: Identity Registration")
    try:
        r = subprocess.run(
            ["uv", "run", "--with", "pyyaml", "python", str(WORKSPACE / "bin" / "agent-workflow.py"), "agents"],
            capture_output=True,
            text=True,
            cwd=str(WORKSPACE),
            timeout=30,
        )
        agents_ok = r.returncode == 0
        results["agents_listed"] = agents_ok
        _check("agent-workflow agents", agents_ok)
        if profile and agents_ok:
            has_profile = profile in r.stdout
            results["profile_registered"] = has_profile
            _check(f"profile '{profile}' registered", has_profile)
        else:
            results["profile_registered"] = True
    except Exception as e:
        results["agents_listed"] = False
        _check("agent-workflow agents", False, str(e))
    print()

    # 2. Workflow lint
    print("Phase 2: Workflow Registry")
    try:
        r = subprocess.run(
            ["uv", "run", "--with", "pyyaml", "python", str(WORKSPACE / "bin" / "agent-workflow.py"), "lint"],
            capture_output=True,
            text=True,
            cwd=str(WORKSPACE),
            timeout=30,
        )
        lint_ok = r.returncode == 0
        results["workflow_lint"] = lint_ok
        _check("agent-workflow lint", lint_ok)
    except Exception as e:
        results["workflow_lint"] = False
        _check("agent-workflow lint", False, str(e))

    # 3. Workflows listed
    try:
        r = subprocess.run(
            ["uv", "run", "--with", "pyyaml", "python", str(WORKSPACE / "bin" / "agent-workflow.py"), "list"],
            capture_output=True,
            text=True,
            cwd=str(WORKSPACE),
            timeout=30,
        )
        list_ok = r.returncode == 0 and "agent-onboarding" in r.stdout
        results["onboarding_workflow"] = list_ok
        _check("agent-onboarding workflow registered", list_ok)
    except Exception as e:
        results["onboarding_workflow"] = False
        _check("agent-onboarding workflow registered", False, str(e))
    print()

    # 4. BOS services
    print("Phase 3: BOS URI Discovery")
    bos_yaml = WORKSPACE / "projects" / "agora" / "etc" / "bos-services.yaml"
    bos_ok = bos_yaml.is_file()
    results["bos_services_yaml"] = bos_ok
    _check("bos-services.yaml exists", bos_ok)
    print()

    # 5. Cockpit CLI
    print("Phase 4: Cockpit CLI")
    cockpit_ok = (WORKSPACE / "projects" / "cockpit" / "src" / "cockpit" / "cli.py").is_file()
    results["cockpit_cli"] = cockpit_ok
    _check("cockpit CLI available", cockpit_ok)
    print()

    # 6. Skills
    print("Phase 5: Skills")
    skills = ["agent-onboarding", "bos-service-discovery", "a2a-coordination", "project-governance"]
    for skill in skills:
        skill_path = WORKSPACE / ".agents" / "skills" / skill / "SKILL.md"
        ok = skill_path.is_file()
        results[f"skill_{skill}"] = ok
        _check(f"skill '{skill}'", ok)
    print()

    # 7. Memory OS cold start (ADR-0372)
    _check_memory_os_surfaces(results)

    # Summary
    all_ok = all(results.values())
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print("════════════════════════════════════════════════")
    if all_ok:
        print(f"  ✅ Onboarding checklist: {passed}/{total} passed")
        print("  Agent is ready to start working.")
        print("  Memory: cockpit memory status · skill memory-recall · bos://memory/mos/*")
    else:
        print(f"  ❌ Onboarding checklist: {passed}/{total} passed")
        print("  Fix failing items before starting work.")
    print()

    if json_output:
        print(json.dumps({"ok": all_ok, "passed": passed, "total": total, "results": results}, indent=2))

    return 0 if all_ok else 1
