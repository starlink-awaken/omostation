#!/usr/bin/env python3
"""Verify that root gitlinks point to commits reachable from submodule remotes.

16 个子模块的判定彼此独立, 故默认并发 (env `PASW_JOBS` 覆盖并发度, `=1` 完全回退
串行)。结果按 index 归位, 与串行逐项一致 —— 并发只改墙钟, 不改结论。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# 治本 followup E (2026-07-04): pre-push hook 跑时 git 设 GIT_DIR/GIT_WORK_TREE 指向主仓,
# 泄漏到 subprocess 的 `git -C <submodule>` → 读主仓而非子模块 → fetch/branch --contains 错乱 → 全误报 unreachable
# (实测: 干净环境 17 gitlinks PASS / 模拟 hook 17 FAIL, 同 followup C sync GIT_DIR 病根).
# pop 后 subprocess 继承干净环境, git -C <submodule> 读子模块自己的 .git.
for _env in ("GIT_DIR", "GIT_WORK_TREE", "GIT_QUARANTINE_PATH"):
    os.environ.pop(_env, None)

# ── 有界执行 (2026-09-24 复盘 H1) ────────────────────────────────────────
# run() 原本无任何超时: pre-push 走 `--fetch`, 冷 `--depth 1` 子模块上 `git fetch`
# 可无限挂起 (实测一次 push 卡死 40min, tmp_pack 字节零增长)。hook-runner 声明的
# run_check 超时参数是死参数 (读进 local 后从未使用), 所以边界必须建在本脚本内。
CMD_TIMEOUT_SECONDS = 60           # 本地 git 查询: 磁盘级, 60s 已属异常
FETCH_TIMEOUT_SECONDS = 120        # 单次网络 fetch 上限
NETWORK_BUDGET_SECONDS = 300       # 整轮网络工作总预算 (× 子模块数不再线性放大)
TIMEOUT_RC = 124                   # 约定俗成的 timeout 退出码, 与真失败区分
#: 「本地没能验完」的 reason 前缀 —— 让降级在汇总里可见, 而不是混进 PASS
UNVERIFIED_PREFIX = "unverified: "
# 陈旧 shallow.lock 的最小年龄: 低于此值视为可能仍有活跃 fetch 在用, 不清除。
STALE_LOCK_MIN_AGE_SECONDS = 30.0

# ── 子模块并发 (2026-09-28, E2-A) ───────────────────────────────────────
# 实测: CI 里 16 个子模块逐个 `fetch --unshallow` + `branch --contains` **全串行**,
# 占 gac-gate job 32–47s (仅次于 strict), 本地 pre-push 同一条命令 64s+。
# 子模块之间无数据依赖 ⇒ 可并发; 结果按 index 归位 ⇒ 与串行**逐项一致**
# (findings 顺序/内容、report/JSON/stdout 都不变)。
# `PASW_JOBS=1` 一键回退完全串行 —— 出问题无需回滚代码。
DEFAULT_PASW_JOBS = 4  # 网络为主: 并发再高只增加 remote 限流/带宽争用风险

#: main() 里置为 time.monotonic() + NETWORK_BUDGET_SECONDS; 单测可为 None
_NETWORK_DEADLINE: float | None = None


def _pasw_jobs(targets: int) -> int:
    """并发度: `PASW_JOBS` 覆盖, 默认 min(DEFAULT_PASW_JOBS, cpu_count)。<=1 即串行。

    上限再取 min(targets) —— 待检子模块少于并发度时不该空转线程。
    """
    try:
        configured = int(os.environ.get("PASW_JOBS", "0"))
    except ValueError:
        configured = 0
    if configured > 0:
        jobs = configured
    else:
        jobs = min(DEFAULT_PASW_JOBS, max(1, os.cpu_count() or 1))
    return max(1, min(jobs, max(1, targets)))


def _remaining_network_budget() -> float:
    """Per-fetch timeout, shrunk by the whole-run network budget."""
    if _NETWORK_DEADLINE is None:
        return float(FETCH_TIMEOUT_SECONDS)
    return max(0.0, min(float(FETCH_TIMEOUT_SECONDS), _NETWORK_DEADLINE - time.monotonic()))


def run(
    cmd: list[str],
    *,
    cwd: Path = WORKSPACE,
    check: bool = False,
    timeout: float | None = CMD_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Run a command under a wall-clock bound.

    A timeout returns rc=TIMEOUT_RC with the reason on stderr instead of
    raising, so callers keep their existing non-zero handling and no caller
    can hang the pre-push hook. Pass timeout=None to opt out deliberately.
    """
    try:
        return subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=check, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout if isinstance(exc.stdout, str) else ""
        return subprocess.CompletedProcess(cmd, TIMEOUT_RC, partial, f"timed out after {timeout}s")


