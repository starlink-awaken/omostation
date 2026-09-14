#!/usr/bin/env python3
"""meta-doctor.py — 治理机制自身的活性巡检 (自进化框架 M1+M2 载体).

北极星: 从"治理代码"升级为"治理治理本身".

M1 心跳契约 — 关键状态投影文件的 generated_at/last_scan 是否超 SLA
M2 引用活性   — cron / launchd 登记中的可执行目标路径是否存在;
              存在且位于 workspace 树内的引用追加 git 跟踪检查
              (untracked = 生产依赖未入库, 清理即断链; 警告级, 见 untracked_refs)

输出: 单行 JSON; exit 0=全绿, 1=存在失活项 (供调度层告警)
--refs-only: 跳过 M1 心跳 (CI 检出态投影恒陈旧, 仅验仓库侧引用活性)
纯标准库, 可由裸 python3 cron 直跑.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

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
_ANCHOR_RE = re.compile(r"\$OMO_WORKSPACE_ROOT|\$HOME/Workspace|/Users/\w+/Workspace")
DEBT_PROPOSAL_SCHEMA = "meta-doctor-debt-proposal/v1"


class DebtProposal(TypedDict):
    schema: str
    id: str
    title: str
    dimension: str
    subdimension: str
    severity: str
    lifecycle_state: str
    owner: str
    source_ref: str
    target_ref: str
    proposed_by: str


def tokenize(line: str) -> list[str]:
    return [t for t in re.split(r'[\s"\'();|&]+', line) if t]


def _load(path: Path) -> dict:
    import yaml
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def candidates_from(tokens: list[str]) -> list[str]:
    out = []
    for tok in tokens:
        if tok.startswith("-"):
            continue
        if tok.endswith((".py", ".sh")) or tok.startswith("bin/"):
            out.append(tok.strip("'\""))
    return out


def _now() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017 - cron uses macOS Python 3.9


def _parse_stamp(raw: str) -> datetime | None:
    raw = raw.strip().strip('"').strip("'")
    try:
        if re.fullmatch(r"\d+(\.\d+)?", raw):
            return datetime.fromtimestamp(
                float(raw), tz=timezone.utc  # noqa: UP017 - macOS Python 3.9
            )
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


def resolve_candidate(tok: str, ws_root: Path) -> Path:
    if tok.startswith("$HOME"):
        return Path(os.path.expandvars(tok))
    if tok.startswith("~"):
        return Path(os.path.expanduser(tok))
    if tok.startswith("/"):
        return Path(tok)
    return ws_root / tok


def _find_repo_root(path: Path) -> Path | None:
    """向上查找含 .git 的目录 (文件/目录均可, 兼容 submodule gitdir 指针与 worktree)."""
    cur = path if path.is_dir() else path.parent
    for d in (cur, *cur.parents):
        if (d / ".git").exists():
            return d
    return None


def _git_track_status(path: Path) -> str | None:
    """path 在其所属 git 仓库中的跟踪状态.

    返回 "tracked" | "untracked" | "ignored" | None(不属于任何仓库).
    2026-09-11: harness-cron.sh 未跟踪但被生产 crontab 引用, 清理即静默
    断链 — M2 原只查存在性, 补跟踪性维度 (存在 ≠ 受版本控制保护).
    """
    repo = _find_repo_root(path)
    if repo is None:
        return None
    try:
        rel = path.relative_to(repo)
    except ValueError:
        return None
    r = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--error-unmatch", "--", str(rel)],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode == 0:
        return "tracked"
    r2 = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", "--", str(rel)],
        capture_output=True, text=True, timeout=10,
    )
    return "ignored" if r2.returncode == 0 else "untracked"


def annotate_tracking(refs: list[dict], ws_root: Path) -> list[dict]:
    """标注 workspace 树内 ok 引用的 git 跟踪状态, 返回未跟踪子集 (警告级).

    只查 workspace 树内 (主仓或子模块) 的引用; $HOME 等外部路径不在范围内。
    不修改 refs 中条目的 status/ok (保持 M2 原有分类语义与既有测试兼容),
    仅追加 "track" 字段并把未跟踪且未忽略的条目收进返回值。
    """
    untracked: list[dict] = []
    cache: dict[str, str | None] = {}
    ws_str = str(ws_root)
    for ref in refs:
        if ref.get("status") != "ok":
            continue
        resolved = str(ref.get("resolved", ""))
        if not resolved.startswith(ws_str):
            continue
        if resolved not in cache:
            cache[resolved] = _git_track_status(Path(resolved))
        status = cache[resolved]
        if status is None:
            continue
        ref["track"] = status
        if status == "untracked":
            untracked.append(ref)
    return untracked


def _is_library_script(rel: str) -> bool:
    """判定相对路径是否库脚本 (不应要求登记到 script-registry)."""
    name = Path(rel).name
    if name.startswith("_") and name != "__main__.py":
        return True  # _lib.py, _compat.py 等私有模块
    if name == "__init__.py":
        return True
    return False


def _script_registry_coverage(refs: list[dict], ws_root: Path) -> list[dict]:
    """M2 扩展: crontab/hook/launchd 引用的可执行脚本是否在 script-registry 登记.

    返回未登记的可执行脚本子集 (警告级). 库脚本 (_lib.py/__init__.py) 与
    $HOME 树外路径跳过. 与 annotate_tracking 的 track 字段并列, 不修改原有 status/ok。
    """
    reg_dir = ws_root / "bin" / "_registry" / "scripts"
    registered: set[str] = set()
    if reg_dir.is_dir():
        for yf in sorted(reg_dir.rglob("*.yaml")):
            try:
                data = _load(yf)
            except Exception:
                continue
            if isinstance(data, dict) and isinstance(data.get("id"), str):
                rid = data["id"]
                if rid.startswith("bin/"):
                    registered.add(rid[4:])  # 去掉 "bin/" 前缀, 与 rel 对齐
    unregistered: list[dict] = []
    seen: set[str] = set()
    ws_str = str(ws_root)
    for ref in refs:
        if ref.get("status") != "ok":
            continue
        resolved = str(ref.get("resolved", ""))
        if not resolved.startswith(ws_str):
            continue
        try:
            rel = Path(resolved).relative_to(ws_root / "bin").as_posix()
        except ValueError:
            continue
        if _is_library_script(rel):
            ref["registry"] = "na"  # 库脚本不要求登记
            continue
        suffix = Path(rel).suffix
        if suffix not in (".py", ".sh"):
            continue
        ref["registry"] = "registered" if rel in registered else "unregistered"
        if rel in registered or rel in seen:
            continue
        seen.add(rel)
        if ref["registry"] == "unregistered":
            unregistered.append(ref)
    return unregistered


def _submod_ptrs(ws_root: Path, ref: str) -> dict[str, str]:
    """读取某 ref 的子模块指针映射 {相对路径: sha}."""
    out: dict[str, str] = {}
    r = subprocess.run(
        ["git", "-C", str(ws_root), "ls-tree", "-r", "--name-only", ref],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        return out
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or not parts[0].endswith(" commit"):
            continue
        sha = parts[0].split()[2]  # "<mode> <type> <sha>"
        out[parts[1]] = sha
    return out


def _submodule_ff_check(ws_root: Path) -> list[dict]:
    """M3: 子模块指针 fast-forward 检查 — 防 PITFALL-GAT-006 并行回退.

    当前 HEAD 的每个子模块指针必须是 origin/main 对应指针的后代,
    否则发生了回退 (常由基于旧 main 的 PR 合并引发).
    返回回退子模块列表 (error 级).
    """
    regressions: list[dict] = []
    cur = _submod_ptrs(ws_root, "HEAD")
    origin = _submod_ptrs(ws_root, "origin/main")
    for path, head_sha in cur.items():
        orig_sha = origin.get(path)
        if not orig_sha or orig_sha == head_sha:
            continue
        ff = subprocess.run(
            ["git", "-C", str(ws_root), "merge-base", "--is-ancestor", orig_sha, head_sha],
            capture_output=True, text=True, timeout=10,
        )
        if ff.returncode != 0:
            regressions.append({
                "submodule": path,
                "origin_main": orig_sha,
                "head": head_sha,
                "issue": "submodule pointer regressed (not fast-forward vs origin/main)",
            })
    return regressions


def scan_crontab_lines(lines: list[str], source: str, ws_root: Path) -> list[dict]:
    found = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        anchored = bool(_ANCHOR_RE.search(s))
        # cd <DIR> && 语义: 后续相对路径 token 锚定到 DIR 而非 ws_root
        # (2026-08-27: line92 'cd .../projects/omlxc && python3 scripts/weekly-report.py'
        #  曾被误判 dead — 相对 token 解析到 workspace 根而实际锚在 omlxc)
        cd_m = re.search(r"(?:^|&&|\s)cd\s+(\S+)", s)
        cd_dir = Path(os.path.expandvars(cd_m.group(1))) if cd_m else None
        for tok in candidates_from(tokenize(s)):
            p = resolve_candidate(tok, ws_root)
            if not p.exists() and cd_dir and not tok.startswith(("/", "$HOME", "~")):
                cd_try = cd_dir / tok
                if cd_try.exists():
                    p = cd_try
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


def _proposal_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()


def _safe_target_label(target: str) -> str:
    basename = Path(target.replace("\\", "/")).name
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", basename).strip("-._")
    return (label or "unavailable")[:64]


def build_debt_proposals(dead_refs: list[dict]) -> list[DebtProposal]:
    """Project dead references for an authorized broker without mutating `.omo`."""
    proposals: list[DebtProposal] = []
    for ref in dead_refs:
        target = str(ref.get("target", ""))
        source = str(ref.get("source", "unknown"))
        raw_line = ref.get("line", 0)
        line = raw_line if isinstance(raw_line, int) and not isinstance(raw_line, bool) else 0
        material = json.dumps(
            {
                "schema": DEBT_PROPOSAL_SCHEMA,
                "source": source,
                "line": line,
                "target": target,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        proposal_digest = _proposal_digest(material)
        proposals.append(
            {
                "schema": DEBT_PROPOSAL_SCHEMA,
                "id": f"MDEAD-{proposal_digest[:20]}",
                "title": f"引用断链: {_safe_target_label(target)}",
                "dimension": "governance",
                "subdimension": "reference",
                "severity": "medium",
                "lifecycle_state": "proposed",
                "owner": "governance-team",
                "source_ref": (
                    f"meta-doctor-source://sha256/{_proposal_digest(source)}#L{line}"
                ),
                "target_ref": (
                    f"meta-doctor-target://sha256/{_proposal_digest(target)}"
                ),
                "proposed_by": "meta-doctor",
            }
        )
    return proposals


# ── M3 仪式检查: 主人周检视心跳 ──────────────────────────────────────────────

_RITUAL_HB_REL = ".omo/state/heartbeats/weekly-review.json"
_RITUAL_SLA_HOURS = 336  # 14 days


def check_ritual(ws_root: Path, now: datetime | None = None) -> list[DebtProposal]:
    """Check weekly-review heartbeat freshness (M3 ritual).

    Returns a T1 debt proposal if the heartbeat is missing or older than 14 days.
    """
    now = now or _now()
    hb_path = ws_root / _RITUAL_HB_REL

    if not hb_path.is_file():
        return [_make_ritual_proposal()]

    try:
        data = json.loads(hb_path.read_text(encoding="utf-8"))
    except Exception:
        return [_make_ritual_proposal()]

    ts_str = data.get("generated_at")
    if not ts_str:
        return [_make_ritual_proposal()]

    ts = _parse_stamp(str(ts_str))
    if ts is None:
        return [_make_ritual_proposal()]

    age_hours = (now - ts).total_seconds() / 3600.0
    if age_hours > _RITUAL_SLA_HOURS:
        return [_make_ritual_proposal()]

    return []


def _make_ritual_proposal() -> DebtProposal:
    """Build the M3 owner-review-lapsed debt proposal."""
    return {
        "schema": DEBT_PROPOSAL_SCHEMA,
        "id": "M3-owner-review-lapsed",
        "title": "主人周检视断供>14天",
        "dimension": "governance",
        "subdimension": "ritual",
        "severity": "medium",
        "lifecycle_state": "proposed",
        "owner": "governance-team",
        "source_ref": f"meta-doctor-ritual://{_RITUAL_HB_REL}",
        "target_ref": "meta-doctor-ritual://weekly-review-heartbeat",
        "proposed_by": "meta-doctor",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", type=Path, default=WORKSPACE,
                    help="工作区根目录 (默认取脚本位置推导)")
    ap.add_argument("--refs-only", action="store_true",
                    help="仅跑 M2 引用活性 (CI/无本地心跳语境: 投影 SLA 不适用)")
    args = ap.parse_args(argv)
    ws_root = args.workspace.resolve()

    beats = [] if args.refs_only else check_heartbeats(ws_root)
    refs = collect_references(ws_root)
    untracked_refs = annotate_tracking(refs, ws_root)
    unregistered_scripts = ([] if args.refs_only
                           else _script_registry_coverage(refs, ws_root))
    submodule_regressions = ([] if args.refs_only
                             else _submodule_ff_check(ws_root))

    stale_beats = [b for b in beats if not b["ok"]]
    dead_refs = [r for r in refs if r.get("status") == "dead"]
    ritual_proposals = [] if args.refs_only else check_ritual(ws_root)
    all_proposals = build_debt_proposals(dead_refs) + ritual_proposals
    report = {
        "generated_at": _now().isoformat(timespec="seconds"),
        "workspace": str(ws_root),
        "ok": (not stale_beats and not dead_refs and not ritual_proposals
                and not submodule_regressions),
        "heartbeat": beats,
        "references": refs,
        "untracked_refs": untracked_refs,
        "unregistered_scripts": unregistered_scripts,
        "submodule_regressions": submodule_regressions,
        "summary": {
            "stale_beats": len(stale_beats),
            "dead_refs": len(dead_refs),
            "ritual_lapsed": len(ritual_proposals),
            "untracked_refs": len(untracked_refs),
            "unregistered_scripts": len(unregistered_scripts),
            "submodule_regressions": len(submodule_regressions),
        },
        "debt_proposals": all_proposals,
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
