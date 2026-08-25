#!/usr/bin/env python3
"""SFOP/DFSQ slot laws — COMP-WS self-report, unique S, runtime discipline.

Laws:
  CR-SFOP-01  COMP-WS must declare legal sfop_slot + dao_layer
  CR-SFOP-02  unique active S-slot = COMP-WS-omo
  CR-SFOP-04  P/O may stay vacant (documented, not an error)
  CR-SFOP-05  H must not call B directly; F is the only H↔B bridge.
              cockpit.adapters is the allowed H-side B-port. Other H files
              fail-closed unless in the line-stable baseline.
  CR-DFSQ-01  dao-layer components must not appear on the cron ledger
  CR-DFSQ-02  qi-layer trees must not author L0 type: required constraints
  CR-X3-NS-001  north-star numerator must not be governance self-data
                (renamed out of the SFOP family; was CR-SFOP-03)

Usage:
    python3 bin/gac/check-sfop-slots.py
    python3 bin/gac/check-sfop-slots.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NODES = ROOT / "projects/ecos/src/ecos/ssot/mof/nodes"
DEFAULT_REGISTRY = ROOT / "docs/project-registry.yaml"
DEFAULT_CRON = ROOT / ".omo/cron/registry.yaml"
DEFAULT_BASELINE = ROOT / ".omo/_truth/registry/sfop-hb-call-baseline.txt"
DEFAULT_X3 = ROOT / ".omo/_truth/x3-value-stack.yaml"

SLOTS = {"K", "H", "P", "C", "S", "B", "J", "O", "F"}
DAO = {"dao", "fa", "shu", "qi"}
VACANT_ALLOWED = {"P", "O"}
DISPATCHER_ID = "COMP-WS-omo"
ARCHIVED_PROJECTS = {"mesh-router"}
EXTERNAL_BACKENDS = {"external-capability-runtime"}
# Direct H→B is the SFOP adjacency law. F (agora / bus-foundation) is the bridge.
B_PROJECTS = {"aetherforge", "omlxc", "runtime", "metaos"}
H_PROJECTS = {"cockpit", "cockpit-ui", "family-hub"}
PYTHON_IMPORT = re.compile(
    r"^\s*(?:from\s+([A-Za-z0-9_]+)(?:\.[A-Za-z0-9_.]+)?\s+import|import\s+([A-Za-z0-9_]+))",
    re.MULTILINE,
)
BIN_IN_COMMAND = re.compile(r"(?:projects/[A-Za-z0-9_./-]+|bin/[A-Za-z0-9_./-]+\.(?:py|sh))")
FORBIDDEN_NS_TOKENS = (
    "gac-local-gate",
    "health_score",
    "pr_count",
    "pr-count",
    "bet_done",
    "scorecard",
    "gac_green",
)


def _load(path: Path):
    if yaml is None:
        raise RuntimeError("pyyaml required")
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


def _is_external(name: str, meta: dict) -> bool:
    if name == "toolbox":
        return True
    backend = str(meta.get("build_backend") or "")
    return backend in EXTERNAL_BACKENDS


def _stable_hb_key(rel: str, caller: str, callee: str) -> str:
    return f"{rel}:H->B:{caller}->{callee}"


def _normalize_baseline_key(key: str) -> str:
    """Accept both `file:line:H->B:...` and `file:H->B:...`."""
    parts = key.split(":H->B:")
    if len(parts) != 2:
        return key
    left, right = parts
    left = re.sub(r":\d+$", "", left)
    return f"{left}:H->B:{right}"


def _is_adapter_seam(rel: str) -> bool:
    return "/adapters/" in rel.replace("\\", "/")


def _load_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        keys.add(_normalize_baseline_key(text))
    return keys


def _path_to_project(rel: str) -> str | None:
    parts = Path(rel).parts
    if not parts:
        return None
    if parts[0] == "projects":
        if len(parts) >= 2 and parts[1] == "knowledge":
            return "knowledge"
        if len(parts) >= 2:
            return parts[1]
        return None
    if parts[0] == "bin":
        return "omo"
    return None


def _scan_hb_calls(projects_root: Path, repo_root: Path) -> list[dict]:
    findings: list[dict] = []
    if not projects_root.is_dir():
        return findings
    for h_name in sorted(H_PROJECTS):
        src = projects_root / h_name
        if not src.is_dir():
            continue
        for path in src.rglob("*.py"):
            if "__pycache__" in path.parts or path.name.startswith("test_"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in PYTHON_IMPORT.finditer(text):
                target = match.group(1) or match.group(2)
                if target not in B_PROJECTS:
                    continue
                try:
                    rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
                except ValueError:
                    rel = str(path)
                findings.append(
                    {
                        "file": rel,
                        "caller": h_name,
                        "callee": target,
                        "seam": _is_adapter_seam(rel),
                        "key": _stable_hb_key(rel, h_name, target),
                    }
                )
    return findings


def _scan_qi_l0(projects_root: Path, qi_projects: set[str], repo_root: Path) -> list[str]:
    hits: list[str] = []
    for name in sorted(qi_projects):
        root = projects_root / name
        if not root.is_dir():
            continue
        for path in root.rglob("*.yaml"):
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "type: required" not in text:
                continue
            if "id: CR-" not in text and "L0-constraints" not in path.name and "l0" not in path.name.lower():
                continue
            try:
                rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                rel = str(path)
            hits.append(rel)
    return hits


def _cron_jobs(path: Path) -> list[dict]:
    data = _load(path)
    if not isinstance(data, dict):
        return []
    jobs = data.get("jobs") or []
    return [j for j in jobs if isinstance(j, dict)]


def _x3_self_data(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    hits = [tok for tok in FORBIDDEN_NS_TOKENS if tok in text]
    return hits


def check(
    *,
    nodes_dir: Path | None = None,
    registry_path: Path | None = None,
    cron_registry_path: Path | None = None,
    projects_root: Path | None = None,
    baseline_path: Path | None = None,
    x3_path: Path | None = None,
    repo_root: Path | None = None,
    skip_call_scan: bool = False,
) -> dict:
    repo_root = Path(repo_root) if repo_root is not None else ROOT
    nodes_dir = Path(nodes_dir) if nodes_dir is not None else DEFAULT_NODES
    registry_path = Path(registry_path) if registry_path is not None else DEFAULT_REGISTRY
    cron_registry_path = (
        Path(cron_registry_path) if cron_registry_path is not None else DEFAULT_CRON
    )
    projects_root = Path(projects_root) if projects_root is not None else repo_root / "projects"
    baseline_path = Path(baseline_path) if baseline_path is not None else DEFAULT_BASELINE
    x3_path = Path(x3_path) if x3_path is not None else DEFAULT_X3

    errors: list[str] = []
    warnings: list[str] = []
    annotated: list[dict] = []
    s_holders: list[str] = []
    occupied: set[str] = set()
    project_dao: dict[str, str] = {}
    project_slot: dict[str, str] = {}
    qi_projects: set[str] = set()

    if not nodes_dir.is_dir():
        warnings.append(f"CR-SFOP-01: COMP-WS nodes dir missing ({nodes_dir}); skip slot scan")
        return {
            "ok": True,
            "errors": errors,
            "warnings": warnings,
            "components": annotated,
            "s_holders": s_holders,
            "vacant_slots": sorted(VACANT_ALLOWED),
            "hb_seam_files": [],
            "constraint_ids": [
                "CR-SFOP-01",
                "CR-SFOP-02",
                "CR-SFOP-04",
                "CR-SFOP-05",
                "CR-DFSQ-01",
                "CR-DFSQ-02",
                "CR-X3-NS-001",
            ],
        }

    nodes = sorted(nodes_dir.glob("COMP-WS-*.yaml"))
    if not nodes:
        errors.append(f"CR-SFOP-01: no COMP-WS-*.yaml under {nodes_dir}")

    for path in nodes:
        data = _load(path) or {}
        if not isinstance(data, dict):
            continue
        cid = str(data.get("id") or path.stem)
        status = str(data.get("status") or "")
        props = data.get("properties") if isinstance(data.get("properties"), dict) else {}
        slot = props.get("sfop_slot") or data.get("sfop_slot")
        dao = props.get("dao_layer") or data.get("dao_layer")
        if slot not in SLOTS:
            errors.append(f"CR-SFOP-01: {cid}: missing/invalid sfop_slot={slot!r}")
        if dao not in DAO:
            errors.append(f"CR-SFOP-01: {cid}: missing/invalid dao_layer={dao!r}")
        if slot in SLOTS:
            occupied.add(str(slot))
        if slot == "S" and status == "active":
            s_holders.append(cid)
        project_name = cid.removeprefix("COMP-WS-")
        if dao in DAO:
            project_dao[project_name] = str(dao)
        if slot in SLOTS:
            project_slot[project_name] = str(slot)
        if dao == "qi":
            qi_projects.add(project_name)
        annotated.append(
            {
                "id": cid,
                "status": status,
                "sfop_slot": slot,
                "dao_layer": dao,
                "path": str(path),
            }
        )

    if len(s_holders) > 1:
        errors.append(f"CR-SFOP-02: multiple active S-slot components: {s_holders}")
    elif s_holders and s_holders != [DISPATCHER_ID]:
        errors.append(f"CR-SFOP-02: S-slot holder {s_holders} != {DISPATCHER_ID}")
    elif not s_holders and nodes:
        errors.append("CR-SFOP-02: no active S-slot dispatcher declared (expected COMP-WS-omo)")

    vacant = sorted(slot for slot in VACANT_ALLOWED if slot not in occupied)

    if registry_path.exists():
        reg = _load(registry_path) or {}
        projects = reg.get("projects") if isinstance(reg, dict) and isinstance(reg.get("projects"), dict) else {}
        present = {p.stem.replace("COMP-WS-", "") for p in nodes}
        for name, meta in projects.items():
            if not isinstance(meta, dict):
                continue
            if meta.get("status") == "archived" or name in ARCHIVED_PROJECTS:
                continue
            if _is_external(name, meta):
                continue
            if name not in present:
                warnings.append(f"registry project {name!r} has no COMP-WS-{name}.yaml")

    # CR-DFSQ-01: dao must not sit on the cron execution ledger.
    for job in _cron_jobs(cron_registry_path):
        command = str(job.get("command") or "")
        job_id = str(job.get("id") or job.get("name") or "cron-job")
        for hit in BIN_IN_COMMAND.findall(command):
            project = _path_to_project(hit)
            dao = project_dao.get(project or "")
            if dao == "dao":
                errors.append(
                    f"CR-DFSQ-01: cron {job_id!r} executes dao-layer project "
                    f"{project!r} via {hit}"
                )

    # CR-DFSQ-02: qi trees must not author L0 required constraints.
    for rel in _scan_qi_l0(projects_root, qi_projects, repo_root):
        errors.append(f"CR-DFSQ-02: qi-layer tree authored L0 required constraint at {rel}")

    # CR-SFOP-05: H↛B except through F. Adapter files are the H-side B-port
    # (anti-corruption seam) until those ports speak BOS/agora. Other H files
    # fail-closed unless listed in the line-stable baseline.
    hb_seam_files: list[str] = []
    if not skip_call_scan:
        baseline = _load_baseline(baseline_path)
        seen_seam: set[str] = set()
        seen_nonseam: set[str] = set()
        for finding in _scan_hb_calls(projects_root, repo_root):
            rel = finding["file"]
            if finding.get("seam"):
                seen_seam.add(rel)
                continue
            key = finding["key"]
            if key in seen_nonseam:
                continue
            seen_nonseam.add(key)
            msg = (
                f"CR-SFOP-05: {rel} "
                f"H({finding['caller']}) → B({finding['callee']}); "
                "cross-slot calls must go through F (agora) or cockpit.adapters"
            )
            if key in baseline:
                warnings.append(msg + " [baseline]")
            else:
                errors.append(msg)
        hb_seam_files = sorted(seen_seam)
        if hb_seam_files:
            warnings.append(
                f"CR-SFOP-05: {len(hb_seam_files)} adapter seam file(s) import B "
                "(allowed H-side port; do not add new non-adapter H→B)"
            )

    # CR-X3-NS-001: north-star stack must not use governance self-data tokens.
    ns_hits = _x3_self_data(x3_path)
    if ns_hits:
        warnings.append(
            "CR-X3-NS-001: x3-value-stack mentions governance self-data tokens "
            f"{ns_hits} (preferred; north_star_meter_v2 already excludes self-data)"
        )

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "components": annotated,
        "s_holders": s_holders,
        "vacant_slots": vacant,
        "vacant_allowed": sorted(VACANT_ALLOWED),
        "hb_seam_files": hb_seam_files,
        "constraint_ids": [
            "CR-SFOP-01",
            "CR-SFOP-02",
            "CR-SFOP-04",
            "CR-SFOP-05",
            "CR-DFSQ-01",
            "CR-DFSQ-02",
            "CR-X3-NS-001",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--nodes-dir", type=Path, default=None)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--cron-registry", type=Path, default=None)
    parser.add_argument("--projects-root", type=Path, default=None)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--x3", type=Path, default=None)
    parser.add_argument("--skip-call-scan", action="store_true")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="rewrite H→B baseline from the current scan (does not fail)",
    )
    args = parser.parse_args(argv)
    if args.write_baseline:
        repo_root = ROOT
        projects_root = args.projects_root or (repo_root / "projects")
        baseline_path = args.baseline or DEFAULT_BASELINE
        findings = _scan_hb_calls(projects_root, repo_root)
        lines = [
            "# SFOP H→B call baseline (CR-SFOP-05).",
            "# Stable keys: file:H->B:caller->callee (no line numbers).",
            "# Adapter seam files are allowed and omitted. Do not add keys to hide new calls.",
            "",
        ]
        seen: set[str] = set()
        n = 0
        for finding in findings:
            if finding.get("seam"):
                continue
            key = finding["key"]
            if key in seen:
                continue
            seen.add(key)
            lines.append(key)
            n += 1
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {n} non-seam H→B baseline keys → {baseline_path}")
        return 0

    result = check(
        nodes_dir=args.nodes_dir,
        registry_path=args.registry,
        cron_registry_path=args.cron_registry,
        projects_root=args.projects_root,
        baseline_path=args.baseline,
        x3_path=args.x3,
        skip_call_scan=args.skip_call_scan,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"SFOP slot check: {'PASS' if result['ok'] else 'FAIL'}")
        for e in result["errors"]:
            print(f"  ERROR  {e}")
        for w in result["warnings"]:
            print(f"  WARN   {w}")
        print(
            f"  components={len(result['components'])} S={result['s_holders']} "
            f"vacant={result.get('vacant_slots')}"
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
