#!/usr/bin/env python3
"""Thin CLI for the deterministic MOF Control Compiler (WP-W1-02-003).

Usage
-----
    python3 src/ecos/ssot/tools/mof-compile.py compile [--m2-dir DIR] [--out-dir DIR]
    python3 src/ecos/ssot/tools/mof-compile.py check   [--m2-dir DIR] [--out-dir DIR]
    python3 src/ecos/ssot/tools/mof-compile.py dump    [--m2-dir DIR] [--artifact CLASS]

``compile`` writes every artifact class plus a SHA-256 manifest to ``out-dir``
(default: ``./mof-control-out``). ``check`` verifies existing output against a
fresh compilation and exits nonzero (1) on any tampering or drift; exit 2 on
usage/compiler errors. ``dump`` prints one artifact class to stdout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ecos.ssot.mof.compiler import ARTIFACT_CLASSES, MofCompiler

DEFAULT_OUT = Path("mof-control-out")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd, help_text in (
        ("compile", "generate artifacts + manifest"),
        ("check", "verify artifacts against fresh compile"),
    ):
        p = sub.add_parser(cmd, help=help_text)
        p.add_argument(
            "--m2-dir",
            type=Path,
            default=None,
            help="M2 model-truth directory (default: checked-in m2)",
        )
        p.add_argument(
            "--out-dir",
            type=Path,
            default=DEFAULT_OUT,
            help=f"output directory (default: {DEFAULT_OUT})",
        )
    d = sub.add_parser("dump", help="print one artifact class to stdout")
    d.add_argument(
        "--m2-dir",
        type=Path,
        default=None,
        help="M2 model-truth directory (default: checked-in m2)",
    )
    d.add_argument(
        "--artifact",
        choices=list(ARTIFACT_CLASSES),
        required=True,
        help="artifact class to print",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        compiler = MofCompiler(m2_dir=args.m2_dir)
        if args.command == "compile":
            written = compiler.write(out_dir=args.out_dir)
            for cls in ARTIFACT_CLASSES:
                print(f"wrote {cls}: {written[cls]}")
            print(f"wrote manifest: {written['manifest']}")
            return 0
        if args.command == "check":
            problems = compiler.check(out_dir=args.out_dir)
            if problems:
                print("MOF control compiler check FAILED:", file=sys.stderr)
                for problem in problems:
                    print(f"  - {problem}", file=sys.stderr)
                return 1
            print("MOF control compiler check OK: artifacts match fresh compile")
            return 0
        if args.command == "dump":
            content = compiler.compile([args.artifact])[args.artifact]
            sys.stdout.write(content)
            return 0
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
