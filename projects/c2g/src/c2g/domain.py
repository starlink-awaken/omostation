from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class TaskSchema(BaseModel):
    task_id: str
    title: str
    description: str
    status: str = "planned"
    priority: str = "P1"
    assignee: str = "unassigned"
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BetSchema(BaseModel):
    goal_id: str
    title: str
    description: str
    status: str = "active"
    vector: str = "V2" # V1 or V2
    appetite: str = "1 week"
    created_at: str

class PitchSchema(BaseModel):
    pitch_id: str
    title: str
    content: str
    upstream_ref: Optional[str] = None
    appetite: Optional[str] = None
    created_at: str
