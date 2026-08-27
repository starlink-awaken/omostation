"""atomic_write.py — 原子文件写入工具.

写入临时文件 → fsync → rename，确保写入途中崩溃不会损坏目标文件。
用于替代直接 write_text() / open("w") 模式。

用法:
    from kairon_utils.atomic_write import atomic_write_text, atomic_write_json

    atomic_write_text(path, "hello world")
    atomic_write_json(path, {"key": "value"}, indent=2)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(
    path: str | Path,
    content: str,
    encoding: str = "utf-8",
) -> Path:
    """原子写入文本文件.

    写入临时文件 → fsync → rename，确保写入途中崩溃不会损坏目标文件。

    Args:
        path: 目标文件路径
        content: 要写入的文本内容
        encoding: 文件编码，默认 utf-8

    Returns:
        目标文件的 Path 对象
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return path


def atomic_write_json(
    path: str | Path,
    data: Any,
    indent: int | None = 2,
    ensure_ascii: bool = False,
    **kwargs: Any,
) -> Path:
    """原子写入 JSON 文件.

    Args:
        path: 目标文件路径
        data: 要序列化的 Python 对象
        indent: JSON 缩进级别，默认 2
        ensure_ascii: 是否转义非 ASCII 字符，默认 False
        **kwargs: 传递给 json.dumps 的其他参数

    Returns:
        目标文件的 Path 对象
    """
    content = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, **kwargs)
    return atomic_write_text(path, content)
