"""external.resources providers — 把 BOS 能力目录暴露给 mesh 能力目录契约。"""

from __future__ import annotations

from agora.external_resources.capability_provider import (
    CapabilityProvider,
    build_capability_descriptor,
)

__all__ = ["CapabilityProvider", "build_capability_descriptor"]
