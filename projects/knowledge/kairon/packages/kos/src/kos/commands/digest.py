#!/usr/bin/env python3
"""kos-digest command wrapper.

DEPRECATED: The standalone kos-digest.py script has been removed.
Use `kos search` or `kos status` instead.
"""

import sys


def main() -> None:
    print("kos-digest is deprecated. Use `kos search` or `kos status` instead.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    sys.argv[0] = "kos-digest"
    main()