def _looks_like_locked(stderr: str) -> bool:
    """True when a git fetch failed because another process holds a lock."""
    text = (stderr or "").lower()
    return (
        "another git process" in text
        or "index.lock" in text
        or "shallow.lock" in text
        or "unable to create" in text and "lock" in text
        or "cannot lock ref" in text
        or ("lock" in text and "exists" in text)
    )


def _clear_stale_shallow_lock(submodule_dir: Path) -> bool:
    """Remove a stale ``shallow.lock`` left by an interrupted fetch.

    Returns True only when a lock file was actually removed. The lock lives in the
    submodule's git dir, not the working tree. We only ever reach this after a
    fetch that *reported a lock error*, so a lock held by a live process would mean
    git's own locking failed; to stay conservative the removal is skipped when the
    lock is younger than ``STALE_LOCK_MIN_AGE_SECONDS``.
    """
    try:
        probe = run(["git", "rev-parse", "--absolute-git-dir"], cwd=submodule_dir)
        git_dir = probe.stdout.strip()
        if not git_dir:
            return False
        lock = Path(git_dir) / "shallow.lock"
        if not lock.is_file():
            return False
        age = time.time() - lock.stat().st_mtime
        if age < STALE_LOCK_MIN_AGE_SECONDS:
            return False
        lock.unlink()
        return True
    except OSError:
        return False


def _fetch_verdict(require_main: bool, detail: str) -> tuple[bool, str]:
    """Translate an unverifiable fetch into a gate verdict.

    网络不可判定 ≠ gitlink 不可达: 本地降级为「未验证」(与下方 partial worktree
    同一哲学, CI full checkout 才是最终守门员), 拒绝把超时伪装成 unreachable 阻断 push。
    require_main 模式 (CI) 没有更低的层兜底, 保持硬失败。
    """
    if require_main:
        return False, f"{detail}; cannot verify origin/main ancestry"
    return True, f"{UNVERIFIED_PREFIX}{detail} — CI full checkout will verify"


def submodule_paths() -> list[str]:
    result = run(
        [
            "git",
            "config",
            "--file",
            ".gitmodules",
            "--get-regexp",
            r"^submodule\..*\.path$",
        ]
    )
    if result.returncode != 0:
        return []
    return [line.split(maxsplit=1)[1] for line in result.stdout.splitlines() if line.strip()]


def gitlink_sha(path: str, source: str) -> str | None:
    if source == "worktree":
        # An uninitialized submodule may still have an empty directory. Running
        # `git -C` there walks up into the superproject and returns the root
        # HEAD, which is not the gitlink. Fall back to the staged gitlink until
        # the submodule has its own Git marker.
        if not (WORKSPACE / path / ".git").exists():
            return gitlink_sha(path, "index")
        result = run(["git", "-C", path, "rev-parse", "HEAD"])
        return result.stdout.strip() if result.returncode == 0 else None
    if source == "index":
        result = run(["git", "ls-files", "-s", "--", path])
        if result.returncode != 0 or not result.stdout.strip():
            return None
        parts = result.stdout.split()
        return parts[1] if len(parts) >= 2 and parts[0] == "160000" else None

    result = run(["git", "ls-tree", "HEAD", "--", path])
    if result.returncode != 0 or not result.stdout.strip():
        return None
    meta, _sep, _name = result.stdout.partition("\t")
    parts = meta.split()
    return parts[2] if len(parts) >= 3 and parts[0] == "160000" else None


