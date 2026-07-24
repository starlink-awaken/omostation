"""YAML loader implementation for ECOS Trigger Registry."""

from pathlib import Path
from typing import List

import yaml

from .registry import (
    BaseTrigger,
    CronTrigger,
    EventTrigger,
    TriggerRegistryFacade,
    TriggerType,
)


class YAMLTriggerRegistry(TriggerRegistryFacade):
    """File-backed Trigger Registry."""

    def __init__(self):
        self._triggers: dict[str, BaseTrigger] = {}

    def register_trigger(self, trigger: BaseTrigger) -> None:
        self._triggers[trigger.name] = trigger

    def unregister_trigger(self, name: str) -> None:
        if name in self._triggers:
            del self._triggers[name]

    def list_triggers(self) -> List[BaseTrigger]:
        return list(self._triggers.values())

    def load_from_yaml(self, path: Path | str) -> None:
        path = Path(path)
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        for t_dict in data.get("triggers", []):
            try:
                t_type = t_dict.get("trigger_type")
                if t_type == TriggerType.CRON:
                    self.register_trigger(CronTrigger(**t_dict))
                elif t_type == TriggerType.EVENT:
                    self.register_trigger(EventTrigger(**t_dict))
                else:
                    # Generic or unknown
                    self.register_trigger(BaseTrigger(**t_dict))
            except Exception:  # defensive fallback
                pass  # skip invalid trigger
