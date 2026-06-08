"""L1 Runtime Matrix Scheduler — continuous health monitoring and lifecycle manager."""

import time
import json
import subprocess
import threading
from pathlib import Path
import os
from datetime import datetime, timezone

from runtime.matrix import list_services, ServiceEntry, health_check_url
from runtime.state_schema import validate_runtime_health_snapshot

import yaml
import shutil
import hashlib

STATE_FILE = Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime")) / "matrix_state.json"
OMO_STATE_FILE = Path("/Users/xiamingxing/Workspace/.omo/state/system_health.yaml")

class MatrixScheduler:
    def __init__(self):
        self.state = {}
        self.running = False
        self.last_state_hash = ""
        self._prev_health = {}
        self._interval = 15
        # X2-NO_FRESHNESS: freshness tracking
        self._freshness: dict[str, float] = {}
        self._stale_count: dict[str, int] = {}
        self._stale_threshold = 3
        # P1-AUTO_HEAL: consecutive failure tracking
        self._consecutive_failures: dict[str, int] = {}
        self._autoheal_enabled = True

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

        # Heartbeat & run statistics
        run_count = state.get("run_count", 0) + 1
        state["run_count"] = run_count
        state["last_run"] = datetime.now(timezone.utc).astimezone().isoformat()
        state.setdefault("state_transitions", 0)
        
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

            # X2-NO_FRESHNESS: update freshness on healthy
            rt = result.get("runtime", {}).get("status")
            hc = result.get("health_check")
            if rt in ("running", "idle") or hc == "healthy":
                self._freshness[svc.name] = time.monotonic()
                self._consecutive_failures.pop(svc.name, None)
            else:
                self._consecutive_failures[svc.name] = self._consecutive_failures.get(svc.name, 0) + 1
                # P1-AUTO_HEAL: trigger autoheal when consecutive failures exceed threshold
                if self._autoheal_enabled and self._consecutive_failures[svc.name] >= self._stale_threshold:
                    print(f"⚠️ [P1-AUTO_HEAL] {svc.name}: {self._consecutive_failures[svc.name]} consecutive failures, triggering autoheal...")
                    self._autoheal_service(svc.name)

            # Freshness seconds for state reporting
            running_since = state.setdefault("running_since", {})
            if rt == "running":
                if svc.name not in running_since:
                    running_since[svc.name] = current_time
                result["runtime"]["freshness_seconds"] = int(current_time - running_since[svc.name])
            else:
                running_since.pop(svc.name, None)

            scan_results[svc.name] = result
            
        # Calculate state hash (excluding last_scan to prevent constant updates)
        state_hash = hashlib.md5(json.dumps(scan_results, sort_keys=True).encode()).hexdigest()
        
        # Detect state transition and increment counter
        state_transitioned = state_hash != self.last_state_hash
        if state_transitioned:
            state["state_transitions"] += 1
            self.last_state_hash = state_hash
        
        # Save state back
        state["restart_history"] = restart_history
        state["running_since"] = state.get("running_since", {})
        try:
            with open(state_file, "w") as f:
                json.dump(state, f)
        except Exception:
            pass

        self.state = {
            "last_scan": current_time,
            "services": scan_results
        }
        
        # Write local state
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state, indent=2))
        
        # HealthPulse: Only write to OMO SSOT if state transitioned
        if state_transitioned:
            OMO_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            try:
                validate_runtime_health_snapshot(self.state)
                with open(OMO_STATE_FILE, "w") as f:
                    yaml.safe_dump(self.state, f, default_flow_style=False)
                print(f"💓 HealthPulse: State transition detected. Updated {OMO_STATE_FILE}")
                self.last_state_hash = state_hash
            except Exception as e:
                print(f"Failed to update OMO state: {e}")

        # Alert on health transitions: healthy → unreachable
        notify_script = Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime")) / "scripts" / "event_driven_notify.py"
        for svc_name, result in scan_results.items():
            current_hc = result.get("health_check")
            prev_hc = self._prev_health.get(svc_name)
            if prev_hc == "healthy" and current_hc == "unreachable":
                print(f"🚨 Health alert: {svc_name} went healthy→unreachable. Notifying...")
                try:
                    subprocess.run(
                        ["python3", str(notify_script), "--service", svc_name, "--status", "unreachable"],
                        capture_output=True, text=True, timeout=10
                    )
                except Exception as e:
                    print(f"Failed to run notify script for {svc_name}: {e}")
            self._prev_health[svc_name] = current_hc

    def run_entropy_gc(self):
        print("🧹 [X2 Anti-Entropy] Running Pan-Entropy GC...")
        workspace = Path("/Users/xiamingxing/Workspace")
        # 1. GC debt ledger
        debt_dir = workspace / ".omo/debt/items"
        archive_dir = workspace / ".omo/debt/archive"
        if debt_dir.exists():
            archive_dir.mkdir(parents=True, exist_ok=True)
            now = time.time()
            compacted = 0
            for item in debt_dir.glob("*.yaml"):
                try:
                    with open(item, "r") as f:
                        data = yaml.safe_load(f)
                    if data and data.get("resolved") is True:
                        if now - item.stat().st_mtime > 604800: # 7 days
                            shutil.move(str(item), str(archive_dir / item.name))
                            compacted += 1
                except Exception:
                    pass
            if compacted > 0:
                print(f"📦 [X2 Anti-Entropy] Compacted {compacted} resolved debt items to archive.")


    def _check_stale_services(self):
        """X2-NO_FRESHNESS: Check for services that have gone stale (not seen healthy)."""
        if not self._freshness:
            return
        now = time.monotonic()
        threshold_seconds = self._stale_threshold * self._interval
        stale_found = False
        for svc_name, last_seen in list(self._freshness.items()):
            age = now - last_seen
            if age > threshold_seconds:
                self._stale_count[svc_name] = self._stale_count.get(svc_name, 0) + 1
                if self._stale_count[svc_name] >= self._stale_threshold:
                    print(f"🧊 [X2-NO_FRESHNESS] Service '{svc_name}' is STALE (age={age:.1f}s, consecutive_scans={self._stale_count[svc_name]})")
                    stale_found = True
                    # Trigger autoheal if enabled and not already triggered by consecutive failures
                    if self._autoheal_enabled and svc_name not in self._consecutive_failures:
                        self._autoheal_service(svc_name)
            else:
                self._stale_count.pop(svc_name, None)
        if not stale_found:
            self._stale_count.clear()

    def _autoheal_service(self, svc_name: str):
        """P1-AUTO_HEAL: Call autoheal.sh to restart a failing service."""
        autoheal_script = Path(__file__).parent.parent.parent / "scripts" / "autoheal.sh"
        if not autoheal_script.exists():
            print(f"⚠️ [P1-AUTO_HEAL] autoheal.sh not found at {autoheal_script}")
            return
        try:
            r = subprocess.run(
                ["bash", str(autoheal_script), svc_name],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                print(f"✅ [P1-AUTO_HEAL] {svc_name}: autoheal succeeded")
            else:
                print(f"❌ [P1-AUTO_HEAL] {svc_name}: autoheal FAILED (exit={r.returncode}): {r.stdout.strip()[-200:]}")
        except subprocess.TimeoutExpired:
            print(f"⚠️ [P1-AUTO_HEAL] {svc_name}: autoheal timed out after 30s")
        except Exception as e:
            print(f"⚠️ [P1-AUTO_HEAL] {svc_name}: autoheal error: {e}")

    def _run_cycle(self):
        """Run one full scheduler cycle: scan, check staleness, and update."""
        self.scan_once()
        self._check_stale_services()

    def start(self, interval: int = 15):
        print(f"🚀 Starting eCOS Matrix Scheduler (scan interval: {interval}s)")
        print(f"📂 State file: {STATE_FILE}")
        self.running = True
        self._interval = interval
        
        # Run GC on startup
        self.run_entropy_gc()
        
        tick = 0
        while self.running:
            self._run_cycle()
            time.sleep(interval)
            tick += 1
            # Run GC every ~1 hour (240 ticks * 15s)
            if tick % 240 == 0:
                self.run_entropy_gc()

    def stop(self):
        self.running = False

def main():
    from runtime.kei_sandbox import enable_sandbox
    import sys
    enable_sandbox()
    scheduler = MatrixScheduler()
    # P1-AUTO_HEAL: --autoheal (default on) / --no-autoheal
    if "--no-autoheal" in sys.argv:
        scheduler._autoheal_enabled = False
        print("🩹 [P1-AUTO_HEAL] Auto-heal is DISABLED (--no-autoheal)")
    elif "--once" not in sys.argv:
        print("🩹 [P1-AUTO_HEAL] Auto-heal is ENABLED (default)")
    if "--once" in sys.argv:
        scheduler.scan_once()
    else:
        try:
            scheduler.start()
        except KeyboardInterrupt:
            print("\n🛑 Stopping Matrix Scheduler")

if __name__ == "__main__":
    main()