def remote_contains(path: str, sha: str, *, fetch: bool, require_main: bool = False) -> tuple[bool, str]:
    submodule_dir = WORKSPACE / path
    if not submodule_dir.exists():
        return False, "submodule working tree missing"
    if not (submodule_dir / ".git").exists():
        if require_main:
            return (
                False,
                "submodule not initialized; cannot verify origin/main ancestry",
            )
        return (
            True,
            f"{UNVERIFIED_PREFIX}submodule not initialized (partial worktree) — CI full checkout will verify",
        )
    # G1 (P79, 2026-08-04): partial worktree 降级 — 子模块目录存在但非有效 git repo
    # (PASW ISOLATED partial init / 新建 worktree 未 init) → 本地 push 降级 warning 不 block.
    # 治本 #907 35+ iteration: partial worktree reachability gate false-positive 死路
    # (init 子模块超时 10min, escape hatch 不覆盖 reachability).
    # 安全网: CI (full checkout, 子模块全 init) 跑同一 gate 正常验证, 是最终守门员.
    init_check = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=submodule_dir)
    # stdout 检查覆盖失败 (空) + false 两种非 init 情况, returncode 冗余
    if init_check.stdout.strip() != "true":
        if require_main:
            return (
                False,
                "submodule not initialized; cannot verify origin/main ancestry",
            )
        return (
            True,
            f"{UNVERIFIED_PREFIX}submodule not initialized (partial worktree) — CI full checkout will verify",
        )

    if fetch:
        # CI actions/checkout depth=1 → submodule shallow → 非 HEAD SHA 不在浅历史
        # → branch --contains 误报 unreachable (#907 cockpit 0fa09c6 实证可达但 gate fail).
        # shallow repo 先 --unshallow 拿 full history; 失败回退 normal fetch.
        # 单 heads refspec (heads→remotes/origin/*, 不覆盖本地 checked-out refs/heads/main).
        # 配合 unshallow (C 层) 拿全 main 历史 — unshallow 后 heads refs 已含所有可达 SHA.
        refspec = "+refs/heads/*:refs/remotes/origin/*"
        budget = _remaining_network_budget()
        if budget <= 0:
            # 预算耗尽就不再派生 git (实测会白 spawn 8 个进程再瞬时超时)
            return _fetch_verdict(require_main, f"network budget exhausted ({NETWORK_BUDGET_SECONDS}s)")
        shallow_res = run(["git", "rev-parse", "--is-shallow-repository"], cwd=submodule_dir)
        is_shallow = shallow_res.stdout.strip() == "true"
        if is_shallow:
            fetch_result = run(
                ["git", "fetch", "--quiet", "--unshallow", "origin", refspec],
                cwd=submodule_dir,
                timeout=budget,
            )
            # 2026-09-29: 上一次 unshallow 超时会留下 shallow.lock, 使本次 fetch 立即
            # 失败于 "Another git process seems to be running" → 仓库永远停在浅克隆 →
            # 祖先链走不通 → 误报 unreachable → **push 被永久阻断**, 而唯一能修好它的
            # 正是这个被阻断的 push (自我阻断死循环, #907 同一类)。
            # 只在 fetch 报锁错误时才清锁并重试一次 —— 活跃进程的锁不会被误删。
            if fetch_result.returncode not in {0, TIMEOUT_RC} and _looks_like_locked(
                fetch_result.stderr
            ):
                if _clear_stale_shallow_lock(submodule_dir):
                    fetch_result = run(
                        ["git", "fetch", "--quiet", "--unshallow", "origin", refspec],
                        cwd=submodule_dir,
                        timeout=_remaining_network_budget() or budget,
                    )
            # unshallow 超时就不再补一发 normal fetch: 预算已耗尽, 重试只把挂死换成慢死
            if fetch_result.returncode == TIMEOUT_RC:
                return _fetch_verdict(require_main, f"fetch timed out ({fetch_result.stderr.strip()})")
            if fetch_result.returncode != 0:
                retry_budget = _remaining_network_budget()
                if retry_budget <= 0:
                    return _fetch_verdict(
                        require_main, f"network budget exhausted ({NETWORK_BUDGET_SECONDS}s)"
                    )
                fetch_result = run(
                    ["git", "fetch", "--quiet", "origin", refspec],
                    cwd=submodule_dir,
                    timeout=retry_budget,
                )
        else:
            fetch_result = run(
                ["git", "fetch", "--quiet", "origin", refspec],
                cwd=submodule_dir,
                timeout=budget,
            )
        if fetch_result.returncode == TIMEOUT_RC:
            return _fetch_verdict(require_main, f"fetch timed out ({fetch_result.stderr.strip()})")
        if fetch_result.returncode != 0:
            # 2026-09-29: 此分支原先直接硬失败, 绕过了 _fetch_verdict 的降级哲学 ——
            # 而 _fetch_verdict 的 docstring 明写「网络不可判定 ≠ gitlink 不可达,
            # 拒绝把超时伪装成 unreachable 阻断 push」。本地原因导致 fetch 失败
            # (陈旧锁 / 认证 / 离线) 同样属于「不可判定」, 不应阻断 push。
            # require_main (CI) 无更低层兜底, _fetch_verdict 仍返回硬失败, 语义不变。
            return _fetch_verdict(require_main, f"fetch failed: {fetch_result.stderr.strip()}")

        # 2026-09-29: fetch 返回 0 **不代表仓库已加深**。unshallow 失败后回退的普通
        # fetch 会在浅克隆上成功返回, 历史仍然截断 —— 此时祖先关系是「不可判定」而非
        # 「不可达」。原实现继续走 branch --contains, 拿到空结果就断言 unreachable,
        # 正是本函数 docstring 明确拒绝的那种「把不可判定伪装成不可达」。
        still_shallow = (
            run(["git", "rev-parse", "--is-shallow-repository"], cwd=submodule_dir).stdout.strip()
            == "true"
        )
        if still_shallow:
            return _fetch_verdict(
                require_main, "submodule still shallow after fetch; ancestry not decidable"
            )
        # 2026-09-29: 还存在「非浅克隆但对象缺失」的残缺 clone —— 2026-09-29 实测
        # 某 PASW 工作树的 kairon: is-shallow=false 但 `rev-parse HEAD` 直接报
        # unknown revision, origin/main 引用却是新的。此时 `branch -r --contains <sha>`
        # 因对象不存在而**静默返回空**, 同样被误判为 unreachable。
        # 判定锚点: SHA 对象本地是否存在 —— 不存在则可达性根本无从计算。
        have_object = run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=submodule_dir
        ).returncode == 0
        if not have_object:
            return _fetch_verdict(
                require_main, f"commit object {sha[:12]} absent locally; ancestry not decidable"
            )

    if require_main:
        main_ref = "refs/remotes/origin/main"
        contains_main = run(["git", "merge-base", "--is-ancestor", sha, main_ref], cwd=submodule_dir)
        if contains_main.returncode == 0:
            return True, main_ref
        if contains_main.returncode != 1:
            detail = contains_main.stderr.strip() or f"exit {contains_main.returncode}"
            return False, f"main ancestry query failed: {detail}"
        return False, f"not contained in {main_ref}"

    # 2026-09-29: 原实现用 `git branch -r --contains`, 它**依赖一个可解析的 HEAD**。
    # PASW 工作树里存在 HEAD 不可解析的残缺 clone (2026-09-29 实测某 kairon:
    # `rev-parse HEAD` -> unknown revision, 而 gitlink 本身可达), 此时该命令
    # 以 rc=128 + "failed to resolve HEAD as a valid ref" 失败, stdout 为空。
    # 而此处**从不检查 returncode** —— 报错与「真的不可达」被当成同一件事,
    # 于是误报 unreachable 并阻断 push。
    # 改为直接回答真正的问题: gitlink 是否是**主线** ref 的祖先。
    #
    # 只认远端跟踪 ref (refs/remotes/*), **不认 refs/heads/main**: clone 里的本地
    # main 可能领先于 origin/main 甚至含孤立提交, 拿它当主线等于给不可达提交开后门
    # (2026-09-29 回归测试实测抓到这一点)。
    mainline_candidates = [
        line.strip()
        for line in run(
            ["git", "for-each-ref", "--format=%(refname)", "refs/remotes/"],
            cwd=submodule_dir,
        ).stdout.splitlines()
        if line.strip() and not line.strip().endswith("/HEAD")
    ]
    ancestry_errors: list[str] = []
    matched: list[str] = []
    for ref in mainline_candidates:
        is_ancestor = run(["git", "merge-base", "--is-ancestor", sha, ref], cwd=submodule_dir)
        if is_ancestor.returncode == 0:
            matched.append(ref)
        elif is_ancestor.returncode == 1:
            continue  # 明确不是祖先
        else:
            ancestry_errors.append(is_ancestor.stderr.strip() or f"exit {is_ancestor.returncode}")
    if matched:
        return True, ", ".join(matched[:3])
    if not mainline_candidates:
        return _fetch_verdict(
            require_main, "no remote-tracking ref present; mainline unknown"
        )
    if ancestry_errors:
        # 可达性无法判定 (而非不可达) —— 降级, 不阻断 push
        return _fetch_verdict(
            require_main, f"ancestry query failed: {ancestry_errors[0]}"
        )
    return False, "not an ancestor of any mainline ref"


