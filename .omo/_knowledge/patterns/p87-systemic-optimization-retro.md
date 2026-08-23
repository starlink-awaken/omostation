# 系统性架构优化深度复盘

> **复盘触发**：系统性分析/方案任务 + 多轮返工 + 判断错误发现
> **日期**：2026-08-23
> **任务**：系统性架构优化 — 全仓 ruff baseline 统一、CI green、MOF governance 闭环

---

## 1. 任务目标回顾

### 原始目标
- 统一全仓 ruff 基线（runtime / cockpit-ui / observability / knowledge）
- 消除预存在 CI failure（subtraction-quota、ruff E701/E702）
- 建立可持续迭代机制（governance-audit.py、ruff-config-drift.py）
- 根仓 tests/ 按 domain 分层
- 将新工具集成到 CI pipeline

### 实际完成
- ✅ 统一 4 个子项目 ruff 配置
- ✅ 修复 runtime E701/E702（4 处）
- ✅ 消除 23 条 runtime E501 长行
- ✅ 治理安全规则 S603/S607/S310/S608/S602/S324/S311/S104
- ✅ 归档 3 个废弃测试脚本，维持脚本配额 427=427
- ✅ 建立跨项目测试执行矩阵（12/12 PASS）
- ✅ 根仓 tests/ domain markers（conftest.py，不动物理路径）
- ✅ CI pipeline 集成 governance-audit.py + ruff-config-drift.py
- ✅ SSOT 登记 ci-surfaces.yaml
- ✅ `make ci-local-fast` 全绿

---

## 2. 关键决策点

| 时间点 | 决策 | 后果 |
|--------|------|------|
| T0 | 发现 gac-validate subtraction-quota 失败 | 触发系统性优化计划 |
| T1 | 决定修复 runtime ruff E701/E702 而非 ignore | 实际代码质量提升，但耗时 4h+ |
| T2 | 尝试将 tests/ 文件移动到子目录 | **错误**：导致路径断裂，需全部回滚 |
| T3 | 发现 gac-mesh-router.py gate-parity | 验证为历史存量问题，非本次引入 |
| T4 | 决定归档 3 个测试脚本而非更新 baseline | 维持配额纪律，避免 baseline 通胀 |
| T5 | 集成 governance-audit.py 到 CI | 需同步登记 ci-surfaces.yaml |

---

## 3. 判断错误与返工记录

### 错误 1：tests/ 文件移动导致路径断裂

**场景**：尝试将根仓 120+ 个测试文件按 domain 移动到子目录（governance/、workflow/、documents/ 等）

**错误判断**：
- 认为 pytest 支持任意目录结构
- 未评估 `parents[1]` vs `parents[2]` 的影响面
- 低估了 120+ 文件的路径修复成本

**返工过程**：
1. 移动 120+ 文件到子目录
2. 运行 pytest，54 个 collection errors
3. 发现 `scenario_lib` 等模块路径断裂
4. 批量 replace `parents[2]` → `parents[1]`
5. 仍有 21 个 errors（collab_round3_d2 等模块不存在）
6. **最终决策：全部回滚到 tests/ 根目录**
7. 采用 pytest markers 方案替代物理分层

**根因**：
- 缺乏对代码base路径依赖的全面扫描
- 未在 5 文件 PoC 后评估全量影响
- 过度追求"整洁"而破坏working约定

**正确做法**：
- 先做 5 文件 PoC，验证路径无断裂
- 使用 `grep -r "parents\["` 全仓扫描路径依赖
- 优先考虑 pytest markers 等零侵入方案

### 错误 2：ruff config 加载行为误判

**场景**：runtime pyproject.toml 已 ignore E501，但 ruff 仍报 21 条

**错误判断**：
- 认为是 ruff 版本或缓存问题
- 反复运行 `--config pyproject.toml` 验证
- 使用 `--isolated` 模式验证，发现是 config 未生效

**根因**：
- ruff 0.16.4 在 monorepo 中可能从子目录向上查找 config
- `--config` 参数行为与预期不符
- 未优先查看 `--show-settings` 确认实际生效的配置

**正确做法**：
- 第一步就应使用 `ruff --show-settings` 确认实际配置
- 检查 ruff 版本 release notes 的 config 查找逻辑变更

### 错误 3：git stash 后冲突处理

**场景**：验证 gac-mesh-router 是否为历史问题时，使用 `git stash` 后 `git stash pop` 产生冲突

**错误判断**：
- 未预期到 `.omo/_knowledge/governance-history.jsonl` 等文件会冲突
- 直接使用 `git checkout --theirs` 解决，可能丢失部分变更

**根因**：
- 工作区有 3 个文件处于 UU（unmerged）状态
- stash pop 会尝试合并，而非简单恢复
- 未使用 `git merge` 工具检查冲突内容

**正确做法**：
- stash 前先 `git status` 确认工作区干净
- 使用 `git mergetool` 或手动检查每个冲突文件
- 对于 jsonl/yaml 等结构化文件，使用专用合并策略

---

## 4. 返工根因分析

### 4.1 路径依赖扫描缺失

**问题**：移动 tests/ 文件前未扫描全仓路径依赖

