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
        from graphlib import TopologicalSorter
        services = list_services()
        current_time = time.time()
        
        # Load state for crash-loop tracking
        state_file = STATE_FILE.parent / "scheduler_state.json"
        state = {}
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
            except Exception:
                pass
                
        restart_history = state.get("restart_history", {})
        scan_results = {}
        
        # Build DAG
        ts = TopologicalSorter()
        svc_dict = {s.name: s for s in services}
        for svc in services:
            ts.add(svc.name, *svc.depends_on)
        try:
            order = list(ts.static_order())
        except Exception as e:
            print(f"Cycle detected in DAG: {e}")
            order = [s.name for s in services]
            
        ordered_services = [svc_dict[name] for name in order if name in svc_dict]
        
        for svc in ordered_services:
            result = {
                "type": svc.type,
                "name": svc.name,
                "timestamp": current_time
            }
            
            # Check dependencies
            deps_healthy = True
            failed_deps = []
            for dep in svc.depends_on:
                dep_res = scan_results.get(dep, {})
                rt = dep_res.get("runtime", {}).get("status", "")
                if rt in ("failed", "error", "stopped", "FROZEN_CRASH_LOOP", "WAITING_FOR_DEPENDENCY", "BACKOFF", "unreachable"):
                    deps_healthy = False
                    failed_deps.append(dep)
                    break
                hc = dep_res.get("health_check")
                if hc and hc != "healthy":
                    deps_healthy = False
                    failed_deps.append(dep)
                    break

            if not deps_healthy:
                result["runtime"] = {"status": "WAITING_FOR_DEPENDENCY", "reason": f"Waiting for: {failed_deps}"}
                scan_results[svc.name] = result
                continue
            
            svc_history = restart_history.get(svc.name, [])
            # Clean old history (> 5 mins)
            svc_history = [t for t in svc_history if current_time - t < 300]
            
            is_frozen = len(svc_history) >= 5
            if is_frozen:
                result["runtime"] = {"status": "FROZEN_CRASH_LOOP", "reason": "More than 5 restarts in 5 minutes"}
                # Check port and health anyway to reflect frozen state accurately
                if svc.port:
                    result["port_listening"] = self._check_port(svc.port)
                if svc.health_url:
                    result["health_check"] = health_check_url(svc.health_url)
                scan_results[svc.name] = result
                restart_history[svc.name] = svc_history
                continue
                
            # Check primary runtime
            if svc.launchd_label:
                rt_status = self._check_launchd(svc.launchd_label)
                result["runtime"] = rt_status
                if rt_status.get("status") in ("failed", "error"):
                    # Exponential Backoff based on recent restart counts
                    backoff = 5 * (2 ** len(svc_history))
                    last_restart = svc_history[-1] if svc_history else 0
                    if current_time - last_restart >= backoff:
                        print(f"⚠️ Service {svc.name} is {rt_status.get('status')}. Backoff={backoff}s. Self-healing...")
                        subprocess.run(["launchctl", "stop", svc.launchd_label], capture_output=True)
                        subprocess.run(["launchctl", "start", svc.launchd_label], capture_output=True)
                        svc_history.append(current_time)
                        result["runtime"]["self_heal_attempted"] = True
                    else:
                        print(f"⏳ Service {svc.name} is in backoff ({backoff}s). Waiting...")
                        result["runtime"]["status"] = "BACKOFF"

            elif svc.docker_container:
                rt_status = self._check_docker(svc.docker_container)
                result["runtime"] = rt_status
                if rt_status.get("status") in ("stopped", "error"):
                    backoff = 5 * (2 ** len(svc_history))
                    last_restart = svc_history[-1] if svc_history else 0
                    if current_time - last_restart >= backoff:
                        print(f"⚠️ Service {svc.name} is {rt_status.get('status')}. Backoff={backoff}s. Self-healing...")
                        subprocess.run(["docker", "restart", svc.docker_container], capture_output=True)
                        svc_history.append(current_time)
                        result["runtime"]["self_heal_attempted"] = True
                    else:
                        print(f"⏳ Service {svc.name} is in backoff ({backoff}s). Waiting...")
                        result["runtime"]["status"] = "BACKOFF"
            else:
                result["runtime"] = {"status": "unmanaged"}

            restart_history[svc.name] = svc_history

            # Check port
            if svc.port:
                result["port_listening"] = self._check_port(svc.port)

            # Check HTTP health
            if svc.health_url:
                result["health_check"] = health_check_url(svc.health_url)

            scan_results[svc.name] = result
            
        # Save state back
        state["restart_history"] = restart_history
        try:
            with open(state_file, "w") as f:
                json.dump(state, f)
        except Exception:
            pass

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
