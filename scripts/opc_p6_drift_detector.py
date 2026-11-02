#!/usr/bin/env python3
"""OPC P6 drift detector — aggregate drift sources into a standard report.

Reads:
  - bin/mof/mof-drift stdout (workspace / commit / governance drifts)
  - .omo/_truth/registry/mcptool-drift-report.yaml (MCP tool impl drift)
  - .omo/_truth/registry/drift-log.yaml (architecture drift log)

Emits a JSON report at <workspace>/runtime/omo/_control/evolution/drift/<date>.json
with schema: {kinds, drift_count, results: [{id, title, kind, severity, source, ref, evidence}]}.

Callable as a module: `from opc_p6_drift_detector import detect_drifts`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_yaml_simple(path: Path) -> dict:
    """Minimal YAML loader for known flat structures (avoid pyyaml dep)."""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        # Fallback: parse summary.total_drifts and recommendations only.
        text = path.read_text(encoding="utf-8")
        out: dict = {"summary": {}, "recommendations": []}
        m = re.search(r"total_drifts:\s*(\d+)", text)
        if m:
            out["summary"]["total_drifts"] = int(m.group(1))
        return out


def _detect_mof_drift(workspace_root: Path) -> list[dict]:
    """Run bin/mof/mof-drift and parse its textual output."""
    cmd = [sys.executable, str(workspace_root / "bin" / "mof" / "mof-drift")]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(workspace_root))
    except (subprocess.TimeoutExpired, OSError):
        return []
    text = (proc.stdout or "") + (proc.stderr or "")
    results: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"[🔴🟠🟡🟢🔵]\s+(CRITICAL|HIGH|MEDIUM|LOW)\s+\((\d+)\):", line, re.IGNORECASE)
        # severity header lines; items follow on indented lines
        # We capture indented item lines instead:
    # Capture items: lines starting with whitespace and '['
    severity = "low"
    for line in text.splitlines():
        sev_match = re.match(r".*?(CRITICAL|HIGH|MEDIUM|LOW)\s*\(\d+\):", line, re.IGNORECASE)
        if sev_match:
            severity = sev_match.group(1).lower()
            continue
        item_match = re.match(r"\s+\[([^\]]+)\]\s+(.+)$", line)
        if item_match:
            kind = item_match.group(1).strip()
            desc = item_match.group(2).strip()
            results.append({
                "id": "mof-" + kind + "-" + f"{len(results)+1:03d}",
                "title": f"[{kind}] {desc[:100]}",
                "kind": kind,
                "severity": severity,
                "source": "mof-drift",
                "ref": "bin/mof/mof-drift",
                "evidence": desc,
            })
    return results


def _detect_mcptool_drift(workspace_root: Path) -> list[dict]:
    report = _load_yaml_simple(workspace_root / ".omo" / "_truth" / "registry" / "mcptool-drift-report.yaml")
    summary = report.get("summary", {}) or {}
    total = int(summary.get("total_drifts", 0) or 0)
    if total == 0:
        return []
    results: list[dict] = []
    categories = report.get("categories", {}) or {}
    for cat_name, items in categories.items():
        for item in (items or [])[:50]:
            if isinstance(item, dict):
                title = item.get("name") or item.get("tool") or str(item)
            else:
                title = str(item)
            results.append({
                "id": "mcptool-" + cat_name + "-" + f"{len(results)+1:03d}",
                "title": f"[mcptool:{cat_name}] {title}",
                "kind": "mcptool-impl-drift",
                "severity": "medium",
                "source": "mcptool-drift-report",
                "ref": ".omo/_truth/registry/mcptool-drift-report.yaml",
                "evidence": json.dumps(item, ensure_ascii=False),
            })
    return results


def _detect_arch_drift_log(workspace_root: Path) -> list[dict]:
    log = _load_yaml_simple(workspace_root / ".omo" / "_truth" / "registry" / "drift-log.yaml")
    drifts = log.get("drifts", []) or []
    results: list[dict] = []
    for d in drifts:
        if not isinstance(d, dict):
            continue
        results.append({
            "id": f"arch-{d.get('id', len(results)+1):03d}",
            "title": d.get("title") or d.get("description") or f"Architecture drift {d.get('id')}",
            "kind": d.get("kind", "architecture"),
            "severity": d.get("severity", "medium"),
            "source": "drift-log",
            "ref": ".omo/_truth/registry/drift-log.yaml",
            "evidence": json.dumps(d, ensure_ascii=False),
        })
    return results


def detect_drifts(workspace_root: Path | str = ROOT) -> dict:
    workspace_root = Path(workspace_root)
    all_results: list[dict] = []
    all_results.extend(_detect_mof_drift(workspace_root))
    all_results.extend(_detect_mcptool_drift(workspace_root))
    all_results.extend(_detect_arch_drift_log(workspace_root))

    kinds = sorted({r["kind"] for r in all_results})
    return {
        "kinds": len(kinds),
        "drift_count": len(all_results),
        "results": all_results,
        "generated_at": _utc_now(),
    }


def main() -> int:
    report = detect_drifts(ROOT)
    sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))
    from omo.omo_ingress_paths import _drift_dir  # noqa: E402

    drift_dir = _drift_dir(ROOT)
    drift_dir.mkdir(parents=True, exist_ok=True)
    now = report["generated_at"]
    out = drift_dir / f"{now[:10]}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
