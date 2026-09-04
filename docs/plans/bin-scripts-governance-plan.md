---
status: superseded
lifecycle: plan
owner: governance-team
last_updated: 2026-08-22
type: ephemeral
---

# bin/ 与 scripts/ 收敛治理实施计划

> **已退役** (2026-08-21): `scripts/bin/` 工具已迁移到 `bin/`，scripts 仓库已 archive。
> 本计划保留作为历史记录。

- 状态：Wave 2 已实施并固化基线（第一波非破坏性治理完成）
- 日期：2026-08-16
- 范围：主仓库 `bin/`、`scripts/` 与 `docs/operations/bin-scripts-convergence-manifest.json`
- 负责人：governance
- 关联审计：`bin/tool-registry-audit.py --scope both`

## 1. 背景与目标

`bin/` 和 `scripts/` 经过长期演进，已经积累大量脚本，出现命名不统一、能力重叠、入口重复和职责边界模糊等问题。目标是：

1. 明确 `bin/` 是主实现、主入口和固化载体。
2. `scripts/` 收敛为 compatibility shim，不再新增重复实现。
3. 用 `docs/operations/bin-scripts-convergence-manifest.json` 作为收敛治理 SSOT。
4. 复用 `bin/tool-registry-audit.py` 建立长期迭代机制，避免再造一套并行注册体系。

## 2. 审计数据摘要

基于 `bin/tool-registry-audit.py --scope both` 快照：

| 维度 | 数量 |
|---|---|
| 总脚本数 | 758 |
| Python 脚本 | 688 |
| Shell 脚本 | 68 |
| 非 snake_case 命名 | 631 |
| 重名脚本 | 237 |
| parallel candidate | 173 |
| mirrored duplicate | 234 |
| shim 候选 | 236 |
| archive 候选 | 87 |
| 当前 manifest 条目 | 233 |

overlap 维度：

| 分类 | 数量 |
|---|---|
| merged | 144 |
| different | 44 |
| only_bin | 340 |
| only_scripts | 57 |

结论：`bin/` 和 `scripts/` 存在大量真实重叠，当前第一波不进行破坏性移动，先用计划、manifest 和审计工具锁定治理基线。

## 3. 收敛策略

### 3.1 `bin/` 是主实现

- 新能力、新工具、治理脚本统一落在 `bin/`。
- `bin/` 作为入口文档、调用链和 CI 引用的事实来源。
- 命名规范向 snake_case 收敛，后续按批次迁移。

### 3.2 `scripts/` 只保留兼容 shim

- `scripts/` 不再承载新实现。
- 已存在的 `scripts/bin/...` 兼容路径保留为 shim，指向 `bin/` 主实现。
- 被调用方完成迁移后，shim 进入清理批次。

### 3.3 manifest 是 SSOT

`docs/operations/bin-scripts-convergence-manifest.json` 记录每个条目的：

- `name`
- `bin` 路径
- `scripts` 路径
- `status`
- `action`
- `owner`
- `note`

以 `action` 表达收敛动作，例如 `bin-master, scripts-compat-shim`。manifest 与审计工具绑定，后续任何工具注册变化都应先更新 manifest。

## 4. 长期迭代机制

1. 新增或调整工具时，先确认是否与现有 `bin/` 或子项目能力重复。
2. 属于治理工具、根仓入口或跨项目脚本的，落在 `bin/` 并登记 manifest。
3. 属于某子项目能力的，下沉到对应子项目，根仓只保留薄 wrapper。
4. 任何 `bin/` / `scripts/` 结构变化，运行审计工具并更新快照：

```bash
python3 bin/tool-registry-audit.py --scope both \
  --parallel-manifest docs/operations/bin-scripts-convergence-manifest.json \
  --snapshot artifacts/bin-tool-registry-audit.json
```

5. 将上述命令逐步纳入治理门禁或 CI 检查，使命名、重名、overlap、shim 和 archive 指标可追踪、可回归。

## 5. 第一波实施范围（非破坏性）

第一波只做基线治理，不执行大量 `mv` / `rm`：

- [x] 完成全量审计扫描并生成快照。
- [x] 确认 manifest 顶层结构与 action 语义。
- [x] 创建本治理计划文档。
- [x] 验证本计划变更通过 agent workflow。
- [x] closeout 后提交 PR 并合并。

风险控制：

- 不动 `scripts` 子模块内的历史实现。
- 不提交审计临时产物。
- 不批量改名、不批量删除。
- 先建立机制，再逐步执行脚本重命名、shim 清理、archive 治理和重复合并。

## 6. 后续治理批次

1. **命名治理**：分批将非 snake_case 脚本迁移为 snake_case，同步 manifest 和调用方。
2. **shim 清理**：对 235 个 shim 候选逐批确认调用链，确认无引用后移除。
3. **archive 治理**：对 90 个 archive 候选确认历史价值，归档到明确目录或删除。
4. **重复合并**：对 mirrored duplicate / parallel candidate 按能力合并到 `bin/` 主实现。
5. **CI 固化**：把 manifest + audit 纳入常态化门禁，防止新增重复和漂移。
6. **子项目下沉**：把根仓中属于子项目能力的工具逐步下沉到对应子项目，根仓只保留统一入口。

## 7. 验收标准

- `bin/` 与 `scripts/` 的能力边界在文档中明确。
- manifest 与审计工具成为唯一收敛治理入口。
- 第一波不引入破坏性变更，主仓门禁保持绿色。
- 后续每一批治理都有独立 PR、审计数据和 closeout 记录。

## 8. 决策记录

本计划落地的架构决策：

- 不另建脚本注册系统，复用现有 manifest + audit。
- 不以 `scripts/` 为第二实现源。
- 先机制后清理，先非破坏性后分批迁移。
