#!/usr/bin/env python3
"""主工作区 WIP 守卫 — 共享工作区脏态的快照、检测与恢复.

问题（2026-09-17 实证）: 主工作区 `/Users/xiamingxing/Workspace` 被多个 agent 共享。
某 agent 的未提交改动会被另一 agent 的分支切换 / `reset --hard` 静默丢失；反之，
提交时也可能把别人的暂存内容一并带走（本人两件事都亲身经历）。

git 无 pre-checkout / pre-reset 钩子，无法在破坏性操作前拦截，因此本守卫采取
**快照兜底 + 脏态告警**：

| 子命令     | 作用 |
|-----------|------|
| `snapshot` | 把主工作区的 dirty 文件（tracked 改动 + untracked）复制到 `runtime/wip-snapshots/<ts>/` |
| `list`     | 列出快照（含文件数、分支、HEAD） |
| `restore`  | 从快照恢复（**默认 dry-run**，`--force` 才写） |
| `status`   | 脏文件数 / 最近快照 / 是否超阈值 |
| `check`    | 供 hook 调用：脏文件超阈值时打印告警并 exit 1（advisory 用） |

安全约束: 只复制、从不删除业务文件；`restore` 默认预览；快照保留最近 20 份。
仅在**主工作区**生效（worktree 是 agent 隔离的，无需守卫）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = _ROOT / "runtime" / "wip-snapshots"
KEEP = 20
# 主工作区脏文件超过该数量即视为异常（多 agent 冲突前兆）
DIRTY_WARN_THRESHOLD = 8
# 快照时跳过的目录（体积大或纯产物）
SKIP_PARTS = {".git", "node_modules", ".venv", "__pycache__", ".mypy_cache",
              ".pytest_cache", "dist", "build", ".next", ".turbo"}


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(_ROOT), *args],
                          capture_output=True, text=True, check=False)


def is_main_workspace() -> bool:
    """主工作区: git-dir == git-common-dir (worktree 时前者指向 .git/worktrees/<name>)."""
    gd = _git("rev-parse", "--git-dir").stdout.strip()
    gcd = _git("rev-parse", "--git-common-dir").stdout.strip()
    return bool(gd) and gd == gcd


def _parse_status() -> list[dict[str, str]]:
    """解析 porcelain 状态（含 rename 的 'old -> new' 形态）."""
    out = _git("status", "--porcelain").stdout
    entries: list[dict[str, str]] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        xy, path = line[:2], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append({"xy": xy.strip() or "?", "path": path})
    return entries


def _copy_out(src: Path, dst: Path) -> dict[str, object]:
    """复制单个文件到快照目录; 返回清单条目."""
    try:
        raw = src.read_bytes()
    except OSError as exc:
        return {"path": str(src), "error": str(exc)[:120]}
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(raw)
    return {"path": str(src.relative_to(_ROOT)), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()[:16]}


def snapshot(reason: str = "manual", quiet: bool = False) -> dict[str, object]:
    if not is_main_workspace():
        return {"ok": True, "skipped": True, "reason": "not_main_workspace"}
    entries = _parse_status()
    if not entries:
        return {"ok": True, "skipped": True, "reason": "clean_workspace"}

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = SNAPSHOT_DIR / stamp
    files, skipped = [], []
    for e in entries:
        rel = e["path"]
        if any(part in SKIP_PARTS for part in Path(rel).parts):
            skipped.append(rel)
            continue
        src = _ROOT / rel
        if not src.is_file():
            skipped.append(rel)  # 目录/子模块指针, 不入快照
            continue
        files.append({**_copy_out(src, dest / rel), "xy": e["xy"]})

    manifest = {
        "schema": "wip-snapshot/v1",
        "ts": stamp,
        "reason": reason,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(),
        "head": _git("rev-parse", "HEAD").stdout.strip(),
        "files": files,
        "skipped": skipped,
    }
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # 保留最近 KEEP 份
    existing = sorted(p for p in SNAPSHOT_DIR.glob("*/") if p.is_dir())
    for old in existing[:-KEEP]:
        shutil.rmtree(old, ignore_errors=True)

    if not quiet:
        print(f"✅ WIP 快照: {len(files)} 文件 → {dest.relative_to(_ROOT)} (reason={reason})")
    return {"ok": True, "snapshot": stamp, "files": len(files), "skipped": len(skipped)}


def list_snapshots() -> list[dict[str, object]]:
    out = []
    if not SNAPSHOT_DIR.is_dir():
        return out
    for d in sorted(p for p in SNAPSHOT_DIR.glob("*/") if p.is_dir()):
        try:
            m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        except Exception:
            m = {}
        out.append({"snapshot": d.name, "reason": m.get("reason", "?"),
                    "branch": m.get("branch", "?"), "files": len(m.get("files", []))})
    return out


def status() -> dict[str, object]:
    entries = _parse_status()
    snaps = list_snapshots()
    return {"main_workspace": is_main_workspace(),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip(),
            "dirty_files": len(entries),
            "warn_threshold": DIRTY_WARN_THRESHOLD,
            "over_threshold": len(entries) > DIRTY_WARN_THRESHOLD,
            "recent_snapshots": snaps[-3:],
            "snapshot_count": len(snaps)}


def check() -> int:
    """hook/巡检用: 脏文件超阈值 → 告警 (exit 1). 仅主工作区判定."""
    info = status()
    if not info["main_workspace"]:
        return 0
    if info["over_threshold"]:
        print(f"⚠️  主工作区脏文件 {info['dirty_files']} 个 (> {DIRTY_WARN_THRESHOLD}) — "
              f"共享工作区易被并发会话覆盖; 建议 `python3 bin/gac/workspace-wip-guard.py snapshot` "
              f"并尽快转入 worktree", file=sys.stderr)
        return 1
    return 0


def restore(snapshot_id: str, force: bool = False) -> dict[str, object]:
    src = SNAPSHOT_DIR / snapshot_id
    manifest_path = src / "manifest.json"
    if not manifest_path.is_file():
        print(f"❌ 快照不存在: {src}")
        return {"ok": False, "reason": "snapshot_missing"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored, missing = [], []
    for f in manifest.get("files", []):
        rel = f.get("path")
        if not rel:
            continue
        backup = src / rel
        if not backup.is_file():
            missing.append(rel)
            continue
        target = _ROOT / rel
        if target.is_file() and target.read_bytes() == backup.read_bytes():
            continue
        if force:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
        restored.append(rel)
    if not force and restored:
        print(f"（dry-run）将恢复 {len(restored)} 个文件; 加 --force 执行:")
        for rel in restored[:20]:
            print(f"   {rel}")
    elif force:
        print(f"✅ 已恢复 {len(restored)} 个文件 from {snapshot_id}")
    else:
        print(f"ℹ️  无差异需要恢复 (snapshot={snapshot_id})")
    return {"ok": True, "dry_run": not force, "restored": len(restored),
            "missing_in_snapshot": missing, "files": restored[:20]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")
    sp = sub.add_parser("snapshot", help="快照主工作区脏文件")
    sp.add_argument("--reason", default="manual")
    sp.add_argument("--quiet", action="store_true")
    sub.add_parser("list", help="列出快照")
    sub.add_parser("status", help="脏态摘要")
    sub.add_parser("check", help="脏文件超阈值告警 (exit 1)")
    rp = sub.add_parser("restore", help="从快照恢复 (默认 dry-run)")
    rp.add_argument("snapshot_id")
    rp.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    command = args.command or "status"

    if command == "snapshot":
        result = snapshot(reason=args.reason, quiet=args.quiet)
        if not args.quiet:
            print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
        return 0
    if command == "list":
        snaps = list_snapshots()
        print(json.dumps(snaps, ensure_ascii=False, indent=1, default=str) if snaps else "无快照")
        return 0
    if command == "check":
        return check()
    if command == "restore":
        result = restore(args.snapshot_id, force=args.force)
        return 0 if result.get("ok") else 1
    print(json.dumps(status(), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
