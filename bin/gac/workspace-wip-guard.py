#!/usr/bin/env python3
"""主工作区 WIP 守卫 — 共享工作区脏态 + 未推送提交的快照、检测与恢复.

问题（2026-09-17 / 2026-09-18 实证）: 主工作区 `/Users/xiamingxing/Workspace`
被多个 agent 共享。两种丢失模式：

  A. **脏态丢失** — 未提交改动被另一 agent 的分支切换 / `reset --hard` 抹掉。
  B. **提交孤立** — 提交已完成（工作树干净）但**未推送**；另一 agent 把工作区
     `git switch` 到别的分支后，该提交不再可从工作树到达。实测 2026-09-18：
     `e4787d290` 提交落在 `agent/governance-agent/t7-08-assisted-routine`
     （该分支 PR 已合并）后被 switch 抹除；同日 #3976 标题 "dropped from
     #3969" 是**同一事故的另一次发生**。

git 无 pre-checkout / pre-reset 钩子，无法在破坏性操作前拦截，因此本守卫采取
**快照兜底 + 提交钉扎 + 异常告警**：

| 子命令            | 作用 |
|------------------|------|
| `snapshot`       | 主工作区 dirty 文件（tracked 改动 + untracked）复制到 `runtime/wip-snapshots/<ts>/` |
| `protect`        | 扫描本地分支, 把**未合入 origin/main 的分支尖端**钉到 `refs/wip/<branch>-<tip>`（每分支 1 个; 可达性传递 → 保住整条历史） |
| `list-protected` | 列出已钉扎的提交 |
| `unprotect`      | 删除钉扎 ref（提交已合入远端后清理） |
| `list` / `restore` | 快照列举 / 恢复（默认 dry-run） |
| `status` / `check` | 脏文件数、分支异常、未推送提交数 / 超阈值告警（exit 1） |

模式 B 的根因不是"没快照"，而是**提交不在任何远端、也不在任何长期 ref 上**。
钉扎到 `refs/wip/` 既让对象可达（gc 不回收），又给出可发现的恢复入口：
`git branch recover/<name> refs/wip/<...>`。

安全约束: 只复制 / 只创建 ref, 从不删除业务文件或业务 ref；`restore` 默认预览；
快照保留最近 20 份。快照与钉扎仅在**主工作区**生效（worktree 本就隔离）。
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
# 未推送提交超过该数量即视为异常（模式 B 前兆）
UNPUSHED_WARN_THRESHOLD = 1
# 钉扎 ref 命名空间（不在 refs/heads|tags 下 → 不会被默认 push 带走）
PIN_REF_PREFIX = "refs/wip/"
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


# ── 模式 B: 未推送提交的检测与钉扎 ──────────────────────────────


def _base_ref() -> str | None:
    """对比基准: 优先 origin/main（未推送提交的判据是"不在远端"）."""
    for ref in ("origin/main", "main"):
        if _git("rev-parse", "--verify", "--quiet", ref).returncode == 0:
            return ref
    return None


def _local_branches() -> list[str]:
    out = _git("for-each-ref", "--format=%(refname:short)", "refs/heads/").stdout
    return [b.strip() for b in out.splitlines() if b.strip()]


def unpushed_commits(branch: str, base: str | None = None) -> list[str]:
    """branch 上不在 base 的提交 SHAs（= 分支删除/切换后会孤立的提交）."""
    base = base or _base_ref()
    if not base:
        return []
    res = _git("rev-list", f"{base}..{branch}")
    if res.returncode != 0:
        return []
    return [s.strip() for s in res.stdout.splitlines() if s.strip()]


def _sanitize(name: str) -> str:
    return name.replace("refs/heads/", "").replace("/", "_")


def protect(dry_run: bool = False, base: str | None = None,
            max_scan: int = 20000) -> dict[str, object]:
    """把各本地分支上未合入 base 的提交钉到 refs/wip/.

    为什么钉扎而不是只告警: 模式 B 的提交在**任何远端和长期 ref 上都不存在**,
    git gc 达到 pruneExpire 后会被回收。refs/wip/ 让对象永久可达, 且提供
    显式恢复入口。仅钉扎"未推送"部分, 已合入的提交不占用 ref 空间。

    **每分支只钉 1 个 ref（分支尖端）**: git 可达性是传递的 —— 钉住 tip 即保住
    整条历史。实测某分支有 3720 个未推送提交, 逐提交钉扎会产生 3720 个 ref
    (无意义且拖慢 for-each-ref); 钉 tip 等价且只占 1 个。
    """
    if not is_main_workspace():
        return {"ok": True, "skipped": True, "reason": "not_main_workspace"}
    base = base or _base_ref()
    if not base:
        return {"ok": True, "skipped": True, "reason": "no_base_ref"}

    pinned, already, branches, truncated = [], [], [], []
    for branch in _local_branches():
        shas = unpushed_commits(branch, base)
        if not shas:
            continue
        tip = shas[0]
        if len(shas) > max_scan:
            truncated.append({"branch": branch, "unpushed": len(shas)})
        branches.append({"branch": branch, "unpushed": len(shas), "tip": tip})

        ref = f"{PIN_REF_PREFIX}{_sanitize(branch)}-{tip[:12]}"
        if _git("rev-parse", "--verify", "--quiet", ref).returncode == 0:
            already.append(ref)
            continue
        if not dry_run:
            _git("update-ref", ref, tip)
        pinned.append({"ref": ref, "sha": tip, "branch": branch, "unpushed": len(shas)})

    # 走失提交台账（跨分支切换存活, 供事后发现）
    if pinned and not dry_run:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ledger = SNAPSHOT_DIR / "pinned-commits.jsonl"
        with ledger.open("a", encoding="utf-8") as fh:
            for item in pinned:
                fh.write(json.dumps({
                    "ts": datetime.now(UTC).isoformat(), **item,
                }, ensure_ascii=False) + "\n")

    return {"ok": True, "base": base, "dry_run": dry_run,
            "branches_with_unpushed": branches,
            "pinned": pinned, "already_pinned": len(already),
            "truncated": truncated}


def list_protected() -> list[dict[str, str]]:
    out = _git("for-each-ref", "--format=%(refname)\t%(objectname)\t%(subject)",
               PIN_REF_PREFIX).stdout
    entries = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            entries.append({"ref": parts[0], "sha": parts[1], "subject": parts[2][:70]})
    return entries


def unprotect(ref: str) -> dict[str, object]:
    """删除钉扎 ref（仅限 refs/wip/, 拒绝越界）."""
    if not ref.startswith(PIN_REF_PREFIX):
        return {"ok": False, "reason": "ref_outside_wip_namespace", "ref": ref}
    res = _git("update-ref", "-d", ref)
    return {"ok": res.returncode == 0, "ref": ref}


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
    branch = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    base = _base_ref()
    # 未推送提交（模式 B 前兆）: 只看当前分支 — 全分支扫描交给 protect
    unpushed = len(unpushed_commits(branch, base)) if branch else 0
    protected = list_protected()
    return {"main_workspace": is_main_workspace(),
            "branch": branch,
            "base_ref": base,
            # 主工作区应停在 main（只读约定）; 其他分支即异常
            "branch_anomaly": bool(branch) and branch != "main",
            "dirty_files": len(entries),
            "warn_threshold": DIRTY_WARN_THRESHOLD,
            "over_threshold": len(entries) > DIRTY_WARN_THRESHOLD,
            "unpushed_commits": unpushed,
            "unpushed_warn_threshold": UNPUSHED_WARN_THRESHOLD,
            "unpushed_over_threshold": unpushed >= UNPUSHED_WARN_THRESHOLD,
            "protected_refs": len(protected),
            "recent_snapshots": snaps[-3:],
            "snapshot_count": len(snaps)}


def check() -> int:
    """hook/巡检用: 脏文件超阈值 / 分支异常 / 有未推送提交 → 告警 (exit 1)."""
    info = status()
    if not info["main_workspace"]:
        return 0
    failed = False
    if info["over_threshold"]:
        print(f"⚠️  主工作区脏文件 {info['dirty_files']} 个 (> {DIRTY_WARN_THRESHOLD}) — "
              f"共享工作区易被并发会话覆盖; 建议 `python3 bin/gac/workspace-wip-guard.py snapshot` "
              f"并尽快转入 worktree", file=sys.stderr)
        failed = True
    if info["unpushed_over_threshold"]:
        print(f"🔴 主工作区当前分支 `{info['branch']}` 有 {info['unpushed_commits']} 个未推送提交 "
              f"(base={info['base_ref']}) — 并发会话切换分支会使这些提交孤立 (2026-09-18 实证 "
              f"e4787d290)。立即钉扎: "
              f"`python3 bin/gac/workspace-wip-guard.py protect`", file=sys.stderr)
        failed = True
    if info["branch_anomaly"]:
        print(f"⚠️  主工作区不在 main 而在 `{info['branch']}` — AGENTS.md 约定主工作区只读, "
              f"改动应走 worktree; 在该分支上提交即有模式 B 风险", file=sys.stderr)
        failed = True
    return 1 if failed else 0


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
    sub.add_parser("status", help="脏态 + 分支异常 + 未推送提交 摘要")
    sub.add_parser("check", help="异常告警 (exit 1)")
    pp = sub.add_parser("protect", help="钉扎未推送提交到 refs/wip/")
    pp.add_argument("--dry-run", action="store_true")
    pp.add_argument("--base", default=None, help="对比基准 (默认 origin/main)")
    sub.add_parser("list-protected", help="列出已钉扎提交")
    up = sub.add_parser("unprotect", help="删除钉扎 ref (提交已合入后清理)")
    up.add_argument("ref")
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
    if command == "protect":
        result = protect(dry_run=args.dry_run, base=args.base)
        print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
        return 0
    if command == "list-protected":
        entries = list_protected()
        print(json.dumps(entries, ensure_ascii=False, indent=1, default=str)
              if entries else "无钉扎提交 (refs/wip/ 为空)")
        return 0
    if command == "unprotect":
        result = unprotect(args.ref)
        print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
        return 0 if result.get("ok") else 1
    if command == "restore":
        result = restore(args.snapshot_id, force=args.force)
        return 0 if result.get("ok") else 1
    print(json.dumps(status(), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
