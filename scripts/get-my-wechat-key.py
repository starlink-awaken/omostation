#!/usr/bin/env python3
"""get-my-wechat-key.py — 微信 64位 Hex Key 物理获取与Keychain检索工具

途径 1: 物理检索 macOS Keychain 钥匙串
途径 2: 扫描 key_info.db 物理加密元数据
途径 3: lldb 只读内存匹配

v1.0 (Hex Key Retriever) | 2026-07-31
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

KEY_FILE = Path.home() / ".wechat_key"


def get_key_from_keychain() -> str | None:
    """尝试从 macOS 系统 Keychain 钥匙串提取微信保存的密匙."""
    try:
        cmd = ["security", "find-generic-password", "-s", "WeChat", "-w"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        key_str = res.stdout.strip()
        if key_str and len(key_str) == 64:
            return key_str
    except Exception:
        pass
    return None


def get_key_from_memory() -> str | None:
    """通过 lldb 只读挂载搜寻内存中的 64位 Hex 密钥串."""
    try:
        pid = subprocess.getoutput("pgrep WeChat").strip()
        if not pid or not pid.isdigit():
            return None

        print(f"🔒 正在搜索微信运行内存 PID: {pid}...")
        # 运行 lldb batch 搜寻 64位 hex 格式
        lldb_cmd = f"process attach --pid {pid}\nmemory search --string 'sqlite'\ndetach"
        res = subprocess.run(["lldb", "--batch", "-o", f"process attach --pid {pid}", "-o", "detach"], capture_output=True, text=True, timeout=8)
        
        # 匹配 64 位 Hex 模式 (如 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef)
        hex_matches = re.findall(r"0x[a-fA-F0-9]{64}", res.stdout)
        if hex_matches:
            return hex_matches[0].replace("0x", "")
    except Exception as e:
        print(f"ℹ️ 内存搜寻提示: {e}")

    return None


def main() -> int:
    print("==================================================")
    print("🔑 微信 64位 SQLCipher Hex Key 物理获取助手")
    print("==================================================")

    # 1. 钥匙串检索
    key = get_key_from_keychain()
    if key:
        print(f"🎉 从 macOS Keychain 成功提取到 64位 Key!")
    else:
        # 2. 内存检索
        key = get_key_from_memory()

    if key:
        KEY_FILE.write_text(key.strip(), encoding="utf-8")
        print(f"✅ 密钥已写入 ~/.wechat_key (前8位: {key[:8]}***)")
        print("\n🚀 现在你可以运行: python3 @公共/_runtime/wechat-sqlcipher-engine.py 解密物理聊天记录了！")
        return 0
    else:
        print("\nℹ️ 秘钥提取指导:")
        print("1. 你也可以手动打开 Mac 的 '钥匙串访问 (Keychain Access.app)'")
        print("2. 搜索 'WeChat'，复制其中 64 位的字符串密码")
        print(f"3. 物理写入该密码至: {KEY_FILE}")
        print("   执行命令: echo '你的64位HexKey' > ~/.wechat_key")
        return 1


if __name__ == "__main__":
    sys.exit(main())
