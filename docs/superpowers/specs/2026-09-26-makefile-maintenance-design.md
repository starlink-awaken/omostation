---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 根仓 Makefile 整理与兼容入口收敛
bet_id: BET-Y2Q4-T10-04
---

# 根仓 Makefile 整理与兼容入口收敛

## Problem

根仓 `Makefile` 已增长到约 1000 行，包含治理、测试、SSOT、运行时、观测和运维入口。现有目标可用，但公共执行约定、目标声明和帮助文本存在重复与漂移风险。部分目标使用不同的 Python/uv/cd 写法，`.PHONY` 与帮助大盘也不是单一事实源。

## Decision

采用不拆分 include 文件的内部整理方案：

- 保留全部既有目标名、别名和命令语义。
- 抽取根目录、Python、uv 和常用项目路径变量。
- 统一目标的目录执行、参数校验、错误退出和注释格式。
- 补齐标准聚合入口：`check`、`test`、`lint`、`ci-local`、`sync`、`status`。
- 让 `help` 由目标注释生成或至少与目标清单保持可验证一致。
- 不修改下游脚本、CI 工作流、子模块 Makefile 或治理规则语义。
- 不新增独立 `make/*.mk` include 文件，避免增加加载路径和调试表面积。

## Compatibility

旧入口必须继续解析并执行。兼容别名保留；标准入口只做聚合，不覆盖旧目标。失败时保持非零退出，不能用 `|| true` 隐藏既有 blocking 检查。

## Verification

验证分三层：

1. 静态：`make -n` 检查标准入口、旧入口和别名可解析。
2. 行为：运行 `make help` 及低副作用的 `status`、`lint`、相关只读目标。
3. 治理：运行 `make gac-local-gate` 与 `python3 bin/plan/bet-ledger.py lint`。

## Out of Scope

- 删除或重命名现有目标。
- 改写下游 Python、Shell、CI 或子模块实现。
- 引入新的 Makefile include 层。
- 重新设计治理命令本身。
