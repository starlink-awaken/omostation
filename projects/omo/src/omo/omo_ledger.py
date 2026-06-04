import argparse
from datetime import datetime, timezone
from pathlib import Path
import yaml
import shutil


def get_omo_dir(base_dir: Path) -> Path:
    current = base_dir.resolve()
    while current != current.parent:
        if (current / ".omo").is_dir():
            return current / ".omo"
        current = current.parent
    return base_dir / ".omo"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="OMO Governance Ledger snapshot")
    parser.add_argument(
        "--message",
        type=str,
        help="Ledger commit message/reason",
        default="Routine Governance Snapshot",
    )
    args = parser.parse_args(argv)

    omo_dir = get_omo_dir(Path.cwd())
    if not omo_dir.exists():
        print(f"Error: {omo_dir} not found.")
        return 1

    print(f"📖 记录 OMO 治理台账 (Ledger) - 目标: {omo_dir}")
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")

    ledger_dir = omo_dir / "_delivery" / "governance-evidence" / "ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)

    # Gather state
    system_yaml = omo_dir / "state" / "system.yaml"
    goals_yaml = omo_dir / "goals" / "current.yaml"
    debt_yaml = omo_dir / "debt" / "dashboard" / "current.yaml"

    snapshot = {
        "timestamp": now.isoformat(),
        "message": args.message,
        "metrics": {
            "active_tasks": len(list((omo_dir / "tasks" / "active").glob("*.yaml")))
            if (omo_dir / "tasks" / "active").exists()
            else 0,
            "planned_tasks": len(list((omo_dir / "tasks" / "planned").glob("*.yaml")))
            if (omo_dir / "tasks" / "planned").exists()
            else 0,
        },
        "system_state": yaml.safe_load(system_yaml.read_text())
        if system_yaml.exists()
        else None,
        "goals": yaml.safe_load(goals_yaml.read_text())
        if goals_yaml.exists()
        else None,
        "debt": yaml.safe_load(debt_yaml.read_text()) if debt_yaml.exists() else None,
    }

    ledger_file = ledger_dir / f"ledger-{timestamp}.yaml"
    ledger_file.write_text(yaml.dump(snapshot, allow_unicode=True, sort_keys=False))

    print(f"✅ 台账记录已生成: {ledger_file}")

    # Update latest pointer
    latest_file = ledger_dir / "ledger-latest.yaml"
    shutil.copy(ledger_file, latest_file)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
