---
title: USER-GUIDE
type: doc
---

# KOS 用户指南

> 版本: v2.0 | 日期: 2026-07-08

---

## 快速开始

### 1. 安装

```bash
cd projects/kairon/packages/kos
pip install -e .
```

### 2. 初始化

```bash
# 设置环境变量
export KOS_HOME=/Users/xiamingxing/Workspace/data/kos

# 首次初始化
kos init

# 构建索引
kos index
```

### 3. 搜索

```bash
# 混合检索 (关键词 + 语义 + 图谱)
kos search "数据治理"

# 仅关键词
kos search "报告" --mode keyword

# 仅语义
kos search "平台架构" --mode semantic

# 限定域
kos search "通知" --domains gongwen

# JSON 输出
kos search "项目" --format json
```

### 4. 语义搜索 (需向量索引)

```bash
# 首次构建向量索引 (使用本地模型)
PYTHONPATH=src python3 kos_index_local.py

# 或使用 omlx 模型 (需 omlx 网关)
OMLX_URL=http://100.96.126.35:4000 OMLX_API_KEY=sk-omlx-admin \
  PYTHONPATH=src python3 -c "from kos.semantic import build_index; build_index()"

# 语义搜索
kos search "信息治理" --mode semantic
```

---

## 核心概念

### 知识域 (Zone)

KOS 将知识按域组织，每个域对应一个目录:

| 域 | 路径 | 说明 |
|----|------|------|
| `workspace` | `~/Workspace` | 项目代码 |
| `docs-cockpit` | `~/Documents/@驾驶舱` | 驾驶舱文档 |
| `docs-learning` | `~/Documents/@学习进化` | 学习笔记 |
| `docs-work` | `~/Documents/@工作文档` | 公文/卫健委/国转 |
| `docs-personal` | `~/Documents/@个人` | 个人事务 |
| `docs-family` | `~/Documents/@家庭生活` | 家庭管理 |
| `config-ai` | `~/.ai` | AI 配置 |
| `engine-minerva` | `~/minerva` | Minerva 引擎 |

### 检索模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `keyword` | FTS5 全文搜索 | 精确术语、错误码 |
| `semantic` | 向量相似度搜索 | 语义相关、长尾查询 |
| `graph` | 图谱实体遍历 | 关联发现 |
| `hybrid` | RRF 融合三路 | 通用场景 (推荐) |

### 上下文模式

| 模式 | chunks | tokens | 适用场景 |
|------|--------|--------|----------|
| `concise` | 3 | 1000 | 简单查询 |
| `balanced` | 7 | 2000 | 通用场景 |
| `detailed` | 15 | 4000 | 复杂分析 |

---

## 使用场景

### 场景 1: 公文搜索

```bash
# 搜索通知
kos search "关于数字化转型的通知" --domains gongwen

# 获取上下文 (用于 LLM)
kos context "卫健委考核要求" --mode detailed

# 生成 LLM prompt
kos context "汇报材料" --persona "公务员" --prompt
```

### 场景 2: 知识订阅

```bash
# 订阅主题
kos bridge gbrain export --limit 100

# 检查新匹配
# (需先获取 sub_id)
kos bridge gbrain status
```

### 场景 3: 深度研究

```bash
# 研究流水线 (KOS 检索 + Minerva 研究 + 事实核查)
kos-minerva research "AI Agent 架构演进" --level L2
```

### 场景 4: 多模态处理

```bash
# 处理图片 (OCR + 描述)
kos multimodal ./screenshot.png

# 处理音频 (转写)
kos multimodal ./meeting.mp3

# 批量处理目录
kos multimodal ./media/ --recursive
```

### 场景 5: 健康监控

```bash
# 完整健康报告
kos monitor full

# 仅索引健康
kos monitor health

# 本体统计
kos evolve stats
```

---

## 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `KOS_HOME` | `~/.kos` | 工作区根目录 |
| `KOS_WORKSPACE` | `~/Workspace` | 项目工作区 |
| `KOS_L4_ROOT` | `~/Documents` | L4 文档根目录 |
| `KOS_HOME_ROOT` | `~` | 用户主目录 |
| `OMLX_URL` | `http://localhost:8000` | omlx 网关地址 |
| `OMLX_API_KEY` | `123456` | omlx API Key |
| `OMLX_EMBED_MODEL` | `embed` | embedding 模型名 |

### manifest.json

配置文件位于 `KOS_HOME/manifest.json`，定义:
- 知识域 (zones)
- 谓词模式 (predicatePatterns)
- 定时任务 (cron)
- 制品路径 (artifacts)

```json
{
  "zones": {
    "workspace": {
      "path": "${KOS_WORKSPACE}",
      "filePatterns": ["*.py", "*.ts", "*.md"],
      "indexingStrategies": {"default": "full_text"}
    }
  },
  "cron": {
    "kos-daily-incremental-index": {
      "schedule": "0 2 * * *",
      "command": "kos index --incremental"
    }
  }
}
```

---

## 运维

### 定时任务

| 任务 | 频率 | 命令 |
|------|------|------|
| 增量索引 | 每日 2:00 | `kos index --incremental` |
| 健康检查 | 每周一 9:00 | `kos monitor full` |
| 本体演化 | 每周一 10:00 | `kos evolve evolve` |
| 全量重建 | 每月1日 3:00 | `kos-semantic build` |

### 故障排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 搜索无结果 | 未构建向量索引 | `PYTHONPATH=src python3 kos_index_local.py` |
| 语义搜索慢 | embedding 模型慢 | 使用本地模型 |
| 缓存不生效 | 缓存 TTL 过期 | `kos cache clear` |
| 索引不一致 | 手动修改了文件 | `kos index --incremental` |
| 健康告警 | 向量索引滞后 | 运行增量索引 |

### 性能调优

```bash
# 缓存统计
kos cache stats

# 缓存基准测试
kos cache benchmark

# 清理缓存
kos cache clear

# 向量索引状态
kos-semantic status
```

---

## 限制

1. **文件大小**: 单文件最大 500MB
2. **文档类型**: 主要支持 Markdown/TXT/JSON/PDF/DOCX
3. **向量维度**: 384d (本地) 或 4096d (omlx)
4. **MCP 确认**: L2 操作 (索引重建) 需显式确认
5. **CJK 分词**: 依赖 jieba 分词器

---

## 参考

- [架构文档](ARCHITECTURE.md)
- [API 参考](API.md)
- [运维手册](OPERATIONS.md)
- [ADR](decisions/)
