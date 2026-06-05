"""L1 Runtime Matrix Scheduler — continuous health monitoring and lifecycle manager."""

import time
import json
import subprocess
import threading
from pathlib import Path
import os

from runtime.matrix import list_services, ServiceEntry, health_check_url

STATE_FILE = Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime")) / "matrix_state.json"

class MatrixScheduler:
    def __init__(self):
        self.state = {}
        self.running = False

    def _check_launchd(self, label: str) -> dict:
        if not label:
            return {"status": "unknown"}
        try:
            r = subprocess.run(["launchctl", "list", label], capture_output=True, text=True)
            if r.returncode != 0:
                return {"status": "failed", "exit_code": r.returncode}
            
            pid, last_exit = None, None
            for line in r.stdout.splitlines():
                if '"PID"' in line:
                    parts = line.split('=')
                    if len(parts) > 1:
                        pid = parts[1].strip().strip(';')
                elif '"LastExitStatus"' in line:
                    parts = line.split('=')
                    if len(parts) > 1:
                        last_exit = parts[1].strip().strip(';')

            if pid and pid != "0":
                return {"status": f"running", "pid": pid}
            elif last_exit == "0":
                return {"status": "idle"}
            else:
                return {"status": "failed", "exit_code": last_exit}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_docker(self, container: str) -> dict:
        if not container:
            return {"status": "unknown"}
        try:
            r = subprocess.run(
                ["docker", "ps", "--filter", f"name={container}", "--format", "{{.Status}}"],
                capture_output=True, text=True
            )
            status = r.stdout.strip()
            if status:
                return {"status": "running", "details": status}
            else:
                return {"status": "stopped"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_port(self, port: int) -> bool:
        if not port:
            return False
        try:
            r = subprocess.run(
                ["lsof", f"-iTCP:{port}", "-sTCP:LISTEN", "-P"],
                capture_output=True
            )
            return r.returncode == 0
        except Exception:
            return False

    def scan_once(self):
        services = list_services()
        current_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        scan_results = {}

        for svc in services:
            result = {
                "type": svc.type,
                "name": svc.name,
                "timestamp": current_time
            }
            
            # Check primary runtime
            if svc.launchd_label:
                result["runtime"] = self._check_launchd(svc.launchd_label)
            elif svc.docker_container:
                result["runtime"] = self._check_docker(svc.docker_container)
            else:
                result["runtime"] = {"status": "unmanaged"}

            # Check port
            if svc.port:
                result["port_listening"] = self._check_port(svc.port)

            # Check HTTP health
            if svc.health_url:
                result["health_check"] = health_check_url(svc.health_url)

            scan_results[svc.name] = result

        self.state = {
            "last_scan": current_time,
            "services": scan_results
        }
        
        # Write state to SSOT file
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

    def start(self, interval: int = 15):
        print(f"🚀 Starting eCOS Matrix Scheduler (scan interval: {interval}s)")
        print(f"📂 State file: {STATE_FILE}")
        self.running = True
        while self.running:
            self.scan_once()
            time.sleep(interval)

    def stop(self):
        self.running = False

def main():
    scheduler = MatrixScheduler()
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n🛑 Stopping Matrix Scheduler")

if __name__ == "__main__":
    main()