def detect_drift(path: str) -> dict[str, object] | None:
    """Check if local working tree HEAD differs from the gitlink SHA (drift detection).

    Returns a finding dict when drift is detected, None when consistent.
    Drift means: the local checked-out commit does not match the gitlink
    recorded in the superproject index/HEAD. This is the P97 squash-SHA
    dangling pattern and the local-uncommitted-change pattern.
    """
    submodule_dir = WORKSPACE / path
    if not submodule_dir.exists():
        return None
    if not (submodule_dir / ".git").exists():
        return None
    # Submodule must be initialized to read local HEAD
    init_check = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=submodule_dir)
    if init_check.stdout.strip() != "true":
        return None
    local_result = run(["git", "-C", path, "rev-parse", "HEAD"])
    if local_result.returncode != 0 or not local_result.stdout.strip():
        return None
    local_sha = local_result.stdout.strip()
    # Read gitlink from the index (most authoritative for the superproject intent)
    gitlink = gitlink_sha(path, "index")
    if gitlink is None:
        return None
    if local_sha == gitlink:
        return None
    return {
        "path": path,
        "local_sha": local_sha,
        "gitlink_sha": gitlink,
        "ok": False,
        "reason": f"gitlink drift: local HEAD ({local_sha[:12]}) != gitlink ({gitlink[:12]})",
    }


