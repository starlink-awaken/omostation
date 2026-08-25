"""
cockpit.tui.swarm_collector — Multi-Agent 全景状态聚合与采集器

负责毫秒级采集并标准化以下核心状态：
1. Agent Swarm 拓扑与最近心跳 (agent-tick-daemon.jsonl)
2. Concurrency 锁与活跃工作树 (agent-workflow & .omo/state/locks)
3. 3年规划 BET 台账进度与阻塞 (docs/plans/3y-bet-ledger.yaml)
4. 19 个子仓指针雷达与本地/远端漂移 (.gitmodules & git cacheinfo)
5. A2A 智能体协作通信事件流 (a2a-messages.jsonl)
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _find_repo_root() -> Path:
    """定位主仓根目录（包含 .gitmodules 的最顶层工作区）。"""
    if (Path.cwd() / ".gitmodules").exists():
        return Path.cwd().resolve()
    env_ws = os.environ.get("WORKSPACE_ROOT")
    if env_ws and (Path(env_ws) / ".gitmodules").exists():
        return Path(env_ws).resolve()
    cur = Path(__file__).resolve().parent
    top_found = None
    for _ in range(8):
        if (cur / ".gitmodules").exists():
            return cur
        if (cur / ".omo").exists():
            top_found = cur
        cur = cur.parent
    return top_found or Path(os.environ.get("WORKSPACE_ROOT", os.getcwd())).resolve()


@dataclass
class AgentHeartbeat:
    name: str
    status: str  # "healthy", "busy", "stale", "unknown"
    action: str
    last_seen_iso: str
    seconds_ago: float


@dataclass
class SwarmAgentSummary:
    total_agents: int
    healthy_count: int
    failed_count: int
    last_tick_iso: str
    agents: list[AgentHeartbeat] = field(default_factory=list)


@dataclass
class LockSummary:
    active_runs: int
    total_locks: int
    stale_locks: int
    details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BetTrackProgress:
    track: str
    total: int
    done: int
    in_progress: int
    blocked: int
    percent: float


@dataclass
class BetLedgerSummary:
    total_bets: int
    done_count: int
    in_progress_count: int
    blocked_count: int
    overall_percent: float
    tracks: list[BetTrackProgress] = field(default_factory=list)


@dataclass
class SubmoduleItem:
    name: str
    path: str
    current_sha: str
    remote_sha: str
    drift_status: str  # "aligned", "drifted", "unknown"
    version: str = ""


@dataclass
class SubmoduleRadarSummary:
    total_submodules: int
    aligned_count: int
    drifted_count: int
    items: list[SubmoduleItem] = field(default_factory=list)


@dataclass
class A2AMessageItem:
    from_agent: str
    to_agent: str
    msg_type: str
    ts_iso: str
    summary: str


@dataclass
class SwarmGlobalState:
    timestamp_iso: str
    agents: SwarmAgentSummary
    locks: LockSummary
    bets: BetLedgerSummary
    submodules: SubmoduleRadarSummary
    daemon: dict = field(default_factory=dict)
    recent_messages: list[A2AMessageItem] = field(default_factory=list)


class SwarmStateCollector:
    """全局多 Agent 状态聚合器。"""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _find_repo_root()
        self._remote_sha_cache: dict[str, tuple[str, float]] = {}
        self._cache_ttl_sec = 300.0  # 5 分钟缓存

    def collect_daemon(self, port: int = 7432) -> dict:
        import urllib.request

        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/health", headers={"User-Agent": "cockpit-tui"})
            with urllib.request.urlopen(req, timeout=0.15) as resp:  # noqa: S310
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return {"status": "offline", "active_agents": 0, "subscribed_topics": []}

    def collect_all(self, probe_remote_submodules: bool = False) -> SwarmGlobalState:
        """全量采集系统状态。"""
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return SwarmGlobalState(
            timestamp_iso=now_iso,
            agents=self.collect_agents(),
            locks=self.collect_locks(),
            bets=self.collect_bets(),
            submodules=self.collect_submodules(probe_remote=probe_remote_submodules),
            daemon=self.collect_daemon(),
            recent_messages=self.collect_a2a_messages(limit=30),
        )

    def collect_agents(self) -> SwarmAgentSummary:
        """从 agent-tick-daemon.jsonl 采集 Agent 心跳。"""
        tick_file = self.root / ".omo" / "state" / "agent-tick-daemon.jsonl"
        known_agents = [
            "governor",
            "advisor",
            "knowledge-curator",
            "observer",
            "task-worker",
            "bridge",
        ]
        if not tick_file.exists():
            return SwarmAgentSummary(
                total_agents=len(known_agents),
                healthy_count=0,
                failed_count=0,
                last_tick_iso="N/A",
                agents=[
                    AgentHeartbeat(
                        name=a,
                        status="unknown",
                        action="idle",
                        last_seen_iso="N/A",
                        seconds_ago=-1,
                    )
                    for a in known_agents
                ],
            )

        last_line = ""
        try:
            with open(tick_file, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.strip():
                        last_line = line.strip()
        except Exception as e:
            logger.debug("Failed to read agent-tick-daemon.jsonl: %s", e)

        if not last_line:
            return SwarmAgentSummary(
                total_agents=len(known_agents),
                healthy_count=0,
                failed_count=0,
                last_tick_iso="N/A",
            )

        try:
            data = json.loads(last_line)
            ts_str = data.get("ts", "")
            agent_count = data.get("agent_count", len(known_agents))
            failed = data.get("failed_count", 0)
            ok_count = data.get("ok_count", agent_count - failed)
            actions = data.get("actions", [])

            # 计算 seconds_ago
            sec_ago = 0.0
            if ts_str:
                try:
                    t = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    sec_ago = (datetime.now(UTC) - t).total_seconds()
                except Exception:
                    sec_ago = 0.0

            heartbeats: list[AgentHeartbeat] = []
            for i, name in enumerate(known_agents):
                act = actions[i] if i < len(actions) else "noop"
                st = "healthy" if sec_ago < 600 else "stale"
                heartbeats.append(
                    AgentHeartbeat(
                        name=name,
                        status=st,
                        action=act,
                        last_seen_iso=ts_str,
                        seconds_ago=max(0.0, sec_ago),
                    )
                )

            return SwarmAgentSummary(
                total_agents=agent_count,
                healthy_count=ok_count,
                failed_count=failed,
                last_tick_iso=ts_str,
                agents=heartbeats,
            )
        except Exception as e:
            logger.debug("Failed to parse tick line: %s", e)
            return SwarmAgentSummary(
                total_agents=len(known_agents),
                healthy_count=0,
                failed_count=0,
                last_tick_iso="ERROR",
            )

    def collect_locks(self) -> LockSummary:
        """从 agent-workflow / locks 采集并发锁状态。"""
        # 读取 lock 目录或 agent-workflow status
        locks_dir = self.root / ".omo" / "state" / "locks"
        active_count = 0
        stale_count = 0
        details: list[dict[str, Any]] = []

        if locks_dir.exists():
            now = time.time()
            for p in locks_dir.glob("*.lock"):
                try:
                    mtime = p.stat().st_mtime
                    age = now - mtime
                    is_stale = age > 1800  # 30min
                    if is_stale:
                        stale_count += 1
                    else:
                        active_count += 1
                    details.append(
                        {
                            "name": p.name,
                            "age_seconds": age,
                            "stale": is_stale,
                        }
                    )
                except Exception:
                    pass

        # 尝试快速运行 agent-workflow.py status (若可用)
        wf_script = self.root / "bin" / "agent-workflow.py"
        if wf_script.exists():
            try:
                proc = subprocess.run(
                    ["python3", str(wf_script), "status"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if proc.returncode == 0:
                    # 解析 runs active=3 closed=69 locks=9 stale=7
                    m = re.search(
                        r"runs active=(\d+).*?locks=(\d+).*?stale=(\d+)",
                        proc.stdout,
                    )
                    if m:
                        return LockSummary(
                            active_runs=int(m.group(1)),
                            total_locks=int(m.group(2)),
                            stale_locks=int(m.group(3)),
                            details=details,
                        )
            except Exception:
                pass

        return LockSummary(
            active_runs=active_count,
            total_locks=active_count + stale_count,
            stale_locks=stale_count,
            details=details,
        )

    def collect_bets(self) -> BetLedgerSummary:
        """轻量解析 docs/plans/3y-bet-ledger.yaml 统计进度。"""
        ledger_path = self.root / "docs" / "plans" / "3y-bet-ledger.yaml"
        if not ledger_path.exists():
            return BetLedgerSummary(
                total_bets=0,
                done_count=0,
                in_progress_count=0,
                blocked_count=0,
                overall_percent=0.0,
            )

        try:
            import yaml

            with open(ledger_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            bets = data.get("bets", [])
            total = len(bets)
            done_cnt = 0
            in_prog_cnt = 0
            blocked_cnt = 0
            track_map: dict[str, dict[str, int]] = {}

            for b in bets:
                st = str(b.get("status", "proposed")).lower()
                tr = str(b.get("track", "UNKNOWN"))
                if tr not in track_map:
                    track_map[tr] = {
                        "total": 0,
                        "done": 0,
                        "in_progress": 0,
                        "blocked": 0,
                    }

                track_map[tr]["total"] += 1
                if st == "done":
                    done_cnt += 1
                    track_map[tr]["done"] += 1
                elif st == "in_progress":
                    in_prog_cnt += 1
                    track_map[tr]["in_progress"] += 1
                elif st == "blocked":
                    blocked_cnt += 1
                    track_map[tr]["blocked"] += 1

            track_progress: list[BetTrackProgress] = []
            for tr, counts in sorted(track_map.items()):
                pct = (counts["done"] / counts["total"] * 100.0) if counts["total"] > 0 else 0.0
                track_progress.append(
                    BetTrackProgress(
                        track=tr,
                        total=counts["total"],
                        done=counts["done"],
                        in_progress=counts["in_progress"],
                        blocked=counts["blocked"],
                        percent=round(pct, 1),
                    )
                )

            overall_pct = (done_cnt / total * 100.0) if total > 0 else 0.0
            return BetLedgerSummary(
                total_bets=total,
                done_count=done_cnt,
                in_progress_count=in_prog_cnt,
                blocked_count=blocked_cnt,
                overall_percent=round(overall_pct, 1),
                tracks=track_progress,
            )
        except Exception as e:
            logger.debug("Failed to read bet ledger: %s", e)
            return BetLedgerSummary(
                total_bets=0,
                done_count=0,
                in_progress_count=0,
                blocked_count=0,
                overall_percent=0.0,
            )

    def collect_submodules(self, probe_remote: bool = False) -> SubmoduleRadarSummary:
        """扫描 .gitmodules 并获取指针状态。"""
        gitmodules_path = self.root / ".gitmodules"
        if not gitmodules_path.exists():
            return SubmoduleRadarSummary(total_submodules=0, aligned_count=0, drifted_count=0)

        # 读取本地 git index 指针
        index_shas: dict[str, str] = {}
        try:
            proc = subprocess.run(
                ["git", "ls-files", "-s"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=3,
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    # 160000 <sha> 0 <path>
                    parts = line.strip().split()
                    if len(parts) >= 4 and parts[0] == "160000":
                        index_shas[parts[3]] = parts[1]
        except Exception as e:
            logger.debug("Failed to git ls-files: %s", e)

        # 解析 .gitmodules
        sub_items: list[SubmoduleItem] = []
        try:
            content = gitmodules_path.read_text(encoding="utf-8")
            paths = re.findall(r'path\s*=\s*([^\s"\']+)', content)
            urls = re.findall(r'url\s*=\s*([^\s"\']+)', content)

            aligned_cnt = 0
            drifted_cnt = 0

            for i, p in enumerate(paths):
                name = Path(p).name
                cur_sha = index_shas.get(p, "unknown")
                short_cur = cur_sha[:7] if cur_sha != "unknown" else "?"
                url = urls[i] if i < len(urls) else ""

                remote_sha = cur_sha
                drift = "aligned"

                if probe_remote and url:
                    cached = self._remote_sha_cache.get(p)
                    now = time.time()
                    if cached and (now - cached[1]) < self._cache_ttl_sec:
                        remote_sha = cached[0]
                    else:
                        try:
                            res = subprocess.run(
                                [
                                    "git",
                                    "ls-remote",
                                    url,
                                    "refs/heads/main",
                                    "HEAD",
                                ],
                                capture_output=True,
                                text=True,
                                timeout=3,
                            )
                            if res.returncode == 0 and res.stdout:
                                remote_sha = res.stdout.split()[0] if res.stdout.split() else cur_sha
                                self._remote_sha_cache[p] = (remote_sha, now)
                        except Exception:
                            pass

                if cur_sha != "unknown" and remote_sha != cur_sha:
                    drift = "drifted"
                    drifted_cnt += 1
                else:
                    aligned_cnt += 1

                sub_items.append(
                    SubmoduleItem(
                        name=name,
                        path=p,
                        current_sha=short_cur,
                        remote_sha=remote_sha[:7] if remote_sha else short_cur,
                        drift_status=drift,
                    )
                )

            return SubmoduleRadarSummary(
                total_submodules=len(sub_items),
                aligned_count=aligned_cnt,
                drifted_count=drifted_cnt,
                items=sub_items,
            )
        except Exception as e:
            logger.debug("Failed to parse submodules: %s", e)
            return SubmoduleRadarSummary(total_submodules=0, aligned_count=0, drifted_count=0)

    def collect_a2a_messages(self, limit: int = 20) -> list[A2AMessageItem]:
        """读取最近的 A2A 消息流。"""
        msg_file = self.root / ".omo" / "state" / "a2a-messages.jsonl"
        if not msg_file.exists():
            return []

        items: list[A2AMessageItem] = []
        try:
            lines: list[str] = []
            with open(msg_file, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.strip():
                        lines.append(line.strip())

            for line in lines[-limit:]:
                try:
                    d = json.loads(line)
                    fr = d.get("from", "?")
                    to = d.get("to", "?")
                    tp = d.get("type", "event")
                    ts = d.get("ts", "")
                    pl = d.get("payload", {})
                    if isinstance(pl, dict):
                        act = pl.get("event") or pl.get("action") or pl.get("status") or str(pl)
                    else:
                        act = str(pl)

                    items.append(
                        A2AMessageItem(
                            from_agent=fr,
                            to_agent=to,
                            msg_type=tp,
                            ts_iso=ts,
                            summary=str(act)[:60],
                        )
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.debug("Failed to read a2a messages: %s", e)

        items.reverse()  # 最新排前面
        return items
