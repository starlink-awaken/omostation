from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
"""
Minerva Executor — Orchestrate research execution in three modes.

Modes:
- Immediate: Execute pipeline immediately, return result
- Scheduled: Register cron task, execute on schedule
- Watch: Poll sources for new content, execute on detection
"""

import asyncio
import json
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, cast

import structlog

from minerva.pipeline.engine import Pipeline, ResearchContext
from minerva.triage.router import ResearchLevel

logger = structlog.get_logger(__name__)


# ============================================================
# Data Models
# ============================================================


class ExecutionMode(Enum):
    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    WATCH = "watch"


@dataclass
class ResearchTask:
    id: str
    query: str
    mode: ExecutionMode
    level: str  # L0-L4 or "auto"
    max_cost: float
    # Scheduled
    cron_expr: str | None = None
    # Watch
    topic: str | None = None
    sources: list[str] | None = None
    check_interval: str | None = None  # hourly|daily|weekly
    notify: str = "mcp"


@dataclass
class ResearchResult:
    task_id: str
    context: ResearchContext
    summary: str
    report_path: str | None
    cost: float
    completed_at: str


@dataclass
class TaskStatus:
    task_id: str
    status: str  # pending|running|completed|failed|cancelled
    mode: ExecutionMode
    query: str
    level: str
    cost: float
    started_at: str | None
    completed_at: str | None
    error: str | None = None


# ============================================================
# Cost Guard
# ============================================================


