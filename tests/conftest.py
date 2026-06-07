"""pytest conftest — add scripts to sys.path for all tests"""

import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


@pytest.fixture(scope="session", autouse=True)
def _ensure_ecos_test_data() -> None:
    """Create missing SSB key and LADS data files so e2e tests can run."""
    ecos = Path(__file__).resolve().parent.parent

    # SSB signing key
    key_file = ecos / "LADS" / "ssb" / ".ssb_key"
    if not key_file.exists():
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(os.urandom(32))
        key_file.chmod(0o600)

    # SSB JSONL line-delimited events file
    jsonl = ecos / "LADS" / "ssb" / "ecos.jsonl"
    if not jsonl.exists():
        jsonl.write_text("", encoding="utf-8")

    # Cross-refs file (must have >=3 entries with link_id/source/target/score>=0.4)
    refs = ecos / "LADS" / "cross_refs.jsonl"
    if not refs.exists() or refs.read_text(encoding="utf-8").strip() == "":
        refs.write_text(
            "\n".join(
                [
                    json.dumps({"link_id": "r1", "source": "a", "target": "b", "score": 0.9}),
                    json.dumps({"link_id": "r2", "source": "b", "target": "c", "score": 0.8}),
                    json.dumps({"link_id": "r3", "source": "c", "target": "a", "score": 0.7}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    # Handoff latest (must contain 'agent' or 'signature' per test)
    handoff = ecos / "LADS" / "HANDOFF" / "LATEST.md"
    if not handoff.exists():
        handoff.parent.mkdir(parents=True, exist_ok=True)
        handoff.write_text(
            "# Handoff\n\n## agent_signature\n- agent: test-agent\n- signature: ok\n",
            encoding="utf-8",
        )
