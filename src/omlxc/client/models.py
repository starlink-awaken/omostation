"""Validated wire values exposed by the private daemon client."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Self, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RemoteError(WireModel):
    code: str = Field(min_length=1, max_length=32)
    message: str = Field(min_length=1, max_length=1_024)
    retryable: bool = False
    technical_detail: str | None = None
    suggested_action: str | None = None
    affected_resources: tuple[str, ...] = ()
    partial_result: JsonValue | None = None


class DaemonEnvelope(WireModel):
    schema_version: int
    request_id: str = Field(min_length=1, max_length=64)
    data: JsonValue | None = None
    error: RemoteError | None = None

    @model_validator(mode="before")
    @classmethod
    def require_one_branch(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            raise ValueError("response envelope must be an object")
        mapping = cast(Mapping[object, object], value)
        if ("data" in mapping) == ("error" in mapping):
            raise ValueError("response envelope must contain exactly one branch")
        return cast(object, value)

    @model_validator(mode="after")
    def require_supported_schema(self) -> Self:
        if self.schema_version != 1:
            raise ValueError("unsupported response schema")
        return self


class DaemonEvent(WireModel):
    schema_version: int
    request_id: str = Field(min_length=1, max_length=64)
    cursor: int | None = Field(default=None, ge=0)
    event_id: str = Field(min_length=1, max_length=256)
    timestamp: datetime
    priority: str = Field(min_length=1, max_length=32)
    kind: str = Field(min_length=1, max_length=256)
    payload: JsonValue
    job_id: str | None = None
    resource_id: str | None = None

    @model_validator(mode="after")
    def require_supported_schema(self) -> Self:
        if self.schema_version != 1:
            raise ValueError("unsupported event schema")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("event timestamp must be timezone-aware")
        return self