def auto_fast_forward(path: str, gitlink_sha: str) -> tuple[bool, str]:
    """Try to fast-forward the submodule working tree to match the gitlink SHA.

    Returns (success, message). Only performs fast-forward (non-destructive);
    refuses if the target is not an ancestor of the local branch or if there
    are uncommitted changes. This is the circuit_breaker: fast-forward failure
    stops, never forces update.
    """
    submodule_dir = WORKSPACE / path
    if not submodule_dir.exists():
        return False, "submodule directory missing"
    if not (submodule_dir / ".git").exists():
        return False, "submodule not initialized"
    init_check = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=submodule_dir)
    if init_check.stdout.strip() != "true":
        return False, "submodule not initialized"
    # Check for uncommitted changes — refuse to move HEAD if dirty
    status = run(["git", "status", "--porcelain"], cwd=submodule_dir)
    if status.stdout.strip():
        return False, "submodule has uncommitted changes — refusing fast-forward"
    # Verify target is reachable (fetch first if needed)
    budget = _remaining_network_budget()
    if budget <= 0:
        return False, f"fast-forward aborted: network budget exhausted ({NETWORK_BUDGET_SECONDS}s)"
    fetch_result = run(
        ["git", "fetch", "--quiet", "origin", f"+refs/heads/*:refs/remotes/origin/*"],
        cwd=submodule_dir,
        timeout=budget,
    )
    if fetch_result.returncode == TIMEOUT_RC:
        # circuit_breaker: 修不动就停, 但要说清是「没验完」而不是「指针坏了」
        return False, f"fast-forward aborted: {fetch_result.stderr.strip()}"
    if fetch_result.returncode != 0:
        return False, f"fetch failed: {fetch_result.stderr.strip()}"
    # Check if target is an ancestor of current HEAD (can only ff forward)
    is_ancestor = run(
        ["git", "merge-base", "--is-ancestor", "HEAD", gitlink_sha],
        cwd=submodule_dir,
    )
    if is_ancestor.returncode != 0:
        return False, f"gitlink SHA {gitlink_sha[:12]} is not a descendant of local HEAD — fast-forward impossible"
    # Perform the fast-forward checkout
    ff_result = run(["git", "checkout", "--quiet", gitlink_sha], cwd=submodule_dir)
    if ff_result.returncode != 0:
        return False, f"checkout failed: {ff_result.stderr.strip()}"
    return True, f"fast-forwarded to {gitlink_sha[:12]}"


