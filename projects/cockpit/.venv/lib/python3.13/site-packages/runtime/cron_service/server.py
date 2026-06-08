"""FastAPI entry point for cron-service.

Starts:
  - FastAPI HTTP server (health, status, job management)
  - Cron scheduler loop (in-process asyncio)

MCP server runs separately for Hermes integration (stdio mode).

Usage:
  python -m runtime.cron_service.server              # HTTP + scheduler
  python -m runtime.cron_service.server --mcp        # MCP stdio + scheduler (for Hermes)
  python -m runtime.cron_service.server --init-db    # Initialize database and exit
"""

import argparse
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

from . import config as svc_config
from . import db, mcp_server, scheduler
from .models import JobCreate

# ── Logging ────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, os.environ.get("CRON_SERVICE_LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cron-service")


# ── Lifecycle ──────────────────────────────────────────────────────

sched = scheduler.CronScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the scheduler with the FastAPI app."""
    db.init_db()
    await sched.start()
    logger.info("cron-service started (HTTP:%d, DATA:%s)", svc_config.HTTP_PORT, svc_config.DATA_DIR)
    yield
    await sched.stop()
    logger.info("cron-service stopped")


# ── FastAPI app ────────────────────────────────────────────────────

app = FastAPI(title="cron-service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check endpoint."""
    now = datetime.now(UTC)
    uptime_secs = None
    if sched.start_time:
        uptime_secs = int((now - sched.start_time).total_seconds())

    # Count broken symlinks
    from pathlib import Path

    hermes_scripts = Path.home() / ".hermes" / "scripts"
    broken = 0
    if hermes_scripts.is_dir():
        try:
            broken = sum(1 for f in hermes_scripts.iterdir() if f.is_symlink() and not f.exists())
        except Exception:
            pass

    # Count job errors
    all_jobs = db.list_jobs()
    error_jobs = [j for j in all_jobs if j.last_status in ("error", "timeout")]

    return {
        "status": "ok",
        "version": "1.0.0",
        "scheduler_running": sched.is_running,
        "uptime_seconds": uptime_secs,
        "ticks": sched.tick_count,
        "last_tick_at": sched.last_tick_time.isoformat() if sched.last_tick_time else None,
        "jobs": {
            "total": len(all_jobs),
            "enabled": len(db.list_jobs(enabled_only=True)),
            "with_errors": len(error_jobs),
        },
        "broken_symlinks": broken,
    }


@app.get("/jobs")
async def list_jobs(enabled_only: bool = False):
    """List all cron jobs."""
    jobs = db.list_jobs(enabled_only=enabled_only)
    return {
        "total": len(jobs),
        "jobs": [_fmt_job_api(j) for j in jobs],
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a specific cron job."""
    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"error": f"Job {job_id!r} not found"}, status_code=404)
    return _fmt_job_api(job)


@app.post("/jobs")
async def create_job(data: JobCreate):
    """Create a new cron job."""
    job = db.create_job(data)
    return {"success": True, "job_id": job.id, "job": _fmt_job_api(job)}


@app.post("/jobs/{job_id}/run")
async def run_job(job_id: str):
    """Trigger immediate execution of a job."""
    from . import executor as ex

    job = db.get_job(job_id)
    if not job:
        return JSONResponse({"error": f"Job {job_id!r} not found"}, status_code=404)

    result = ex.execute(
        job.script,
        timeout=job.timeout or svc_config.DEFAULT_TIMEOUT,
        workdir=job.workdir,
    )

    if result.timed_out:
        db.record_run(job_id, "timeout", "", f"Timed out after {job.timeout}s")
        return {"success": False, "error": "timeout"}
    elif result.success:
        db.record_run(job_id, "ok", result.output, result.error)
        return {"success": True, "output": result.output[:2000]}
    else:
        db.record_run(job_id, "error", result.output, result.error)
        return {"success": False, "output": result.output[:1000], "error": result.error[:1000]}


@app.put("/jobs/{job_id}")
async def update_job_http(job_id: str, data: dict):
    """Update a cron job's fields. Only provided fields are updated."""
    from .models import JobUpdate

    allowed = {"name", "schedule", "script", "deliver", "workdir", "timeout", "enabled", "no_agent"}
    update_data = {k: v for k, v in data.items() if k in allowed}
    if not update_data:
        return {"error": "No valid fields to update"}
    job = db.update_job(job_id, JobUpdate(**update_data))
    if not job:
        return JSONResponse({"error": f"Job {job_id!r} not found"}, status_code=404)
    return {"success": True, "job": _fmt_job_api(job)}


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a cron job."""
    ok = db.delete_job(job_id)
    return {"success": ok}


def _fmt_job_api(job):
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


# ── Main ───────────────────────────────────────────────────────────


def _start_sched_in_thread():
    """Run scheduler in a new event loop on a background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(sched.start())
    loop.run_forever()


def run_mcp():
    """Run MCP server in stdio mode (for Hermes)."""
    db.init_db()
    fastmcp = FastMCP("cron-service")

    # Register tools
    mcp_server._register_tools(fastmcp, sched)

    # MCP mode does NOT start a scheduler — the HTTP server process
    # (started separately via start-cron-service.sh) handles scheduling.
    # MCP mode only exposes management tools for Hermes integration.
    logger.info("MCP server starting (no scheduler — HTTP process handles it)...")
    fastmcp.run(transport="stdio")


def run_http():
    """Run HTTP API server."""
    uvicorn.run(
        app,
        host=svc_config.HOST,
        port=svc_config.HTTP_PORT,
        log_level="info",
    )


def main():
    parser = argparse.ArgumentParser(description="cron-service")
    parser.add_argument("--mcp", action="store_true", help="Run MCP server in stdio mode")
    parser.add_argument("--init-db", action="store_true", help="Initialize database and exit")
    args = parser.parse_args()

    if args.init_db:
        db.init_db()
        print(f"Database initialized at {svc_config.DATA_DIR}/cron.db")
        return

    if args.mcp:
        run_mcp()
    else:
        run_http()


if __name__ == "__main__":
    main()
