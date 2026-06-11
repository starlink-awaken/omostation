# AGENTS.md — Spaces

> eCOS v5 空间配置 · 租户空间 + 系统空间权限策略定义

## Overview

纯 YAML 配置仓，不包含可执行代码。定义了系统多维空间之间的准入、能力、路由规则。

### 目录结构

```
spaces/
├── _schema/               ── 空间数据结构定义
├── runtime-space*.yaml    ── 运行时空间策略
├── system-space*.yaml     ── 系统空间策略
└── registry.yaml          ── 空间注册表
```

### 文件一览

| 文件 | 职责 |
|:-----|:------|
| `registry.yaml` | 空间注册与发现 |
| `runtime-space.yaml` | 运行时空间基线配置 |
| `system-space.yaml` | 系统空间基线配置 |
| `runtime-space-admission-matrix.yaml` | 运行时准入矩阵 |
| `system-space-admission-matrix.yaml` | 系统空间准入矩阵 |

## Dependencies

无代码依赖。纯 YAML 配置，由 agora 和 runtime 消费。

## CI

无测试环境。修改后需通过 `bash tests/integration/run-all.sh` 或手工验证。
