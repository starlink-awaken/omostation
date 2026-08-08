#!/usr/bin/env python3
"""C5 (ADR-0373): auto-maintain `.omo/_knowledge/sweeps/INDEX.md` from sweeps/<date>.json.

Index generation rule:
  - Read every `.json` file in `--out-dir` (default: `.omo/_knowledge/sweeps`).
  - Each row: date | relative path | total_errors | suppression_ratio
  - Sort by date asc; deterministic header.
  - The header & metric legend are kept in lockstep with `bin/sweep/README.md`
    so a CR-SWEEP-INDEX-AUTO gate can detect when the projection diverges
    from the `.json` source-of-truth.

Modes:
  --write   : overwrite INDEX.md with the regenerated contents (default mode)
  --check   : exit 1 if INDEX.md is missing or differs from the regenerated
              text; otherwise print a one-line summary and exit 0
  (default) : --write without arguments; CI uses --check (GaC executor)

Designed to be invoked by:
  - `bin/sweep/scan.py` (after every successful scan)
  - `make gac-local-gate` (CR-SWEEP-INDEX-AUTO, executor here)
  - `python3 bin/sweep/sweep_index.py --check` (CI strict)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = ROOT / ".omo" / "_knowledge" / "sweeps"
INDEX_FILE = "INDEX.md"


HEADER = """# Sweep 扫描历史归档 (A5, ADR-0367 + ADR-0373)

> 本目录只存**指针与索引**, 不复制数据. 报告本体: `<date>.json` (由 `bin/sweep/scan.py` 落盘).
> 生成方式: `python3 bin/sweep/scan.py [--projects <p1> <p2>]` ; 索引由 `bin/sweep/sweep_index.py` 自动维护.

| 日期 | 报告 | total_errors | suppression_ratio |
|------|------|-------------|-------------------|
"""

FOOTER = """
## 指标口径 (与 ADR-0366/P91 对齐)

- `errors`: pyright `severity=error` 诊断总数
- `line_suppressions`: 诊断行已有 `# type: ignore[<rule>]` 的数量
- `file_suppressions`: 文件头 `# pyright: <rule>=false` 覆盖规则的文件数
- `suppression_ratio`: (line + file 覆盖诊断) / errors

## 门禁

- `bin/sweep/pyright.py --suppression-gate`: `file_suppressions >= 3` 或 `suppression_ratio > 0.6` → exit 1 (A3)
- `pyright-sweep-check` diff_check: `required: true` (A2)
- `bin/sweep/scan.py --strict`: 任一项目 `file_suppressions > 0` → exit 1 (A4, ADR-0373)
- `bin/sweep/sweep_index.py --check`: INDEX.md 与 `<date>.json` 漂移 → exit 1 (C5, ADR-0373, CR-SWEEP-INDEX-AUTO)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Sweeps output dir (default: {DEFAULT_OUT_DIR.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="(default) overwrite INDEX.md from current <date>.json files",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when INDEX.md differs from regenerated contents",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the regenerated INDEX.md as JSON {drift: bool, contents: <str>}",
    )
    args = parser.parse_args()
    if not args.write and not args.check:
        args.write = True  # default mode
    if args.write and args.check:
        parser.error("--write and --check are mutually exclusive")
    return args


def collect_reports(out_dir: Path) -> list[dict]:
    """Read every `<date>.json` payload; skip INDEX.md and non-JSON files.

    Returns a list of dicts each with keys:
      date / path / rel_path / total_errors / suppression_ratio
    """
    rows: list[dict] = []
    if not out_dir.is_dir():
        return rows
    for payload_path in sorted(out_dir.glob("*.json")):
        try:
            data = json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        date = str(data.get("date") or payload_path.stem)
        rows.append(
            {
                "date": date,
                "path": payload_path,
                "rel_path": payload_path.name,
                "total_errors": int(data.get("total_errors", 0) or 0),
                "suppression_ratio": float(data.get("suppression_ratio", 0.0) or 0.0),
            }
        )
    return rows


def render_index(rows: list[dict]) -> str:
    """Construct the deterministic INDEX.md markdown."""
    lines = [HEADER.rstrip()]
    for row in rows:
        ratio = row["suppression_ratio"]
        lines.append(
            f"| {row['date']} | [{row['rel_path']}]({row['rel_path']}) | "
            f"{row['total_errors']} | {ratio:.3f} |"
        )
    lines.append(FOOTER.rstrip())
    return "\n".join(lines).rstrip() + "\n"


def run() -> int:
    args = parse_args()
    out_dir: Path = args.out_dir
    rows = collect_reports(out_dir)
    rendered = render_index(rows)

    index_path = out_dir / INDEX_FILE

    if args.json:
        print(
            json.dumps(
                {
                    "out_dir": str(out_dir),
                    "row_count": len(rows),
                    "drift": index_path.is_file() and index_path.read_text(encoding="utf-8") != rendered,
                    "contents": rendered,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.write:
        index_path.write_text(rendered, encoding="utf-8")
        try:
            rel = index_path.relative_to(ROOT)
        except ValueError:
            rel = index_path
        print(f"sweep_index: wrote {rel} ({len(rows)} rows)")
        return 0

    # --check
    if not index_path.is_file():
        print(f"❌ INDEX.md missing at {index_path}", file=sys.stderr)
        return 1
    current = index_path.read_text(encoding="utf-8")
    if current != rendered:
        # surface a 5-line diff hint for humans
        cur_lines = current.splitlines()
        new_lines = rendered.splitlines()
        drift = max(0, len(new_lines) - len(cur_lines))
        first_diff_line = 0
        for i, (a, b) in enumerate(zip(cur_lines, new_lines)):
            if a != b:
                first_diff_line = i + 1
                break
        print(
            f"❌ INDEX.md drift: {drift} lines shorter; first diff near line {first_diff_line}",
            file=sys.stderr,
        )
        return 1
    print(f"✅ sweep_index: INDEX.md matches {len(rows)} reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
