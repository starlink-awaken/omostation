"""前门文档不得「无说明地」链接 gitignored 路径。

契约来源：2026-11-15 —— `.omo/state/system.yaml` 是 gitignored 的生成文件
（`.gitignore` 命中），干净检出里不存在。`LAYER-INDEX.md` 一直写明
「untracked generated file — materialize with …」，而 README 的中英两张入口表
**没有**任何说明 ⇒ 干净检出里就是死链（doc-link-check 实测 14 条「死链」，
其中前门 6 条全是它）。

判据：**跟踪的前门文档**（顶层 `*.md` + `docs/*.md`）里，每条指向 gitignored
路径的相对链接，**同一行**必须出现 `materialize` 或 `untracked`（中英共用该判据，
中文说明里也带 `materialize-system-state.py`）。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CAVEAT_WORDS = ("materialize", "untracked", "未跟踪")


def _front_door_docs() -> list[Path]:
    docs: list[Path] = []
    for base in (ROOT, ROOT / "docs"):
        for md in sorted(base.glob("*.md")):
            tracked = subprocess.run(
                ["git", "ls-files", "--", str(md.relative_to(ROOT))],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if tracked.stdout.strip():
                docs.append(md)
    return docs


def test_front_door_docs_exist() -> None:
    assert len(_front_door_docs()) >= 5


def test_no_caveatless_links_to_gitignored_paths() -> None:
    offenders: list[str] = []
    for md in _front_door_docs():
        for lineno, line in enumerate(md.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for match in LINK_RE.finditer(line):
                target = match.group(1).split("#", 1)[0].strip()
                if not target or target.startswith(("http", "mailto:", "#", "bos://", "repo://", "git://")):
                    continue
                if "<" in target:
                    continue
                resolved = (md.parent / target).resolve()
                try:
                    rel = str(resolved.relative_to(ROOT.resolve()))
                except ValueError:
                    continue
                if not rel.startswith(("bin/", "docs/", ".omo/", "projects/", "runtime/", "protocols/")):
                    continue
                ignored = subprocess.run(
                    ["git", "check-ignore", "-q", rel], cwd=ROOT, capture_output=True, check=False
                )
                if ignored.returncode != 0:
                    continue
                if not any(word in line for word in CAVEAT_WORDS):
                    offenders.append(f"{md.relative_to(ROOT)}:{lineno} -> {rel}")
    assert offenders == [], "前门文档无说明地链接 gitignored 路径: " + "; ".join(offenders)