def changed_submodules(base_ref: str, source: str) -> set[str] | None:
    """相对 base_ref 真正变了 gitlink 的子模块路径。

    base_ref 不可解析(未 fetch / 新克隆 / 分支不存在)时返回 None,
    调用方回退全量 —— 增量只用来提速, 绝不能因基线缺失而漏检。
    """
    if run(["git", "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"]).returncode != 0:
        return None
    changed: set[str] = set()
    for path in submodule_paths():
        base = run(["git", "ls-tree", base_ref, "--", path])
        base_sha = None
        if base.returncode == 0 and base.stdout.strip():
            meta, _sep, _name = base.stdout.partition("\t")
            parts = meta.split()
            if len(parts) >= 3 and parts[0] == "160000":
                base_sha = parts[2]
        if gitlink_sha(path, source) != base_sha:
            changed.add(path)
    return changed


def check_one(path: str, source: str, *, fetch: bool, require_main: bool) -> dict[str, object]:
    """单个子模块的可达性判定 —— 与串行循环里的分支逐项同语义。

    拆成独立函数是为了能进线程池 (check() 里并发调用); 它自身不写全局状态,
    因此可并发 (网络预算 `_NETWORK_DEADLINE` 只在 main() 写一次, 并发只读)。
    """
    sha = gitlink_sha(path, source)
    if sha is None:
        return {"path": path, "sha": None, "ok": False, "reason": f"no {source} gitlink"}
    ok, detail = remote_contains(path, sha, fetch=fetch, require_main=require_main)
    return {"path": path, "sha": sha, "ok": ok, "reason": detail}


