#!/usr/bin/env python3
"""CR-SUBMODULE-REWIND: 检测子模块指针回退 (rewind).

当主仓 commit 中子模块指针被意外回退 (例如从 d4a9d1c 回退到 f57d13dd) 时,
本检查通过对比 index 当前指针与上一次 commit 的指针, 检测是否存在 rewind.

Rewind 判定: 当前指针 NOT ancestor of 上一次指针 (即指针历史被改写/回退).

--range 模式 (gitlink ancestry gate, 2026-08-24): 对比 base..head 两端的
gitlink 指针, 拦截并发合并把子模块指针带回旧 SHA 的回退。豁免: base..head
区间 commit body 含 `[gitlink-regress: <理由>]` → 降级 warning + 指纹写入
gate-known-debt.yaml (shrink_only, 只追加)。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# hook 环境下 git 会设这些, 泄漏到 subprocess 会让 `git -C <submodule>` 读错仓
for _env in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_QUARANTINE_PATH"):
    os.environ.pop(_env, None)


def _git(*args: str, cwd: Path | None = None) -> str:
    """Run a git command and return stdout, or empty string on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def get_current_gitlinks() -> dict[str, str]:
    """Read current submodule gitlinks from the index.

    Returns {submodule_path: sha1} for each submodule entry in the index.
    """
    output = _git("ls-files", "--stage")
    gitlinks: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        mode, sha1, stage, path = parts[0], parts[1], parts[2], parts[3]
        if mode == "160000" and stage == "0":
            gitlinks[path] = sha1
    return gitlinks


def _gitlink_pointer_at(commit: str, path: str, cwd: Path | None = None) -> str | None:
    """Extract the submodule gitlink pointer value recorded at a given commit.

    Parses `git ls-tree <commit> -- <path>` for the `160000 commit <sha>` line.
    Returns the pointer SHA, or None if the commit does not record a gitlink for
    the path (e.g. the path was absent or not a submodule at that commit).
    """
    line = _git("ls-tree", commit, "--", path, cwd=cwd)
    parts = line.split()
    if len(parts) >= 3 and parts[0] == "160000" and parts[1] == "commit":
        return parts[2]
    return None


def get_previous_pointer(path: str) -> str | None:
    """Get the submodule pointer value from the last commit that touched it.

    Walks the first-parent history of the path and returns the gitlink pointer
    recorded by the most recent commit that actually carries a submodule entry.
    Returns None if no commit in history records a gitlink for the path.
    """
    commits = _git("log", "--first-parent", "--format=%H", "--", path)
    for commit in commits.splitlines():
        pointer = _gitlink_pointer_at(commit, path)
        if pointer is not None:
            return pointer
    return None


