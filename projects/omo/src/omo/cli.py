#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args and args[0] in {"capability", "registry", "scenario", "pkg"}:
        from omo.omo_capability import main as capability_main

        return capability_main(args)
    if args and args[0] == "metacognition":
        from omo.omo_metacognition import main as metacognition_main

        return metacognition_main(args[1:])
    if args and args[0] == "phase14":
        from omo.omo_phase14 import main as phase14_main

        return phase14_main(args[1:])
    if args and args[0] == "phase15":
        from omo.omo_phase15 import main as phase15_main

        return phase15_main(args[1:])
    if args and args[0] == "phase16":
        from omo.omo_phase16 import main as phase16_main

        return phase16_main(args[1:])

    if args and args[0] == "ledger":
        from omo.omo_ledger import main as ledger_main
        return ledger_main(args[1:])
    if args and args[0] == "bridge":
        from omo.omo_bridge import main as bridge_main
        return bridge_main(args[1:])
    if args and args[0] == "gc":
        from omo.omo_gc import main as gc_main
        return gc_main(args[1:])

    from omo.omo_worker import main as worker_main
    return worker_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
