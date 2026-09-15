#!/usr/bin/env python3
"""kos-setup command wrapper.

DEPRECATED: The standalone kos-setup.py script has been removed.
Use `pip install -e .` to set up KOS.
"""

import sys


def main() -> None:
    print("kos-setup is deprecated. Use `pip install -e .` instead.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    sys.argv[0] = "kos-setup"
    main()
