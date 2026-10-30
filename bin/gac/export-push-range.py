#!/usr/bin/env python3
"""从 pre-push 的 stdin ref 对导出本次 push 的 commit 范围 (PUSH_RANGE)。

**为什么需要它**: `bin/change-lane-check.py` 的 `PUSH_RANGE` 分支 (ADR-4443 v9 设计)
在 `.githooks/` 里**从来没有导出点** ⇒ 该机制自设计起从未生效
(2026-10-30 实锤: `grep -rn PUSH_RANGE .githooks/` = 0 命中, 仓内
`docs/reports/2026-10-27-bet-273-...md` §6 已记同一事实)。
本脚本补上那个导出点。

**输入**: git pre-push 把 ref 对写到 stdin, 每行 4 个字段:
    <local_ref> <local_sha> <remote_ref> <remote_sha>
`hook-runner.sh` 已把 stdin 存到 `$PUSH_REFS_FILE` (export 出来) ⇒ 本脚本读它。

**输出**: 打印 `PUSH_RANGE=<base>..<head>` 到 stdout (一行), 供调用方 export。

**base 怎么取** —— 这是本脚本的全部难点:

stdin 里的 `remote_sha` 是**推送前**远端指向的 commit, 该对象在本地**通常不存在**
(实测 `git cat-file -t <remote_sha>` 失败 —— 本地没 fetch 过那个点)。所以不能用它。

本脚本取 `merge-base(origin/<branch>, local_sha)`:
- `origin/<branch>` 是 remote-tracking ref, 本地必有, 指向远端**当前**位置;
- merge-base 与 local_sha 求交 ⇒ 精确表示「本地分支相对远端**多出**的那些 commit」。

**为什么不用 `origin/<branch>` 直接当 base**: 分支可能落后于远端 (远端有别人推的
commit), 此时 `origin/<branch>..local_sha` 会把远端多出的 commit 也算进范围 ——
那些不是本次 push 的内容, 判据会看到不属于本次推送的变更。merge-base 规避了这一点。

**降级语义 (fail-visible, 不假装通过)**:
- 解析不出 remote-tracking ref (例如首次 push 新分支) ⇒ 打印 SKIP 理由并 exit 0,
  由调用方决定是否跳过该检查 —— **不输出 PUSH_RANGE**, 让下游看到「没有范围」而不是
  「范围是空」。
- merge-base 解析失败 (历史被重写 / 远端与本地无共同祖先) ⇒ 同上, 显式 SKIP。

**用法**:
    PUSH_RANGE=$(python3 bin/gac/export-push-range.py) || true
    [ -n "$PUSH_RANGE" ] && export PUSH_RANGE
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )


def _remote_tracking_ref(remote_ref: str) -> str | None:
    """remote_ref (refs/heads/x) → remote-tracking ref (origin/x); 无对应则 None。"""
    if not remote_ref.startswith("refs/heads/"):
        return None
    branch = remote_ref[len("refs/heads/"):]
    for candidate in (f"origin/{branch}", f"refs/remotes/origin/{branch}"):
        if _git("rev-parse", "--verify", "--quiet", candidate).returncode == 0:
            return candidate
    return None


def _default_branch_ref() -> str | None:
    """远端默认分支的 remote-tracking ref (origin/HEAD -> refs/remotes/origin/main)。

    新分支首次 push 时还没有 origin/<branch> (git 在 push **成功之后** 才创建
    remote-tracking ref, 而 pre-push 钩子跑在 push 之前) ⇒ 该场景下唯一可用的
    基线就是默认分支。`origin/HEAD` 是本地 symref, 无需网络。
    """
    for candidate in ("origin/HEAD", "refs/remotes/origin/HEAD"):
        if _git("rev-parse", "--verify", "--quiet", candidate).returncode == 0:
            return candidate
    return None


def resolve_range(refs_file: str) -> tuple[str, str]:
    """返回 (range, reason); range 为空串表示无法判定。"""
    path = Path(refs_file)
    if not path.is_file():
        return "", f"PUSH_REFS_FILE 不可用 ({refs_file})"
    try:
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError as exc:
        return "", f"读取 ref 对失败: {exc}"
    if not lines:
        return "", "ref 对为空 (本次 push 没有要推的 ref)"

    # 多 ref 推送: 取第一个能解析出范围的 (pre-push 对每个 ref 逐个触发,
    # 但 hook-runner 只保存了一份 stdin ⇒ 多 ref 时只能取首个)。
    first_error = ""
    for line in lines:
        fields = line.split()
        if len(fields) < 4:
            first_error = first_error or f"ref 对字段数异常: {line[:80]}"
            continue
        _local_ref, local_sha, remote_ref, _remote_sha = fields[:4]

        # base 候选: 优先该分支自己的 remote-tracking ref; 没有则退到默认分支
        # (新分支首次 push 时 origin/<branch> 还不存在 —— git 在 push 成功后才创建它,
        #  而 pre-push 跑在 push 之前)。
        tracking = _remote_tracking_ref(remote_ref)
        if tracking is None:
            tracking = _default_branch_ref()
            if tracking is None:
                first_error = first_error or (
                    f"无 remote-tracking ref (remote_ref={remote_ref}) 且无 origin/HEAD"
                )
                continue

        merge_base = _git("merge-base", tracking, local_sha)
        if merge_base.returncode != 0 or not merge_base.stdout.strip():
            first_error = first_error or (
                f"merge-base 失败 (tracking={tracking} local={local_sha[:9]})"
            )
            continue
        base = merge_base.stdout.strip()
        if base == local_sha:
            first_error = first_error or "本地分支与远端无新增 commit (range 为空)"
            continue
        return f"{base}..{local_sha}", ""

    return "", first_error or "无法解析 push 范围"


def main() -> int:
    refs_file = os.environ.get("PUSH_REFS_FILE", "").strip()
    if not refs_file:
        print(
            "[export-push-range] SKIP PUSH_REFS_FILE 未设置 (非 pre-push 场景)",
            file=sys.stderr,
        )
        return 0

    git_range, reason = resolve_range(refs_file)
    if not git_range:
        print(f"[export-push-range] SKIP {reason}", file=sys.stderr)
        return 0

    print(git_range)
    return 0


if __name__ == "__main__":
    sys.exit(main())
