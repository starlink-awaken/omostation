# 根仓 Makefile 整理与兼容入口收敛 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在保留全部旧目标语义的前提下，整理根仓 Makefile 的公共变量、目标声明、帮助输出和标准聚合入口。

**Architecture:** 继续使用单一根 `Makefile`，不拆分 include 文件。公共路径和工具命令集中在变量区；旧入口保持原名，标准入口通过依赖聚合既有目标；帮助输出由目标注释生成并通过静态检查验证。

**Tech Stack:** GNU Make、POSIX shell、uv、Python 3、现有仓库治理脚本。

## Global Constraints

- 保留所有现有目标名、别名和命令语义。
- 不修改下游脚本、CI 工作流和子模块 Makefile。
- 不新增独立 Makefile include 文件。
- blocking 检查不得用 `|| true` 隐藏失败。
- 所有写入限定于 `Makefile`、本计划、设计文档、BET 台账和 retro。

---

### Task 1: 建立公共变量与安全执行约定

**Files:**
- Modify: `Makefile:24-25` 及现有重复工具调用

**Steps:**
- 保留现有 `PY`、`PY_STDLIB` 变量。
- 增加 `ROOT := $(CURDIR)`、`PYTHON ?= python3`、`UV ?= uv` 和常用项目目录变量。
- 仅替换等价的 `python3`、`uv run`、`cd projects/... &&` 表达式；不改参数和退出行为。
- 运行 `make -n omlxc-test omlxc-lint kairon-test`，确认展开命令仍指向原路径。

### Task 2: 补齐标准聚合入口

**Files:**
- Modify: `Makefile` `.PHONY`、help、质量门禁和测试区

**Steps:**
- 增加 `check: gate-local`。
- 增加 `test: test-all`。
- 增加 `lint: lint-all`。
- 增加 `ci-local: gate-local lint test`，保持依赖失败传播。
- 增加 `sync: sync-all-docs`。
- 增加 `status: ssot-status`。
- 将六个入口加入 `.PHONY` 和帮助输出。
- 运行 `make -n check test lint ci-local sync status`，确认所有目标可解析。

### Task 3: 统一帮助输出与兼容目标审计

**Files:**
- Modify: `Makefile` help 区域和 `.PHONY`

**Steps:**
- 保留现有帮助分类和旧入口文字。
- 为所有新增标准入口增加 `##` 注释。
- 使用 `make -qp` 提取目标集合，与 `.PHONY` 和帮助中新增入口逐项比对。
- 验证旧兼容入口：`fabric-inspect`、`fabric-bench`、`test-omlxc`、`test-kairon`。
- 运行 `make help` 并确认退出码为 0。

### Task 4: 全面验证并记录结果

**Files:**
- Modify: `.omo/_knowledge/retros/BET-Y2Q4-T10-04.md`

**Steps:**
- 运行 `make -n help check test lint ci-local sync status`。
- 运行 `make help`。
- 运行 `python3 bin/plan/bet-ledger.py lint`，记录既有错误与本 BET 新增内容没有引入的新错误。
- 运行 `make gac-local-gate`；若环境依赖导致失败，记录精确命令、退出码和失败面。
- 记录表面积净变化和兼容性结果。
