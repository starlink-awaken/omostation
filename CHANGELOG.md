# Changelog

> 所有显著更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [未发布]

### Added
- **C2G v3 (Cybernetic Solutions)**:
  - 引入了 Fast-Track 碎片聚变机制 (`omo worker gc`)，支持自动打包微观任务为聚变报告。
  - 引入 Agent 战术退让机制 (`omo_yield_task`)，防止执行长尾死锁卡点。

### 新增
- 初始化项目

### 变更
- 无

### 修复
- **omo_debt_cli.main 接收 argv 参数**: 对齐其他子命令 (`omo_baseline_write` / `omo_cards` / `omo_gc`) 的 `main(argv: list[str] | None = None)` 签名。修复 `cli.py` 路由 `debt_main(args[1:])` 传参给 0 参数 main 导致的 `TypeError`，使 `omo debt list/close/register/reopen` 等子命令恢复可用。关联 `TASK-F7114ABA` God Module P110 拆分副产物。
- **cmd_debt_list 计数修正**: `resolved` 计数仅基于 `debt_weight_items`，`resolved_debt_items` 仅用于显示标记。避免 `resolved_debt_items` 含外部历史项时 `open_count = total - resolved` 出现负数 (P71 SSOT 口径不一致副作用)。

---