def _git_in_submodule(*args: str, submodule_dir: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=submodule_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def is_descendant_or_equal(
    descendant_candidate: str,
    ancestor_candidate: str,
    submodule_path: str,
    verbose: bool = False,
) -> tuple[bool, str]:
    """Check if descendant_candidate is a valid forward pointer from ancestor_candidate.

    Returns (is_valid, reason) where reason explains which tolerance layer passed
    or why the check failed.

    Tolerance layers (evaluated in order):
    1. Same commit
    2. SHA missing in submodule (force-pushed away)
    3. descendant is ancestor of candidate on default branch
    4. descendant is ancestor of candidate in any ref
    5. ancestor no longer reachable from any ref (force-push cleaned it up)
    6. HEAD is on a non-default branch (feature-branch rebase)
    7. descendant is the tip of any branch ref (detached-HEAD branch switch)
    8. Otherwise — rewind or unrelated history
    """
    if descendant_candidate == ancestor_candidate:
        return True, "same-commit"

    submodule_dir = REPO_ROOT / submodule_path

    # Verify both SHAs exist in the submodule's object store.
    for sha in (descendant_candidate, ancestor_candidate):
        result = subprocess.run(
            ["git", "cat-file", "-t", sha],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "commit":
            return True, f"sha-missing:{sha[:12]}"

    # Cache default branch lookup (same for all submodules in a run).
    default_branch = getattr(
        is_descendant_or_equal,
        "_default_branch_cache",
        None,
    )
    if default_branch is None:
        default_branch = _git_in_submodule("symbolic-ref", "refs/remotes/origin/HEAD", submodule_dir=submodule_dir)
        if default_branch:
            default_branch = default_branch.rsplit("/", 1)[-1] or "main"
        else:
            default_branch = "main"
        is_descendant_or_equal._default_branch_cache = default_branch

    for ref in (default_branch, "HEAD"):
        result = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                ancestor_candidate,
                descendant_candidate,
            ],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, f"default-branch:{ref}"

    # Cache all refs lookup (same for all submodules in a run).
    all_commit_refs = getattr(
        is_descendant_or_equal,
        "_all_commit_refs_cache",
        None,
    )
    if all_commit_refs is None:
        all_commit_refs = _git_in_submodule(
            "for-each-ref",
            "--format=%(refname)",
            "refs/heads/",
            "refs/remotes/",
            submodule_dir=submodule_dir,
        )
        is_descendant_or_equal._all_commit_refs_cache = all_commit_refs

    for ref in all_commit_refs.splitlines():
        result = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                ancestor_candidate,
                descendant_candidate,
            ],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return True, f"any-ref:{ref}"

    # 3) If ancestor is no longer reachable from any ref (force-push cleaned it up),
    #    treat as acceptable history rewrite rather than blocking rewind.
    ancestor_reachable = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ancestor_candidate],
        cwd=submodule_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if ancestor_reachable.returncode != 0:
        return True, "force-pushed-away"

    # 4) Feature-branch rebase: ancestor was removed from branch history but the
    #    submodule is now on a non-default branch at descendant. Allow it rather than
    #    blocking every feature-branch rebase.
    head_ref = _git_in_submodule("symbolic-ref", "--quiet", "HEAD", submodule_dir=submodule_dir)
    head_branch = head_ref.rsplit("/", 1)[-1] if head_ref else ""
    if head_branch and head_branch not in (default_branch, "main", "master"):
        return True, f"feature-branch:{head_branch}"

    # 5) Detached-HEAD branch switch: if descendant is the tip of any branch ref,
    #    treat as acceptable even if ancestor is not in that branch's history.
    descendant_tip_of = _git_in_submodule(
        "for-each-ref",
        "--format=%(objectname)",
        "refs/heads/",
        "refs/remotes/",
        submodule_dir=submodule_dir,
    )
    if any(tip.startswith(descendant_candidate) for tip in descendant_tip_of.splitlines()):
        return True, "detached-head-tip"

    return False, "rewind-or-unrelated"


def format_violation(path: str, current_sha: str, previous_sha: str, reason: str) -> str:
    return (
        f"  {path} — 子模块指针方向非法: 当前 {current_sha[:12]} 不是上一次指针 {previous_sha[:12]} 的后代 ({reason})"
    )


# ── --range 模式: gitlink ancestry gate (base..head 指针回退检测) ──────────

EXEMPT_TAG_RE = re.compile(r"^\s*\[gitlink-regress:\s*([^\]]+)\]\s*$", re.MULTILINE)
PLACEHOLDER_REASON_RE = re.compile(r"<理由>|<reason>", re.IGNORECASE)
DEBT_SURFACE = "gitlink-ancestry"
DEBT_CHECK_ID = "submodule-ancestry-gate"


def _run_in(subdir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=subdir,
        capture_output=True,
        text=True,
        check=False,
    )