class CostGuard:
    """Enforce monthly budget for cloud API usage."""

    def __init__(
        self,
        monthly_budget: float = 50.0,
        warn_pct: float = 0.80,
        ledger_path: str = "~/minerva/state/cost_ledger.jsonl",
    ) -> None:
        self.monthly_budget = monthly_budget
        self.warn_threshold = monthly_budget * warn_pct
        self.current_spend = 0.0
        self.reset_day = 1
        self.ledger_path = Path(ledger_path).expanduser()
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_ledger()

    def _load_ledger(self) -> None:
        """Load current month's spend from persistent ledger."""
        if not self.ledger_path.exists():
            return
        current_month = datetime.now(UTC).strftime("%Y-%m")
        try:
            with open(self.ledger_path) as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("month") == current_month:
                        self.current_spend += entry.get("cost", 0.0)
        except Exception:
            pass

    def check(self, estimated_cost: float) -> bool:
        """Check if estimated cost is within budget. Returns True if allowed."""
        if self.current_spend + estimated_cost > self.monthly_budget:
            logger.warning(
                "budget_exceeded",
                current=self.current_spend,
                estimated=estimated_cost,
                budget=self.monthly_budget,
            )
            return False
        return True

    def record(self, actual_cost: float) -> None:
        """Record actual API spend with persistent ledger."""
        self.current_spend += actual_cost
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "month": datetime.now(UTC).strftime("%Y-%m"),
            "cost": actual_cost,
        }
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        if self.current_spend >= self.warn_threshold:
            logger.warning("budget_warning", current=self.current_spend, budget=self.monthly_budget)

    def get_status(self) -> dict:
        """Get current budget status."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spend": self.current_spend,
            "remaining": self.monthly_budget - self.current_spend,
            "warn_threshold": self.warn_threshold,
            "pct_used": self.current_spend / self.monthly_budget * 100,
        }


# ============================================================
# Source Checkers (Watch mode)
# ============================================================


class SourceChecker:
    """Check external sources for new content matching a topic."""

    async def check_arxiv(self, topic: str, since: datetime | None) -> list[dict]:
        """Query arXiv API for new papers matching topic since given date."""
        try:
            encoded = urllib.parse.quote(topic)
            url = f"http://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results=10&sortBy=submittedDate&sortOrder=descending"
            import httpx

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                raw = resp.text
        except Exception:
            return []

        items = []
        try:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(raw)
            for entry in root.findall("atom:entry", ns):
                published_el = entry.find("atom:published", ns)
                published = published_el.text[:10] if published_el is not None and published_el.text else ""
                if since:
                    from datetime import datetime as dt

                    pub_dt = dt.strptime(published, "%Y-%m-%d")
                    since_dt = since if isinstance(since, dt) else dt.fromisoformat(str(since)[:10])
                    if pub_dt < since_dt:
                        continue
                title_el = entry.find("atom:title", ns)
                summary_el = entry.find("atom:summary", ns)
                link_el = entry.find("atom:id", ns)
                items.append(
                    {
                        "title": title_el.text.strip() if title_el is not None and title_el.text else "",
                        "url": link_el.text.strip() if link_el is not None and link_el.text else "",
                        "summary": summary_el.text.strip()[:200] if summary_el is not None and summary_el.text else "",
                        "published": published,
                        "source": "arxiv",
                    }
                )
        except Exception:
            pass
        return items

    async def check_github_trending(self, topic: str, since: datetime | None) -> list[dict]:
        """Check GitHub trending for repos matching topic."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://gh-trending-api.herokuapp.com/repositories",
                    params={"language": "", "since": "daily"},
                )
                resp.raise_for_status()
                repos = resp.json()
        except Exception:
            return []
        items = []
        topic_lower = topic.lower()
        for repo in (repos or [])[:20]:
            desc = (repo.get("description") or "").lower()
            name = (repo.get("name") or "").lower()
            lang = (repo.get("language") or "").lower()
            if topic_lower in desc or topic_lower in name or topic_lower in lang:
                items.append(
                    {
                        "title": repo.get("name", ""),
                        "url": repo.get("url", ""),
                        "summary": (repo.get("description") or "")[:200],
                        "published": "",
                        "source": "github_trending",
                    }
                )
        return items

    async def check_rss(self, feed_url: str, topic: str, since: datetime | None) -> list[dict]:
        """Check RSS feed for new items matching topic."""
        try:
            import feedparser  # type: ignore[reportMissingImports]

            feed = feedparser.parse(feed_url)
        except Exception:
            return []

        items = []
        topic_lower = topic.lower()
        for entry in feed.entries[:15]:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))
            if topic_lower in title.lower() or topic_lower in summary.lower()[:200]:
                items.append(
                    {
                        "title": title,
                        "url": entry.get("link", ""),
                        "summary": summary[:200] if summary else "",
                        "published": entry.get("published", entry.get("updated", "")),
                        "source": feed_url,
                    }
                )
        return items

    async def check_zhihu(self, topic: str, since: datetime | None) -> list[dict]:
        """Check Zhihu for new content matching topic (via 秘塔 or direct)."""
        return []

    async def check(self, source: str, topic: str, since: datetime | None) -> list[dict]:
        """Dispatch to appropriate checker."""
        checkers = {
            "arxiv": self.check_arxiv,
            "github_trending": self.check_github_trending,
            "techcrunch": lambda t, s: self.check_rss("https://techcrunch.com/feed/", t, s),
            "reddit": lambda t, s: self.check_rss("https://www.reddit.com/r/MachineLearning/.rss", t, s),
            "zhihu": self.check_zhihu,
        }
        checker = checkers.get(source)
        if checker:
            return await checker(topic, since)
        return []


# ============================================================
# Executor
# ============================================================


