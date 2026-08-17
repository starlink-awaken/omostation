from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "bin/ssot/bin-scripts-convergence-audit.py"
    spec = importlib.util.spec_from_file_location("bin_scripts_convergence_audit", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reconcile_deduplicates_and_retire_confirmed_entries(tmp_path: Path) -> None:
    module = load_module()
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/tool.py").write_text("print('ok')\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "name": "tool",
                        "bin": "bin/tool.py",
                        "scripts": "scripts/bin/tool.py",
                        "status": "managed",
                        "action": "close-duplicate-gap-first",
                        "evidence": {"active_files": ["bin/tool.py", "scripts/bin/tool.py"]},
                    },
                    {
                        "name": "tool",
                        "bin": "bin/tool.py",
                        "scripts": "scripts/bin/tool.py",
                        "status": "managed",
                        "action": "close-duplicate-gap-first",
                        "evidence": {"active_files": ["bin/tool.py", "scripts/bin/tool.py"]},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "exec.md"
    report.write_text(
        "| tool | x | x | x | removed | bin/tool.py | scripts/bin/tool.py |\n",
        encoding="utf-8",
    )

    before = module.audit(tmp_path, manifest, report)
    assert before["summary"]["findings"] == 3

    module.reconcile_manifest(tmp_path, manifest, report)
    after = module.audit(tmp_path, manifest, report)
    assert after["summary"]["findings"] == 0
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["action"] == "bin-master, scripts-retired"
