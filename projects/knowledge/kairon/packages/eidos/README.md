---
title: README
type: doc
---

# Eidos — Schema Definition & Validation Layer

元模型驱动的本体建模工具集。

## Quick Start

```bash
# 查看元模型
eidos meta

# 定义 Schema
eidos define MySchema

# 校验数据
eidos validate data.json --type KnowledgeCard

# 可视化
eidos viz web

# 一键管线
eidos pipeline --name knowledge-base
```

## Commands

| Command | Description |
|---------|-------------|
| `eidos list` | List registered schemas |
| `eidos validate` | Validate JSON against schema |
| `eidos meta` | Show 8×4 meta-model |
| `eidos define` | Define schema interactively |
| `eidos viz` | Visualize (schema/graph/state/web) |
| `eidos pipeline` | Run ontology pipeline |

## Integration

- **KOS**: `kos ingest --schema KnowledgeCard`
- **OntoDerive**: `ontoderive derive --eidos`
- **Minerva**: `minerva research --eidos-output`
- **Agora**: Via `agora start-pipeline`

## Architecture

```text
Eidos (t) → KOS (Storage) → OntoDerive (Reasoning)
         ↘ Minerva (Extraction)
         → Agora (Routing)
```
