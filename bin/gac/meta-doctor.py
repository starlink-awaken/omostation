#!/usr/bin/env python3
"""meta-doctor.py — 治理机制自身的活性巡检 (自进化框架 M1+M2 载体).

北极星: 从"治理代码"升级为"治理治理本身".

M1 心跳契约 — 关键状态投影文件的 generated_at/last_scan 是否超 SLA
M2 引用活性   — cron / launchd 登记中的可执行目标路径是否存在

输出: 单行 JSON; exit 0=全绿, 1=存在失活项 (供调度层告警)
纯标准库, 可由裸 python3 cron 直跑.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# M1 心跳登记: 相对路径 → (时间戳字段, SLA 小时)
HEARTBEATS: dict[str, tuple[str, int]] = {
    ".omo/state/system_health.yaml": ("last_scan", 48),
    ".omo/state/health.yaml": ("generated_at", 72),
    # 周更 debt-audit 节奏配套的 dashboard 投影
    ".omo/_control/debt-dashboard/current.yaml": ("generated_at", 24 * 14),
}

LAUNCHD_PREFIXES = ("com.omostation.", "com.opencode.", "com.l4.", "com.aetherforge.", "com.omlxc.")
_LA = Path.home() / "Library" / "LaunchAgents"

SYSTEM_PREFIXES = ("/usr/", "/bin/", "/opt/", "/tmp/", "/private/", "/Applications/", "/Library/", "/System/")
_ANCHOR_RE = re.compile(r"\$HOME/Workspace|/Users/\w+/Workspace")


def tokenize(line: str) -> list[str]:
    return [t for t in re.split(r'[\s"\'();|&]+', line) if t]


def candidates_from(tokens: list[str]) -> list[str]:
    out = []
    for tok in tokens:
        if tok.startswith("-"):
            continue
        if tok.endswith((".py", ".sh")) or tok.startswith("bin/"):
            out.append(tok.strip("'\""))
    return out


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_stamp(raw: str) -> datetime | None:
    raw = raw.strip().strip('"').strip("'")
    try:
        if re.fullmatch(r"\d+(\.\d+)?", raw):
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def check_heartbeats(ws_root: Path, now: datetime | None = None) -> list[dict]:
    now = now or _now()
    out = []
    for rel, (field, sla_h) in HEARTBEATS.items():
        f = ws_root / rel
        entry = {
            "file": rel, "field": field, "sla_hours": sla_h,
            "exists": f.exists(), "age_hours": None, "ok": False,
        }
        if f.exists():
            m = None
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s.startswith(field):
                    m = _parse_stamp(s.split(":", 1)[1])
                    break
            if m:
                age = (now - m).total_seconds() / 3600.0
                entry["age_hours"] = round(age, 1)
                entry["ok"] = age <= sla_h
        out.append(entry)
    return out


def extract_candidates(line: str) -> list[str]:
    cands = []
    for groups in _CAND_RE.findall(line):
        tok = next(g for g in groups if g)
        if tok.startswith("-"):
            continue
        cands.append(tok.strip("'\""))
    return cands


def resolve_candidate(tok: str, ws_root: Path) -> Path:
    if tok.startswith("$HOME"):
        return Path(os.path.expandvars(tok))
    if tok.startswith("~"):
        return Path(os.path.expanduser(tok))
    if tok.startswith("/"):
        return Path(tok)
    return ws_root / tok


def scan_crontab_lines(lines: list[str], source: str, ws_root: Path) -> list[dict]:
    found = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        anchored = bool(_ANCHOR_RE.search(s))
        for tok in candidates_from(tokenize(s)):
            p = resolve_candidate(tok, ws_root)
            sp = str(p)
            entry = {"source": source, "line": i, "target": tok,
                     "resolved": sp, "exists": p.exists(), "ok": True}
            if any(sp.startswith(px) for px in SYSTEM_PREFIXES):
                entry["status"] = "skip_system"
            elif not anchored and not tok.startswith(("/", "$HOME", "~")):
                entry["status"] = "skip_unanchored"
            else:
                entry["status"] = "dead" if not p.exists() else "ok"
                entry["ok"] = p.exists()
            found.append(entry)
    return found


def collect_references(ws_root: Path) -> list[dict]:
    refs: list[dict] = []
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            refs += scan_crontab_lines(r.stdout.splitlines(), "user-crontab", ws_root)
    except Exception:
        pass
    cron_dir = ws_root / ".omo" / "cron"
    if cron_dir.is_dir():
        for f in sorted(cron_dir.glob("*-crontab")):
            if f.name.startswith("_archived"):
                continue
            refs += scan_crontab_lines(
                f.read_text(encoding="utf-8", errors="replace").splitlines(),
                f".omo/cron/{f.name}", ws_root,
            )
    if _LA.is_dir():
        for pref in LAUNCHD_PREFIXES:
            for pf in sorted(_LA.glob(pref + "*.plist")):
                try:
                    data = plistlib.loads(pf.read_bytes())
                except Exception:
                    continue
                args = data.get("ProgramArguments") or []
                src = f"launchd:{pf.stem}"
                for tok in args:
                    if isinstance(tok, str) and (tok.endswith((".py", ".sh"))):
                        p = Path(os.path.expandvars(tok))
                        sp = str(p)
                        skip = any(sp.startswith(px) for px in SYSTEM_PREFIXES)
                        refs.append({
                            "source": src, "line": 0, "target": tok,
                            "resolved": sp, "exists": p.exists(), "ok": p.exists(),
                            "status": "skip_system" if skip else ("dead" if not p.exists() else "ok"),
                        })
    seen, dedup = set(), []
    for r in refs:
        key = (r["source"], r["target"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    return dedup


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", type=Path, default=WORKSPACE,
                    help="工作区根目录 (默认取脚本位置推导)")
    args = ap.parse_args(argv)
    ws_root = args.workspace.resolve()

    beats = check_heartbeats(ws_root)
    refs = collect_references(ws_root)

    stale_beats = [b for b in beats if not b["ok"]]
    dead_refs = [r for r in refs if r.get("status") == "dead"]
    report = {
        "generated_at": _now().isoformat(timespec="seconds"),
        "workspace": str(ws_root),
        "ok": not stale_beats and not dead_refs,
        "heartbeat": beats,
        "references": refs,
        "summary": {"stale_beats": len(stale_beats), "dead_refs": len(dead_refs)},
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