**证据**：
- `grep -r "parents\["` 发现 100+ 处路径计算
- 涉及 50+ 个测试文件
- 部分文件使用 `parents[2]`、`parents[3]`

**改进**：
```bash
# 建立路径依赖扫描脚本
find tests/ -name "*.py" -exec grep -l "parents\[" {} \; | wc -l
# 任何文件移动/重命名操作前必须运行
```

### 4.2 PoC 范围不足

**问题**：tests/ 移动仅在小范围验证，未做全量影响评估

**证据**：
- 先移动 9 个 documents 测试，运行通过
- 未验证 governance 域 136 个文件的路径
- 未验证 cross 域外部依赖模块

**改进**：
- 5 文件 PoC → 5% 随机抽样 → 全量 dry-run
- 建立"文件移动影响评估清单"

### 4.3 工具行为假设

**问题**：假设 ruff 配置加载行为，未验证

**证据**：
- pyproject.toml 明确 ignore E501
- ruff 仍报 21 条
- 浪费 2h+ 调试时间

**改进**：
- 新工具/新版本行为必须 `--show-settings` 验证
- 建立工具行为文档

---

## 5. 正确做法总结

### 5.1 零侵入优先

**原则**：能不动的文件就不动，能不移动的路径就不移动

**实践**：
- tests/ domain 分层 → pytest markers（零文件移动）
- 新增检查工具 → ci-surfaces.yaml 登记（零工作流修改）
- 废弃脚本 → 归档到 `_archive/`（零 baseline 通胀）

### 5.2 验证前置

**原则**：任何改动前先验证影响范围

**实践**：
```bash
# 文件移动前
grep -r "old_pattern" . --include="*.py" | wc -l

# 配置修改前
ruff --show-settings | grep -A 2 "line_length"

# git 操作前
git stash list  # 确认无残留
```

### 5.3 基线纪律

**原则**：维持基线 = 更新 baseline，而非删除规则

**实践**：
- 脚本配额：删除 3 个废弃脚本 → 维持 427=427
- ruff debt：消除 26 条 → known_debt=0
- 禁止 baseline 通胀（ci-local-fast 已阻断）

---

## 6. 改进措施

### 6.1 短期（本周）

| 措施 | 负责 | 状态 |
|------|------|------|
| 建立 tests/ 移动前检查清单 | 下次任务 | Pending |
| 工具行为验证模板（ruff/pytest/uv） | 下次任务 | Pending |
| git stash 前检查清单 | 下次任务 | Pending |

### 6.2 中期（本月）

| 措施 | 负责 | 状态 |
|------|------|------|
| 路径依赖扫描脚本（`bin/gac/path-dependency-scan.py`） | 下次任务 | Pending |
| 文件移动影响评估 CI check | 下次任务 | Pending |
| 工具行为文档（ruff/pytest/uv/git） | 下次任务 | Pending |

### 6.3 长期（本季度）

| 措施 | 负责 | 状态 |
|------|------|------|
| 建立"零侵入改造"设计模式库 | 下次任务 | Pending |
| 自动化 PoC 验证框架 | 下次任务 | Pending |
| 返工根因自动检测 | 下次任务 | Pending |

---

## 7. 三层固化计划

### 7.1 Memory（教训层）

**文件**：`.omo/_knowledge/patterns/p87-systemic-optimization-retro.md`

**内容**：
- 本次复盘全文
- 3 个判断错误详细记录
- 改进措施与验证方法

### 7.2 AGENTS.md（协议层）

**文件**：`AGENTS.md`（根仓）

**新增规则**：
```markdown
## 11. 文件/目录移动纪律

1. **零侵入优先**：优先考虑 pytest markers、symlink、配置等零文件移动方案
2. **路径依赖扫描**：移动前必须 `grep -r "old_pattern" . --include="*.py"` 统计影响面
3. **PoC 验证**：5 文件 PoC → 5% 随机抽样 → 全量 dry-run
4. **回滚预案**：移动前 commit 或 stash，确保可一键回滚
```

### 7.3 Hook（Harness 层）

**文件**：`.git/hooks/pre-commit` 或 `bin/gac/path-dependency-check.py`

**逻辑**：
```python
# 检测 tests/ 目录下文件移动
# 自动扫描路径依赖
# 影响面 > 10% 时阻断并提示
```

---

## 8. 核心教训

1. **零侵入 > 物理分层**：pytest markers 完全满足需求，无需移动文件
2. **验证前置 > 事后调试**：5 分钟扫描可避免 4 小时返工
3. **基线纪律 > 规则删除**：维持配额纪律比更新 baseline 更重要
4. **工具行为 > 工具功能**：用 `--show-settings` 确认实际行为，而非假设
5. **git 状态 > git 假设**：stash/pop 前确认工作区干净，冲突时检查内容而非直接 resolve

---

## 9. 复盘元数据

- **任务类型**：系统性架构优化
- **返工轮次**：3 轮（tests/ 移动、ruff config、git stash 冲突）
- **判断错误数**：3 个
- **最终状态**：✅ `make ci-local-fast` 全绿
- **下次触发条件**：类似系统性优化任务前必读本复盘
