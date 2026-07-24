"""ECOS L0 Trigger Registry Protocol.

Defines declarative triggers for BOS URI events and crons.
"""

from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TriggerType(StrEnum):
    CRON = "cron"
    EVENT = "event"
    WEBHOOK = "webhook"


class BaseTrigger(BaseModel):
    """Base definition for a declarative trigger."""

    name: str = Field(..., description="Unique name of the trigger")
    trigger_type: TriggerType = Field(..., description="Type of the trigger")
    target_bos_uri: str = Field(
        ..., description="Target BOS URI to invoke when triggered"
    )
    payload_template: Optional[Dict[str, Any]] = Field(
        default=None, description="Static payload or template to send"
    )


class CronTrigger(BaseTrigger):
    """Cron-based trigger."""

    trigger_type: TriggerType = TriggerType.CRON
    expression: str = Field(
        ..., description="Standard cron expression (e.g. '0 * * * *')"
    )
    timezone: str = Field(default="UTC", description="Timezone for the cron expression")


class EventTrigger(BaseTrigger):
    """Event-based trigger (pub/sub)."""

    trigger_type: TriggerType = TriggerType.EVENT
    source_event_type: str = Field(..., description="Event type to subscribe to")


class TriggerRegistryFacade(ABC):
    """Protocol for managing and loading declarative triggers."""

    @abstractmethod
    def register_trigger(self, trigger: BaseTrigger) -> None:
        """Register a single trigger."""
        pass

    @abstractmethod
    def unregister_trigger(self, name: str) -> None:
        """Unregister a trigger by name."""
        pass

    @abstractmethod
    def list_triggers(self) -> List[BaseTrigger]:
        """List all registered triggers."""
        pass

    @abstractmethod
    def load_from_yaml(self, path: Path | str) -> None:
        """Load declarative triggers from a YAML manifest."""
        pass
