import re
from typing import Any

from pydantic import BaseModel, create_model


def _map_type(type_str: str) -> type[Any]:
    mapping = {
        "string": str,
        "dict": dict[str, Any],
        "int": int,
        "float": float,
        "boolean": bool,
        "list": list[Any]
    }
    return mapping.get(type_str.lower().strip(), str)

class MarkdownProtocolReflector:
    """L0 SSOT Protocol Reflector.

    Dynamically reads Markdown table definitions from SSOT documents
    and compiles them into Pydantic models at runtime.
    """

    def __init__(self, ssot_path: str):
        self.ssot_path = ssot_path
        self._models: dict[str, type[BaseModel]] = {}
        self._parse()

    def _parse(self):
        try:
            with open(self.ssot_path, encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            return

        # Simple AST parsing for Markdown sections and tables
        current_model_name = None
        current_fields = {}

        lines = content.splitlines()
        for line in lines:
            # Match headers like `## Model: TaskObject`
            match = re.match(r"^##\s*Model:\s*(\w+)", line)
            if match:
                # Save previous model if exists
                if current_model_name and current_fields:
                    self._models[current_model_name] = create_model(current_model_name, **current_fields)

                current_model_name = match.group(1)
                current_fields = {}
                continue

            # Match table rows: | field_name | type | description |
            if current_model_name and line.startswith("|") and "---" not in line and "Field" not in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4:
                    field_name = parts[1]
                    field_type = parts[2]
                    # Create field definition for Pydantic (Type, Default)
                    # We use None as default to make them optional for now
                    current_fields[field_name] = (_map_type(field_type), None)

        # Save last model
        if current_model_name and current_fields:
            self._models[current_model_name] = create_model(current_model_name, **current_fields)

    def get_model(self, model_name: str) -> type[BaseModel]:
        if model_name not in self._models:
            raise ValueError(f"Model {model_name} not found in SSOT {self.ssot_path}")
        return self._models[model_name]

# Global singleton reflector for L0
_reflector = None

def get_protocol_reflector() -> MarkdownProtocolReflector:
    global _reflector
    if _reflector is None:
        _reflector = MarkdownProtocolReflector("/Users/xiamingxing/Workspace/.omo/standards/interface_contract.md")
    return _reflector

def get_task_object_model() -> type[BaseModel]:
    return get_protocol_reflector().get_model("TaskObject")

def get_agent_message_model() -> type[BaseModel]:
    return get_protocol_reflector().get_model("AgentMessage")