def declared_submodules(root: Path) -> list[str]:
    cfg = root / ".gitmodules"
    if not cfg.is_file():
        return []
    out = subprocess.run(
        ["git", "config", "--file", str(cfg), "--get-regexp", r"^submodule\..*\.path$"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    paths = []
    for line in out.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[1]:
            paths.append(parts[1])
    return sorted(set(paths))


def is_submodule_initialized(subdir: Path) -> bool:
    if not (subdir / ".git").exists():
        return False
    for entry in subdir.iterdir():
        if entry.name != ".git":
            return True
    return False


def submodule_has_object(subdir: Path, sha: str) -> bool:
    return _run_in(subdir, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def scan_exemption_tags(base: str, head: str, root: Path) -> list[str]:
    out = _git("log", "--format=%B", f"{base}..{head}", cwd=root)
    tags = []
    for match in EXEMPT_TAG_RE.findall(out):
        reason = match.strip()
        if not reason or PLACEHOLDER_REASON_RE.search(reason):
            continue
        tags.append(reason)
    return tags


def record_known_debt(root: Path, findings: list[dict], base: str, head: str) -> tuple[list[str], int]:
    """Append gitlink-regress fingerprints to gate-known-debt.yaml.

    growth_policy=shrink_only: 只追加本次指纹条目, 不清除他人已有条目。
    复用 swarm_discipline 的 fingerprint_key/load_known_debt (import, 非复制)。
    Returns (added_keys, already_present_count).
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import yaml
        from swarm_discipline import KNOWN_DEBT_REL, fingerprint_key, load_known_debt
    except ImportError:
        return [], 0

    debt_path = root / KNOWN_DEBT_REL
    existing = load_known_debt(root)
    existing_keys = {e.get("fingerprint") or fingerprint_key(e) for e in existing}
    now = datetime.now(UTC).isoformat()
    added: list[str] = []
    skipped_existing = 0
    for finding in findings:
        signature = hashlib.sha256(
            f"{finding['path']}\n{finding['old_sha']}\n{finding['new_sha']}".encode()
        ).hexdigest()[:16]
        fp = {
            "surface": DEBT_SURFACE,
            "check_id": DEBT_CHECK_ID,
            "signature": signature,
        }
        key = fingerprint_key(fp)
        if key in existing_keys:
            skipped_existing += 1
            continue
        existing.append(
            {
                "fingerprint": key,
                "surface": fp["surface"],
                "check_id": fp["check_id"],
                "signature": signature,
                "kind": "gitlink-regress",
                "reason": (
                    f"submodule {finding['path']} pointer {finding['new_sha'][:12]} "
                    f"rewinds {finding['old_sha'][:12]}"
                ),
                "range": f"{base[:12]}..{head[:12]}",
                "recorded_at": now,
                "active": True,
            }
        )
        existing_keys.add(key)
        added.append(key)
    if not added:
        return [], skipped_existing

    debt_path.parent.mkdir(parents=True, exist_ok=True)
    header = ""
    doc: dict = {}
    if debt_path.is_file():
        text = debt_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                header += line + "\n"
            else:
                break
        loaded = yaml.safe_load(text)
        if isinstance(loaded, dict):
            doc = loaded
    doc["entries"] = existing
    doc["version"] = doc.get("version", 1)
    doc.setdefault("growth_policy", "shrink_only")
    debt_path.write_text(
        header + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return added, skipped_existing


def _format_rewind_block(base: str, head: str, findings: list[dict]) -> str:
    lines = [f"FAIL 检测到 {len(findings)} 个子模块指针回退 ({base[:12]}..{head[:12]}):"]
    for f in findings:
        lines.append(f"  {f['path']} — 指针由 {f['old_sha'][:12]} 回退至 {f['new_sha'][:12]} (非前进)")
    lines.append("修复指引:")
    lines.append("  1. 误回退 (并发合并覆盖): 恢复子模块前进指针并重新 commit 主仓 gitlink")
    lines.append(f"     git -C <submodule> checkout {findings[0]['old_sha'][:12]} && git add <submodule> && git commit")
    lines.append("  2. 有意回退: 在本次 push 区间 (base..head) 任一 commit body 加豁免标签")
    lines.append("     [gitlink-regress: <理由>]   (须独立成行, 理由非占位符)")
    lines.append("     该回退降级为 warning, 指纹记入 .omo/_truth/registry/gate-known-debt.yaml")
    lines.append("     (growth_policy=shrink_only, 只追加本次条目); 豁免指纹需随本次交付提交")
    return "\n".join(lines)


def _format_rewind_exempt(findings: list[dict], tags: list[str], debt_keys: list[str], debt_skipped: int, write_debt: bool) -> str:
    reason = tags[0] if tags else ""
    lines = [f"WARN 子模块指针回退已豁免 (commit body 含 [gitlink-regress: {reason}], base..head 区间):"]
    for f in findings:
        lines.append(f"  {f['path']} — {f['old_sha'][:12]} → {f['new_sha'][:12]}")
    if debt_keys:
        lines.append(f"  已写入 known-debt 指纹 ({len(debt_keys)} 条): " + ", ".join(debt_keys))
        lines.append("  注意: gate-known-debt.yaml 为受治 SSOT, 请随本次交付提交")
    elif debt_skipped:
        lines.append(f"  指纹已存在 known-debt ({debt_skipped} 条), 无需重复写入")
    elif write_debt:
        lines.append("  known-debt 指纹写入失败 (pyyaml 不可用), 请在 CI 侧复核豁免记录")
    else:
        lines.append("  known-debt 指纹写入跳过 (--no-write-debt)")
    return "\n".join(lines)


def run_ancestry_gate(base: str, head: str, root: Path, *, write_debt: bool, json_out: bool) -> int:
    warnings: list[str] = []
    unresolvable = False

    if not _git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}", cwd=root):
        warnings.append(f"[WARN] base '{base}' 无法解析, 跳过 ancestry gate (浅检出/无该 ref 属预期)")
        unresolvable = True
    elif not _git("rev-parse", "--verify", "--quiet", f"{head}^{{commit}}", cwd=root):
        warnings.append(f"[WARN] head '{head}' 无法解析, 跳过 ancestry gate")
        unresolvable = True

    violations: list[dict] = []
    if not unresolvable:
        for path in declared_submodules(root):
            old = _gitlink_pointer_at(base, path, cwd=root)
            new = _gitlink_pointer_at(head, path, cwd=root)
            if new is None or old is None or old == new:
                continue
            subdir = root / path
            if not is_submodule_initialized(subdir):
                warnings.append(f"[WARN] {path}: 子模块未初始化 (工作树无文件), 跳过 ancestry 校验")
                continue
            missing = [sha for sha in (old, new) if not submodule_has_object(subdir, sha)]
            if missing:
                warnings.append(
                    f"[WARN] {path}: 子模块缺对象 {missing[0][:12]}, 无法判定 ancestry, 跳过"
                )
                continue
            if _run_in(subdir, "merge-base", "--is-ancestor", old, new).returncode == 0:
                continue
            violations.append({"path": path, "old_sha": old, "new_sha": new})

    tags = scan_exemption_tags(base, head, root) if not unresolvable else []
    exempted = bool(violations) and bool(tags)
    debt_keys: list[str] = []
    debt_skipped = 0
    if exempted and write_debt:
        debt_keys, debt_skipped = record_known_debt(root, violations, base, head)

    ok = not violations or exempted
    if json_out:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "mode": "range",
                    "base": base,
                    "head": head,
                    "violations": violations,
                    "warns": warnings,
                    "exempted": exempted,
                    "exempt_tags": tags,
                    "debt_written": debt_keys,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if ok else 1

    for w in warnings:
        print(w)
    if violations and not tags:
        print(_format_rewind_block(base, head, violations))
        return 1
    if exempted:
        print(_format_rewind_exempt(violations, tags, debt_keys, debt_skipped, write_debt))
        return 0

    print(f"OK 区间 {base[:12]}..{head[:12]} 未检测到子模块指针回退")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CR-SUBMODULE-REWIND check")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", action="store_true", help="Show tolerance layer details")
    parser.add_argument(
        "--warn-threshold",
        type=int,
        default=3,
        help="WARN if same tolerance layer triggers N+ times (default: 3)",
    )
    parser.add_argument(
        "--range",
        nargs="+",
        metavar="RANGE",
        help="base [head] — ancestry gate over a commit range (pre-push/CI). head 默认 HEAD",
    )
    parser.add_argument("--cwd", default=None, help="repo root override (default: script repo)")
    parser.add_argument(
        "--no-write-debt",
        action="store_true",
        help="豁免时不写 gate-known-debt.yaml 指纹 (CI 只读场景)",
    )
    args = parser.parse_args()

    if args.range:
        if not 1 <= len(args.range) <= 2:
            parser.error("--range 接受 1-2 个参数: base [head]")
        base = args.range[0]
        head = args.range[1] if len(args.range) == 2 else "HEAD"
        root = Path(args.cwd).resolve() if args.cwd else REPO_ROOT
        return run_ancestry_gate(base, head, root, write_debt=not args.no_write_debt, json_out=args.json)

    violations: list[dict] = []
    details: list[dict] = []
    tolerance_counts: dict[str, int] = {}
    current_gitlinks = get_current_gitlinks()

    for path, current_sha in sorted(current_gitlinks.items()):
        previous_sha = get_previous_pointer(path)
        if previous_sha is None:
            continue
        if previous_sha == current_sha:
            continue

        is_valid, reason = is_descendant_or_equal(current_sha, previous_sha, path, verbose=args.verbose)
        detail = {
            "path": path,
            "current_sha": current_sha,
            "previous_sha": previous_sha,
            "valid": is_valid,
            "reason": reason,
        }
        details.append(detail)

        if args.verbose:
            print(f"[DEBUG] {path}: {reason}")

        # Track tolerance layer frequency for WARN detection
        if is_valid:
            tolerance_counts[reason] = tolerance_counts.get(reason, 0) + 1

        if not is_valid:
            violations.append(detail)

    # WARN if any tolerance layer is triggered more than threshold
    warns = []
    for reason, count in sorted(tolerance_counts.items()):
        if count > args.warn_threshold:
            warns.append(f"[WARN] 容忍层 '{reason}' 已触发 {count} 次 (阈值: {args.warn_threshold})")

    if args.json:
        output = {
            "ok": len(violations) == 0,
            "violations": [
                format_violation(v["path"], v["current_sha"], v["previous_sha"], v["reason"]) for v in violations
            ],
            "details": details,
            "warns": warns,
            "tolerance_counts": tolerance_counts,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if output["ok"] else 1

    if warns:
        for w in warns:
            print(w)

    if violations:
        print(f"FAIL 发现 {len(violations)} 个子模块指针回退:")
        for v in violations:
            print(format_violation(v["path"], v["current_sha"], v["previous_sha"], v["reason"]))
        return 1

    print("OK 未检测到子模块指针回退")
    return 0


if __name__ == "__main__":
    sys.exit(main())
