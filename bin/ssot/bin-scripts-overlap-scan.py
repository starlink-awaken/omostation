#!/usr/bin/env python3
"""Scan overlap and consolidation candidates between root bin and scripts/bin.

Outputs:
- markdown report of overlap classes
- optional JSON for CI/robots
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


KNOWN_SUFFIX = {
    ".py",
    ".sh",
    ".bash",
    ".pl",
    ".rb",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".cfg",
    ".ini",
    ".conf",
    ".txt",
    ".md",
}


def iter_files(root: Path, max_depth: int | None = None) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if path.name.startswith("."):
            continue
        rel = path.relative_to(root)
        if rel.parts[0] in {".git", "__pycache__", ".ruff_cache", "node_modules"}:
            continue
        if not path.suffix and path.suffixes:
            pass
        if path.suffix.lower() not in KNOWN_SUFFIX:
            # Keep extension-less scripts (rare, mostly shell entry points) if executable.
            try:
                mode = path.stat().st_mode
                if not (mode & 0o111):
                    continue
            except OSError:
                continue
        if path.suffix.lower() in KNOWN_SUFFIX and path.suffix:
            pass
        yield path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_key(path: Path, base: Path) -> str:
    rel = path.relative_to(base).as_posix()
    return rel


@dataclass
class Item:
    path: Path
    base: str
    key: str
    hash: str
    size: int


def collect(base: Path, base_name: str) -> dict[str, Item]:
    out = {}
    for p in iter_files(base):
        key = norm_key(p, base)
        out[key] = Item(
            path=p,
            base=base_name,
            key=key,
            hash=sha256(p),
            size=p.stat().st_size,
        )
    return out


def to_dict(item: Item) -> dict[str, object]:
    return {
        "base": item.base,
        "path": item.key,
        "sha256": item.hash,
        "size": item.size,
    }


def render_markdown(merged: list[str], only_bin: list[str], only_scripts: list[str], diff: list[tuple[str, str, str]]) -> str:
    lines = [
        "# bin/scripts 能力重叠扫描",
        "",
        f"- 重叠脚本: {len(merged)}",
        f"- 仅 bin: {len(only_bin)}",
        f"- 仅 scripts/bin: {len(only_scripts)}",
        f"- 同名不同码: {len(diff)}",
        "",
        "## 完全一致（建议优先收敛到 bin）",
    ]
    if merged:
        for key in sorted(merged):
            lines.append(f"- `{key}`")
    else:
        lines.append("- 当前无完全一致项。")

    lines.extend(["", "## 同名但不同码（需逐个对比）"])
    if diff:
        for key, a, b in sorted(diff):
            lines.append(f"- `{key}`: bin={a} / scripts={b}")
    else:
        lines.append("- 当前无同名差异项。")

    lines.extend(["", "## 收敛建议"])
    if merged:
        lines.append("- 将完全一致项统一迁移到 `bin/` 作为主入口，并保留 scripts 子项目引用为薄 wrapper（如仍有兼容需求）。")
    else:
        lines.append("- 当前不存在可立即收敛项，先补齐 wrappers 与引用关系后再分批归并。")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--bin-root", default="bin")
    p.add_argument("--scripts-bin-root", default="scripts/bin")
    p.add_argument("--json", action="store_true")
    p.add_argument("--json-output", default="", help="Write JSON 到指定文件")
    p.add_argument("--output", default="")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    bin_root = Path(args.bin_root).resolve()
    scripts_root = Path(args.scripts_bin_root).resolve()

    bin_items = collect(bin_root, "bin")
    scripts_items = collect(scripts_root, "scripts")

    keys_bin = set(bin_items)
    keys_scripts = set(scripts_items)
    overlap = sorted(keys_bin & keys_scripts)

    merged = []
    diff = []
    for key in overlap:
        b_item = bin_items[key]
        s_item = scripts_items[key]
        if b_item.hash == s_item.hash:
            merged.append(key)
        else:
            diff.append((key, b_item.hash, s_item.hash))

    only_bin = sorted(keys_bin - keys_scripts)
    only_scripts = sorted(keys_scripts - keys_bin)

    payload = {
        "summary": {
            "total_bin": len(bin_items),
            "total_scripts_bin": len(scripts_items),
            "overlap": len(overlap),
            "merged": len(merged),
            "diff": len(diff),
            "only_bin": len(only_bin),
            "only_scripts": len(only_scripts),
        },
        "merged": [to_dict(bin_items[k]) for k in merged],
        "different": [
            {
                "path": key,
                "bin": to_dict(bin_items[key]),
                "scripts": to_dict(scripts_items[key]),
            }
            for key, _, _ in diff
        ],
        "only_bin": [to_dict(bin_items[k]) for k in only_bin],
        "only_scripts": [to_dict(scripts_items[k]) for k in only_scripts],
    }
    payload_text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload_text + "\n", encoding="utf-8")

    if not args.json and not args.output:
        print(render_markdown(merged, only_bin, only_scripts, diff))
        return

    if args.json:
        print(payload_text)
        return

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(merged, only_bin, only_scripts, diff), encoding="utf-8")
        return

    # fallback: both output and json not requested, print markdown only (default behavior unchanged)
    print(render_markdown(merged, only_bin, only_scripts, diff))


if __name__ == "__main__":
    main()
