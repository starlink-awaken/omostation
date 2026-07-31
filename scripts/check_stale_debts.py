"""Check for debt items with stale x2_freshness."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path.home() / "Workspace/projects/omo/src"))
from omo.omo_debt_registry import load_debt_ledger

ledger = load_debt_ledger(Path.home() / "Workspace/projects/omo/.omo")
now = datetime.now(timezone.utc)
cutoff = now - timedelta(days=7)
for i in ledger.items:
    if i.x2_freshness:
        try:
            ts = datetime.fromisoformat(i.x2_freshness.replace("Z", "+00:00"))
            if ts < cutoff:
                print(f"{i.id}: last checked {(now - ts).days}d ago - {i.title[:40]}")
        except Exception:
            pass
