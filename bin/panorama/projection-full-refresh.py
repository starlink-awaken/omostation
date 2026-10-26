#!/usr/bin/env python3
"""projection-full-refresh.py — 全量投影数据周期刷新 driver (BET-Y2Q4-T10-227)

T10-223 的 republisher 只续租约 (重打 generated_at/fresh_until, 保留 data_observed_at),
投影内容的观测龄期随时间单调增长。本 driver 维护持久专用洁净检出并周期执行全量发布:

  1. flock 防重入 (运行中第二次触发直接跳过);
  2. remote 卫生校验 (origin 必须以 starlink-awaken/omostation.git 结尾);
  3. git fetch + reset --hard origin/main + clean -fdx + 浅子模块对齐;
  4. 以该检出为 PANORAMA_CODE_ROOT 运行检出内 panorama-collect.py 全量发布
     (publisher 自带 workspace 身份 + deploy 身份双校验, 一字不改);
  5. 发布成功后 republisher 自动接续续期新 revision。

fail-closed: 任何步骤失败 → 退出非零 + JSON 行日志; 旧 revision 仍由 republisher 续期,
读端全程可用。锁文件置于 deploy 侧 revisions/ 内 (state root 顶层会触发读端 CODE_DRIFT)。
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DEPLOY_DIR = Path(
    os.environ.get("ZHIXING_DASHBOARD_STATE_ROOT", "~/.local/share/zhixing-dashboard")
).expanduser()
CHECKOUT = Path(
    os.environ.get("OMOSTATION_PUBLISHER_CHECKOUT", "~/.local/opt/omostation-publisher")
).expanduser()
LOCK_PATH = DEPLOY_DIR / "revisions" / ".fullrefresh.lock"
LOG_PATH = Path("~/.local/log/projection-fullrefresh.log").expanduser()
EXPECTED_ORIGIN_SUFFIX = "starlink-awaken/omostation.git"
CLONE_URL = "https://github.com/starlink-awaken/omostation.git"
PUBLISHER_TIMEOUT_SEC = 3600  # 全量采集典型 5~14min, 留足裕量
# 子模块历史深度。depth 1 的检出里 ``merge-base --is-ancestor <child> HEAD`` 结构性
# 不可判: 对象根本不在本地, 而 A8 门禁正是用这条判据证明 BET-Y1Q4-T10-151 的
# omo PR #173 merge (5e1f7eae) 落在当前 pin 上 —— 实测该 merge 距子模块
# origin/main 60 个 commit, 于是 A8 在生产里永远 ABSENT (2026-10-20 实证)。
# 200 与本文件上方 clone 自身的深度同值, 对 60 留 3x 裕量。
SUBMODULE_HISTORY_DEPTH = 200
# 加深的尝试次数与重试间隔。本机网络实测抖动 (2026-10-20: 连 github.com 的 TLS 握手
# 约 1/3 概率 SSL_ERROR_SYSCALL), 单次尝试的失败率不可忽略。已加深的子模块再跑是
# no-op, 所以重试是安全且幂等的。加深范围由 ancestry_verified_submodules() 从
# collector 导出 —— 只有真正按祖先关系被读取的子模块才付这份网络成本。
SUBMODULE_DEEPEN_ATTEMPTS = 5
STEP_RETRY_DELAY_SEC = 3
# event_ledger 是运行时文件（不在检出内）—— publisher 检出每轮 clean -fdx，那份按构造不存在。
# 根只能在调用时刻解析：import 时冻结会把 ledger 钉在一次性的 publisher 克隆上 (ADR-0456 B4b 前置, T10-247)。
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from repo_root import canonical_root, state_root  # noqa: E402


def task_state_root() -> Path:
    """Task authority is independent of code/output roots and any ledger override."""
    return state_root() if os.environ.get("OMOSTATION_STATE_ROOT") else canonical_root()


def ledger_db_path() -> Path:
    """事件 ledger 的 DB 路径 (三行裁决, spec §2)。

    ① OMO_EVENT_LEDGER_DB 原样; ② 声明了 profile → state 根; ③ 都没声明 → canonical 检出。
    ③ 不是 code_root(): 本 driver 常驻执行位置是被 clean -fdx 的 publisher 克隆。
    canonical_root() 定位不到时抛 RuntimeError, 由调用方转成 fail-closed 的 JSON 日志行。
    """
    env = os.environ.get("OMO_EVENT_LEDGER_DB")
    if env:
        return Path(env).expanduser()
    if os.environ.get("OMOSTATION_STATE_ROOT"):
        return state_root() / "runtime" / "omo" / "event-ledger.sqlite3"
    return canonical_root() / "runtime" / "omo" / "event-ledger.sqlite3"


def log(event: str, **kw) -> None:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **kw}
    line = json.dumps(rec, ensure_ascii=False)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def ancestry_verified_submodules(collector: Path) -> tuple[str, ...]:
    """读出 collector 声明的「按祖先关系被读取的子模块」，作为加深的唯一范围。

    名单的单一真源是 ``panorama-collect.py`` 的 ``ANCESTRY_VERIFIED_SUBMODULES``：
    那边加一条，publisher 就自动多准备一个子模块的历史，反之亦然。用 AST 而不是正则
    读，是为了让改名字面量（`"projects/omo"` → `OMO_REL`）不至于静默失配 —— 那类
    失配会让 A8 悄悄退回 ABSENT。
    """
    import ast

    tree = ast.parse(collector.read_text(encoding="utf-8"), filename=str(collector))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "ANCESTRY_VERIFIED_SUBMODULES"
                   for t in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            raise ValueError("ANCESTRY_VERIFIED_SUBMODULES must be a dict literal")
        paths = []
        for value in node.value.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                raise ValueError("ANCESTRY_VERIFIED_SUBMODULES values must be string literals")
            paths.append(value.value)
        return tuple(paths)
    raise ValueError("ANCESTRY_VERIFIED_SUBMODULES not found in " + str(collector))


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int | None = None,
        readonly: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1",
               PYTHONDONTWRITEBYTECODE="1")
    if readonly:
        # Background probes must not write stat-cache refreshes to the index;
        # Git's child processes inherit this while still computing full status.
        env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, timeout=timeout,
        text=True, capture_output=True, env=env,
    )


def fail(kind: str, **kw) -> int:
    # kind 而非 step: 调用方会传 step=<子步名> 关键字, 同名会 TypeError 掩盖真实错误
    log("failed", step=kind, **kw)
    return 1


def official_origin(url: str) -> bool:
    return url in (CLONE_URL, "git@github.com:starlink-awaken/omostation.git",
                   "ssh://git@github.com/starlink-awaken/omostation.git")


def checkout_alignment(checkout: Path, target: str) -> tuple[bool, dict]:
    """Read exact Git state; never use slow submodule shell traversal as a probe.

    Top-level gitlinks match the existing nonrecursive update contract. Already
    initialized nested repositories are checked too; absent nested modules are
    recorded rather than promoted to a claim of complete recursive checkout.
    """
    details = {"target_oid": target, "checked_modules": [], "uninitialized_nested": []}
    started = time.monotonic()

    def probe(args, root):
        if time.monotonic() - started > 20:
            raise ValueError("alignment_probe_deadline")
        result = run(["git", *args], cwd=root, timeout=5, readonly=True)
        if result.returncode:
            raise ValueError("git_probe_failed:" + args[0])
        return result.stdout

    try:
        if re.fullmatch(r"[0-9a-f]{40}", target) is None:
            raise ValueError("invalid_target_oid")
        root = checkout.resolve()
        if Path(probe(["rev-parse", "--show-toplevel"], root).strip()).resolve() != root:
            raise ValueError("checkout_top_mismatch")
        if probe(["rev-parse", "HEAD", "refs/remotes/origin/main"], root).splitlines() != [target, target]:
            raise ValueError("checkout_oid_changed")
        # Skipping clean -fdx must also account for ignored residue, which is
        # invisible to porcelain status. This is a dry-run, never a deletion.
        if probe(["clean", "-ndx"], root).strip():
            raise ValueError("checkout_clean_residue")
        pending = [(root, True)]
        while pending:
            current, top_level = pending.pop()
            if probe(["for-each-ref", "--format=%(refname)", "refs/replace/"], current).strip():
                raise ValueError("replace_refs_present")
            if probe(["status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"], current).strip():
                raise ValueError("checkout_or_child_dirty")
            for entry in probe(["ls-tree", "-rz", "--full-tree", "HEAD"], current).split("\0"):
                if not entry:
                    continue
                meta, path = entry.split("\t", 1)
                mode, kind, pin = meta.split()
                if mode != "160000":
                    continue
                child = current / path
                relative = str(child.relative_to(root))
                if not (child / ".git").exists():
                    if top_level:
                        raise ValueError("required_submodule_missing:" + relative)
                    details["uninitialized_nested"].append(relative)
                    continue
                # A missing .git must never let git -C walk upward to the parent.
                actual = probe(["rev-parse", "--show-toplevel", "HEAD"], child).splitlines()
                if (len(actual) != 2 or Path(actual[0]).resolve() != child.resolve()
                        or actual[1] != pin or kind != "commit"):
                    raise ValueError("submodule_pin_or_top_mismatch:" + relative)
                details["checked_modules"].append(relative)
                pending.append((child, False))
        details["reason"] = "exact_clean_pins"
        return True, details
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        details["reason"] = str(exc)
        return False, details
    finally:
        details["duration_seconds"] = round(time.monotonic() - started, 4)


def clear_stale_git_lock(checkout: Path, *, max_age_s: float = 600.0) -> None:
    """git 的 index.lock 是秒级短锁; 龄超限且无进程持有 → 必是 crash 残留, 清掉再对齐。
    2026-10-10 14:58 一枚 0 字节锁卡死投影链 43h (每 30min reset 撞锁), 加这道自愈。"""
    lock = checkout / ".git" / "index.lock"
    if not lock.exists():
        return
    age_s = time.time() - lock.stat().st_mtime
    if age_s <= max_age_s:
        return  # 可能属于活 git, 不误杀
    r = subprocess.run(["/usr/sbin/lsof", "--", str(lock)],
                       capture_output=True, text=True)
    if r.stdout.strip():
        log("stale_lock_held", age_s=round(age_s),
            holder=r.stdout.strip().splitlines()[-1][:120])
        return  # 有进程持有 (如长跑 gc), 留给它
    lock.unlink()
    log("stale_lock_cleared", age_s=round(age_s))


def resolve_dashboard_release_root(deploy_dir: Path) -> Path:
    """Bind exactly one direct immutable legacy or explicit publication release."""
    link = deploy_dir / "current"
    if not link.is_symlink():
        return deploy_dir.resolve()
    target = link.resolve()
    if (target.parent != (deploy_dir / "releases").resolve()
            or re.fullmatch(r"[0-9a-f]{40}(?:--pub-[0-9a-f]{32})?", target.name) is None
            or not target.is_dir()):
        raise ValueError("dashboard_release_invalid")
    return target


def main() -> int:
    # 0) 防重入锁
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as lockf:
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("skip_already_running")
            return 0

        # 1) 定位 ledger 根 —— fail-closed: 定位不到就退出, 别跑完同步才发现
        try:
            ledger_db = ledger_db_path()
        except RuntimeError as exc:
            return fail("ledger_root", error=str(exc)[:300])
        log("ledger_root_resolved", path=str(ledger_db))
        try:
            task_root = task_state_root()
        except RuntimeError as exc:
            return fail("task_root", error=str(exc)[:300])
        log("task_root_resolved", path=str(task_root))

        # 2) 确保专用检出存在
        if not (CHECKOUT / ".git").exists():
            CHECKOUT.parent.mkdir(parents=True, exist_ok=True)
            r = run(["git", "clone", "--depth", "200", CLONE_URL, str(CHECKOUT)], timeout=1800)
            if r.returncode != 0:
                return fail("clone", stderr=(r.stderr or "")[-500:])
            log("checkout_cloned", path=str(CHECKOUT))
        # Both transport directions must identify the exact official repository.
        r = run(["git", "rev-parse", "--show-toplevel"], cwd=CHECKOUT, timeout=5)
        if r.returncode or Path(r.stdout.strip()).resolve() != CHECKOUT.resolve():
            return fail("checkout_top_mismatch")
        for flags in (["--all"], ["--push", "--all"]):
            r = run(["git", "remote", "get-url", *flags, "origin"], cwd=CHECKOUT, timeout=10)
            urls = (r.stdout or "").splitlines()
            if r.returncode or len(urls) != 1 or not official_origin(urls[0]):
                return fail("remote_hygiene", urls=urls)
        log("remote_hygiene_ok", url=urls[0])

        # Always fetch; a cached origin/main must not masquerade as live authority.
        started = time.monotonic()
        try:
            r = run(["git", "fetch", "--no-recurse-submodules", "origin",
                     "+refs/heads/main:refs/remotes/origin/main"], cwd=CHECKOUT, timeout=1800)
        except subprocess.TimeoutExpired:
            return fail("sync_step", sub="fetch", error="timeout")
        log("sync_step_complete", step="fetch", seconds=round(time.monotonic() - started, 4), rc=r.returncode)
        if r.returncode:
            return fail("sync_step", sub="fetch", stderr=(r.stderr or "")[-500:])
        r = run(["git", "rev-parse", "refs/remotes/origin/main^{commit}"], cwd=CHECKOUT, timeout=5)
        target = r.stdout.strip()
        if r.returncode or re.fullmatch(r"[0-9a-f]{40}", target) is None:
            return fail("fetched_main_oid_invalid")
        unchanged, alignment = checkout_alignment(CHECKOUT, target)
        log("checkout_alignment", route="unchanged" if unchanged else "full", **alignment)
        # `--depth` cannot widen an already-shallow checkout: re-running
        # `submodule update --init --depth 200` over a depth-1 submodule leaves
        # it at 1 commit (verified locally). Ancestry-verified gates need the
        # real history behind the pin, so fetch it explicitly — and only for the
        # submodules the collector declares, not all 16: the list is the single
        # source of truth and today it is one entry, so the failure surface
        # shrinks with it. `--depth` (not `--deepen`) keeps the boundary
        # bounded and the step idempotent.
        ancestry_submodules = () if unchanged else ancestry_verified_submodules(
            CHECKOUT / "bin/panorama/panorama-collect.py"
        )
        deepen_steps = [
            (["git", "-C", str(CHECKOUT / rel), "fetch", "--depth",
              str(SUBMODULE_HISTORY_DEPTH), "origin"],
             600, SUBMODULE_DEEPEN_ATTEMPTS)
            for rel in ancestry_submodules
        ]
        steps = ([] if unchanged else [
            (["git", "reset", "--hard", "origin/main"], 300, 1),
            (["git", "clean", "-fdx"], 600, 1),
            (["git", "submodule", "sync", "--recursive"], 300, 1),
            # ⚠ `--force` 是对齐契约的一半: `checkout_alignment` 要求子模块工作树
            #   与钉住的 commit 逐字一致 (`--ignore-submodules=none`), 而不带
            #   `--force` 的 `submodule update` **不会复位「已在正确 commit 上的
            #   脏文件」** ⇒ ⇒ `post_sync_alignment` 永远报
            #   `checkout_or_child_dirty` ⇒ ⇒ 作业永久 exit 1 ⇒ 入口层数据不更新。
            #   ⇒ ⇒ 实测 (2026-10-26): publisher 的 projects/omlxc 被手改了一行,
            #   于是每一轮都对不齐。⇒ ⇒ 复位必须与对齐契约同强度。
            (["git", "submodule", "update", "--init", "--force", "--depth",
              str(SUBMODULE_HISTORY_DEPTH)], 3600, 1),
        ]) + deepen_steps
        if not unchanged:
            clear_stale_git_lock(CHECKOUT)
        for cmd, timeout, attempts in steps:
            r = None
            for attempt in range(1, attempts + 1):
                started = time.monotonic()
                r = run(cmd, cwd=CHECKOUT, timeout=timeout)
                log("sync_step_complete", step=" ".join(cmd[1:3]), attempt=attempt,
                    seconds=round(time.monotonic() - started, 4), rc=r.returncode)
                if r.returncode == 0:
                    break
                if attempt < attempts:
                    time.sleep(STEP_RETRY_DELAY_SEC)
            if r.returncode != 0:
                return fail("sync_step", sub=cmd[1], attempt=attempt,
                            stderr=(r.stderr or "")[-500:])
        if not unchanged:
            aligned, alignment = checkout_alignment(CHECKOUT, target)
            if not aligned:
                return fail("post_sync_alignment", **alignment)
        log("checkout_synced", head=target, route="unchanged" if unchanged else "full")

        # 3) 全量发布 (用检出内 publisher, 与 origin/main 同步演进)
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PANORAMA_ROOT"] = str(CHECKOUT)
        env["PANORAMA_CODE_ROOT"] = str(CHECKOUT)
        env["ZHIXING_DASHBOARD_STATE_ROOT"] = str(DEPLOY_DIR)
        env["OMO_EVENT_LEDGER_DB"] = str(ledger_db)
        env["OMOSTATION_STATE_ROOT"] = str(task_root)
        # Bind one immutable release once; mutable projections stay at DEPLOY_DIR.
        try:
            dashboard_code_root = resolve_dashboard_release_root(DEPLOY_DIR)
        except ValueError:
            return fail("dashboard_release_invalid")
        env["ZHIXING_DASHBOARD_CODE_ROOT"] = str(dashboard_code_root)
        started = time.monotonic()
        r = subprocess.run(
            [sys.executable, "-B", str(CHECKOUT / "bin/panorama/panorama-collect.py")],
            cwd=str(CHECKOUT), env=env, text=True, capture_output=True,
            timeout=PUBLISHER_TIMEOUT_SEC,
        )
        if r.returncode != 0:
            return fail(
                "publish", rc=r.returncode,
                stderr=(r.stderr or "")[-800:], stdout_tail=(r.stdout or "")[-800:],
            )
        log("publish_ok", seconds=round(time.monotonic() - started, 4), stdout_tail=(r.stdout or "")[-500:])
        return 0


if __name__ == "__main__":
    sys.exit(main())
