---
status: active
lifecycle: ssot
owner: governance-team
last-reviewed: 2026-06-28
related: F7114ABA (gbrain SRP), TASK-F7114ABA (cockpit god-module)
---

# cockpit research.py SRP wave 2 拆分计划

**审计日期**: 2026-06-28
**触发**: debt-realness-audit P0 #16 (TASK-F7114ABA GodModule) + check-god-module 1351L (>1200L error 阈值)
**目标**: 1351L → <800L (4 子模块拆分)

## 现状 (已实地验证)

- **文件**: `projects/cockpit/src/cockpit/commands/research.py` (1351L)
- **结构**: 31 个 `cmd_research_*` 命令处理器 (经典 God Module) + 5 局部 helpers
- **依赖**: cli.py 显式 `from .commands.research import (31 names)` — 拆分需 re-export 保持兼容
- **import 基础**: 已有 `.base` 共享 helpers (`_get_data_access`/`_fmt_time`/`_short`/`_topic_text`/`_panel`/`_run_ollama` 等 18 个)

## 关键架构优势 (不同于 omo F7114ABA gates)

omo governance surfaces 拆分遇 **child→parent circular** (parent re-export child 在文件头, helper 定义在后 → child 无法反向 import parent helper). 治本需提取 helper 到 leaf sibling gates.py.

**research.py 无此问题**: 局部 helpers (`_human_summary` L227 / `_get_all_active_ids` L612) 在文件**中段定义**, re-export 可放**文件末尾** → 子模块 `from .research import _human_summary` 时 research 已执行到末尾 (helpers 已绑定). **无 circular, 无需 gates 式 helper 提取**.

## 4 域拆分方案

| 子模块 | 函数 | 行范围 | 职责 |
|:-------|:-----|:-------|:-----|
| `research_query.py` | search/list/open/compare/merge/digest | 191-849 | 查询/展示/聚合 |
| `research_meta.py` | timeline/tag/rename/archive/unarchive/dossier/agent/follow_up | 529-684, 991-1239 | 元数据管理 |
| `research_governance.py` | audit/quarantine/restore/export | 850-990 | 治理状态 |
| `research_health.py` | health/heatmap/backup/backup_restore/batch | 1027-1351 | 健康/维护 |
| `research.py` (瘦化) | cmd_research 主入口 + 5 helpers + re-export 全部 | <800L | 入口 + 分发 |

## 执行步骤 (续会, 4 波)

每波: 提取 1 子模块 + research.py 删函数 + 末尾 re-export + `uv run pytest tests/test_cli_research*.py` 验证.

1. **wave 2A**: research_query.py (search/list/open/compare/merge/digest, ~650L)
2. **wave 2B**: research_meta.py (timeline/tag/rename/archive/unarchive/dossier/agent/follow_up)
3. **wave 2C**: research_governance.py (audit/quarantine/restore/export)
4. **wave 2D**: research_health.py (health/heatmap/backup/backup_restore/batch)

## re-export 范式 (research.py 末尾)

```python
# research.py 末尾 (helpers 已定义在前, 子模块反向 import 安全)
from .research_query import (
    cmd_research_search, cmd_research_list, cmd_research_open,
    cmd_research_compare, cmd_research_merge, cmd_research_digest,
)
from .research_meta import (...)
from .research_governance import (...)
from .research_health import (...)

__all__ = ["cmd_research", ...]  # cli.py 兼容
```

## 验证基线

- `wc -l research.py` < 800L (check-god-module warn 阈值)
- `uv run pytest tests/test_cli_research*.py` 全 pass
- `cockpit research --help` 子命令全可用 (cli.py import 不破)

## 续会触发

本会话 context 已极深 (push 闭环 7 仓 + debt P0 治本 6/9 + F7114ABA gates + kairon format 148 + omo 补 add 19). research.py 完整拆分 (4 波) 需独立续会执行. 本文档为 roadmap, 方案已验证 (circular 治本路径明确), 续会可直接执行 wave 2A.