class ResearchExecutor:
    """Orchestrate research execution in three modes.

    Usage:
        executor = ResearchExecutor(triage_router, pipeline, knowledge_store, cost_guard)
        result = await executor.execute_now(task)
        task_id = await executor.schedule(task)
        task_id = await executor.watch(task)
    """

    def __init__(
        self,
        triage_router: Any,
        pipeline: Pipeline,
        knowledge_store: Any,
        cost_guard: CostGuard,
        state_dir: str = "~/minerva/state",
    ) -> None:
        self.router = triage_router
        self.pipeline = pipeline
        self.kb = knowledge_store
        self.cost_guard = cost_guard
        self.state_dir = Path(state_dir).expanduser()
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Active tasks
        self.scheduled_tasks: dict[str, asyncio.Task] = {}
        self.watch_tasks: dict[str, asyncio.Task] = {}
        self.notifications: deque[dict] = deque(maxlen=1000)

        # Task metadata for persistence (populated by schedule/watch)
        self._task_meta: dict[str, dict] = {}

        # Source checker
        self.source_checker = SourceChecker()

        # Restore persisted state
        self.restore_state()

    # ============================================================
    # Public API
    # ============================================================

    async def execute_now(self, task: ResearchTask) -> ResearchResult:
        """Execute research immediately.

        Flow:
        1. Classify query via TriageRouter (if level=auto)
        2. Check budget via CostGuard
        3. Run Pipeline
        4. Persist result
        5. Notify
        6. Return result
        """
        logger.info("execute_now_start", task_id=task.id, query=task.query[:100])

        # 1. Classify
        level = ResearchLevel(task.level) if task.level != "auto" else None
        if level is None:
            triage = await self.router.classify(task.query)
            level = triage.level
        else:
            triage = None  # User explicitly chose level, skip classification

        # 2. Cost check
        if not self.cost_guard.check(task.max_cost):
            raise BudgetExceededError(f"Cost {task.max_cost} exceeds remaining budget")

        # 3. Execute pipeline
        if triage is None:
            triage = await self.router.classify(task.query)  # Need triage for model plan

        started_at = datetime.now(UTC).isoformat()
        ctx = await self.pipeline.run(task.query, level, triage)
        completed_at = datetime.now(UTC).isoformat()

        # 4. Record cost
        self.cost_guard.record(ctx.cost)

        # 5. Build result
        result = ResearchResult(
            task_id=task.id,
            context=ctx,
            summary=self._generate_summary(ctx),
            report_path=ctx.report_path,
            cost=ctx.cost,
            completed_at=completed_at,
        )

        # 6. Persist execution log
        self._log_execution(task, result, started_at, completed_at)

        # 7. Notify
        self._notify(task, result)

        logger.info("execute_now_complete", task_id=task.id, cost=ctx.cost, elapsed=ctx.stage_timings)
        return result

    async def schedule(self, task: ResearchTask) -> str:
        """Schedule recurring research via APScheduler. Returns task_id."""
        task_id = task.id or str(uuid.uuid4())[:8]
        task.id = task_id

        self._ensure_scheduler()

        async def _execute_scheduled() -> None:
            try:
                await self.execute_now(task)
                logger.info("scheduled_task_complete", task_id=task_id, cron=task.cron_expr)
            except Exception as exc:
                logger.error("scheduled_task_failed", task_id=task_id, error=str(exc))

        from apscheduler.triggers.cron import CronTrigger

        job = self._apscheduler.add_job(
            _execute_scheduled,
            CronTrigger.from_crontab(task.cron_expr),
            id=task_id,
            replace_existing=True,
            misfire_grace_time=300,
        )
        self.scheduled_tasks[task_id] = job  # type: ignore[reportArgumentType]
        self._task_meta[task_id] = {
            "query": task.query,
            "cron_expr": task.cron_expr,
            "level": task.level,
        }
        self._persist_scheduled_tasks()
        next_run = str(job.next_run_time) if job.next_run_time else "now"
        logger.info("schedule_created", task_id=task_id, cron=task.cron_expr, next_run=next_run)
        return task_id

    async def watch(self, task: ResearchTask) -> str:
        """Watch topics for new content via APScheduler. Returns task_id."""
        task_id = task.id or str(uuid.uuid4())[:8]
        task.id = task_id

        interval_secs = {"hourly": 3600, "daily": 86400, "weekly": 604800}.get(task.check_interval or "daily", 86400)
        self._ensure_scheduler()

        async def _watch_check() -> None:
            for source in task.sources or []:
                try:
                    new_items = await self.source_checker.check(source, cast("str", task.topic), None)
                    for item in new_items:
                        watch_task = ResearchTask(
                            id=str(uuid.uuid4())[:8],
                            query=(f"[WATCH: {task.topic}] {item.get('title', item.get('summary', ''))}"),
                            mode=ExecutionMode.IMMEDIATE,
                            level="L2",
                            max_cost=task.max_cost,
                        )
                        await self.execute_now(watch_task)
                        self._notify(task, None)
                except Exception as exc:
                    logger.error("watch_check_failed", source=source, error=str(exc))

        job = self._apscheduler.add_job(
            _watch_check,
            "interval",
            seconds=interval_secs,
            id=task_id,
            replace_existing=True,
            misfire_grace_time=300,
        )
        self.watch_tasks[task_id] = job  # type: ignore[reportArgumentType]
        self._task_meta[task_id] = {
            "topic": task.topic,
            "sources": task.sources,
            "check_interval": task.check_interval,
        }
        self._persist_watch_configs()
        logger.info("watch_created", task_id=task_id, topic=task.topic, sources=task.sources)
        return task_id

    def _ensure_scheduler(self) -> None:
        """Lazy-init APScheduler with SQLite persistence."""
        if hasattr(self, "_apscheduler"):
            return
        from apscheduler.jobstores.memory import MemoryJobStore
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        self._apscheduler = AsyncIOScheduler(jobstores={"default": MemoryJobStore()})
        self._apscheduler.start()

    async def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled or watch task."""
        cancelled = False
        if task_id in self.scheduled_tasks:
            self.scheduled_tasks[task_id].cancel()
            del self.scheduled_tasks[task_id]
            cancelled = True
        if task_id in self.watch_tasks:
            self.watch_tasks[task_id].cancel()
            del self.watch_tasks[task_id]
            cancelled = True
        return cancelled

    async def get_status(self, task_id: str) -> TaskStatus | None:
        """Get status of a task."""
        # Check in-memory tasks
        if task_id in self.scheduled_tasks:
            t = self.scheduled_tasks[task_id]
            return TaskStatus(
                task_id=task_id,
                status="running" if not t.done() else "completed",
                mode=ExecutionMode.SCHEDULED,
                query="",
                level="",
                cost=0,
                started_at=None,
                completed_at=None,
            )
        # Check execution log
        log_path = self.state_dir / "execution_log.jsonl"
        if log_path.exists():
            with open(log_path) as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("task_id") == task_id:
                        return TaskStatus(**entry)
        return None

    async def list_tasks(self, mode: str | None = None) -> list[dict]:
        """List all tasks, optionally filtered by mode."""
        tasks = []
        # Scheduled
        for tid, t in self.scheduled_tasks.items():
            tasks.append(
                {
                    "task_id": tid,
                    "mode": "scheduled",
                    "status": "running" if not t.done() else "completed",
                }
            )
        # Watch
        for tid, t in self.watch_tasks.items():
            tasks.append(
                {
                    "task_id": tid,
                    "mode": "watch",
                    "status": "running" if not t.done() else "completed",
                }
            )
        if mode:
            tasks = [t for t in tasks if t["mode"] == mode]
        return tasks

    # ============================================================
    # Public: State Persistence & Health
    # ============================================================

    def restore_state(self) -> dict:
        """Restore scheduled tasks and watch configs from disk on startup."""
        result = {"scheduled": 0, "watch": 0}
        try:
            spath = self.state_dir / "scheduled_tasks.json"
            if spath.exists():
                with open(spath) as f:
                    configs = json.load(f)
                for cfg in configs:
                    tid = cfg.get("id", "")
                    if tid:
                        self._task_meta[tid] = {
                            "query": cfg.get("query", ""),
                            "cron_expr": cfg.get("cron", ""),
                            "level": cfg.get("level", "auto"),
                        }
                result["scheduled"] = len(configs)
        except Exception:
            pass
        try:
            wpath = self.state_dir / "watch_configs.json"
            if wpath.exists():
                with open(wpath) as f:
                    configs = json.load(f)
                for cfg in configs:
                    tid = cfg.get("id", "")
                    if tid:
                        self._task_meta[tid] = {
                            "topic": cfg.get("topic", ""),
                            "sources": cfg.get("sources", []),
                            "check_interval": cfg.get("check_interval", "daily"),
                        }
                result["watch"] = len(configs)
        except Exception:
            pass
        return result

    def persist_state(self) -> None:
        """Persist all execution state to disk."""
        self._persist_scheduled_tasks()
        self._persist_watch_configs()

    def health_check(self) -> dict:
        """Return current daemon health status."""
        return {
            "scheduled": len(self.scheduled_tasks),
            "watch": len(self.watch_tasks),
            "budget_used": self.cost_guard.current_spend,
            "budget_limit": self.cost_guard.monthly_budget,
            "notifications": len(self.notifications),
        }

    # ============================================================
    # Private: State Persistence
    # ============================================================

    def _persist_task_dict(self, tasks: dict, filename: str, keys: dict[str, tuple[str, object]]) -> None:
        """Persist task metadata to JSON file using key mapping.

        Always includes the task ID as 'id'. Additional keys are extracted from
        _task_meta using the provided attr_key → default mapping.
        """
        configs = []
        for tid in tasks:
            meta = self._task_meta.get(tid, {})
            entry = {"id": tid}
            for json_key, (attr_key, default) in keys.items():
                entry[json_key] = meta.get(attr_key, default)
            configs.append(entry)
        with open(self.state_dir / filename, "w") as f:
            json.dump(configs, f, indent=2)

    def _persist_scheduled_tasks(self) -> None:
        self._persist_task_dict(
            self.scheduled_tasks,
            "scheduled_tasks.json",
            {
                "id": ("id", ""),
                "query": ("query", ""),
                "cron": ("cron_expr", ""),
                "level": ("level", "auto"),
            },
        )

    def _persist_watch_configs(self) -> None:
        self._persist_task_dict(
            self.watch_tasks,
            "watch_configs.json",
            {
                "id": ("id", ""),
                "topic": ("topic", ""),
                "sources": ("sources", []),
                "check_interval": ("check_interval", "daily"),
            },
        )

    def _log_execution(self, task: ResearchTask, result: ResearchResult, started: str, completed: str) -> None:
        """Append execution record to JSONL log using atomic append."""
        entry = {
            "task_id": task.id,
            "mode": task.mode.value,
            "query": task.query[:200],
            "level": result.context.level.value,
            "cost": result.cost,
            "started_at": started,
            "completed_at": completed,
            "stage_timings": result.context.stage_timings,
        }
        log_path = self.state_dir / "execution_log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # 使用原子追加确保多进程安全
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _notify(self, task: ResearchTask, result: ResearchResult | None) -> None:
        """Queue notification for agent consumption via MCP."""
        if result is None:
            return None
        notification = {
            "task_id": task.id,
            "mode": task.mode.value,
            "status": "completed",
            "summary": result.summary,
            "report_path": result.report_path,
            "cost": result.cost,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.notifications.append(notification)
        # 使用原子写入持久化
        notif_path = self.state_dir / "notifications.json"
        notif_path.parent.mkdir(parents=True, exist_ok=True)
        with open(notif_path, "a") as f:
            f.write(json.dumps(notification) + "\n")

    @staticmethod
    def _generate_summary(ctx: ResearchContext) -> str:
        """Generate one-paragraph summary from pipeline context."""
        # Extract first 200 chars of report or key findings
        if ctx.report:
            return ctx.report[:300] + ("..." if len(ctx.report) > 300 else "")
        return f"Research completed at level {ctx.level.value} with {len(ctx.entities)} entities extracted."


class BudgetExceededError(Exception):
    """Raised when research cost exceeds remaining budget."""

    pass
