---
title: OPERATIONS
type: doc
---

# KOS 运维手册

> 版本: v2.0 | 日期: 2026-07-08

---

## 部署

### 系统要求

| 资源 | 最低 | 推荐 |
|------|------|------|
| 磁盘 | 1GB | 5GB (含向量索引) |
| 内存 | 512MB | 2GB |
| Python | 3.10+ | 3.12+ |
| 依赖 | sqlite3, lancedb | + sentence-transformers |

### 安装

```bash
# 1. 克隆
cd projects/kairon/packages/kos

# 2. 安装依赖
pip install -e .
pip install lancedb sentence-transformers

# 3. 设置环境变量
export KOS_HOME=~/.kos
export KOS_WORKSPACE=~/Workspace

# 4. 首次构建索引
kos index

# 5. 构建向量索引
PYTHONPATH=src python3 kos_index_local.py
```

### 验证

```bash
# 搜索测试
kos search "测试"

# 健康检查
kos monitor health

# 向量索引状态
kos-semantic status
```

---

## 日常运维

### 索引维护

#### 增量索引 (推荐每日)

```bash
kos index --incremental
```

输出示例:
```json
{
  "scanned": 31944,
  "added": 5,
  "updated": 12,
  "unchanged": 31927,
  "removed": 0,
  "elapsed_seconds": 12.3
}
```

#### 全量重建 (每月或异常时)

```bash
# FTS5 全量重建
kos index

# 向量索引全量重建
PYTHONPATH=src python3 kos_index_local.py
```

#### 实时监控模式

```bash
kos index --watch  # 持续监控文件变更
```

### 缓存管理

```bash
# 查看缓存状态
kos cache stats

# 清理过期缓存
kos cache clear

# 性能基准测试
kos cache benchmark
```

### 本体维护

```bash
# 本体统计
kos evolve stats

# 运行演化 (去重 + 关系推导)
kos evolve evolve

# 获取改进建议
kos evolve recommend
```

---

## 监控

### 健康检查

```bash
kos monitor health
```

检查项:
- 索引完整性 (FTS vs 文档数一致性)
- 向量索引对齐
- 实体-文档关联

### 质量监控

```bash
kos monitor quality
```

检查项:
- 中文查询命中率
- 搜索延迟
- 实体搜索可用性

### 性能监控

```bash
kos monitor performance
```

指标:
- 数据库大小
- 文档数量
- 域分布
- 文档年龄分布

### 告警

```bash
# 查看告警
kos monitor alerts

# 告警 + 通知推送
kos monitor alerts --notify
```

告警阈值:

| 检查项 | 阈值 | 级别 |
|--------|------|------|
| 索引完整性 | diff > 0 | CRITICAL |
| 向量滞后 | >100 chunks | WARNING |
| 搜索延迟 P99 | >500ms | WARNING |
| 缓存命中率 | <50% | INFO |
| 孤立实体 | >50 | INFO |
| 数据库大小 | >10GB | WARNING |

---

## 故障排查

### 搜索问题

#### 问题: 搜索无结果

**可能原因**:
1. 文档未索引
2. 向量索引未构建
3. 域过滤错误

**排查步骤**:
```bash
# 1. 检查索引状态
kos monitor health

# 2. 检查向量索引
kos-semantic status

# 3. 尝试不同模式
kos search "查询" --mode keyword
kos search "查询" --mode semantic

# 4. 不限制域
kos search "查询" --domains ""
```

#### 问题: 语义搜索慢

**可能原因**:
1. 使用 omlx 远程模型
2. 向量索引过大

**解决方案**:
```bash
# 切换到本地模型重建索引
PYTHONPATH=src python3 kos_index_local.py

# 或使用 omlx (首次加载慢)
OMLX_URL=http://100.96.126.35:4000 kos search "查询" --mode semantic
```

### 索引问题

#### 问题: 索引不一致

**症状**: `kos monitor health` 显示 FTS ≠ 文档数

