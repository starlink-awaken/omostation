#!/usr/bin/env python3
"""治理 SSOT 的安全编辑工具：yaml round-trip，根治字符串手术事故。

治理 SSOT（registry/ledger/debt）的编辑一律走本工具：load → 编辑回调 →
dump → 重新 load 语义校验 → 原子写回。字符串手术（sed/re.sub/段内插入）
在缩进层级上反复翻车（2026-08-30 单日三连炸），此后禁止用于治理 SSOT。

用法（CLI）：
    python3 bin/ssot/yaml-roundtrip-edit.py --file <yaml> --script <edit.py>
edit.py 定义 ``def edit(data: dict) -> dict``，返回修改后的数据。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml


def roundtrip_edit(path: Path, editor) -> dict:
    """按编辑回调修改 yaml 文件并安全写回。

    editor: 接收解析后的 dict，返回修改后的 dict（可原地修改后返回同一对象）。
    失败时文件保持不变；成功时原子替换（tmp + os.replace）。
    """
    path = Path(path)
    original_text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(original_text)
    if not isinstance(data, dict):
        raise SystemExit(f"roundtrip-edit: {path} 顶层必须是 mapping")

    edited = editor(data)
    if edited is None:
        edited = data
    if not isinstance(edited, dict):
        raise SystemExit("roundtrip-edit: 编辑回调必须返回 dict")

    dump = yaml.dump(
        edited,
        allow_unicode=True,
        sort_keys=False,
        width=200,
        default_flow_style=False,
    )
    # 语义校验：dump 产物必须能无损还原为编辑后的数据
    reloaded = yaml.safe_load(dump)
    if reloaded != edited:
        raise SystemExit("roundtrip-edit: dump 后语义校验失败，文件未写入")

    if reloaded == yaml.safe_load(original_text):
        print("roundtrip-edit: no changes")  # 幂等：无变化不写
        return edited

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(dump)
    os.replace(tmp_name, path)
    print(f"roundtrip-edit: {path} updated")
    return edited


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True, help="含 edit(data) 的 python 脚本")
    args = parser.parse_args(argv)
    spec = importlib.util.spec_from_file_location("ssot_edit_script", args.script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "edit"):
        raise SystemExit("roundtrip-edit: --script 必须定义 edit(data)")
    roundtrip_edit(args.file, module.edit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
