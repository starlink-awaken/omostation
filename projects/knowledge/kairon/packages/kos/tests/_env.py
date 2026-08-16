"""KOS test environment setup."""

import os
from pathlib import Path

KOS_TOOLS = Path(__file__).resolve().parent.parent
os.environ.setdefault("KOS_HOME", str(KOS_TOOLS))