**解决方案**:
```bash
# 全量重建 FTS5
kos index

# 或增量更新
kos index --incremental
```

#### 问题: 向量索引滞后

**症状**: 新文档搜索不到 (语义模式)

**解决方案**:
```bash
# 增量向量索引
PYTHONPATH=src python3 kos_index_local.py --batch 500

# 或重建
PYTHONPATH=src python3 -c "from kos.semantic import build_index; build_index()"
```

### 缓存问题

#### 问题: 缓存不更新

**解决方案**:
```bash
# 清理缓存
kos cache clear

# 使用 --no-cache 跳过缓存
kos search "查询" --no-cache
```

### 内存/磁盘问题

#### 问题: 数据库过大

**排查**:
```bash
# 查看数据库大小
ls -lh ~/.kos/kos-index.sqlite

# 查看向量索引大小
ls -lh ~/.kos/vectors/
```

**解决方案**:
```bash
# 清理旧缓存
kos cache clear

# 清理调试日志
rm -rf ~/.kos/debug-logs/
```

---

## 备份与恢复

### 备份

```bash
# 备份索引数据库
cp ~/.kos/kos-index.sqlite ~/.kos/backups/kos-index-$(date +%Y%m%d).sqlite

# 备份向量索引
cp -r ~/.kos/vectors ~/.kos/backups/vectors-$(date +%Y%m%d)

# 备份配置
cp ~/.kos/manifest.json ~/.kos/backups/manifest-$(date +%Y%m%d).json
```

### 恢复

```bash
# 恢复索引数据库
cp ~/.kos/backups/kos-index-YYYYMMDD.sqlite ~/.kos/kos-index.sqlite

# 恢复向量索引
cp -r ~/.kos/backups/vectors-YYYYMMDD ~/.kos/vectors

# 恢复后验证
kos monitor health
```

---

## 安全

### 只读保护

SQLite 连接默认强制只读 (`mode=ro`)，防止意外写入。

### 写操作拦截

正则拦截危险 SQL:
- INSERT, UPDATE, DELETE
- DROP, ALTER, CREATE
- REPLACE, VACUUM

### MCP 操作确认

L2 级别操作 (索引重建、全量同步) 需显式 `confirmed=true`。

---

## 性能调优

### 搜索优化

| 场景 | 优化 |
|------|------|
| 热查询 | 缓存命中 <1ms |
| 精确术语 | 使用 `--mode keyword` |
| 中文查询 | 确保 jieba 分词正常 |
| 域过滤 | 指定 `--domains` 减少扫描 |

### 索引优化

| 场景 | 优化 |
|------|------|
| 增量更新 | 使用 mtime 快速跳过 |
| 向量构建 | 本地模型快于 omlx |
| 大规模构建 | 分批处理 (batch=500) |

### 缓存优化

| 场景 | 优化 |
|------|------|
| 热查询 | L1 内存缓存 |
| 持久缓存 | L2 SQLite |
| 缓存失效 | TTL 自动过期 |

---

## 附录

### 定时任务配置

```json
{
  "cron": {
    "kos-daily-incremental-index": {
      "schedule": "0 2 * * *",
      "command": "kos index --incremental"
    },
    "kos-weekly-health-check": {
      "schedule": "0 9 * * 1",
      "command": "kos monitor full"
    },
    "kos-monthly-full-rebuild": {
      "schedule": "0 3 1 * *",
      "command": "kos-semantic build"
    }
  }
}
```

### 环境变量速查

```bash
export KOS_HOME=~/.kos
export KOS_WORKSPACE=~/Workspace
export OMLX_URL=http://100.96.126.35:4000
export OMLX_API_KEY=sk-omlx-admin
export OMLX_EMBED_MODEL=embed
```

### 磁盘使用参考

| 组件 | 大小 (32K docs) |
|------|----------------|
| SQLite 索引 | ~200MB |
| 向量索引 (384d) | ~150MB |
| 向量索引 (4096d) | ~500MB |
| 缓存 | ~10MB |
| **总计** | ~400MB-700MB |
