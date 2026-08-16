#!/usr/bin/env python3
# ruff: noqa
"""KOS CLI Color helpers — 终端着色工具.

从 cli/__main__.py 抽出 (God Module 拆 wave 8, __main__.py 1096->~1030).
"""

from __future__ import annotations

_NO_COLOR = False


def _c(code: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def BOLD(t) -> str:  # noqa: N802
    return _c("1", t)


def DIM(t) -> str:  # noqa: N802
    return _c("2", t)


def CYAN(t) -> str:  # noqa: N802
    return _c("36", t)


def GREEN(t) -> str:  # noqa: N802
    return _c("32", t)


def YELLOW(t) -> str:  # noqa: N802
    return _c("33", t)


def RED(t) -> str:  # noqa: N802
    return _c("31", t)


def MAG(t) -> str:  # noqa: N802
    return _c("35", t)
