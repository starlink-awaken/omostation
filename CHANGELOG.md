# Changelog

> 所有显著更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [未发布]

### Added
- **omo CLI 统一入口迁移 (Tier 1-4)**:
  - `omo health dashboard`: Keeper Dashboard (从 bin/omo-health.py 迁移)
  - `omo lint projection-guard`: P74 runtime projection guard (从 bin/omo-state-projection-guard.py 迁移)
  - `omo lint stamp-policy`: P74 runtime stamp policy (从 bin/omo-runtime-stamp-policy.py 迁移)
  - `omo manage`: .omo 目录管理工具集 (从 bin/omo-manage 迁移)
  - `omo validate`: .omo 目录验证工具集 (从 bin/omo-validate 迁移)
  - `omo audit cards`: CARDS X3 value metrics (从 scripts/omo/cards_x3_metrics.py 迁移)
  - `omo audit vault`: Vault X1 audit (从 scripts/omo/vault_x1_audit.py 迁移)
  - `omo audit freshness`: X2 freshness audit (从 scripts/omo/x2_freshness_audit.py 迁移)
- **omo CLI 统一入口 (方向 A)**:
  - `omo doctor`: 统一健康检查入口 (state freshness + key files + agora health + debt evidence)
  - `omo inspect`: 统一检查入口 (completeness + references + schemas + god-module)
- **omo CLI 文档自动生成 (方向 C)**:
  - `omo docs`: 从 docstring 提取帮助文本生成 Markdown 参考文档
  - `docs/CLI-REFERENCE.md`: 自动生成的 CLI 参考文档
- **omo CLI 扩展 (方向 G)**:
  - `omo report`: 综合报告生成 (doctor + inspect + audit freshness)
  - `omo watch`: 实时监控模式 (定期运行 doctor，检测状态变化)
- **测试覆盖**:
  - `tests/test_omo_audit_cli.py`: 16 个单元测试覆盖 omo audit 子命令
- **C2G v3 (Cybernetic Solutions)**:
  - 引入了 Fast-Track 碎片聚变机制 (`omo worker gc`)，支持自动打包微观任务为聚变报告。
  - 引入 Agent 战术退让机制 (`omo_yield_task`)，防止执行长尾死锁卡点。

### Changed
- **scripts/omo/ 退役 (方向 B)**:
  - 为 8 个脚本添加 deprecation 注释，指向 omo CLI 替代命令
  - 保留所有脚本作为 backward-compat wrapper
- **文档同步**:
  - 更新 mof-capabilities.yaml: 添加 omo audit 命令引用
  - 更新 x3-value-stack.yaml: 更新审计工具引用
  - 更新 AGENT.md: 更新所有 scripts/ 引用为 omo CLI 格式
  - 更新 mutation-surfaces.yaml: 更新 entrypoint 为 omo CLI 格式

### 新增
- 初始化项目

### 变更
- 无

### 修复
- **omo_debt_cli.main 接收 argv 参数**: 对齐其他子命令 (`omo_baseline_write` / `omo_cards` / `omo_gc`) 的 `main(argv: list[str] | None = None)` 签名。修复 `cli.py` 路由 `debt_main(args[1:])` 传参给 0 参数 main 导致的 `TypeError`，使 `omo debt list/close/register/reopen` 等子命令恢复可用。关联 `TASK-F7114ABA` God Module P110 拆分副产物。
- **cmd_debt_list 计数修正**: `resolved` 计数仅基于 `debt_weight_items`，`resolved_debt_items` 仅用于显示标记。避免 `resolved_debt_items` 含外部历史项时 `open_count = total - resolved` 出现负数 (P71 SSOT 口径不一致副作用)。

---

