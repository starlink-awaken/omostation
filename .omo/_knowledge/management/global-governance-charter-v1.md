---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# eCOS v5 全局治理宪章 (Global Governance Charter)

> 版本: 1.0 | 2026-06-06 | 基于 5+3+1 架构 Phase 28 全量审计
> 范围: 9 项目 · 25 kairon 包 · ~460K 行代码

---

## §1 架构宪法 (Architecture Canon)

### 1.1 层间依赖规则

```
L4 自我层 → 纯文档, 不运行代码, 不暴露 MCP
L3 入口层 → 所有 Agent/Human 的唯一入口 (cockpit)
I0 织层   → 所有跨层通信的唯一通道 (agora MCP)
L2 内核   → 知识引擎, 治理, 记忆, 编排
L1 运行时 → 服务注册, 健康, 调度, 沙箱
L0 协议   → YAML 定义, 涌现计算
```

**硬约束**:
- ❌ L4 永远不部署 MCP server
- ❌ L2 包不绕过 I0 直连其他 L2 包
- ❌ L3 不重复实现 L2 功能
- ✅ 所有跨层调用必须经 Agora ProxyManager
- ✅ Agent 首次启动必须调 `workspace_context`

### 1.2 层归属判定表

| 功能 | 归属 | 原因 |
|------|------|------|
| 知识检索 | L2 kairon | 核心领域 |
| MCP 路由 | I0 agora | 唯一通道 |
| 系统状态 | L3 cockpit | 统一入口 |
| 定时调度 | L1 runtime | 基础设施 |
| 协议定义 | L0 protocols | 数据层 |
| 身份/目标 | L4 CARDS+Vault | 人类意图 |
| 治理/债务 | L2 omo | 治理面 |
| 审计沙箱 | L1 runtime (KEI) | X1 切面 |

---

## §2 接口治理 (Interface Governance)

### 2.1 端口 SSOT

| 端口 | 归属 | 协议 | 说明 |
|------|------|------|------|
| 7422 | agora | MCP HTTP | I0 MCP Hub |
| 7431 | agora | MCP SSE | I0 MCP Hub |
| 7430 | agora | FastAPI | Web dashboard |
| 8080 | agora | aiohttp | REST API gateway |
| 8090 | cockpit | http.server | L3 dashboard |
| 8765 | minerva | FastAPI | Web (待统一) |
| 9090 | ecos | http.server | L0 dashboard |

**端口注册规则**:
1. 新端口 → 先在此表注册, 后在代码中实现
2. 端口冲突 → 按 L3 > I0 > L2 > L1 > L0 优先级裁决
3. 环境变量 → 必须使用 `{PROJECT}_PORT` 格式

### 2.2 CLI 命名规范

| 模式 | 示例 | 说明 |
|------|------|------|
| 项目名 | `cockpit`, `agora`, `omo` | 主入口 |
| 项目-功能 | `cockpit-mcp`, `agora-mcp` | 子入口 |
| 废弃保留 | `workspace` (→cockpit) | 别名标记 |

### 2.3 MCP 工具规则

1. MCP 入口统一: 所有 kairon 包通过 Agora ProxyManager 注册
2. 命名规范: `{服务名}_{工具名}` (避免跨项目同名冲突)
3. 描述规范: 英文 1 行描述 + Agent 调用指引
4. 去重规则: 同名工具 → 合并到高优先级项目 (L3 > I0 > L2)

---

## §3 代码治理 (Code Governance)

### 3.1 包结构标准

```
项目/
├── pyproject.toml        # hatchling + uv workspace
├── src/{命名空间}/        # 源码
│   ├── __init__.py
│   └── ...
├── tests/                # pytest
└── README.md             # 包含 MCP 配置章节
```

### 3.2 依赖规则

1. 基础依赖 (`kairon-utils`, `kairon-lib-events`) → 所有包可用
2. 领域依赖 (`kairon-pipeline`, `kairon-observability`) → 仅 L2 内
3. 跨项目依赖 → 仅通过 Agora MCP, 不直接 import

