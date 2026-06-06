"""Allow `python3 -m runtime` to work as CLI entry point."""
from .cli import main
import sys
sys.exit(main())
