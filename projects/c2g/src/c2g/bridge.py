import argparse
import sys
from pathlib import Path

from .bridge_utils import get_omo_dir
from .bridge_import import _import_bmad, _import_fast_track, _import_pitch

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="OMO Bridge (Connect external tools like BMAD, OpenSpec, Pitches)"
    )
    parser.add_argument("source_file", type=str, help="The file to import from")
    parser.add_argument(
        "--format",
        type=str,
        choices=["bmad", "openspec", "fast_track", "pitch"],
        default="bmad",
        help="Format of the source file",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Automatically make each task depend on the previous one",
    )
    parser.add_argument(
        "--adapter",
        type=str,
        default="ecos",
        help="Storage adapter to use (ecos, local)",
    )
    args = parser.parse_args(argv)

    source = Path(args.source_file)
    if not source.exists():
        print(f"Error: {source} not found.")
        return 1

    omo_dir = get_omo_dir(Path.cwd()) if args.adapter == "ecos" else Path.cwd()
    if not omo_dir.exists():
        print(f"Error: {omo_dir} not found.")
        return 1

    if args.format in ["bmad", "openspec"]:
        _import_bmad(source, omo_dir, args.sequential, args.adapter)
    elif args.format == "fast_track":
        _import_fast_track(source, omo_dir, args.adapter)
    elif args.format == "pitch":
        _import_pitch(source, omo_dir, args.adapter)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
