---
title: KOS 季度扩量目标（跃迁期前置）
status: active
type: goals-support
related:
  - G-CONV.6
  - BET-b8c5
  - .omo/goals/current.yaml
created: 2026-07-18
---

# KOS 季度扩量目标

G-CONV.6 完成首批入库后，跃迁期「个人大脑」依赖 KOS 持续增长。  
SSOT 目标字段见 `.omo/goals/current.yaml` → `id: KOS-Q-GROWTH`。

| 季度 | 目标 documents | 口径 |
|------|----------------|------|
| 2026Q3 | ≥ 1,500 | workspace docs + decisions + 创意创作 vault 首批扩展 |
| 2026Q4 | ≥ 3,000 | 叠加学习笔记 / 工作文档精选 |
| 2027Q1 | ≥ 5,000 | 跃迁期 M1 后个人图谱预备 |

## 操作

```bash
# 扩量（可重复 UPSERT）
python3 bin/gac/kos-seed-import.py --limit 2000
python3 bin/gac/kos-seed-import.py --creative-root ~/Documents/@创意创作 --limit 2000

# 计数
python3 -c "import sqlite3; print(sqlite3.connect('kos/kos-index.sqlite').execute('select count(*) from documents').fetchone()[0])"
```

## 门禁

- 不以「代码写完」算完成；以 `documents` 实测计数为准。  
- 季度目标写进 goals SSOT，不写死在本文件正文外的别处。
