---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# 41-L1: 契约版本化策略

## 1. 背景

Eidos 项目定义了 8 个核心 Schema，每个均在 `schemas/registry.json` 中注册并携带 `version` 字段：

| Schema | 文件 | 当前版本 | 描述 |
|--------|------|---------|------|
| identity-role | `identity-role.schema.json` | v1.0.0 | L4 自我层身份与角色定义 |
| value-principle | `value-principle.schema.json` | v1.0.0 | X3 价值堆栈原则性约束 |
| consensus | `consensus.schema.json` | v1.0.0 | X3 价值堆栈三级共识模型 |
| task-object | `task-object.schema.json` | v1.0.0 | L3 协作层任务对象定义 |
| epoch-life | `epoch-life.schema.json` | v1.0.0 | 组件约束（--json 输出 + 路径无关约束） |
| identity-envelope | `identity-envelope.schema.json` | v1.0.0 | L4 自我层身份凭证封装 |
| capability-grant | `capability-grant.schema.json` | v1.0.0 | X3 价值堆栈能力授予模型 |
| node-type | `node-type.schema.json` | v1.0.0 | L3 协作层节点类型定义 |

所有 Schema 当前均为 `status: "active"`，版本 `v1.0.0`。

## 2. 版本化策略：SemVer (MAJOR.MINOR.PATCH)

采用 **语义化版本控制 (Semantic Versioning, SemVer 2.0.0)**，格式为 `MAJOR.MINOR.PATCH`。

### 2.1 MAJOR — Breaking Change

当 Schema 变更**不向后兼容**时递增。包括但不限于：

- 删除必填字段
- 重命名字段
- 字段类型变更（如 `string` → `integer`）
- 删除或修改枚举值
- 修改结构性约束（如 `required` 数组增减）
- 调整 Schema 的 `$id` 或顶级结构

### 2.2 MINOR — Backward Compatible 新增

当新增功能且**向后兼容**时递增。包括但不限于：

- 新增可选字段
- 新增枚举值（不破坏已有枚举）
- 扩展已有类型（如 `oneOf` 新增分支）
- 放宽约束（如将 `string` 改为 `string | null`）

### 2.3 PATCH — 文档/描述更新

当仅**不影响结构和语义**的变更时递增。包括但不限于：

- 更新 `description` 字段
- 修正拼写错误
- 添加注释/示例
- 格式化调整

## 3. change_type 分类

每次变更提交时必须标注 `change_type`，用于自动化判定版本号的递增方式。

| change_type | 对应的版本增幅 | 说明 |
|-------------|--------------|------|
| `backward_compatible` | MINOR | 向后兼容的新增 |
| `breaking` | MAJOR | 不向后兼容的变更 |

变更提交格式示例：

```yaml
change:
  schema: identity-role
  type: backward_compatible   # 或 breaking
  description: "新增 optional 字段 displayName"
  affected_fields:
    - displayName
```

## 4. 过期规则 (Deprecation Policy)

Schema 版本遵循「两版警告，三版删除」的过期规则：

| 条件 | 操作 |
|------|------|
| 旧版本 >= 当前 MAJOR - 1 | 正常兼容，无警告 |
| 旧版本 >= 当前 MAJOR - 2 | 运行时输出 `deprecation_warning` |
| 旧版本 >= 当前 MAJOR - 3 | 从注册表中移除，不再支持 |

**示例**：当前最新版本为 v3.x.x

- v2.x.x → 正常使用（差 1 个 MAJOR）
- v1.x.x → 输出 `deprecation_warning`（差 2 个 MAJOR）
- v0.x.x → 已删除（差 3 个 MAJOR）

消费者应在收到 `deprecation_warning` 后一个版本周期内升级。

## 5. 当前 Schema 版本快照

| Schema | 版本 | 状态 | 注册时间 |
|--------|------|------|---------|
| identity-role | v1.0.0 | active | 2026-05-25 |
| value-principle | v1.0.0 | active | 2026-05-25 |
| consensus | v1.0.0 | active | 2026-05-25 |
| task-object | v1.0.0 | active | 2026-05-25 |
| epoch-life | v1.0.0 | active | 2026-05-25 |
| identity-envelope | v1.0.0 | active | 2026-05-25 |
| capability-grant | v1.0.0 | active | 2026-05-25 |
| node-type | v1.0.0 | active | 2026-05-25 |

## 6. 跨项目策略

所有依赖 Eidos Schema 的下游项目**必须**在其项目根目录下声明所依赖的 Schema 版本。

### 6.1 依赖声明格式

每个下游项目（kronos / kos / iris）应在项目根目录维护 `eidos-deps.json`：

```json
{
  "_comment": "Eidos Schema 依赖声明",
  "project": "kronos",
  "eidos_version_constraint": ">=1.0.0 <2.0.0",
  "dependencies": {
    "identity-role":    ">=1.0.0",
    "value-principle":  ">=1.0.0",
    "consensus":        ">=1.0.0",
    "task-object":      ">=1.0.0",
    "epoch-life":       ">=1.0.0",
    "identity-envelope":">=1.0.0",
    "capability-grant": ">=1.0.0",
    "node-type":        ">=1.0.0"
  },
  "updated_at": "2026-05-27"
}
```

### 6.2 集成校验

CI/CD 管线应包含以下校验步骤：

1. **版本一致性检查**：检查下游声明的约束是否满足 Eidos 注册表中的当前版本
2. **新版本通知**：当 Eidos 发布新 MAJOR 版本时，自动通知所有下游项目负责人
3. **兼容性测试**：每次 Eidos Schema 更新时，运行所有下游项目的集成测试

### 6.3 更新流程

```
Eidos Schema 变更 → Registry 版本递增
    ↓
版本校验通过 → 通知下游项目
    ↓
下游项目：更新 eidos-deps.json 中的版本约束
    ↓
CI 重新运行集成测试
    ↓
通过 → 合并依赖更新
```

---

*文档版本: v1.0.0*  
*创建时间: 2026-05-27*  
*维护者: Eidos Infra Team*
