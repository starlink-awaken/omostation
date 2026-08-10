"""Deterministic MOF Control Compiler (WP-W1-02-003).

Reads the W1 core M2 YAML contracts under ``ecos.ssot.mof.m2`` as the single
model truth and deterministically compiles them into artifact classes:
JSON Schema, Pydantic v2 models, Zod schemas and SQLite DDL.

Public surface:

- :class:`MofCompiler` — the reusable Python compiler API
  (``compile`` / ``write`` / ``check``)
- :func:`load_m2_dir` — parse the M2 truth into the IR
- ``ARTIFACT_CLASSES`` — registered artifact classes
"""

from ecos.ssot.mof.compiler.api import (
    ARTIFACT_CLASSES,
    M2Property,
    M2Schema,
    CompilerError,
    MofCompiler,
    load_m2_dir,
)

__all__ = [
    "ARTIFACT_CLASSES",
    "CompilerError",
    "M2Property",
    "M2Schema",
    "MofCompiler",
    "load_m2_dir",
]
