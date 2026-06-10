"""cockpit CLI — 统一入口"""

from .cli import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
