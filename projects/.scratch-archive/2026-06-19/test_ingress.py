from pathlib import Path
from omo.omo_ingress import upsert_debt_item
import json

tmp_path = Path("/tmp/omo_test")
tmp_path.mkdir(exist_ok=True)
payload = {
    "id": "DEBT-TEST",
    "title": "Test"
}
res = upsert_debt_item(
    tmp_path,
    debt_data=payload,
    ingress_plane="test",
)
print(json.dumps(res, indent=2))
