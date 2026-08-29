#!/usr/bin/env python3
"""
check-kems-update.py — KEMS 强制更新检查（统一包装器 · @公共版）

各文档域通过符号链接挂载本文件（<域>/_runtime/check-kems-update.py → @公共/_runtime/check-kems-update.py）。
利用 Python 不解析符号链接的特性，abspath(__file__) 返回挂载路径，上两级即挂载域根——
同一脚本天然以各域为根运行。

本包装器只做一件事：定位统一工具 kems-toolkit.py 并透传 --root 与参数。
逻辑单点维护于 @公共，域内不复制逻辑。

健康度巡检：python3 check-kems-update.py --mode health
"""

import os
import subprocess
import sys
from pathlib import Path

# 挂载域根：absolute() 不解析符号链接 → 上两级 = 挂载域根
# （未挂载直接运行时 = @公共 根，对 @公共 自身执行检查）
DOMAIN = Path(__file__).absolute().parent.parent

# 前店后厂缓冲区（存在则一并检查）
BUFF_INBOX = Path.home() / "Documents" / "_inbox"


def main():
    toolkit = Path(__file__).resolve().parent / "kems-toolkit.py"
    if not toolkit.is_file():
        sys.exit(f"❌ 未找到统一工具: {toolkit}")

    argv = [sys.executable, str(toolkit), "--root", str(DOMAIN)]
    if BUFF_INBOX.is_dir():
        argv += ["--inbox-extra", str(BUFF_INBOX)]
    argv += sys.argv[1:]

    sys.exit(subprocess.call(argv))


if __name__ == "__main__":
    main()
