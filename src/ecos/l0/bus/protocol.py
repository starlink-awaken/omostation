import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


class OmniEnvelope(BaseModel):
    """
    Omni-Bus L0 Unified Envelope Protocol.
    SSOT: M2 Schema at ecos/src/ecos/ssot/mof/m2/omni_envelope.yaml
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str
    timestamp: float = Field(default_factory=time.time)
    version: str = "1.0"

    plane: str
    topic: str
    source_uri: str

    payload: dict[str, Any]
    signature: Optional[str] = None

    seq_id: Optional[int] = None
    retry_count: int = 0
