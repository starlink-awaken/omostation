import json
import os
import subprocess
import sys
from pathlib import Path
import logging

_log = logging.getLogger(__name__)
CACHE_FILE = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / ".runtime"))) / "cache" / "quota_rates.json"

def main():
    try:
        # 1. Fetch from models
        rates = {}
        try:
            models_res = subprocess.run(["models", "list", "--json"], capture_output=True, text=True, timeout=10)
            if models_res.returncode == 0:
                models_data = json.loads(models_res.stdout)
                for m in models_data:
                    rates[m.get("id", "").lower()] = {
                        "input": m.get("input_cost", 0.0),
                        "output": m.get("output_cost", 0.0)
                    }
        except Exception as e:
            _log.debug("Failed to fetch from models: %s", e)

        # 2. Fetch from codexbar
        quota = []
        try:
            codexbar_res = subprocess.run(["codexbar", "usage", "--format", "json"], capture_output=True, text=True, timeout=20)
            if codexbar_res.returncode == 0:
                quota = json.loads(codexbar_res.stdout)
        except Exception as e:
            _log.debug("Failed to fetch from codexbar: %s", e)
            
        # Write to cache atomically
        data = {
            "rates": rates,
            "quota": quota
        }
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(CACHE_FILE)
        
    except Exception as e:
        _log.debug("Failed to update quota cache: %s", e)

if __name__ == "__main__":
    main()
