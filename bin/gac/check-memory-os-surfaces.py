#!/usr/bin/env python3
"""CR-X4-MEMORY-OS-SURFACE-INTEGRITY: Memory OS light gate (blocking).

Validates SSOT files, env keys, ports, CLI/smoke surfaces, and help catalog test.
Also runs an ADVISORY (WARN-only) execution-seam check (ADR-0464 blind spot 1):
it reads <state-root>/runtime/mos/observations.jsonl to see whether a REAL
(non-fixture) MOS recall has been observed, instead of trusting the registry's
`status: phase10` declaration as a liveness proof.
Exit 0 = pass; exit 1 = hard fail (CI / make memory-os-check).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Required SSOT / ops surfaces (must exist for Memory OS to be "declared")
REQUIRED_PATHS = [
    ".omo/_truth/registry/memory-os.yaml",
    ".omo/_truth/registry/memory-rbac.yaml",
    ".omo/standards/memory-os-ops.md",
    ".omo/_knowledge/decisions/0372-memory-os-control-plane.md",
    "docs/architecture/memory-os.md",
    "docs/operations/memory-os-neo4j-local.md",
    "docs/operations/memory-os.env.example",
    "docs/operations/memory-os-epic-retro.md",
    "bin/memory-os-env.sh",
    "bin/memory-os-neo4j-up.sh",
    "bin/memory-os-smoke.sh",
    "bin/memory-os-asof-seed.sh",
    "bin/gac/check-memory-os-surfaces.py",
    ".agents/skills/memory-recall/SKILL.md",
    "projects/knowledge/kairon/packages/mos/pyproject.toml",
    "projects/cockpit/src/cockpit/commands/help_map.py",
    "projects/cockpit/src/cockpit/tests/test_help_discover_ssot.py",
    "projects/cockpit/src/cockpit/tests/test_status_memory_os_line.py",
    "protocols/port-registry.yaml",
]

REQUIRED_ENV_KEYS = (
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "NEO4J_HTTP_PORT",
    "NEO4J_BOLT_PORT",
)

REQUIRED_PORTS = (7474, 7687)


def _read(rel: str) -> str | None:
    p = REPO_ROOT / rel
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def check_required_paths() -> list[str]:
    missing: list[str] = []
    for rel in REQUIRED_PATHS:
        if not (REPO_ROOT / rel).is_file():
            missing.append(rel)
    return missing


def check_env_example() -> list[str]:
    errs: list[str] = []
    text = _read("docs/operations/memory-os.env.example")
    if text is None:
        return ["docs/operations/memory-os.env.example unreadable"]
    for key in REQUIRED_ENV_KEYS:
        if not re.search(rf"(?m)^{re.escape(key)}=", text):
            errs.append(f"env.example missing key: {key}")
    return errs


def check_cockpit_env_example() -> list[str]:
    errs: list[str] = []
    text = _read("projects/cockpit/.env.example")
    if text is None:
        # cockpit submodule may be sparse in some checkouts — soft fail only if path missing entirely
        return ["projects/cockpit/.env.example missing"]
    for key in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
        if key not in text:
            errs.append(f"cockpit .env.example missing: {key}")
    return errs


def check_ports() -> list[str]:
    errs: list[str] = []
    text = _read("protocols/port-registry.yaml")
    if text is None:
        return ["protocols/port-registry.yaml unreadable"]
    for port in REQUIRED_PORTS:
        # Accept either bare key "  7474:" or env map form
        if not re.search(rf"(?m)^\s*{port}\s*:", text) and f"{port}" not in text:
            errs.append(f"port {port} not registered in port-registry.yaml")
    # Prefer explicit neo4j naming when present
    if "neo4j" not in text.lower() and "NEO4J" not in text:
        errs.append("port-registry.yaml has no neo4j/NEO4J mention")
    return errs


def check_registry_ssot() -> list[str]:
    errs: list[str] = []
    text = _read(".omo/_truth/registry/memory-os.yaml")
    if text is None:
        return ["memory-os.yaml unreadable"]
    # Structural SSOT markers only. The former literal "phase10" needle was a
    # LIVENESS PROXY: the registry can declare phase10 while every production
    # backend defaults OFF (ADR-0464 blind spot 1). Liveness is now observed by
    # the seam check below, not asserted from a declaration marker.
    for needle in (
        "id: memory-os",
        "surface_check:",
        "bos://memory/mos/",
    ):
        if needle not in text:
            errs.append(f"memory-os.yaml missing marker: {needle}")
    return errs


def check_default_execution_seam() -> list[str]:
    """ADVISORY (WARN) — ADR-0464 blind spot 1: inert-by-default.

    Asserts observable evidence that the capability has executed a REAL
    (non-fixture) recall under DEFAULT configuration, read from the append-only
    seam file <state-root>/runtime/mos/observations.jsonl (written by
    `mos.observations.record_real_execution`, resolved at call time here via
    bin/lib/repo_root.py:state_root()).

    Shipped as WARN, never a hard error:
      - the seam is new, so no real execution may be recorded yet;
      - a hard error here would be a false red on every clean checkout / CI.
    Promotion path to ERROR (do NOT enable yet): once a baseline record is
    observed in production and committed as evidence for the owning BET, flip
    the "no real execution observed" branch to a hard error AND add a freshness
    window (last default-env record older than N days => FAIL).
    """
    try:
        lib = Path(__file__).resolve().parents[1] / "lib"
        if str(lib) not in sys.path:
            sys.path.insert(0, str(lib))
        from repo_root import state_root  # noqa: E402 — call-time import by design (ADR-0456)

        seam = state_root() / "runtime" / "mos" / "observations.jsonl"
    except Exception as exc:  # pragma: no cover - resolver is present in-repo
        return [f"ADR-0464 execution seam: resolver unavailable ({exc}); advisory skipped"]

    if not seam.is_file():
        return [
            "ADR-0464 execution seam: no real (non-fixture) MOS execution has been observed "
            f"({seam}); registry 'status: phase10' is a declaration, not liveness. "
            "ADVISORY — promote to ERROR once a baseline record exists."
        ]
    try:
        lines = [ln for ln in seam.read_text(encoding="utf-8").splitlines() if ln.strip()]
        records = [json.loads(ln) for ln in lines]
    except (OSError, json.JSONDecodeError) as exc:
        return [f"ADR-0464 execution seam: observation file unreadable ({exc}); advisory skipped"]
    real = [r for r in records if isinstance(r, dict) and r.get("data_mode") in ("live", "mixed")]
    if not real:
        return [
            "ADR-0464 execution seam: observation file present but contains no real (non-fixture) "
            "execution; the capability is still inert under default config. ADVISORY."
        ]
    if not any(r.get("default_env") is True for r in real):
        return [
            "ADR-0464 execution seam: real executions recorded ONLY under explicit live overrides "
            "(default_env=false); execution under DEFAULT configuration remains unproven. ADVISORY."
        ]
    return []


def check_help_catalog_mentions_memory() -> list[str]:
    errs: list[str] = []
    text = _read("projects/cockpit/src/cockpit/commands/help_map.py")
    if text is None:
        return ["help_map.py unreadable"]
    if 'name="memory"' not in text and "name='memory'" not in text and 'CmdRow("memory"' not in text:
        # accept various row constructors
        if not re.search(r'["\']memory["\']', text):
            errs.append("help_map.py does not catalog 'memory' command")
    return errs


def _collect() -> tuple[list[tuple[str, str]], list[str]]:
    """Run every check once.

    Returns (hard, soft): hard = [(check_id, message), ...] in the exact order
    the text output has always printed them; soft = human-readable warnings.
    """
    hard: list[tuple[str, str]] = []
    soft: list[str] = []

    missing = check_required_paths()
    hard.extend(("required_paths", f"missing required path: {m}") for m in missing)

    for check_id, check in (
        ("env_example", check_env_example),
        ("ports", check_ports),
        ("registry_ssot", check_registry_ssot),
        ("help_catalog", check_help_catalog_mentions_memory),
    ):
        hard.extend((check_id, msg) for msg in check())

    cockpit_env = check_cockpit_env_example()
    # cockpit env is required when submodule is present
    if (REPO_ROOT / "projects/cockpit").is_dir():
        hard.extend(("cockpit_env", msg) for msg in cockpit_env)
    else:
        soft.extend(cockpit_env)

    # ADR-0464 blind spot 1 — advisory only (never hard): the seam is new and a
    # hard error would be a false red before any real execution is recorded.
    soft.extend(check_default_execution_seam())

    return hard, soft


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check-memory-os-surfaces.py",
        description="Memory OS light gate (CR-X4-MEMORY-OS-SURFACE-INTEGRITY). "
        "Exit 0 = pass; exit 1 = hard fail (CI / make memory-os-check).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable JSON result (status + failed checks) instead of text",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    hard, soft = _collect()

    if args.json:
        # Machine-readable contract: status + failed checks (+ soft warnings).
        # Exit code stays identical to the text mode (0 pass / 1 hard fail).
        print(
            json.dumps(
                {
                    "status": "fail" if hard else "pass",
                    "failed_checks": [
                        {"check": check_id, "message": msg} for check_id, msg in hard
                    ],
                    "warnings": list(soft),
                    "required_paths": len(REQUIRED_PATHS),
                },
                ensure_ascii=False,
            )
        )
        return 1 if hard else 0

    print("Memory OS light gate (CR-X4-MEMORY-OS-SURFACE-INTEGRITY)")
    print(f"  required_paths: {len(REQUIRED_PATHS)}")
    if soft:
        print(f"  soft warnings ({len(soft)}):")
        for s in soft:
            print(f"    WARN {s}")
    if hard:
        print(f"  HARD FAIL ({len(hard)}):")
        for _check_id, msg in hard:
            print(f"    FAIL {msg}")
        print("  fix: restore SSOT/ops surfaces listed in .omo/standards/memory-os-ops.md")
        return 1

    print("  OK all required Memory OS surfaces present")
    print("  OK env.example keys + ports + registry + help catalog")
    return 0


if __name__ == "__main__":
    sys.exit(main())
