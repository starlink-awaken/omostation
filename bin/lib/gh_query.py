"""gh 查询安全层 — 重试 + 空保护 (TOOL-GRAPHQL-FLAKY-EMPTY-MEANS-UNKNOWN 处置).

规则 (debt decision_needed, 2026-09-25/27 双实证):
  外部查询失败/空 = UNKNOWN, 破坏性调用方必须中止流程, 绝不能当否定结论用.

用法:
    from gh_query import gh_json, GhQueryUnknown

    # 破坏性决策前: 空结果必须显式选择才可用, 默认空 = UNKNOWN → 抛异常
    prs = gh_json("pr", "list", "--state", "open", "--json", "number")

    # 非破坏性调用方 (展示/统计): 显式允许空
    prs = gh_json("pr", "list", "--json", "number", treat_empty_as_unknown=False)

瞬态失败判定: rc != 0 且 stderr 含 EOF / timed out / connection / network /
unexpected end / i/o timeout（gh GraphQL 抖动的典型字样）。重试耗尽后抛
GhQueryUnknown。非瞬态失败（权限/参数等）直接抛 GhQueryFailed，不重试。
"""

from __future__ import annotations

import json
import subprocess
import time

_TRANSIENT_MARKERS = (
    "eof",
    "timed out",
    "timeout",
    "connection",
    "network",
    "unexpected end",
    "http 5",
    "http 50",
    "rate limit",
)


class GhQueryFailed(RuntimeError):
    """非瞬态失败（权限/参数/不存在等）——重试无意义, 直接上抛。"""


class GhQueryUnknown(RuntimeError):
    """查询结果 UNKNOWN——重试耗尽后仍失败, 或成功但输出为空。

    破坏性调用方收到此异常必须中止流程, 不得把 UNKNOWN 当否定结论
    （如"无 OPEN PR"→删 worktree / 建 PR 的历史事故）。
    """


def _is_transient(stderr: str) -> bool:
    low = (stderr or "").lower()
    return any(marker in low for marker in _TRANSIENT_MARKERS)


def gh_json(
    *args: str,
    retries: int = 3,
    retry_delay: float = 2.0,
    treat_empty_as_unknown: bool = True,
    cwd: str | None = None,
) -> list | dict:
    """运行 gh 子命令并解析 JSON 输出.

    - 瞬态失败重试 retries 次（指数退避 retry_delay 起步）;
    - 重试耗尽仍失败 → GhQueryUnknown;
    - 非瞬态失败 → GhQueryFailed;
    - 成功但 stdout 为空/[]: treat_empty_as_unknown=True（默认）→ GhQueryUnknown;
      False → 原样返回解析结果（非破坏性调用方显式选择）。
    """
    delay = retry_delay
    last_error = ""
    for attempt in range(1, max(1, retries) + 1):
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd,
        )
        if proc.returncode == 0:
            stdout = (proc.stdout or "").strip()
            if not stdout:
                # rc=0 + 空输出 = GraphQL 抖动的典型签名 (2026-09-25 实证):
                # 与瞬态失败同样重试, 耗尽后按调用方语义分流。
                if attempt < retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                if treat_empty_as_unknown:
                    raise GhQueryUnknown(
                        f"gh {' '.join(args)} empty output after {retries} attempts "
                        f"— 结果 UNKNOWN, 拒绝当作否定结论"
                    )
                return []
            try:
                return json.loads(stdout)
            except json.JSONDecodeError as exc:
                raise GhQueryFailed(
                    f"gh {' '.join(args)} returned invalid JSON: {exc}"
                ) from exc
        last_error = (proc.stderr or "").strip()[:300]
        if not _is_transient(last_error):
            raise GhQueryFailed(f"gh {' '.join(args)} failed: {last_error}")
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    raise GhQueryUnknown(
        f"gh {' '.join(args)} failed after {retries} attempts "
        f"(transient): {last_error} — 结果 UNKNOWN"
    )
