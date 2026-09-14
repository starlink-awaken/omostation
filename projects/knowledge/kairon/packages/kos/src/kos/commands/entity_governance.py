#!/usr/bin/env python3
"""kos-entity-governance command wrapper.

DEPRECATED: The standalone kos-entity-governance.py script has been removed.
Use `kos onto` instead.
"""

import sys


def main() -> None:
    print("kos-entity-governance is deprecated. Use `kos onto` instead.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    sys.argv[0] = "kos-entity-governance"
    main()
