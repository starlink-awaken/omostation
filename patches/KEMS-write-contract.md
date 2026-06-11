---
title: 01-Write Contract
description: KEMS v7 写入契约——控制面/事实面/知识面/资料面的写入规范与约束
status: draft
type: protocol
domain: meta
created: 2026-06-11
tags: [KEMS, 契约, 写入规范]
---

# 写入契约 (Write Contract)

> 目标域: `~/Documents/@学习进化/_knowledge/10-systems/KEMS/.kems/_protocol/01-write-contract.md`
> KEMS v7 四份平面间协作契约的第一份。

---

## 契约一：控制面 → 事实面

写入 `_entities/` 的文件必须：

1. 包含 YAML frontmatter：`title/status/type/owner/created`
2. facts.md 中的每条事实必须可溯源（附来源文件路径）
3. 不复制事实到知识面——使用指针 `[[entity-id]]`
4. 更新事实面后必须追加一条 `real: true` 信号

## 契约二：事实面 → 知识面

写入 `_knowledge/` 的文件必须：

1. 概念类文件使用概念模板（frontmatter + 问题 + 核心概念 + 关联）
2. 引用事实面实体时使用 `[[entity-id]]` 而非复制内容
3. 经验教训使用三问法（事实 + 新认知 + 下次怎么做）
4. 方法论文档需更新 `QUICK-REFERENCE.md`

## 契约三：资料面 → 控制面

写入 `_storage/` 的文件必须：

1. 知识订阅内容带标签分类和来源日期
2. 资料库文件更新 `INDEX.md`
3. 删除操作不能直接 rm——先移入 `_archive/`
4. 重大资料变更（新增/删除）需追加信号

## 契约四：跨域写入

从其他域写入本域的文件必须：

1. 包含 `source_domain` 字段标记来源
2. 不创建同事实的第二个版本——先搜索再看是否新建
3. 跨域写入后通知 @驾驶舱（跨域信号）
