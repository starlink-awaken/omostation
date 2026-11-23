#!/usr/bin/env python3
"""债务条目陈旧度信号: `affected_roots` 在 `last_reviewed_at` 之后被改过 ⇒ 可能陈旧。

## 为什么需要

2026-11 那一轮里, 债务文献**四次**落后于代码 (两条 A9 / zhixing-provenance /
launchd-plist), 每次都要人逐条读才发现。本信号把它机械化: 一条债务若在它**上次复审
之后**它所指向的文件被 commit 碰过, 那它描述的事情可能已经不成立了。

## 判据是信号, 不是判决

`affected_roots` 变了 **≠** 条目错了 (可能是无关改动)。所以本检查**默认
advisory (exit 0)**, 只点名 + 计数, 不阻断 —— 与 `check-runner-cost` 的
「未登记即阻塞」不同, 这里没有「必须」可言: 条目可以指向一个本就没再动的面。

## 读数诚实性

只统计**同时有** `affected_roots` 与 `last_reviewed_at` 的条目, 并在汇总行打出
分母 (`候选 N / identified M`) —— 没有 `affected_roots` 的条目不进判定也不假装被跳过。

用法::

    python3 bin/gac/check-debt-staleness.py            # 人类可读
    python3 bin/gac/check-debt-staleness.py --json
    python3 bin/gac/check-debt-staleness.py --self-test
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ITEMS_DIR = ROOT / ".omo" / "debt" / "items"
TERMINAL = frozenset({"resolved", "closed", "wontfix"})


def _parse_ts(value: object) -> datetime.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _commits_since(root: Path, path: str, ts: datetime.datetime) -> int:
    """`path` 在 `ts` 之后的 commit 数。文件/目录都支持 (`git log -- <path>`)。

    返回**计数**而不是布尔: 二元命中在活跃期会全绿/全红 (实测 21/21 全命中),
    没有区分度; 有梯度才能让人先看最可能陈旧的。
    """
    try:
        out = subprocess.run(
            ["git", "log", f"--since=@{int(ts.timestamp())}", "--format=%h", "--", path],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    return len(out.stdout.split())


def collect(items_dir: Path = ITEMS_DIR, *, root: Path = ROOT) -> dict:
    import yaml

    identified = 0
    candidates = 0
    stale: list[dict] = []
    for path in sorted(items_dir.glob("*.yaml")):
        try:
            item = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(item, dict) or item.get("lifecycle_state") in TERMINAL:
            continue
        if item.get("lifecycle_state") != "identified":
            continue
        identified += 1
        refs = [r for r in (item.get("affected_roots") or []) if isinstance(r, str) and r.strip()]
        reviewed = _parse_ts(item.get("last_reviewed_at"))
        if not refs or reviewed is None:
            continue
        candidates += 1
        per_root = {r: _commits_since(root, r, reviewed) for r in refs}
        touched = {r: n for r, n in per_root.items() if n}
        if touched:
            stale.append(
                {
                    "id": item.get("id"),
                    "last_reviewed_at": str(item.get("last_reviewed_at"))[:10],
                    "changed_roots": sorted(touched),
                    "changed_commits": sum(touched.values()),
                }
            )
    return {
        "identified": identified,
        "candidates": candidates,
        "stale_count": len(stale),
        # 按改动提交数降序 —— 最可能陈旧的排前面 (二元命中没有区分度)
        "stale": sorted(stale, key=lambda row: (-row["changed_commits"], str(row["id"]))),
    }


def _render(report: dict) -> str:
    lines = [
        "=== 债务条目陈旧度信号 ===",
        f"identified={report['identified']} 候选(有 roots+复审日)={report['candidates']} "
        f"疑似陈旧={report['stale_count']}",
    ]
    for row in report["stale"]:
        lines.append(
            f"  ⚠️  {row['id']}  (复审 {row['last_reviewed_at']}, "
            f"{row['changed_commits']} commits 落在其 roots 上: {row['changed_roots'][:2]})"
        )
    if not report["stale"]:
        lines.append("  ✅ 无: 所有候选条目的 affected_roots 自复审以来未被改动")
    lines.append("判据是信号不是判决 (roots 变了 != 条目错了); 本检查 advisory, exit 0。")
    return "\n".join(lines)


def self_test() -> int:
    """检测器自证: 合成样本必须能被命中/放行, 否则「0 条陈旧」可能只是仪器没接上。"""
    import tempfile

    import yaml

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", "-b", "main", "."], cwd=root, check=True)
        (root / "touched.txt").write_text("v1\n", encoding="utf-8")
        (root / "untouched.txt").write_text("v1\n", encoding="utf-8")
        # 基线 commit **必须早于**条目的复审日, 否则 `--since` 会连基线一起算进去,
        # 两条样本都会命中 ⇒ 自证变成恒真 (判据与被检对象共享失效模式)。
        base_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10)
        env = {
            **__import__("os").environ,
            "GIT_AUTHOR_DATE": base_date.isoformat(),
            "GIT_COMMITTER_DATE": base_date.isoformat(),
        }
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "base"],
            cwd=root,
            check=True,
            env=env,
        )
        # 复审日 = 基线之后、touch 之前 ⇒ 只有 touched.txt 该被点名
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)).isoformat()
        items = root / "items"
        items.mkdir()
        (items / "stale.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "STALE-X",
                    "lifecycle_state": "identified",
                    "affected_roots": ["touched.txt"],
                    "last_reviewed_at": old,
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        (items / "fresh.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "FRESH-X",
                    "lifecycle_state": "identified",
                    "affected_roots": ["untouched.txt"],
                    "last_reviewed_at": old,
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        # 之后只改 touched.txt ⇒ 只有 STALE-X 该被点名
        (root / "touched.txt").write_text("v2\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "touch"],
            cwd=root,
            check=True,
        )
        report = collect(items, root=root)
        ids = {row["id"] for row in report["stale"]}
        if ids != {"STALE-X"}:
            failures.append(f"合成样本读数应为 {{STALE-X}}, 实为 {ids}")
    if failures:
        print(f"SELF-TEST FAILED: {failures}")
        return 1
    print("SELF-TEST PASSED")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="债务条目陈旧度信号 (advisory)")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    parser.add_argument("--self-test", action="store_true", help="检测器自证")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    report = collect()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(_render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
