"""OPC-P2-GATE-C YAML self-check.

Validates the .omo/tasks/done/OPC-P2-GATE-C.yaml file for:
  - top-level status / gate / gate_status consistency
  - no duplicate sub_gate ids
  - every sub_gate (C1-C4) is 'passed'
  - no 'not_started' leaks
  - no dirty XML markers

Run from /Users/xiamingxing/Workspace:
    python3 .omo/tasks/done/OPC-P2-GATE-C.check.py
"""
import sys
from pathlib import Path

import yaml

YAML_PATH = Path(__file__).parent / "OPC-P2-GATE-C.yaml"


def main() -> int:
    raw = YAML_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    ids = [sg["id"] for sg in data.get("sub_gates", [])]
    dups = [i for i in set(ids) if ids.count(i) > 1]

    checks = {
        "top status=completed": data.get("status") == "completed",
        "gate==Gate C": data.get("gate") == "Gate C",
        "gate_status==passed": data.get("gate_status") == "passed",
        "no duplicate sub_gate ids": len(dups) == 0,
        "C1 passed": any(
            sg.get("status") == "passed" and sg.get("id") == "OPC-P2-C1"
            for sg in data.get("sub_gates", [])
        ),
        "C2 passed": any(
            sg.get("status") == "passed" and sg.get("id") == "OPC-P2-C2"
            for sg in data.get("sub_gates", [])
        ),
        "C3 passed": any(
            sg.get("status") == "passed" and sg.get("id") == "OPC-P2-C3"
            for sg in data.get("sub_gates", [])
        ),
        "C4 passed": any(
            sg.get("status") == "passed" and sg.get("id") == "OPC-P2-C4"
            for sg in data.get("sub_gates", [])
        ),
        "no 'not_started' leaks": not any(
            sg.get("status") == "not_started" for sg in data.get("sub_gates", [])
        ),
        "no dirty XML markers": "</content>" not in raw and "</invoke>" not in raw,
    }
    print(f"=== OPC-P2-GATE-C.yaml self-check ({YAML_PATH}) ===")
    for k, v in checks.items():
        marker = "PASS" if v else "FAIL"
        print(f"  [{marker}] {k}")
    print(f"\n  result: {'PASS' if all(checks.values()) else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
