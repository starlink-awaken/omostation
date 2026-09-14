"""OntoDerive — 渊衍框架 v3.6.4

知识工程分析平台。三模式：结构分析 | 规则推理 | 形式推理。
物理五层架构 + ToolForge工具匹配 + 分析模式引擎 + 连续推理谱系。

用法:
    from ontoderive import OntoDerive, ToolForge, FormalPipeline
    od = OntoDerive("my-project").derive()
"""

__all__ = []

__version__ = "3.6.4"

# 顶层 re-export — 保持向后兼容
from ontoderive.core.derive import VERSION as _VERSION
from ontoderive.core.derive import OntoDerive as _OntoDerive
from ontoderive.reasoners.formalize import Formalizer as _Formalizer
from ontoderive.reasoners.formalize import FormalKnowledge as _FormalKnowledge
from ontoderive.reasoners.pipeline_v4 import FormalPipeline as _FormalPipeline
from ontoderive.toolforge import ToolForge as _ToolForge

from . import core as core
from . import foundation as foundation
from . import intelligence as intelligence
from . import reasoners as reasoners
from . import theories as theories

OntoDerive = _OntoDerive
VERSION = _VERSION
ToolForge = _ToolForge
Formalizer = _Formalizer
FormalKnowledge = _FormalKnowledge
FormalPipeline = _FormalPipeline

__all__ = [
    "OntoDerive",
    "VERSION",
    "ToolForge",
    "Formalizer",
    "FormalKnowledge",
    "FormalPipeline",
    "core",
    "foundation",
    "intelligence",
    "reasoners",
    "theories",
]

# 子包门面 — 可直接 from engine import xxx_layer
