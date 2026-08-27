"""LLM智能层 — 推理增强 + 洞察 + 评估 + 提示词工程"""

from ontoderive.intelligence.insight import (
    Insight,
    InsightCache,
    InsightEngine,
)
from ontoderive.intelligence.judge import JudgeResult, OntoDeriveJudge
from ontoderive.intelligence.llm import LLMEnhancer, get_enhancer
from ontoderive.intelligence.prompts import (
    DOMAIN_PRESETS,
    PromptTemplate,
    auto_detect_domain,
    get_template,
)
