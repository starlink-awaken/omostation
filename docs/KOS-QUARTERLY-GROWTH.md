---
title: KOS 季度扩量目标（跃迁期前置）
status: active
type: goals-support
related:
  - G-CONV.6
  - BET-b8c5
  - .omo/goals/current.yaml
created: 2026-07-18
updated: 2026-07-20
---

# KOS 季度扩量目标

G-CONV.6 完成首批入库后，跃迁期「个人大脑」依赖 KOS 持续增长。  
SSOT 目标字段见 `.omo/goals/current.yaml` → `id: KOS-Q-GROWTH`。

| 季度 | 目标 documents | 口径 | 状态（以实测为准） |
|------|----------------|------|-------------------|
| 2026Q3 | ≥ 1,500 | workspace docs + decisions + 创意创作 vault 首批扩展 | ✅ 已过 |
| 2026Q4 | ≥ 3,000 | 叠加学习笔记 / **工作文档 + 驾驶舱** 精选 | ✅ 实测 ≥3000 |
| 2027Q1 | ≥ 5,000 | 跃迁期个人图谱预备（家庭/个人/残余 vault） | 进行中 |

## 操作

```bash
# 默认：workspace + 默认 vault 集合（含 @工作文档 / @驾驶舱）
python3 bin/gac/kos-seed-import.py --limit 2000

# Q4 扩量推荐：只拉「库中尚无」的路径（避免 limit 被旧文档占满）
python3 bin/gac/kos-seed-import.py --prefer-new --limit 800 \
  --roots-only \
  --root ~/Documents/@工作文档 \
  --root ~/Documents/@驾驶舱

# 创意创作 vault（legacy 单根）
python3 bin/gac/kos-seed-import.py --creative-root ~/Documents/@创意创作 --limit 2000

# 计数（运行时 DB，gitignored）
python3 -c "import sqlite3; print(sqlite3.connect('kos/kos-index.sqlite').execute('select count(*) from documents').fetchone()[0])"
```

### CLI 要点

| 参数 | 作用 |
|------|------|
| `--prefer-new` | limit 只计 DB 中尚不存在的路径（季度增长模式） |
| `--root PATH` | 可重复；追加扫描根 |
| `--roots-only` | 只扫 `--root`，不扫默认 workspace/vault 集合 |
| `--workspace-docs-only` | 只扫 workspace 默认文档面 |

## 门禁

- 不以「代码写完」算完成；以 `documents` 实测计数为准。  
- 季度目标写进 goals SSOT，不写死在本文件正文外的别处。  
- `kos/` 为运行时索引（gitignored）；PR 只交付 seed 工具与证据/目标字段。
