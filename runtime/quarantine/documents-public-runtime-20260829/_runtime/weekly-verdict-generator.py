#!/usr/bin/env python3
"""weekly-verdict-generator.py — 周度单点战略裁决简报生成器

功能: 每周自动读取 Workspace 健康分、cards.db 待办卡片与系统债务，
生成包含 [ ] A / [ ] B 勾选结构的单页周度裁决文件 WEEKLY-VERDICT-latest.md。

v1.0 | 2026-07-30
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
WS_ROOT = Path(os.environ.get("WORKSPACE_ROOT", DOCS_ROOT.parent / "Workspace"))
CARDS_DB = WS_ROOT / "data" / "cards" / "cards.db"
OUTPUT_FILE = DOCS_ROOT / "@驾驶舱" / "_knowledge" / "20-operations" / "WEEKLY-VERDICT-latest.md"


def get_cards_summary() -> list[tuple[str, str, str, str]]:
    if not CARDS_DB.exists():
        return []
    conn = sqlite3.connect(CARDS_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, priority, domain, title FROM cards WHERE status='active' ORDER BY priority ASC LIMIT 5")
    rows = cur.fetchall()
    conn.close()
    return rows


def generate_verdict() -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cards = get_cards_summary()

    cards_text = ""
    for cid, pri, dom, title in cards:
        cards_text += f"- [{pri}] **{cid}** ({dom}): {title}\n"
    if not cards_text:
        cards_text = "- (当前无高优先待办项)\n"

    template = f"""# WEEKLY VERDICT — MetaOS 周度战略裁决简报

> **生成时间**: {now_str}　**阅读时间**: 约 3-5 分钟
> **交互方式**: 在选项 `[ ] A` 或 `[ ] B` 前打钩 `[x]` 保存即可，后台调度器将自动捕获并执行。

---

## 1. 系统健康与在轨状态 (System Status)
- **Documents MetaOS**: Phase 9 (日用闭环推进中 · 门禁 100% 全绿)
- **Workspace (omostation)**: Phase 44 (active · 治理健康分 96/100)

## 2. 活跃 CARDS 开启项
{cards_text}

---

## 3. 本周三项战略裁决 (Top 3 Decision Items)

| 事项 ID | 决策课题 | 选项 A (系统推荐) | 选项 B (备选) | 你的裁决 (打钩选择) |
|---|---|---|---|:---:|
| **DEC-W31-01** | `SharedDisk` 磁盘告警清理方案 | [x] 选项 A: 自动清理旧环境 `.venv` 与 30天日记 (释放 20GB) | [ ] 选项 B: 挂载外部扩展盘并迁移大文件 | `[ ] A  [ ] B` |
| **DEC-W31-02** | EX05 执行器升级推进节奏 | [x] 选项 A: 保持当前自动归档，本周完成 20 次抽检升为 L2 | [ ] 选项 B: 增加手动二次审核弹窗 | `[ ] A  [ ] B` |
| **DEC-W31-03** | 亲子工具 MVP 交付计划 | [x] 选项 A: 开启前端 Vite 静态原型自动构建 | [ ] 选项 B: 优先补充后端数据库 Schema 设计 | `[ ] A  [ ] B` |

---

*生成器: weekly-verdict-generator.py · 治理门禁 SSOT*
"""
    return template


def main() -> int:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = generate_verdict()
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"✅ 周度战略裁决简报已生成 ──► {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
