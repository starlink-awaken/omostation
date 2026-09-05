from __future__ import annotations

import argparse
import json
from pathlib import Path

from .design_asset_adapter import choose_design_assets, find_awesome_design_repo


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forge design asset discovery and prompt assembly.")
    subparsers = parser.add_subparsers(dest="command")

    design_parser = subparsers.add_parser("design", help="Design asset discovery and prompt generation")
    design_parser.add_argument("repo_path", nargs="?", default=str(find_awesome_design_repo()))
    design_parser.add_argument("--query", default="")
    design_parser.add_argument("--platform")
    design_parser.add_argument("--style", dest="style_family")
    design_parser.add_argument("--limit", type=int, default=3)
    design_parser.add_argument("--json", action="store_true")

    asset_parser = subparsers.add_parser("design-assets", help="Alias for design asset discovery")
    asset_parser.add_argument("repo_path", nargs="?", default=str(find_awesome_design_repo()))
    asset_parser.add_argument("--query", default="")
    asset_parser.add_argument("--platform")
    asset_parser.add_argument("--style", dest="style_family")
    asset_parser.add_argument("--limit", type=int, default=3)
    asset_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command in {"design", "design-assets"}:
        assets = choose_design_assets(
            Path(args.repo_path).expanduser(),
            query=args.query,
            platform=args.platform,
            style_family=args.style_family,
            limit=args.limit,
        )
        payload = {
            "repo_path": str(Path(args.repo_path).expanduser()),
            "query": args.query,
            "platform": args.platform,
            "style_family": args.style_family,
            "count": len(assets),
            "assets": assets,
        }
        output = json.dumps(payload, ensure_ascii=False, indent=2)
        print(output)
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