### 3.3 版本策略

| 包类型 | 版本格式 | 示例 |
|--------|---------|------|
| 独立项目 | SemVer | agora 3.0.0 |
| L0 基础包 | 跟随 shared-lib | 0.4.0 |
| Kairon 包 | 独立版本 | eidos 0.5.0 |

---

## §4 质量治理 (Quality Governance)

### 4.1 CI/CD 标准

| 要求 | 阈值 | 执行方式 |
|------|------|---------|
| 测试覆盖 | ≥70% | CI pytest |
| Lint | ruff 0 error | CI ruff-check |
| 类型检查 | mypy strict | CI type-check |
| 构建验证 | hatchling build | CI build |

### 4.2 测试标准

1. 每个包必须有 `tests/` 目录
2. 新建模块 → 必须附带测试
3. 修复 bug → 必须附带回归测试
4. CI 失败 → 禁止合并

---

## §5 债务治理 (Debt Governance)

### 5.1 OMO 债务生命周期

```
识别 → 登记 (OMO debt create) → 分级 (X1/X2/X3) → 分配 (owner)
  → 修复 → 验证 (test pass) → 关闭 (OMO debt close)
```

### 5.2 债务分类

| 级别 | 定义 | 响应时间 |
|------|------|---------|
| P0 | 生产缺陷, 安全漏洞 | 24h |
| P1 | 架构偏差, CI 断裂 | 7d |
| P2 | 代码异味, 文档过时 | 30d |
| P3 | 优化建议 | 按需 |

### 5.3 周检清单

- [ ] OMO goals 与实际情况一致
- [ ] P0 债务清零
- [ ] 9 项目 CI 全绿
- [ ] LAYER-INDEX.md 保鲜 (7d 内更新)

---

## §6 演化治理 (Evolution Governance)

### 6.1 新增项目流程

```
1. 在 LAYER-INDEX.md 注册 (层归属 + 职责)
2. 创建 pyproject.toml (hatchling + uv workspace)
3. 实现 CI workflow (pytest)
4. 创建 README.md (含 MCP 配置 SSOT)
5. OMO 登记 (债务清单初始为空)
```

### 6.2 归档项目流程

```
1. 验证 0 外部 import 依赖
2. 移至 projects/_archived/
3. 更新 LAYER-INDEX.md (标记 ⚪)
4. 更新 uv.sources (移除)
5. OMO 登记 (归档原因)
```

### 6.3 架构变更流程

```
1. 提议 → .omo/_knowledge/management/ 新文档
2. 评审 → 人在 CLAUDE.md §0 确认
3. 实施 → 按 §6.1 或 §6.2 流程
4. 验证 → 全量测试 + CI 通过
5. 固化 → 更新本宪章 + LAYER-INDEX.md
```

---

## §7 Agent 治理 (Agent Governance)

### 7.1 Agent 启动契约

每次会话:
1. 连接 cockpit MCP
2. 调用 `workspace_context` → 获取 Phase/P0/约束
3. 调用 `cards_check` → 验证操作合规
4. 执行 (经 Agora → L2)
5. 调用 `cards_update` → 写回状态

### 7.2 Agent 行为边界

| 允许 | 禁止 |
|------|------|
| 通过 cockpit MCP 访问 L4 | 直读写 CARDS SQLite/Vault 文件 |
| 通过 Agora 调用 L2 工具 | 跨包直接 import |
| 修改后 git commit | 跳过 pre-commit hook |
| 更新 cards 状态 | 绕过 OMO 修改 .omo/ |

---

## §8 维护节奏

| 节奏 | 动作 |
|------|------|
| 每日 | Agent 通过 workspace_context 获取当前上下文 |
| 每周 | 审查 P0 债务, CI 健康度, 文档保鲜 |
| 每月 | OMO goals 更新, 架构对齐审计 |
| 每季 | 全量测试, 依赖升级, 宪章修订 |

---

*本宪章是 5+3+1 架构的活文档。任何架构决策必须以本文件为基准。*
