---
type: ssot
last-reviewed: 2026-08-26
---

# Changelog

> 所有显著更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [0.5.0] - 2026-07-31

### 新增
- **Brain MVP**: 个人数字大脑 CLI + Web API（ask/context/remember/history 子命令，SQLite 存储，KOS 搜索集成）
- **Web API 路由**: `/api/brain/*` 端点（FastAPI router）

### 变更
- **Pyright 类型修复**: 49 → 0 个 Pyright 错误（workspace 子项目 import 通过 `# type: ignore[import-not-found]` 处理）
- **版本号**: 0.4.0 → 0.5.0

### 修复
- `api_sandbox.py`: 修复 `runtime.executor.sandbox` 导入的 Pyright 报错

---

## [0.4.0] - 2026-06-12

### 新增
- 初始化项目
- CLI 路由框架（click CLI + 多子命令）
- Web API 框架（FastAPI + 多路由模块）
- 适配器层（ecos/l4_kernel/omo/runtime）
- 健康检查、知识研究、脚本管理等核心命令
