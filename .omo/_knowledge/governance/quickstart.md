# 治理快速入门

> 新成员入职指南：了解 eCOS v5 治理流程

---

## 概述

eCOS v5 使用 OMO (Operating Model Orchestration) 治理体系，确保系统一致性、可维护性和技术债务可控。

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

| 指标 | 说明 | 目标 |
|------|------|------|
| debt_weight | 债务权重 (0-1) | ≥ 0.9 |
| debt_health | 健康度 (0-100) | ≥ 90 |
| resolved_rate | 解决率 | ≥ 90% |

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
make debt-check

# 查看债务排行榜
make debt-leaderboard
```

### 3. 完成修复后

```bash
# 运行审计
make debt-audit

# 查看治理数据
make governance-query
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
make governance-audit     # 全量治理审计
make debt-check           # 债务状态
make debt-audit           # 债务审计
make debt-leaderboard     # 债务排行榜
make doc-lint             # 文档检查

# 可视化
make governance-dashboard # 生成 HTML 报告
make governance-data      # 生成 JSON 数据
make governance-query     # 查询治理数据
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

### 债务响应时间

| 严重程度 | 响应时间 | 解决时间 |
|----------|----------|----------|
| critical | 1 小时 | 24 小时 |
| high | 24 小时 | 7 天 |
| medium | 7 天 | 30 天 |
| low | 30 天 | 90 天 |

### 健康度目标

- debt_weight ≥ 0.9
- debt_health ≥ 90
- resolved_rate ≥ 90%

---

## 工具链

| 工具 | 用途 | 命令 |
|------|------|------|
| omo-debt | 债务管理 | `omo-debt register/score/compare` |
| ruff | 代码检查 | `ruff check/format` |
| pytest | 测试 | `pytest tests/` |
| debt-audit | 债务审计 | `bash scripts/debt-audit.sh` |
| governance-query | 治理查询 | `python3 scripts/governance-query.py` |

---

## 常见问题

### Q: Pre-commit 检查失败怎么办？

A: 根据提示修复问题，或使用 `git commit --no-verify` 跳过（不推荐）。

### Q: 如何查看债务详情？

A: 使用 `omo-debt list --status unresolved` 查看未解决债务。

### Q: 健康度低于目标怎么办？

A: 运行 `make debt-audit` 查看详细报告，优先处理 critical/high 债务。

### Q: 如何生成治理报告？

A: 使用 `make governance-dashboard` 生成 HTML 报告。

---

*最后更新: 2026-06-12*
