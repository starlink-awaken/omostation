"""
SSOT Kernel — 提取层
=====================

从原始文本到结构化 YAML 知识的一站式流水线。

三路提取器（自动降级）:
    1. Template （毫秒级，固定格式文本）
    2. LLM      （秒级，Ollama / 云端 API 后端链）
    3. Interactive（交互式，人机对话引导）

使用:
    from .extractor import ExtractionPipeline, TextSource

    pipe = ExtractionPipeline()
    source = TextSource(raw_text="...", source_type="document")
    result = pipe.run(source)

    for c in result["result"].candidates:
        print(c.category, c.id)

后端链优先级（自动检测）:
    Ollama → 硅基流动 → DeepSeek → OpenAI

环境变量:
    OLLAMA_MODEL=xxx           Ollama 模型名
    OLLAMA_TIMEOUT=120         Ollama 请求超时
    SILICONFLOW_API_KEY=xxx    硅基流动 API Key
    DEEPSEEK_API_KEY=xxx       DeepSeek API Key
    OPENAI_API_KEY=xxx         OpenAI API Key

导出:
    TextSource             — 输入：原始文本及元信息
    ExtractionCandidate    — 输出：单条提取候选
    ExtractionResult       — 输出：提取结果集合
    ValidationResult       — 校验结果
    Conflict               — 校验冲突
    ExtractionPipeline     — 流水线入口
"""

from .base import Conflict, ExtractionCandidate, ExtractionResult, TextSource, ValidationResult
from .pipeline import ExtractionPipeline

__all__ = [
    "TextSource",
    "ExtractionCandidate",
    "ExtractionResult",
    "Conflict",
    "ValidationResult",
    "ExtractionPipeline",
]
