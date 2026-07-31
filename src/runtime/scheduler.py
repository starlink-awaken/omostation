"""L1 Runtime Matrix Scheduler — continuous health monitoring and lifecycle manager."""

import time
import json
import subprocess
from pathlib import Path
import os
import sys
from datetime import datetime, timezone

from runtime.adapters.omo import (
    archive_resolved_debt_items,
    summarize_system_health_snapshot,
)
from runtime.matrix import list_services, health_check_url
from runtime.state_schema import validate_runtime_health_snapshot

import yaml
import hashlib

STATE_FILE = (
    Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime")) / "matrix_state.json"
)
# Compute OMO state path from RUNTIME_HOME or workspace root
_workspace_root = (
    Path(__file__).resolve().parents[4]
)  # runtime/src/runtime/scheduler.py → workspace root
OMO_STATE_FILE = Path(
    os.environ.get(
        "OMO_STATE_FILE", str(_workspace_root / ".omo" / "state" / "system_health.yaml")
    )
)


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
        # Route B: force-write OMO state even without state transition
        self._force_write = False

    def _check_launchd(self, label: str) -> dict:
        if not label:
            return {"status": "unknown"}
        try:
            r = subprocess.run(
                ["launchctl", "list", label], capture_output=True, text=True, check=False)
            if r.returncode != 0:
                return {"status": "failed", "exit_code": r.returncode}

            pid, last_exit = None, None
            for line in r.stdout.splitlines():
                if '"PID"' in line:
                    parts = line.split("=")
                    if len(parts) > 1:
                        pid = parts[1].strip().strip(";")
                elif '"LastExitStatus"' in line:
                    parts = line.split("=")
                    if len(parts) > 1:
                        last_exit = parts[1].strip().strip(";")

            if pid and pid != "0":
                return {"status": "running", "pid": pid}
            elif last_exit == "0":
                return {"status": "idle"}
            else:
                return {"status": "failed", "exit_code": last_exit}
        except Exception as e:  # noqa: BLE001  # defensive fallback
            return {"status": "error", "error": str(e)}

    def _repair_launchd_service(self, label: str, config_path: str) -> bool:
        """Repair launchd LWCR desync by unloading/loading the plist (ISC-2).

        Returns True if the service is running after repair.
        """
        if not config_path:
            return False
        cfg = Path(config_path).expanduser()
        if not cfg.is_file():
            return False
        try:
            print(f"🔧 [launchd repair] {label}: unloading/loading {cfg}")
            subprocess.run(
                ["launchctl", "unload", str(cfg)], capture_output=True, timeout=10, check=False)
            subprocess.run(
                ["launchctl", "load", str(cfg)], capture_output=True, timeout=10, check=False)
            time.sleep(0.5)
            status = self._check_launchd(label)
            return status.get("status") == "running"
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ [launchd repair] {label} failed: {e}")
            return False

    def _check_docker(self, container: str) -> dict:
        if not container:
            return {"status": "unknown"}
        try:
            r = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"name={container}",
                    "--format",
                    "{{.Status}}",
                ],
                capture_output=True,
                text=True, check=False)
            status = r.stdout.strip()
            if status:
                return {"status": "running", "details": status}
            else:
                return {"status": "stopped"}
        except Exception as e:  # noqa: BLE001  # defensive fallback
            return {"status": "error", "error": str(e)}

    def _check_port(self, port: int) -> bool:
        if not port:
            return False
        try:
            r = subprocess.run(
                ["lsof", f"-iTCP:{port}", "-sTCP:LISTEN", "-P"], capture_output=True, check=False)
            return r.returncode == 0
        except Exception:  # noqa: BLE001  # defensive fallback
            return False

    def _check_log_freshness(self, log_path: str, max_age: int = 90) -> bool:
        """检查日志新鲜度 — stdio-only daemon 真活探测.

        launchd 只验 PID 抓不住 "uv launcher 保活但子服务已死" 的假阳性 (launcher 僵尸).
        对无 port/health_url 的 stdio daemon (如 agora-gateway mcp_gateway), 用日志 mtime
        交叉校验: heartbeat 类服务日志持续更新, 进程卡死/退出后日志停止更新.

        Returns:
            True = 日志新鲜 (服务真活) 或无 log_path (不作为降级依据);
            False = 日志陈旧/不存在 (服务疑似死).
        """
        if not log_path:
            return True
        try:
            expanded = os.path.expandvars(os.path.expanduser(log_path))
            if not os.path.isfile(expanded):
                return False
            age = time.time() - os.path.getmtime(expanded)
            return age <= max_age
        except Exception:  # noqa: BLE001  # 探测出错保守不降级
            return True

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
            except Exception:  # noqa: BLE001, S110, S112  # defensive fallback
                pass  # noqa: S110, BLE001, S112  # defensive fallback

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
        except Exception as e:  # noqa: BLE001  # defensive fallback
            print(f"Cycle detected in DAG: {e}")
            order = [s.name for s in services]

        ordered_services = [svc_dict[name] for name in order if name in svc_dict]

        for svc in ordered_services:
            result = {"type": svc.type, "name": svc.name, "timestamp": current_time}

            # Scheduled (cron-managed) jobs 不走 daemon launchd 健康检查 / self-heal.
            # 它们由 cron-service 按计划触发, 常驻 alive 检查是误报 (e.g. gbrain-index daily 02:00).
            if svc.type == "scheduled":
                result["runtime"] = {"status": "scheduled"}
                result["health_check"] = "scheduled"
                scan_results[svc.name] = result
                continue

            # Check dependencies
            deps_healthy = True
            failed_deps = []
            for dep in svc.depends_on:
                dep_res = scan_results.get(dep, {})
                rt = dep_res.get("runtime", {}).get("status", "")
                if rt in (
                    "failed",
                    "error",
                    "stopped",
                    "FROZEN_CRASH_LOOP",
                    "WAITING_FOR_DEPENDENCY",
                    "BACKOFF",
                    "unreachable",
                ):
                    deps_healthy = False
                    failed_deps.append(dep)
                    break
                hc = dep_res.get("health_check")
                if hc and hc != "healthy":
                    deps_healthy = False
                    failed_deps.append(dep)
                    break

            if not deps_healthy:
                result["runtime"] = {
                    "status": "WAITING_FOR_DEPENDENCY",
                    "reason": f"Waiting for: {failed_deps}",
                }
                scan_results[svc.name] = result
                continue

            svc_history = restart_history.get(svc.name, [])
            # Clean old history (> 5 mins)
            svc_history = [t for t in svc_history if current_time - t < 300]

            is_frozen = len(svc_history) >= 5
            if is_frozen:
                result["runtime"] = {
                    "status": "FROZEN_CRASH_LOOP",
                    "reason": "More than 5 restarts in 5 minutes",
                }
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
                # ISC-2 治本: launchd LWCR 失步时先 unload/load plist 修复
                if (
                    rt_status.get("status") in ("failed", "error")
                    and svc.launchd_config
                ):
                    exit_code = rt_status.get("exit_code")
                    if exit_code in ("78", "19968", 78, 19968):
                        if self._repair_launchd_service(
                            svc.launchd_label, svc.launchd_config
                        ):
                            rt_status = self._check_launchd(svc.launchd_label)
                            result["runtime"] = rt_status
                if rt_status.get("status") in ("failed", "error"):
                    # B 治本 (self-heal 死循环防护): 确定性故障 (ImportError/配置错) 重启不可能
                    # 修复, launchctl stop/start 会无限重试. 服务持续未 healthy 超 30 分钟 →
                    # 标 unrecoverable, 停止死循环, 让健康分如实反映 (区别于 FROZEN_CRASH_LOOP 的 5 分钟窗口).
                    _lh_ts = state.get("last_healthy", {}).get(svc.name)
                    if _lh_ts and current_time - _lh_ts > 1800:
                        result["runtime"]["status"] = "unrecoverable"
                        result["runtime"]["unrecoverable_reason"] = (
                            "persistent failure >1800s despite self-heal (deterministic fault)"
                        )
                    else:
                        # Exponential Backoff based on recent restart counts
                        backoff = 5 * (2 ** len(svc_history))
                        last_restart = svc_history[-1] if svc_history else 0
                        if current_time - last_restart >= backoff:
                            print(
                                f"⚠️ Service {svc.name} is {rt_status.get('status')}. Backoff={backoff}s. Self-healing..."
                            )
                            subprocess.run(
                                ["launchctl", "stop", svc.launchd_label],
                                capture_output=True, check=False)
                            subprocess.run(
                                ["launchctl", "start", svc.launchd_label],
                                capture_output=True, check=False)
                            svc_history.append(current_time)
                            result["runtime"]["self_heal_attempted"] = True
                        else:
                            print(
                                f"⏳ Service {svc.name} is in backoff ({backoff}s). Waiting..."
                            )
                            result["runtime"]["status"] = "BACKOFF"

            elif svc.docker_container:
                rt_status = self._check_docker(svc.docker_container)
                result["runtime"] = rt_status
                if rt_status.get("status") in ("stopped", "error"):
                    backoff = 5 * (2 ** len(svc_history))
                    last_restart = svc_history[-1] if svc_history else 0
                    if current_time - last_restart >= backoff:
                        print(
                            f"⚠️ Service {svc.name} is {rt_status.get('status')}. Backoff={backoff}s. Self-healing..."
                        )
                        subprocess.run(
                            ["docker", "restart", svc.docker_container],
                            capture_output=True, check=False)
                        svc_history.append(current_time)
                        result["runtime"]["self_heal_attempted"] = True
                    else:
                        print(
                            f"⏳ Service {svc.name} is in backoff ({backoff}s). Waiting..."
                        )
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

            # 治本 (launcher-zombie 假阳性): launchd/docker 报 PID 在 ≠ 服务真在提供服务.
            # uv/python launcher 被 KeepAlive 保活时, 子服务可能已崩溃但 launchctl 仍报 running,
            # 导致 status/uptime/health_score 全线假阳性 (2026-07-10 agora 事件根因).
            # 交叉校验端口监听 / HTTP 健康, 命中即降级 degraded, 让假绿灯无所遁形.
            _pre_status = result.get("runtime", {}).get("status")
            if _pre_status in ("running", "idle"):
                _degrade_reasons = []
                if svc.port and result.get("port_listening") is False:
                    _degrade_reasons.append(f"port {svc.port} not listening")
                if svc.health_url and result.get("health_check") not in (
                    "healthy",
                    None,
                ):
                    _degrade_reasons.append(
                        f"health_check={result.get('health_check')}"
                    )
                # stdio-only daemon (无 port 无 health_url): 日志新鲜度交叉校验真活,
                # 揭穿 launcher 僵尸 (uv 保活但子服务死, 无 heartbeat). 仅当配了 log_path 才生效.
                if not svc.port and not svc.health_url and svc.log_path:
                    if not self._check_log_freshness(svc.log_path):
                        _degrade_reasons.append(
                            f"log {svc.log_path} stale (no heartbeat)"
                        )
                if _degrade_reasons:
                    result["runtime"]["status"] = "degraded"
                    result["runtime"]["degraded_reason"] = "; ".join(_degrade_reasons)

            # X2-NO_FRESHNESS: update freshness on healthy
            rt = result.get("runtime", {}).get("status")
            hc = result.get("health_check")
            if rt in ("running", "idle") or hc == "healthy":
                self._freshness[svc.name] = time.monotonic()
                self._consecutive_failures.pop(svc.name, None)
            else:
                self._consecutive_failures[svc.name] = (
                    self._consecutive_failures.get(svc.name, 0) + 1
                )
                # P1-AUTO_HEAL: trigger autoheal when consecutive failures exceed threshold
                if (
                    self._autoheal_enabled
                    and self._consecutive_failures[svc.name] >= self._stale_threshold
                ):
                    print(
                        f"⚠️ [P1-AUTO_HEAL] {svc.name}: {self._consecutive_failures[svc.name]} consecutive failures, triggering autoheal..."
                    )
                    self._autoheal_service(svc.name)

            # Uptime/staleness tracking (ADR-0120: semantic separation)
            # uptime_seconds: how long the service has been running (stability indicator)
            # last_healthy_seconds: time since last confirmed healthy (staleness indicator)
            running_since = state.setdefault("running_since", {})
            running_pid = state.setdefault(
                "running_pid", {}
            )  # Bug A: 跟踪 pid 治 uptime 虚高
            last_healthy = state.setdefault("last_healthy", {})
            if rt == "running":
                current_pid = result.get("runtime", {}).get("pid")
                # Bug A 治本: PID 变化(进程重启) → 重置 running_since. 否则 uptime/freshness
                # 沿用旧进程启动时间永久虚高 (agora-gateway uptime 13天 > 进程实际5天).
                pid_changed = bool(current_pid) and str(
                    running_pid.get(svc.name)
                ) != str(current_pid)
                if svc.name not in running_since or pid_changed:
                    running_since[svc.name] = current_time
                    if current_pid:
                        running_pid[svc.name] = current_pid
                result["runtime"]["uptime_seconds"] = int(
                    current_time - running_since[svc.name]
                )
                # freshness_seconds: time since last confirmed healthy
                last_healthy_ts = last_healthy.get(svc.name, 0)
                if last_healthy_ts:
                    freshness = int(current_time - last_healthy_ts)
                else:
                    freshness = int(
                        current_time - running_since.get(svc.name, current_time)
                    )
                result["runtime"]["freshness_seconds"] = freshness
            # Track last healthy time — runs for both running and idle services
            if rt in ("running", "idle") or hc == "healthy":
                last_healthy[svc.name] = current_time
                result["runtime"]["last_healthy_seconds"] = 0
            else:
                running_since.pop(svc.name, None)
                running_pid.pop(svc.name, None)  # Bug A: 连带清 pid tracking
                # Report staleness: time since last seen healthy
                result["runtime"]["last_healthy_seconds"] = int(
                    current_time - last_healthy.get(svc.name, current_time)
                )

            scan_results[svc.name] = result

        # Calculate state hash (excluding last_scan to prevent constant updates)
        state_hash = hashlib.md5(
            json.dumps(scan_results, sort_keys=True).encode()
        ).hexdigest()

        # Detect state transition and increment counter
        state_transitioned = state_hash != self.last_state_hash
        if state_transitioned:
            state["state_transitions"] += 1
            self.last_state_hash = state_hash

        # Save state back
        state["restart_history"] = restart_history
        state["running_since"] = state.get("running_since", {})
        state["running_pid"] = state.get(
            "running_pid", {}
        )  # Bug A: 持久化 pid tracking
        state["last_healthy"] = state.get("last_healthy", {})
        try:
            with open(state_file, "w") as f:
                json.dump(state, f)
        except Exception:  # noqa: BLE001, S110, S112  # defensive fallback
            pass  # noqa: S110, BLE001, S112  # defensive fallback

        self.state = {"last_scan": current_time, "services": scan_results}

        # Write local state
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

        # HealthPulse: Only write to OMO SSOT if state transitioned or force_write
        if state_transitioned or self._force_write:
            OMO_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            try:
                validate_runtime_health_snapshot(self.state)
                with open(OMO_STATE_FILE, "w") as f:
                    yaml.safe_dump(self.state, f, default_flow_style=False)
                print(
                    f"💓 HealthPulse: Updated {OMO_STATE_FILE} "
                    f"({'state transition' if state_transitioned else 'force write'})"
                )
                self.last_state_hash = state_hash
                # ISC-2 治本: 同步 runtime 健康汇总到 system.yaml
                self._sync_system_yaml_runtime_summary(self.state)
            except Exception as e:  # noqa: BLE001  # defensive fallback
                print(f"Failed to update OMO state: {e}")

        # Alert on health transitions: healthy → unreachable
        notify_script = (
            Path(os.environ.get("RUNTIME_HOME", Path.home() / "runtime"))
            / "scripts"
            / "event_driven_notify.py"
        )
        for svc_name, result in scan_results.items():
            current_hc = result.get("health_check")
            prev_hc = self._prev_health.get(svc_name)
            if prev_hc == "healthy" and current_hc == "unreachable":
                print(
                    f"🚨 Health alert: {svc_name} went healthy→unreachable. Notifying..."
                )
                try:
                    subprocess.run(
                        [
                            "python3",
                            str(notify_script),
                            "--service",
                            svc_name,
                            "--status",
                            "unreachable",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10, check=False)
                except Exception as e:  # noqa: BLE001  # defensive fallback
                    print(f"Failed to run notify script for {svc_name}: {e}")
            self._prev_health[svc_name] = current_hc

    def run_entropy_gc(self):
        print("🧹 [X2 Anti-Entropy] Running Pan-Entropy GC...")
        workspace = _workspace_root
        compacted = archive_resolved_debt_items(
            workspace / ".omo",
            now=time.time(),
            older_than_seconds=604800,
        )
        if compacted > 0:
            print(
                f"📦 [X2 Anti-Entropy] Compacted {compacted} resolved debt items to archive."
            )

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
                    print(
                        f"🧊 [X2-NO_FRESHNESS] Service '{svc_name}' is STALE (age={age:.1f}s, consecutive_scans={self._stale_count[svc_name]})"
                    )
                    stale_found = True
                    # Trigger autoheal if enabled and not already triggered by consecutive failures
                    if (
                        self._autoheal_enabled
                        and svc_name not in self._consecutive_failures
                    ):
                        self._autoheal_service(svc_name)
            else:
                self._stale_count.pop(svc_name, None)
        if not stale_found:
            self._stale_count.clear()

    def _autoheal_service(self, svc_name: str):
        """P1-AUTO_HEAL: Call autoheal.sh to restart a failing service."""
        autoheal_script = (
            Path(__file__).parent.parent.parent / "scripts" / "autoheal.sh"
        )
        if not autoheal_script.exists():
            print(f"⚠️ [P1-AUTO_HEAL] autoheal.sh not found at {autoheal_script}")
            return
        try:
            r = subprocess.run(
                ["bash", str(autoheal_script), svc_name],
                capture_output=True,
                text=True,
                timeout=30, check=False)
            if r.returncode == 0:
                print(f"✅ [P1-AUTO_HEAL] {svc_name}: autoheal succeeded")
            else:
                print(
                    f"❌ [P1-AUTO_HEAL] {svc_name}: autoheal FAILED (exit={r.returncode}): {r.stdout.strip()[-200:]}"
                )
        except subprocess.TimeoutExpired:
            print(f"⚠️ [P1-AUTO_HEAL] {svc_name}: autoheal timed out after 30s")
        except Exception as e:  # noqa: BLE001  # defensive fallback
            print(f"⚠️ [P1-AUTO_HEAL] {svc_name}: autoheal error: {e}")

    def _sync_system_yaml_runtime_summary(self, snapshot: dict) -> None:
        """同步 runtime_health_summary + service_online_ratio 到 system.yaml.

        ISC-3 / G-CONV.3 single-source: summary.ratio 与顶层 service_online_ratio
        必须同源 (daemon 去假阳性)。只写 summary 会留下 1.0 vs 0.75 双写者分裂
        (compass 写顶层 1.0, 旧 summarize 把 idle ollama 计离线写 summary 0.75).
        """
        system_yaml = OMO_STATE_FILE.parent / "system.yaml"
        if not system_yaml.is_file():
            print(f"⚠️  system.yaml 不存在: {system_yaml}, 跳过 runtime summary 同步")
            return
        try:
            summary = summarize_system_health_snapshot(snapshot)
            data = yaml.safe_load(system_yaml.read_text(encoding="utf-8")) or {}
            data["runtime_health_summary"] = summary
            # single-source: top-level ratio follows the same daemon de-false-positive summary
            if summary.get("ratio") is not None:
                data["service_online_ratio"] = summary["ratio"]
            data["updated_at"] = datetime.now(timezone.utc).astimezone().isoformat()

            # GCSI 维度 2 (ADR-0121): record feedback loop timestamp + evidence score
            data["governance_feedback_last_run"] = data["updated_at"]

            tmp = system_yaml.with_suffix(".yaml.tmp")
            tmp.write_text(
                yaml.dump(
                    data, allow_unicode=True, sort_keys=False, default_flow_style=False
                ),
                encoding="utf-8",
            )
            tmp.replace(system_yaml)
            print(
                f"✅ system.yaml runtime_health_summary 同步完成: online={summary.get('online_services')}/{summary.get('total_services')} ratio={summary.get('ratio')}"
            )
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  system.yaml runtime summary 同步失败: {e}")

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
