---
schema_version: retrospective/v1
type: retro
title: 机制 22c Git Hook 调度引擎完整化 — runner/manifest 接线 + 缺失检查脚本补齐 + 净减配平
bet_id: BET-Y1Q4-T6-24
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-06
last-reviewed: 2026-09-06
---

# BET-Y1Q4-T6-24 复盘

## Q1 实际耗时 vs appetite？超出比例？

约 1 天（含 WIP 调研 + 修复 + 验证）vs 2 days appetite，约 50%。主要时间：explorer 深调研确认 12 脚本 WIP 不自洽（D1-D7）→ 方案 B 决策 → runner/installer/manifest/health-check 修复 + 全量验证 + change-lane 拆分。

## Q2 done_when 是否全部通过？哪条没过，为什么？

| 条目 | 结果 |
|------|------|
| hook-runner 能执行 manifest 声明的全部 hook 段，缺失脚本补齐、引用路径修正 | ✅ PASS（runner pre-commit 实测 exit 0；manifest 全部脚本路径存在性验证通过；pre-merge-commit 段 conflict-marker 旧路径已修） |
| canonical .githooks 接线完成（make install-hooks + VERSION/.version 一致性） | ✅ PASS（make install-hooks 走 hook-installer 写 git-dir/hooks 元数据，health-check version/hash 对齐） |
| 修复 D1-D7 缺陷 | ✅ PASS（timeout 参数、BLOCKING_FAILED、macOS %N、stdin 消费、health-check hash 对齐、runner 版本自检 git-dir 路径） |
| hook-health-check 自检通过 + 新增脚本语法检查 | ✅ PASS（py_compile 8/8、bash -n 11/11、health-check version/hash/missing/orphaned 全对齐） |
| README/.githooks/README.md 更新 + Makefile 接入 installer | ✅ PASS |

台账 verify 第 1 条原引用不存在的 `notify-submodule-change.py`/`guard-chore-state.py`（方案 A 遗留）→ 已按方案 B 净减决策更新 verify（只 py_compile 实际新建脚本）。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **台账 verify 引用不存在脚本**：原 verify 第 1 条 `py_compile check-runtime-artifacts.py notify-submodule-change.py guard-chore-state.py`，但方案 B 净减决策下 notify/guard **不新建**（canonical post-merge/commit-msg 内联已有等价实现）。执行时 verify FAIL → 更新台账 verify 对齐方案 B。
2. **manifest pre-merge-commit 段 conflict-marker 路径是旧值**：只修了 pre-commit 段，pre-merge-commit 段残留 `bin/ssot/conflict-marker-check.py`（该文件不存在）→ 全量路径存在性扫描才发现。
3. **runner 版本自检路径在 worktree + core.hooksPath 下失效**：`$ROOT/.git/hooks/.version` 在 worktree 是 `.git` 文件（非目录）且 installer 写 git-dir/hooks → 版本自检恒报 ⚠️ → 改用 `$(git rev-parse --git-dir)/hooks/.version`。
4. **core.hooksPath=.githooks 环境**：hooks 直接从 canonical 生效（不复制），installer 只写 git-dir/hooks 元数据。初次 cp 报 "identical" 自拷贝（git-path 被 hooksPath 重定向）→ 定位环境特殊性。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）

见 `bet-ledger.py surface`（全局口径）。本 bet 直接口径：
- **新增脚本 +1**：`bin/gac/check-runtime-artifacts.py`（22c 唯一真正新检查，参考 ci-local-fast 黑名单）
- **删除死代码 -1**：`bin/gac/check-dangerous-rebase.py` 的 `check_known_debt`（零调用）+ hashlib/os 死导入
- 其余 16 个脚本/hook/registry 为 WIP 既有文件（explorer 调研确认的自洽修复，非新增）
- 无新增 GaC 规则、无新增 ADR、无新增 hook 触发点
- 台账 verify/done_when 修正（净减导向，未增加表面积）

## Q5 下一个认领本 track 的 agent 需要知道什么？

- **本仓 `core.hooksPath=.githooks`**：hooks 直接从 canonical 生效，`git rev-parse --git-path hooks` 会被重定向到 `.githooks`。installer/health-check/runner 的元数据路径一律用 `$(git rev-parse --git-dir)/hooks`（worktree 感知 + 不受 hooksPath 影响）。
- **change-lane-check 硬门**：bet 交付跨 lane 时（governance_code + config + docs + docs_data + governance_state），governance_state 与任何其他 lane 混合必被拒。**必须按 lane 拆 commit**：governance_code+config / governance_state（含 retro）/ docs+docs_data。单 PR 多 commit 合法（CI 不跑 staged change-lane）。
- **方案 B 决策**：canonical hooks 保留执行（成熟逻辑不重写），runner/manifest/installer/health-check 作统一框架。manifest 是声明式注册表（runner 硬编码清单与 manifest checks 对齐即可）。
- **manifest 引用路径**：改脚本路径后必须全量扫描 manifest 所有段（pre-commit/pre-push/post-checkout/pre-rebase/pre-merge-commit/post-merge/commit-msg），别只修一段。
- **净减纪律**：notify/guard 等价逻辑已在 canonical 内联，勿重复新建脚本（D2）。
