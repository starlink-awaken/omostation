"""Sophia — Symbolic Research Paradigm Engine.

A formal system for composing, compiling, and evolving research paradigms.
Research is modeled as a finite state machine with atomic operations.

Quick start:
    from sophia import compile_paradigm_sync
    program = compile_paradigm_sync("Compare Rust vs Go")
    print(program.to_dict())
"""

from .compiler import compile_paradigm, compile_paradigm_sync, recompile_from_dict
from .learner import ParadigmLearner, ResearchTrace
from .symbols import (
    BASE_TRANSITIONS,
    AtomicOp,
    ParadigmProgram,
    ResearchState,
    TransitionRule,
    gate_always,
    gate_has_contradictions,
    gate_has_entities,
    gate_has_sources,
    gate_quality_pass,
)

__all__ = (
    "BASE_TRANSITIONS",
    "AtomicOp",
    "ParadigmLearner",
    "ParadigmProgram",
    "ResearchState",
    "ResearchTrace",
    "TransitionRule",
    "compile_paradigm",
    "compile_paradigm_sync",
    "gate_always",
    "gate_has_contradictions",
    "gate_has_entities",
    "gate_has_sources",
    "gate_quality_pass",
    "recompile_from_dict",
)
"""
Sophia — 符号化研究范式引擎。

跨项目桥接:
- sophia → minerva: minerva 测试依赖 sophia.compiler + sophia.learner
- sophia → pallas: pallas pipeline 可加载 sophia 范式
- sophia → agora: 共享 MCP/fastmcp 生态
"""
