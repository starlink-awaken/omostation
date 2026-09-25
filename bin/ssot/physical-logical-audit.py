#!/usr/bin/env python3
"""physical-logical-audit.py — 3-class physical/logical mapping audit (BET-Y2Q4-SH-3).

按 spec docs/superpowers/specs/2026-09-25-physical-logical-mapping-audit.md:

3 类映射漂移检测:
  1. gitlink: 主仓 .gitmodules ↔ origin/<sub>/main HEAD ↔ 主仓 gitlink commit (3-way)
  2. launchd: .omo/cron/*.plist Label ↔ launchctl list 实际 entry
  3. OMO asset: .omo/_truth/registry/omo-governance-surfaces.yaml ref ↔ 文件系统存在 + gitignore 状态

每个发现给:
  - drift type
  - severity (high / medium / low)
  - 修复路径 (auto-fixable / advisory / owner-decision)

circuit-breaker:
  - 默认 read-only, 不修改任何文件
  - gitlink/launchd 检测只读运行, 不 gitlink-bump, 不 plist
  - OMO asset 仅报告, 不自动摘除声明

用法:
  uv run python bin/ssot/physical-logical-audit.py
  uv run python bin/ssot/physical-logical-audit.py --json
  uv run python bin/ssot/physical-logical-audit.py --class gitlink
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

CLASSES = ["gitlink", "launchd", "omo-asset"]


def _git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd or str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _is_tracked(rel: str) -> bool:
    """Check whether path is git-tracked."""
    r = _git(["ls-files", "--error-unmatch", rel])
    return r.returncode == 0


def _is_gitignored(rel: str) -> bool:
    """Check whether path is gitignored."""
    r = _git(["check-ignore", rel])
    return r.returncode == 0


def audit_gitlink() -> list[dict]:
    """3-way diff: .gitmodules ↔ origin/<sub>/main HEAD ↔ 主仓 gitlink commit."""
    findings: list[dict] = []
    cfg = configparser.ConfigParser()
    cfg.read(WORKSPACE_ROOT / ".gitmodules")
    if not cfg.sections():
        return findings
    # current main gitlinks
    head_ls = _git(["ls-tree", "-r", "HEAD", "--format=%(objecttype) %(objectname)", "--", "projects"])
    head_tree = {}
    for line in head_ls.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2 and parts[0] == "commit":
            head_tree[parts[1]] = True
    # iterate .gitmodules
    for sec in cfg.sections():
        path = cfg[sec]["path"]
        url = cfg[sec]["url"]
        # submodule top-level name: first component after "projects/"
        # (kairon nested under knowledge/ → top-level is "knowledge")
        if path.startswith("projects/"):
            sub_top = path[len("projects/"):].split("/")[0]
        else:
            sub_top = path.split("/")[0]
        # fetch origin (best-effort, skip if network fails)
        try:
            _git(["fetch", "--quiet", "origin"], timeout=20)
        except Exception:
            pass
        sub_main = _git(["rev-parse", f"origin/{sub_top}/main"], cwd=str(WORKSPACE_ROOT / path)).stdout.strip()
        head_sub = _git(["rev-parse", "HEAD:./" + path], cwd=str(WORKSPACE_ROOT)).stdout.strip()
        if not sub_main or not head_sub:
            continue
        # 3-way diff
        is_omostation = "starlink-awaken" in url or "omostation" in url
        url_warning = "" if is_omostation else f" non-canonical URL: {url}"
        if sub_main != head_sub:
            findings.append({
                "class": "gitlink",
                "submodule": path,
                "id": f"GITLINK-DRIFT-{path.replace('/', '-')}",
                "severity": "medium" if is_omostation else "high",
                "head_submodule_commit": head_sub,
                "origin_submodule_main": sub_main,
                "url": url,
                "drift_kind": "gitlink_behind_submodule_main",
                "fix_hint": f"git checkout origin/main -- {path} && git commit -m 'fix(submodule): forward {path} to origin/main'" + url_warning,
            })
        if path not in head_tree and head_sub == sub_main:
            findings.append({
                "class": "gitlink",
                "submodule": path,
                "id": f"GITLINK-MISSING-{path.replace('/', '-')}",
                "severity": "high",
                "head_submodule_commit": head_sub,
                "origin_submodule_main": sub_main,
                "url": url,
                "drift_kind": "missing_gitlink_in_head",
                "fix_hint": f"git add {path} && git commit -m 'submodule: add {path}'" + url_warning,
            })
    return findings


def audit_launchd() -> list[dict]:
    """Audit .omo/cron/*.plist Labels vs `launchctl list` actual entries."""
    findings: list[dict] = []
    cron_dir = WORKSPACE_ROOT / ".omo/cron"
    if not cron_dir.is_dir():
        return findings
    # launchctl list output: "<pid>\t<status>\t<label>"
    lc = subprocess.run(
        ["launchctl", "list"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    running_labels = set()
    if lc.returncode == 0:
        for line in lc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                running_labels.add(parts[2].strip())
    # parse plist files
    for plist in sorted(cron_dir.glob("*.plist")):
        try:
            text = plist.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # extract Label from <key>Label</key><string>...</string>
        import re as _re
        m = _re.search(r"<key>Label</key>\s*<string>([^<]+)</string>", text)
        if not m:
            continue
        label = m.group(1).strip()
        # determine if plist represents a launchd service (vs user crontab or other)
        if "omostation" not in label:
            continue
        if label not in running_labels:
            findings.append({
                "class": "launchd",
                "id": f"LAUNCHD-MISSING-{label}",
                "plist": str(plist.relative_to(WORKSPACE_ROOT)),
                "label": label,
                "severity": "medium",
                "drift_kind": "declared_not_running",
                "fix_hint": (
                    f"Either: (a) install the plist via `launchctl load {plist.name}` "
                    f"or (b) remove the plist file. Auto-audit does not act."
                ),
            })
    return findings


def audit_omo_assets() -> list[dict]:
    """Audit .omo/_truth/registry/omo-governance-surfaces.yaml refs vs filesystem + gitignore."""
    findings: list[dict] = []
    reg_path = WORKSPACE_ROOT / ".omo/_truth/registry/omo-governance-surfaces.yaml"
    if not reg_path.is_file():
        return findings
    # load multi-doc yaml
    try:
        import yaml as _yaml
        with reg_path.open(encoding="utf-8") as f:
            docs = list(_yaml.safe_load_all(f))
    except Exception as e:
        findings.append({
            "class": "omo-asset",
            "id": "OMO-REGISTRY-MALFORMED",
            "path": str(reg_path.relative_to(WORKSPACE_ROOT)),
            "severity": "high",
            "drift_kind": "registry_malformed",
            "fix_hint": f"repair YAML: {e}",
        })
        return findings
    for d in docs:
        if not isinstance(d, dict):
            continue
        for asset in d.get("assets", []):
            asset_id = asset.get("id", "?")
            ref = asset.get("ref", "")
            if not ref:
                continue
            # path may contain $VAR expansion? treat as literal
            target = WORKSPACE_ROOT / ref
            if target.exists():
                continue
            # missing — check if gitignored (runtime face — not a real zombie)
            is_gignored = _is_gitignored(ref)
            if is_gignored:
                # gitignored but missing = runtime face, expected
                continue
            # missing + not gitignored = real zombie
            findings.append({
                "class": "omo-asset",
                "id": f"OMO-ZOMBIE-{asset_id}",
                "asset_id": asset_id,
                "ref": ref,
                "severity": "medium",
                "drift_kind": "declared_but_missing",
                "fix_hint": (
                    f"Owner decision: (a) add file at {ref} to satisfy declaration "
                    f"or (b) remove the asset entry from omo-governance-surfaces.yaml"
                ),
            })
    return findings


AUDITORS = {
    "gitlink": audit_gitlink,
    "launchd": audit_launchd,
    "omo-asset": audit_omo_assets,
}


def audit_all(targets: list[str] | None = None) -> list[dict]:
    if targets is None:
        targets = CLASSES
    findings: list[dict] = []
    for c in targets:
        fn = AUDITORS.get(c)
        if fn:
            findings.extend(fn())
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--class", dest="cls", choices=CLASSES, help="audit only this class")
    args = ap.parse_args()
    targets = [args.cls] if args.cls else None
    findings = audit_all(targets)
    fail_count = sum(1 for f in findings if f.get("severity") == "high")
    warn_count = sum(1 for f in findings if f.get("severity") == "medium")
    if args.json:
        out = {
            "schema": "physical-logical-audit/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workspace_root": str(WORKSPACE_ROOT),
            "total_findings": len(findings),
            "by_class": {c: sum(1 for f in findings if f["class"] == c) for c in CLASSES},
            "by_severity": {"high": fail_count, "medium": warn_count, "low": len(findings) - fail_count - warn_count},
            "findings": findings,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"=== physical-logical-audit ===")
        print(f"Total findings: {len(findings)} (high={fail_count}, medium={warn_count}, low={len(findings)-fail_count-warn_count})")
        for c in CLASSES:
            count = sum(1 for f in findings if f["class"] == c)
            if count:
                print(f"  {c}: {count}")
        print()
        for f in findings:
            sev = f.get("severity", "?")
            print(f"  [{sev}] {f['id']}")
            for k in ("submodule", "plist", "label", "ref", "head_submodule_commit", "origin_submodule_main"):
                if k in f:
                    print(f"      {k}: {f[k]}")
            print(f"      hint: {f.get('fix_hint', '-')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())