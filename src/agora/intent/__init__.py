"""Intent model — answer "what's the most important thing right now".

BET-Y2Q1-T3-02: 让 Agent 能回答"现在最重要的是哪件".

Reads active tasks (TaskManager) + goals/mandates (omo state) and
produces a ranked priority list with rationale.
"""

from agora.intent.model import IntentModel, IntentResult
from agora.intent.prioritizer import Prioritizer, ScoredItem, ScoreWeights, Priority

__all__ = [
    "IntentModel",
    "IntentResult",
    "Prioritizer",
    "Priority",
    "ScoreWeights",
    "ScoredItem",
]
