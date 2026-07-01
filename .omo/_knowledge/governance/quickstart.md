---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# 治理快速入门

> 新成员入职指南：了解 eCOS v6 治理流程
> 本页只保留入门动作与查询入口，不维护健康度阈值、固定 make 命令矩阵或静态 SLA 数字。
> 当前权威源：`/.omo/state/system.yaml`、`/.omo/goals/current.yaml`、`/.omo/debt/`、`/.omo/standards/omo-governance-surfaces.md`。

---

## 概述

eCOS v6 使用 OMO (Operating Model Orchestration) 治理体系，确保系统一致性、可维护性和技术债务可控。

---

## 核心概念

### 债务管理

**什么是技术债务？**
- 代码质量问题（缺少测试、非原子写入）
- 流程违规（文档缺失、SSOT 偏离）
- 架构遗留（未完成的迁移、版本不一致）

**债务分类：**
- `technical` — 代码质量、测试覆盖
- `governance` — 文档、流程
- `process` — 架构、迁移

### 健康度指标

> 健康度口径会随治理模型演进而调整，不在本页硬编码数值阈值。
> 读取当前口径请查看 `/.omo/state/system.yaml`、治理报告和相关标准。

---

## 日常工作流

### 1. 提交代码前

```bash
# Pre-commit hook 会自动检查
git commit -m "feat: xxx"
# 输出:
# 🔍 Pre-commit: ruff + debt prevention
# ⚠️  潜在非原子写入: xxx.py  (如果有问题)
# ✅ Pre-commit check complete
```

### 2. 发现债务时

```bash
# 登记债务
omo-debt register --source kairon --title "缺少原子写入" --severity high

# 查看债务状态
omo-debt list

# 查看债务报告/趋势
omo-debt report
```

### 3. 完成修复后

```bash
# 运行治理检查
make governance-verify

# 查看当前系统/目标
cockpit status
```

---

## 常用命令

```bash
# 测试
make kairon-test          # 全量测试
make kairon-test-fast     # 单元测试
make kairon-test-diff     # 差异测试
make kairon-test-e2e      # E2E 测试

# 治理
make governance-verify    # 工作区治理验证链
omo-debt list             # 债务状态
omo-debt report           # 债务报告
cockpit status            # 当前系统/目标入口
```

---

## 治理标准

### 原子写入规范

**必须使用原子写入的场景：**
- 用户数据写入
- 共享数据写入
- 关键业务数据

**Python 示例：**
```python
from kairon_utils import atomic_write_json, atomic_write_text

atomic_write_json(path, data)
atomic_write_text(path, content)
```

**TypeScript 示例：**
```typescript
import { writeFileSync, renameSync } from 'fs';

const tmp = `${path}.tmp`;
writeFileSync(tmp, JSON.stringify(data));
renameSync(tmp, path);
```

### 测试覆盖标准

- 新包必须有 `tests/` 目录
- 核心功能必须有测试
- CI 必须通过

### 文档维护标准

- 新功能必须更新 README
- 架构变更必须更新 ARCHITECTURE.md
- 每个文档必须有版本信息

---

## SLA 标准

> 当前 SLA 与阈值请回看 [sla.md](./sla.md)；若 SLA 文档进一步降为原则说明，则以对应 control/truth SSOT 为准。

---

## 工具链

| 工具 | 用途 | 命令 |
|------|------|------|
| omo-debt | 债务管理 | `omo-debt register/list/report` |
| ruff | 代码检查 | `ruff check/format` |
| pytest | 测试 | `pytest tests/` |
| cockpit | 当前状态入口 | `cockpit status` |
| governance-verify | 工作区治理验证 | `make governance-verify` |

---

## 常见问题

### Q: Pre-commit 检查失败怎么办？

A: 根据提示修复问题，或使用 `git commit --no-verify` 跳过（不推荐）。

### Q: 如何查看债务详情？

A: 使用 `omo-debt list --status unresolved` 查看未解决债务。

### Q: 健康度低于目标怎么办？

A: 先核对 `/.omo/state/system.yaml` 和最近治理报告，再按 `/.omo/debt/` 中的 open 项处理高优问题。

### Q: 如何生成治理报告？

A: 优先查看 `/.omo/_delivery/` 中现有治理交付物；需要重跑时走当前治理验证链和对应 CLI。

---

*维护: 2026-06-17 · 本页不再维护固定阈值与静态命令矩阵*
