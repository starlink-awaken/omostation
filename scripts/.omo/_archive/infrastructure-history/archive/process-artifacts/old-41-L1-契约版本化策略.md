---
id: 41
title: "L1: 契约版本化策略（早期简版）"
type: ARCHITECTURE_PATTERN
phase: Phase6
layer: L1
status: superseded
superseded_by: pat-41
version: v1.0.0
tags: [phase6, L1, eidos, constitution]
date: 2026-05-27
---

# L1: 契约版本化策略

> ⚠️ 本文档已由 [phase6-完成化/pat-41-L1契约版本化策略.md](./phase6-完成化/pat-41-L1契约版本化策略.md) 替代。保留作历史参考。
>
> 日期: 2026-05-27

## 1. 背景

Eidos 有 8 个 Schema，registry.json 中已有 version 字段：

| Schema | 当前版本 | 状态 |
|--------|---------|------|
| identity-role | v1.0.0 | active |
| value-principle | v1.0.0 | active |
| consensus | v1.0.0 | active |
| task-object | v1.0.0 | active |
| epoch-life | v1.0.0 | active |
| identity-envelope | v1.0.0 | active |
| capability-grant | v1.0.0 | active |
| node-type | v1.0.0 | active |

## 2. SemVer 策略

格式: MAJOR.MINOR.PATCH

| 变更类型 | 触发条件 |
|---------|---------|
| MAJOR | 字段删除/重命名/类型变更 (breaking change) |
| MINOR | 新增可选字段/新枚举值/新Schema (backward compatible) |
| PATCH | 描述更新/文档修复/示例修正 |

## 3. change_type 分类

| 分类 | 说明 | 对应MAJOR版本 |
|------|------|--------------|
| backward_compatible | 仅新增不删不改 | MINOR |
| breaking | 字段名/类型/必选变更 | MAJOR |

## 4. 过期规则

| 落后版本数 | 状态 | 动作 |
|-----------|------|------|
| 0 | active | 正常使用 |
| 1 MAJOR | deprecated | deprecation_warning 日志 |
| 2 MAJOR | sunset | 阻断验证, 强制升级 |
| 3+ MAJOR | removed | 从 registry 删除 |

## 5. 跨项目策略

所有下游项目必须声明依赖的Schema版本:
- `kronos/eidos-deps.json` — 声明 ≥1.0.0 <2.0.0
- kos/iris 后续补充

## 6. 版本迁移流程

MAJOR变更: prod 并行运行 2 个版本, 旧版 deprecation 标注
MINOR变更: 直接升级, backward compatible
PATCH变更: 直接升级
