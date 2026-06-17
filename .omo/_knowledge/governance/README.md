# 治理流程指南

> eCOS v5 治理流程标准化文档
> 本页只保留稳定治理原则，不维护健康度阈值、实时状态、工具覆盖率或阶段性命令清单。
> 当前治理面 SSOT 以 `/.omo/standards/omo-governance-surfaces.md`、`/.omo/state/system.yaml`、`/.omo/goals/current.yaml`、`/.omo/debt/` 为准。

---

## 债务管理

### 债务登记

使用 `omo-debt register` 快速登记：

```bash
# 登记技术债务
omo-debt register --source kairon --title "缺少原子写入" --severity high

# 登记治理债务
omo-debt register --source metaos --title "缺少.omo平面" --severity medium --description "无法参与OMO治理流程"
```

### 债务分类

| 类别 | 说明 | 示例 |
|------|------|------|
| technical | 代码质量、测试覆盖、架构违规 | 非原子写入、缺少测试 |
| governance | 文档缺失、流程违规、SSOT偏离 | 缺少.omo平面、文档过时 |
| process | 遗留迁移、API版本对齐、架构重构 | SharedBrain拆解、版本统一 |

### 债务优先级

| 级别 | 权重 | 响应时间 |
|------|------|----------|
| critical | 0.3 | 立即响应 |
| high | 0.2 | 优先处理 |
| medium | 0.1 | 按周期处理 |
| low | 0.05 | 纳入 backlog |

---

## 文档维护

### 文档版本控制

每个文档需维护版本信息：

```yaml
# 在文档头部添加
version: 1.0
last_updated: YYYY-MM-DD
change_summary: "初始版本"
```

### 文档更新触发条件

| 条件 | 操作 |
|------|------|
| 新增功能 | 更新 README、添加使用示例 |
| 修复 bug | 更新 CHANGELOG |
| 架构变更 | 更新 ARCHITECTURE.md |
| 债务解决 | 更新 debt-cleanup-plan.md |

---

## 原子写入规范

### 必须使用原子写入的场景

1. **用户数据写入** — 配置、记忆、状态
2. **共享数据写入** — 多进程/多服务访问的数据
3. **关键业务数据** — 交易、审计、日志

### 推荐模式

```python
# Python
from kairon_utils import atomic_write_json, atomic_write_text

atomic_write_json(path, data)
atomic_write_text(path, content)
```

```typescript
// TypeScript
import { writeFileSync, renameSync } from 'fs';

const tmp = `${path}.tmp`;
writeFileSync(tmp, JSON.stringify(data));
renameSync(tmp, path);
```

---

## 测试覆盖标准

### 新包要求

- 至少 1 个单元测试文件
- 核心功能有测试覆盖
- CI 通过

### 债务阈值

- 新增非原子写入 → 债务警告
- 新包无测试 → 债务警告
- 测试覆盖率 < 50% → 债务登记

---

*维护: 2026-06-17 · 运行时指标与阈值请回看 control/truth SSOT*
