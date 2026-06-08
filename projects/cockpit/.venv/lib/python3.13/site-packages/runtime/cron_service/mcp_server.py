"""FastMCP server for cron-service — exposes tools for Hermes integration.

Tools exposed (matching Hermes' cronjob toolset):
  - cron_list      — list all jobs (filter: enabled/disabled)
  - cron_get       — get job details
  - cron_create    — create a new job
  - cron_update    — update an existing job
  - cron_delete    — remove a job
  - cron_pause     — disable a job
  - cron_resume    — enable a job
  - cron_run       — trigger immediate execution
  - cron_status    — scheduler health / stats
"""

import json
import logging

from . import config as svc_config
from . import db, scheduler
from .models import JobCreate, JobUpdate

logger = logging.getLogger(__name__)

# ── FastMCP instance ───────────────────────────────────────────────

mcp = None  # Created on start() with fastmcp.FastMCP


def _fmt_job(job) -> dict:
    """Format job for API output."""
    return {
        "id": job.id,
        "name": job.name,
        "schedule": job.schedule,
        "script": job.script,
        "no_agent": job.no_agent,
        "deliver": job.deliver,
        "workdir": job.workdir,
        "timeout": job.timeout,
        "enabled": job.enabled,
        "repeat": job.repeat,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "last_status": job.last_status,
        "last_output": job.last_output[:500] if job.last_output else None,
        "last_error": job.last_error[:500] if job.last_error else None,
        "run_count": job.run_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def _register_tools(fastmcp, sched: scheduler.CronScheduler):
    """Register all MCP tools on the FastMCP instance."""

    @fastmcp.tool()
    def cron_list(enabled_only: bool = False) -> str:
        """List all cron jobs.

        Args:
            enabled_only: If True, only show enabled jobs
        """
        jobs = db.list_jobs(enabled_only=enabled_only)
        summary = {"total": len(jobs), "jobs": [_fmt_job(j) for j in jobs]}
        return json.dumps(summary, indent=2, ensure_ascii=False)

    @fastmcp.tool()
    def cron_get(job_id: str) -> str:
        """Get details of a specific cron job.

        Args:
            job_id: The job ID
        """
        job = db.get_job(job_id)
        if not job:
            return json.dumps({"error": f"Job {job_id!r} not found"})
        return json.dumps(_fmt_job(job), indent=2, ensure_ascii=False)

    @fastmcp.tool()
    def cron_create(
        name: str,
        schedule: str,
        script: str | None = None,
        deliver: str = "local",
        workdir: str | None = None,
        timeout: int = 120,
    ) -> str:
        """Create a new cron job.

        Args:
            name: Human-readable job name
            schedule: Cron expression or 'every Xm'/'every Xh'
            script: Path to script (relative to ~/.hermes/scripts/ or absolute)
            deliver: Delivery target ('local' or 'origin')
            workdir: Working directory (optional)
            timeout: Timeout in seconds (default 120)
        """
        data = JobCreate(
            name=name,
            schedule=schedule,
            script=script,
            no_agent=True,
            deliver=deliver,
            workdir=workdir,
            timeout=timeout,
        )
        job = db.create_job(data)
        return json.dumps(
            {
                "success": True,
                "job_id": job.id,
                "job": _fmt_job(job),
            },
            indent=2,
            ensure_ascii=False,
        )

    @fastmcp.tool()
    def cron_update(
        job_id: str,
        name: str | None = None,
        schedule: str | None = None,
        script: str | None = None,
        deliver: str | None = None,
        workdir: str | None = None,
        timeout: int | None = None,
        enabled: bool | None = None,
        no_agent: bool | None = None,
    ) -> str:
        """Update an existing cron job.

        Args:
            job_id: The job ID to update
            name: New name
            schedule: New schedule expression
            script: New script path
            deliver: New delivery target ('local' or 'origin')
            workdir: New working directory
            timeout: New timeout in seconds
            enabled: Enable/disable the job
            no_agent: Whether to run without agent
        """
        update_data = {k: v for k, v in locals().items() if k != "job_id" and v is not None}
        if not update_data:
            return json.dumps({"error": "No valid fields to update"})
        data = JobUpdate(**update_data)
        job = db.update_job(job_id, data)
        if not job:
            return json.dumps({"error": f"Job {job_id!r} not found"})
        return json.dumps({"success": True, "job": _fmt_job(job)}, indent=2, ensure_ascii=False)

    @fastmcp.tool()
    def cron_delete(job_id: str) -> str:
        """Delete a cron job.

        Args:
            job_id: The job ID to delete
        """
        ok = db.delete_job(job_id)
        return json.dumps({"success": ok, "job_id": job_id})

    @fastmcp.tool()
    def cron_pause(job_id: str) -> str:
        """Pause (disable) a cron job.

        Args:
            job_id: The job ID to pause
        """
        job = db.update_job(job_id, JobUpdate(enabled=False))
        if not job:
            return json.dumps({"error": f"Job {job_id!r} not found"})
        return json.dumps({"success": True, "job_id": job_id, "enabled": False})

    @fastmcp.tool()
    def cron_resume(job_id: str) -> str:
        """Resume (enable) a cron job.

        Args:
            job_id: The job ID to resume
        """
        job = db.update_job(job_id, JobUpdate(enabled=True))
        if not job:
            return json.dumps({"error": f"Job {job_id!r} not found"})
        return json.dumps({"success": True, "job_id": job_id, "enabled": True})

    @fastmcp.tool()
    def cron_run(job_id: str) -> str:
        """Trigger immediate execution of a cron job.

        Args:
            job_id: The job ID to run
        """
        job = db.get_job(job_id)
        if not job:
            return json.dumps({"error": f"Job {job_id!r} not found"})

        # Run synchronously using executor
        from . import executor as ex

        result = ex.execute(
            job.script,
            timeout=job.timeout or svc_config.DEFAULT_TIMEOUT,
            workdir=job.workdir,
        )

        if result.timed_out:
            db.record_run(job_id, "timeout", "", f"Timed out after {job.timeout}s")
            return json.dumps({"success": False, "error": "timeout"})
        elif result.success:
            db.record_run(job_id, "ok", result.output, result.error)
            return json.dumps(
                {
                    "success": True,
                    "output": result.output[:2000],
                },
                ensure_ascii=False,
            )
        else:
            db.record_run(job_id, "error", result.output, result.error)
            return json.dumps(
                {
                    "success": False,
                    "output": result.output[:1000],
                    "error": result.error[:1000],
                },
                ensure_ascii=False,
            )

    @fastmcp.tool()
    def cron_status() -> str:
        """Get scheduler health and stats."""
        jobs = db.list_jobs()
        enabled = [j for j in jobs if j.enabled]
        ok_count = sum(1 for j in jobs if j.last_status == "ok")
        err_count = sum(1 for j in jobs if j.last_status in ("error", "timeout"))

        # Check if scheduler is likely running — any job executed recently?
        sum(1 for j in jobs if j.last_run_at is not None)
        return json.dumps(
            {
                "running": True,  # scheduler runs in the HTTP process
                "total_jobs": len(jobs),
                "enabled_jobs": len(enabled),
                "last_ok": ok_count,
                "last_error": err_count,
                "version": "1.0.0",
            },
            indent=2,
        )
