#!/usr/bin/env python3
"""check-readme-hardcoded.py — README/CLAUDE.md 硬编码数据检测 + 仓库健康周报 (T10-127)

doc-ssot-contract 精神: README/CLAUDE.md 是导航层, 硬编码运行时事实 (端口/计数/日期)
必然漂移。本工具检测两类违规并生成健康周报:
  A. 具体端口断言 (如 ": 8080"、port 8080)
  B. 计数/排名类断言 (如 "N 个 BET"、"N 个 agent")
  C. last_updated 日期陈旧 (>14 天)

--update-health 时同步聚合生成 docs/repository-health.md 周报。

用法:
  python3 bin/gac/check-readme-hardcoded.py                # 检测报告
  python3 bin/gac/check-readme-hardcoded.py --update-health  # + 周报刷新
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parents[2]
HEALTH_MD = WS_ROOT / "docs/repository-health.md"

PORT_RE = re.compile(r"(?:port\s*:?\s*|:)(\d{4,5})\b", re.I)
COUNT_RE = re.compile(r"(\d+)\s*(个|条|项|个 ?BET|agents?|projects?|PRs?|条规则)")


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=WS_ROOT)
    return r.stdout.strip() if r.returncode == 0 else ""


def check_file(path: Path) -> list[dict]:
    hits: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return hits
    m = re.search(r"last_updated:\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        age = (dt.date.today() - dt.date.fromisoformat(m.group(1))).days
        if age > 14:
            hits.append({"kind": "stale-date", "detail": f"last_updated {m.group(1)} ({age}d 前)"})
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("#") is False and PORT_RE.search(line):
            for pm in PORT_RE.finditer(line):
                port = pm.group(1)
                if 1024 <= int(port) <= 65535 and not line.strip().startswith(("http", "科普")):
                    hits.append({"kind": "hardcoded-port", "detail": f"L{i}: {line.strip()[:60]} (:{port})"})
                    break
        cm = COUNT_RE.search(line)
        if cm:
            hits.append({"kind": "hardcoded-count", "detail": f"L{i}: {line.strip()[:60]}"})
    return hits


def update_health_report(issues: list[dict]) -> None:
    today = dt.date.today().isoformat()
    bets_total = bets_done = ""
    try:
        out = subprocess.run(
            [sys.executable, str(WS_ROOT / "bin/plan/bet-ledger.py"), "list", "--json"],
            capture_output=True, text=True, timeout=60,
        )
        if out.returncode == 0 and out.stdout.strip():
            import json
            data = json.loads(out.stdout)
            bets = data if isinstance(data, list) else data.get("bets", [])
            bets_total = str(len(bets))
            bets_done = str(sum(1 for b in bets if isinstance(b, dict) and b.get("status") == "done"))
    except Exception:
        pass
    lines = [
        "# Repository Health 周报 (自动生成)",
        "",
        f"> 生成: {today} | 工具: check-readme-hardcoded.py --update-health (T10-127)",
        "> 本文件为派生物, 不要手编。",
        "",
        "## 文档硬编码检测",
        "",
        f"- 违规: {len(issues)}",
    ]
    for it in issues[:10]:
        lines.append(f"  - [{it['kind']}] {it['detail']}")
    lines += [
        "",
        "## BET 台账规模",
        "",
        f"- 总数: {bets_total or 'n/a'} | done: {bets_done or 'n/a'} (归档另计, 见 3y-bet-ledger-archive.yaml)",
        "",
        "## 分支/worktree 治理",
        "",
    ]
    branches = _git("branch", "--format=%(refname:short)").splitlines()
    work_n = sum(1 for b in branches if b.strip().lstrip("* ").startswith("work/"))
    agent_n = sum(1 for b in branches if b.strip().lstrip("* ").startswith("agent/"))
    wts = sorted(WS_ROOT.parent.glob("ws-*"))
    lines += [
        f"- work/ 分支: {work_n} | agent/ 分支: {agent_n} (TTL 见 branch-prefix-policy.yaml)",
        f"- 活跃 worktree: {len(wts)}",
        "",
    ]
    HEALTH_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[health] 周报已更新 → {HEALTH_MD.relative_to(WS_ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--update-health", action="store_true", help="同步刷新 repository-health.md")
    args = ap.parse_args()

    targets = [WS_ROOT / "README.md", WS_ROOT / "CLAUDE.md"]
    issues: list[dict] = []
    for f in targets:
        for it in check_file(f):
            it["file"] = f.name
            issues.append(it)

    print(f"=== README 硬编码检测: {len(issues)} 项 ===")
    for it in issues:
        print(f"  [{it['kind']}] {it.get('file','')}: {it['detail']}")
    if args.update_health:
        update_health_report(issues)
    return 0


if __name__ == "__main__":
    sys.exit(main())
