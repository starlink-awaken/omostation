---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
bet_id: BET-Y1Q4-T6-24
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
last_updated: 2026-09-06
---

# 机制 22c Git Hook 调度引擎完整化 — Design

> 日期：2026-09-06
> 状态：accepted
> Bet：BET-Y1Q4-T6-24（T6-SUBTRACT，2 days）

## 背景（Context）

工作树中存在一批机制 22c（2026-09-05）的 git hook 加固 WIP：`hook-runner.sh`（调度引擎）、`hook-manifest.yaml`（声明式检查清单）、`hook-installer.sh`（安装）、`hook-health-check.py`（健康检查）及 12 个检查脚本。调研确认该 WIP 处于**未完成、未接线、含缺陷**状态：

- 5 个被引用脚本缺失（`check-runtime-artifacts.py`、`conflict-marker-check.py`、`notify-submodule-change.py`、`guard-chore-state.py`、`gac-hygiene-check.py` 路径错误）
- `hook-runner.sh` 不解析 manifest、四段 hook（pre-rebase/pre-merge-commit/post-merge/commit-msg）无法执行
- 缺陷 D1-D7（blocking/timeout 参数错位、BLOCKING_FAILED 退出、macOS `%N`、stdin 消费、health-check hash 算法不一致等）

## 接线决策（2026-09-06 用户拍板）

**方案 B（低风险）**：canonical `.githooks/pre-commit` + `pre-push` 是生产关键路径（含大量成熟逻辑：clone-guard require-clone、submodule-guard known-debt 指纹、gitlink ancestry 豁免、remote-hygiene、ci-local 预检）。**保留 canonical 为实际执行者**；`hook-runner` / `hook-manifest` / `hook-installer` 作为**统一安装 + 健康检查框架**：

- `hook-installer.sh`：统一安装全部 canonical hooks（含新 hook）到 `.git/hooks/`，写入 VERSION/.version/content-hash
- `hook-health-check.py`：校验已安装 hooks 的版本/hash/缺失/孤儿
- `hook-manifest.yaml`：记录各 hook 执行的检查清单（文档用途 + runner 调试入口）
- `hook-runner.sh`：可选调试入口（不走生产路径）

## 目标（Goal）

将机制 22c 补完为**可交付、可运行、自洽**的 hook 统一安装/健康检查框架：

1. **补齐缺失脚本**：新建被引用的 `check-runtime-artifacts.py` / `notify-submodule-change.py` / `guard-chore-state.py`；修正 `gac-hygiene-check.py` / `conflict-marker-check.py` 引用到现有真实路径（`bin/gac/gac-hygiene-check.py`、`bin/gac/check-conflict-markers.py`）。
2. **修复 D1-D7 缺陷**：`run_check` 参数错位、`BLOCKING_FAILED` 退出逻辑、macOS `date %N` 兼容、pre-push stdin 消费、health-check hash 算法对齐、manifest 与 runner 清单对齐、缺失脚本引用守卫。
3. **接线（方案 B）**：`make install-hooks` 统一走 `hook-installer.sh`（含新 hook + VERSION/.version/content-hash）；`hook-health-check.py` 作为校验入口；`.githooks/README.md` 更新为新架构。
4. **净减配平**：删除死代码（`check-dangerous-rebase.py` 的 `check_known_debt`），删除 manifest 中 runner 无法分派的重复段声明，实现净减或持平。

## 非目标（Non-Goals）

- 不新增 hook 检查项（只修复/接线既有 22c 设计）
- **不重写 canonical pre-commit/pre-push 的执行逻辑**（方案 B：保留为实际执行者）
- 不做新功能（新 hook 触发点、远程 hook 服务、UI）
- 不修改 ecos gatekeeper 规则本身（仅修正引用路径）

## 完成标准（Done When）

1. 缺失脚本补齐、引用路径修正（manifest/runner/canonical 三处一致指向真实文件）
2. `make install-hooks` 统一走 `hook-installer.sh`：安装全部 canonical hooks（含新 hook）到 `.git/hooks/`，写入 VERSION/.version/content-hash
3. 修复 D1-D7 缺陷（blocking/timeout、BLOCKING_FAILED、macOS %N、stdin、health-check hash 对齐、manifest/runner 对齐）
4. hook-health-check.py 自检通过；所有新增/修改脚本通过语法检查（bash -n / py_compile）
5. README/.githooks/README.md 更新为新架构（统一安装/健康检查框架）

## 验证标准（Verify）

```bash
python3 -m py_compile bin/gac/check-runtime-artifacts.py bin/gac/notify-submodule-change.py bin/gac/guard-chore-state.py
bash -n bin/gac/hook-runner.sh bin/gac/hook-installer.sh .githooks/pre-merge-commit .githooks/pre-rebase .githooks/post-merge
bash bin/gac/hook-installer.sh --check
python3 bin/gac/hook-health-check.py
make gac-local-gate
```

## 净减记账（D2）

- 新增：`check-runtime-artifacts.py`、`notify-submodule-change.py`、`guard-chore-state.py`（3 脚本，均为缺失引用补齐）
- 删除：`check-dangerous-rebase.py` 死代码 `check_known_debt`、manifest 中 runner 无法分派的重复段（pre-rebase/pre-merge-commit/post-merge/commit-msg 若与 canonical 执行冲突则收敛为记录）
- 目标：净减或持平（Y1 主目标变小）

## 逃生口

- 任何接线改动不得引入新的硬阻断点；`SWARM_ESCAPE_ID` 逃生机制保持有效。
- 若 `make install-hooks` 接线导致本地 commit/push 被阻断，立即回退到旧 canonical 版本并记录。
