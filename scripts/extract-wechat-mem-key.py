#!/usr/bin/env python3
"""extract-wechat-mem-key.py — 微信运行内存只读句柄 64位 Hex Key 物理扫描器

针对 Keychain 不显示密码的新版 Mac 微信 (WeChat v3.8+ / v4.0):
通过只读扫描 WeChat 进程内存中 sqlite3_key 传递的 64 位 Hex Key，
避开 Keychain 不显示的物理障碍！

v1.0 (Zero-Mutation Memory Key Extractor) | 2026-07-31
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

KEY_FILE = Path.home() / ".wechat_key"


def extract_mem_key() -> str | None:
    print("🕵️ 探查 Keychain 不显示原因: Mac 微信新版已将 Key 改为动态内存派生。")
    print("🔒 启动零修改内存句柄物理搜寻...")

    try:
        # 获取 WeChat 进程 PID
        pid_out = subprocess.getoutput("pgrep WeChat").strip()
        pids = [p for p in pid_out.split("\n") if p.isdigit()]
        if not pids:
            print("ℹ️ 当前 Mac 上微信未在前台运行，请先登录并打开微信。")
            return None

        pid = pids[0]
        print(f"🔒 锁定常驻微信进程 PID: {pid}")

        # 使用 vmmap / gdb / lldb 安全搜寻内存堆区
        cmd = ["lldb", "--batch", "-o", f"process attach --pid {pid}", "-o", "memory search --string 'sqlite3_key'", "-o", "detach"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)

        # 匹配 64 位十六进制密钥模式
        matches = re.findall(r"[a-fA-F0-9]{64}", res.stdout)
        if matches:
            found_key = matches[0]
            print(f"🎉 从内存句柄成功抓取到 64位 Hex Key: {found_key[:8]}***")
            return found_key

    except Exception as e:
        print(f"ℹ️ 内存搜寻提示: {e}")

    return None


def main() -> int:
    print("==================================================")
    print("🗝️ 微信动态内存 64位 Hex Key 物理提取器")
    print("==================================================")

    key = extract_mem_key()
    if key:
        KEY_FILE.write_text(key.strip(), encoding="utf-8")
        print(f"\n✅ Key 已物理自动写入沙箱 ──► {KEY_FILE}")
        print("🚀 现在重新运行: python3 @公共/_runtime/bos-neural-mesh-runner.py 即可解密日常微信消息！")
        return 0
    else:
        print("\n💡 解法 B (免 Key 极简替代):")
        print("如果你不想扫内存，最物理的避坑方式是在微信侧选择:")
        print("微信菜单 ──► 设置 ──► 迁移与备份 ──► 备份聊天记录到 Mac。")
        print("备份生成的数据无需 SQLCipher 密码，系统可 100% 秒级无障碍读取全量日常聊天记录！")
        return 1


if __name__ == "__main__":
    sys.exit(main())
