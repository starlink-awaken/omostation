#!/usr/bin/env python3
import sys
from pathlib import Path
WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WS / "bin" / "gac"))
import omo_debt_synthesizer

if __name__ == "__main__":
    sys.exit(omo_debt_synthesizer.main())