def check(
    source: str,
    *,
    fetch: bool,
    require_main: bool = False,
    skip_paths: set[str] | None = None,
    only_paths: set[str] | None = None,
) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    checked = 0
    skipped = 0
    paths = submodule_paths()
    if only_paths is not None:
        # 增量模式: 只检查本次 diff 实际变化的 submodule
        paths = [p for p in paths if p in only_paths]
        if not paths:
            return {
                "ok": True,
                "source": source,
                "fetch": fetch,
                "checked": 0,
                "skipped": 0,
                "unverified": 0,
                "mode": "incremental-empty",
                "failures": [],
                "findings": [],
            }
    pending: list[str] = []
    for path in paths:
        if skip_paths and path in skip_paths:
            skipped += 1
            continue
        if only_paths is not None and path not in only_paths:
            skipped += 1
            continue
        pending.append(path)

    jobs = _pasw_jobs(len(pending))
    if len(pending) > 1 and jobs > 1:
        # 并发只改墙钟, 不改结论: 池内 future → index 映射, 完成后按 index 归位
        # ⇒ findings 顺序与串行逐项一致 (report/JSON/stdout 均不变)。
        slots: list[dict[str, object] | None] = [None] * len(pending)
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {
                pool.submit(check_one, path, source, fetch=fetch, require_main=require_main): index
                for index, path in enumerate(pending)
            }
            for future in as_completed(futures):
                slots[futures[future]] = future.result()
        per_path = [item for item in slots if item is not None]
    else:
        per_path = [check_one(path, source, fetch=fetch, require_main=require_main) for path in pending]

    for item in per_path:
        if item["sha"] is not None:
            checked += 1
        findings.append(item)
    failures = [item for item in findings if not item["ok"]]
    unverified = [
        item
        for item in findings
        if item["ok"] and str(item["reason"]).startswith(UNVERIFIED_PREFIX)
    ]
    return {
        "ok": not failures,
        "source": source,
        "fetch": fetch,
        "require_main": require_main,
        "checked": checked,
        "skipped": skipped,
        "unverified": len(unverified),
        "failures": failures,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify submodule gitlinks are reachable from origin")
    parser.add_argument("--source", choices=("head", "index", "worktree"), default="head")
    parser.add_argument("--fetch", action="store_true", help="Fetch origin branches before checking")
    parser.add_argument(
        "--require-main",
        action="store_true",
        help="Require each gitlink to be an ancestor of refs/remotes/origin/main, "
        "not merely reachable from any origin branch",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--drift-check",
        action="store_true",
        help="Detect gitlink drift: local HEAD vs gitlink SHA mismatch (P97 squash-SHA dangling pattern)",
    )
    parser.add_argument(
        "--auto-fast-forward",
        action="store_true",
        help="When drift is detected, attempt fast-forward to the gitlink SHA (circuit_breaker: stops on failure)",
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        default=[],
        help="Submodule paths to skip (known false positives)",
    )
    parser.add_argument("--skip-file", type=str, help="File with submodule paths to skip (one per line)")
    parser.add_argument(
        "--changed-from",
        type=str,
        default=None,
        metavar="REF",
        help="Incremental mode: only check submodules whose selected-source gitlink differs from REF "
        "(e.g. origin/main). Unchanged submodules are skipped — parallel-agent mid-flight state "
        "no longer blocks local pushes. CI full checkout (no flag) remains the full-coverage gate. "
        "基线不可解析时自动回退全量。",
    )
    args = parser.parse_args()

    # 防御: WORKSPACE 不存在 (worktree 被 cleanup 误清等) → 友好退出, 不 traceback
    # (2026-08-03: 曾因 worktree 被 cleanup 清理, subprocess cwd 失效 → FileNotFoundError)
    if not WORKSPACE.exists():
        sys.stderr.write(
            f"❌ WORKSPACE 不存在: {WORKSPACE}\n"
            f"   worktree 可能被外部清理 (cleanup TTL?). 中止 push 避免误判 unreachable.\n"
        )
        return 2

    # 整轮网络预算: N 个子模块 × 各自 timeout 不再线性放大成半小时
    global _NETWORK_DEADLINE
    _NETWORK_DEADLINE = time.monotonic() + NETWORK_BUDGET_SECONDS

    skip_paths: set[str] = set(args.skip)
    if args.skip_file:
        skip_file = Path(args.skip_file)
        if skip_file.exists():
            skip_paths.update(
                line.strip()
                for line in skip_file.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            )

    only_paths: set[str] | None = None
    mode = "full"
    if args.changed_from:
        only_paths = changed_submodules(args.changed_from, args.source)
        if only_paths is None:
            sys.stderr.write(f"[reachability] 基线 {args.changed_from} 不可解析, 回退全量校验\n")
            mode = "full (baseline unresolvable)"
        else:
            mode = f"changed-from {args.changed_from}"

    # --- Gitlink drift detection (BET-Y1Q4-T6-03) ---
    drift_findings: list[dict[str, object]] = []
    drift_ok = True
    if args.drift_check:
        paths = submodule_paths()
        for path in paths:
            finding = detect_drift(path)
            if finding is not None:
                drift_findings.append(finding)
                drift_ok = False
                # Auto fast-forward if requested (circuit_breaker: fails → stop, no force)
                if args.auto_fast_forward and finding.get("gitlink_sha"):
                    ff_ok, ff_msg = auto_fast_forward(path, finding["gitlink_sha"])
                    finding["fast_forward"] = {"ok": ff_ok, "message": ff_msg}
                    if ff_ok:
                        # After successful ff, drift is resolved
                        finding["ok"] = True
                        finding["reason"] = f"drift resolved: {ff_msg}"
                        drift_ok = True

    report = check(
        args.source,
        fetch=args.fetch,
        require_main=args.require_main,
        skip_paths=skip_paths,
        only_paths=only_paths,
    )
    report["mode"] = mode
    if args.drift_check:
        report["drift_findings"] = drift_findings
        report["drift_ok"] = drift_ok
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["ok"] and (not args.drift_check or drift_ok):
        skip_msg = f", skipped={report['skipped']}" if report["skipped"] else ""
        mode_msg = f", mode={mode}" if mode != "full" else ""
        drift_msg = f", drift={len(drift_findings)}" if drift_findings else ""
        unver = [item for item in report["findings"] if str(item["reason"]).startswith(UNVERIFIED_PREFIX)]
        unver_msg = f", unverified={len(unver)}" if unver else ""
        print(f"submodule-reachability: PASS ({report['checked']} gitlinks, source={args.source}{skip_msg}{mode_msg}{drift_msg}{unver_msg})")
        # 降级必须喊出来: 静默 PASS 会让「没验完」读起来像「验过了」
        for item in unver:
            sys.stderr.write(f"[reachability] ⚠️  {item['path']}: {item['reason']}\n")
    elif not report["ok"]:
        for item in report["failures"]:
            print(f"{item['path']}: {item['sha'] or '-'} unreachable: {item['reason']}")
        print(f"submodule-reachability: FAIL ({len(report['failures'])} failures)")
    else:
        # drift failures only (reachability passed)
        for item in drift_findings:
            if not item.get("ok", True):
                print(f"{item['path']}: {item['reason']}")
        print(f"submodule-reachability: FAIL (drift: {len([f for f in drift_findings if not f.get('ok', True)])} submodules)")
    overall_ok = report["ok"] and (not args.drift_check or drift_ok)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
