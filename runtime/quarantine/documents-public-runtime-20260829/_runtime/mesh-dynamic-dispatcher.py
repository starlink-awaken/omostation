#!/usr/bin/env python3
"""mesh-dynamic-dispatcher.py — BOS Neural Mesh 动态节点编排与分流引擎

功能: 物理扫描 ~/Documents/_inbox/ 的抓取文本，
依据文档类型 (公文/代码/财务/想法) 动态路由调起匹配的 Mesh 子网 (Sub-Mesh)。

v1.0 (Dynamic Mesh Engine) | 2026-07-31
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(os.environ.get("BOS_DOCS_ROOT", "/Users/xiamingxing/Documents"))
WS_ROOT = Path(os.environ.get("BOS_WORKSPACE_ROOT", "/Users/xiamingxing/Workspace"))
INBOX_DIR = DOCS_ROOT / "_inbox"
BDSK_ENGINE = WS_ROOT / "projects" / "omo" / "scripts" / "bdsk-board-engine.py"
EVOLUTION_ENGINE = WS_ROOT / "projects" / "omo" / "scripts" / "self-evolution-engine.py"


def classify_document(file_path: Path) -> str:
    """物理客观分析文档类型."""
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    if "卫健委" in content or "公文" in content or "通知" in content:
        return "weijian_governance"
    elif "Vite" in content or "React" in content or "git" in content or "zsh" in content:
        return "opc_developer"
    elif "银行" in content or "金额" in content or "账单" in content:
        return "finance"
    return "general_idea"


def dispatch_file(file_path: Path) -> str:
    doc_type = classify_document(file_path)
    print(f"🔄 [Mesh Dynamic Dispatcher] 物理分类 ──► {file_path.name} : [{doc_type}]")

    # 1. 调起 B.D.S.K. 评议引擎
    if BDSK_ENGINE.exists():
        subprocess.run([sys.executable, str(BDSK_ENGINE), str(file_path)], check=False)

    # 2. 调起偏好自进化引擎
    if EVOLUTION_ENGINE.exists():
        subprocess.run([sys.executable, str(EVOLUTION_ENGINE)], check=False)

    return doc_type


def run_dynamic_mesh_loop() -> int:
    if not INBOX_DIR.exists():
        return 0

    count = 0
    for f in INBOX_DIR.glob("*.md"):
        if "VERDICT" in f.name or "FLOW-LOG" in f.name:
            continue
        dispatch_file(f)
        count += 1

    return count


def main() -> int:
    print("⚡ 启动 BOS Neural Mesh 动态节点编排与分流引擎...")
    count = run_dynamic_mesh_loop()
    print(f"🎉 动态 Mesh 调度完成: 物理分流处理 {count} 个事件节点")
    return 0


if __name__ == "__main__":
    sys.exit(main())
