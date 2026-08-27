#!/usr/bin/env python3
"""kos-ai-audit command wrapper.

DEPRECATED: The standalone kos-ai-audit.py script has been removed.
"""

import sys


def main() -> None:
    print("kos-ai-audit is deprecated and no longer available.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    sys.argv[0] = "kos-ai-audit"
    main()
