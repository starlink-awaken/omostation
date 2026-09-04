---
title: README
type: doc
---

# Kronos — 知识摄取管线

> 从外部世界收割内容，注入知识系统。

## 定位

Kronos 是 Workspace 知识工程生态链的**输入端**。当用户甩链接、文章、PDF、推文等任何外部内容过来时，Kronos 负责：

1. **摄取** — 抓取内容、解析、去重
2. **处理** — 摘要、结构化、打标签、实体抽取
3. **分发** — 路由到各下游系统存档

## 在生态中的位置

```
外部内容 (链接/文章/PDF/推文)
    ↓
KRONOS (摄取管线)          ← 本项目
    ↓
┌─────────────────────────────────┐
│   vault (Obsidian ontology)     │  ← 知识化存档
│   WPS Note (标签路由笔记)        │  ← 随手可查
│   KOS (跨域索引)                │  ← 可搜索
│   ontoderive (事实推导)          │  ← 深度加工
│   minerva (深度研究)             │  ← 扩展调研
└─────────────────────────────────┘
```

## 快速开始

```bash
# 查看管线定义
cat pipelines/*.md

# 手动触发一次内容处理
cd kronos && cat CLAUDE.md
# → 在对话中直接甩链接即可，Kronos SOP 会被自动加载
```

## 项目结构

```
kronos/
├── CLAUDE.md                 ← AI 入口（处理链接的 SOP）
├── README.md                 ← 本文件
├── pipelines/
│   ├── link-pipeline.md      ← 单链接处理
│   ├── batch-pipeline.md     ← 批量处理
│   └── deep-read.md          ← 深度阅读
├── integrations/
│   ├── vault.md              ← Obsidian vault 集成
│   ├── wps-note.md           ← WPS Note 集成
│   ├── kos.md                ← KOS 集成
│   └── workspace.md          ← Workspace 工具集成
├── schemas/
│   └── pipeline-schemas.json ← 输入/输出数据格式
└── .claude/
    └── settings.local.json
```

## 命名来源

Kronos（克洛诺斯）——希腊神话中的时间之神，也是"收割"的概念原型。
收割外部信息，转化为可用的知识。
