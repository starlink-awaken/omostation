"""Data models for cron-service."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    """Input for creating a new cron job."""

    name: str
    schedule: str
    script: str | None = None
    prompt: str | None = None
    no_agent: bool = True
    deliver: str = "local"  # "local" | "origin"
    workdir: str | None = None
    timeout: int = 120
    repeat: str = "∞"
    enabled: bool = True


class JobUpdate(BaseModel):
    """Input for updating an existing job. All fields optional."""

    name: str | None = None
    schedule: str | None = None
    script: str | None = None
    prompt: str | None = None
    no_agent: bool | None = None
    deliver: str | None = None
    workdir: str | None = None
    timeout: int | None = None
    enabled: bool | None = None


class Job(JobCreate):
    """Full job model as stored and returned."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    last_run_at: datetime | None = None
    last_status: str | None = None  # "ok" | "error" | "timeout"
    last_output: str | None = None
    last_error: str | None = None
    run_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobResult(BaseModel):
    job_id: str
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int | None = None
    timed_out: bool = False


class ScheduleConfig(BaseModel):
    expression: str = "every 5m"
    timezone: str = "UTC"
