"""WP6 drill replay: restored integrity assertion (non-production)."""
import glob
import hashlib
import sys
from pathlib import Path

root = sys.argv[1] if len(sys.argv) > 1 else "/private/tmp/wp6-drill-live-b3/restore"
cards = sorted(glob.glob(f"{root}/**/*.yaml", recursive=True))
assert len(cards) >= 20, f"cards={len(cards)}"
src = sorted(glob.glob("/Users/xiamingxing/Workspace/docs/scene-cards/*.yaml"))
pairs = list(zip(src, cards))
for a, b in pairs:
    ha = hashlib.sha256(Path(a).read_bytes()).hexdigest()
    hb = hashlib.sha256(Path(b).read_bytes()).hexdigest()
    assert ha == hb, f"byte mismatch: {a}"
print(f"replay ok: {len(pairs)} files byte-identical")
