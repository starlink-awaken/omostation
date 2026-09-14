"""C2c: SharedBrain organ self-healing trigger for forge entropy monitoring.

When forge's entropy monitor detects organ anomalies (timeout, memory, CPU),
triggers SharedBrain D-Genesis self-healing engine via Agora MCP.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

import yaml

_log = logging.getLogger(__name__)

RULES_FILE = Path(__file__).parent / "rules" / "sharedbrain_organ_health.yaml"


class SharedBrainHealingTrigger:
    """Entropy anomaly detected → trigger SharedBrain organ self-healing."""

    RULES: dict[str, str]

    def __init__(self, agora_endpoint: str | None = None, timeout: int = 5) -> None:
        if agora_endpoint is None:
            agora_endpoint = os.environ.get(
                "AGORA_ENDPOINT", f"http://localhost:{os.environ.get('AGORA_INTERNAL_PORT', '7430')}"
            )
        self.endpoint = agora_endpoint.rstrip("/")
        self.timeout = timeout
        self.RULES = self._load_rules()

    def _load_rules(self) -> dict[str, str]:
        if RULES_FILE.exists():
            try:
                return cast("dict", yaml.safe_load(RULES_FILE.read_text()).get("rules", {}))
            except Exception:
                pass
        return {
            "organ_timeout": "sharedbrain/genesis/heal --organ {organ} --reason timeout",
            "organ_memory_leak": "sharedbrain/genesis/heal --organ {organ} --reason memory",
            "organ_cpu_spike": "sharedbrain/genesis/cool-down --organ {organ}",
        }

    def trigger(self, anomaly_type: str, organ: str, **context: Any) -> dict:
        """Trigger self-healing for a detected anomaly.

        Returns the response from SharedBrain D-Genesis.
        """
        command = self.RULES.get(anomaly_type, "").format(organ=organ, **context)
        if not command:
            return {"ok": False, "error": f"Unknown anomaly type: {anomaly_type}"}

        payload = json.dumps(
            {
                "command": command,
                "anomaly_type": anomaly_type,
                "organ": organ,
                "context": context,
            }
        ).encode()
        req = Request(f"{self.endpoint}/call", data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            resp = urlopen(req, timeout=self.timeout)
            data = json.loads(resp.read().decode())
            _log.info("Healing triggered: %s → %s → %s", anomaly_type, organ, command)
            return {"ok": True, "data": data}
        except Exception as e:
            _log.error("Healing trigger failed: %s", e)
            return {"ok": False, "error": str(e)}
