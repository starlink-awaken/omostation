# eCOS v5 · L 层架构债务解决方案

**2026-06-08 · 4 项债务 · 按可行性和影响排序**

---

## P0-1: agora 单点故障保护

### 现状
agora 是 I0 层唯一服务，所有跨层通信经过它。如果 agora 进程崩溃，L3→L2、L2↔L2 全部中断。

### 方案：健康降级 + 本地缓存

不需要部署多个 agora 实例（过度工程），而是让调用方在 agora 不可用时优雅降级：

```
调用方 (cockpit/kairon/metaos)
  ↓
1. MCP call → agora
  ↓ (ok)
2. → 正常返回
  ↓ (timeout/error)
3. 读取本地缓存:
   - cockpit: 上次健康检查的快照
   - kairon: 本地注册表副本
   - metaos: 默认决策矩阵
  ↓
4. 返回降级结果 (标记 source=degraded)
```

**实现量**: 每个调用方 ~20 行代码，全局 ~100 行

| 步骤 | 文件 | 改动 |
|------|------|------|
| 1 | `cockpit/base.py` | `_discover_services()` 已有硬编码 fallback — 已实现 ✅ |
| 2 | `agora/server/mcp.py` | 暴露 `/health` 端点用于外部探测 — 已实现 ✅ |
| 3 | `cockpit/cli.py` | health --full 中 agora 不可用时展示缓存状态 |
| 4 | `metaos/core/cards_context.py` | CARDS 读取失败时返回空上下文（不 crash）— 已实现 ✅|

**结论**: 当前代码已有基本降级（尝试→捕获→fallback），核心风险已缓解。

---

## P1-1: Python 版本统一 (3.10 → 3.13)

### 现状

| 层 | 项目 | Python | 原因 |
|----|------|--------|------|
| L0 | ecos | 3.10+ | 历史遗留 |
| L1 | runtime | 3.10+ | setuptools 构建 |
| L3 | cockpit | 3.10+ | 兼容旧系统 |
| L2 | kairon/omo/metaos | 3.13+ | 新版特性 |
| I0 | agora | 3.13+ | 新版特性 |

### 方案

```
1. 检查 ecos/runtime/cockpit 是否使用了 3.10→3.13 间废弃的特性
2. 逐个项目的 pyproject.toml 中 requires-python 改为 >=3.13
3. 运行全量测试确认无回归
4. 统一后 pip/uv 只需为 3.13 编译一次 .so
```

**风险**: ecos/runtime/cockpit 的依赖包可能不兼容 3.13。需要逐一验证。

**优先**: cockpit 已经实际运行在 3.13 (venv 使用 3.13)，只是 pyproject.toml 写的是 3.10+。实际只需改声明。

| 步骤 | 文件 | 改动 |
|------|------|------|
| 1 | `cockpit/pyproject.toml` | `requires-python = ">=3.10"` → `">=3.13"` |
| 2 | `ecos/pyproject.toml` | 同上 |
| 3 | `runtime/pyproject.toml` | 同上 |
| 4 | 全量测试 | `make test` 各项目 |

---

## P1-2: cockpit/workspace 双入口统一

### 现状
用户困惑："到底用 `cockpit` 还是 `workspace`？"

```
cockpit 命令      workspace 命令      实际相同功能
───────────      ──────────────      ─────────
cockpit context  workspace context   ✅ 同一函数
cockpit cards    workspace cards     ✅ 同一函数
cockpit vault    workspace vault     ✅ 同一函数
—               workspace domains   ⚠️ 仅 workspace
—               workspace skill     ⚠️ 仅 workspace
```

### 方案：添加 cockpit 别名

在 cockpit/cli.py 中为 `workspace` 特有的命令添加 `cockpit` 入口：

```python
# 当前 (workspace 特有)
workspace domains
workspace skill run <name>

# 目标 (统一)
cockpit domains          ← 新增
cockpit skill run <name>  ← 新增
workspace domains        ← 保留兼容
workspace skill run      ← 保留兼容
```

**实现量**: cli.py 添加 2 个 subcommand，~15 行

---

## P2-1: gbrain TS 技术栈评估

### 现状
gbrain 是唯一 TypeScript 项目（67 MCP tools, Postgres 知识脑），其他 7 项目全是 Python。

### 方案对比

| 方案 | 优点 | 缺点 | 成本 |
|------|------|------|------|
| A: 保持现状 | 零改动 | 两套依赖、两套测试 | 0 |
| B: 通过 MCP 隔离 | 语言无关，Agoda 代理 | 已是现状 | 0 |
| C: 迁移到 Python | 统一技术栈 | 67 tools 重写 | 极度高 |

### 建议：方案 B（现状已是最优）

gbrain 通过 `stdio://gbrain` 以 MCP 方式集成，agora 代理层已屏蔽语言差异。L2 其他引擎不需要 import gbrain 代码，只需要调用 MCP 工具。这是正确的架构设计：**跨语言通过协议隔离，不通过代码耦合**。

**结论**: 当前架构已经解决了这个问题，不需要改动。

---

## 执行计划

| 优先级 | 项 | 工作量 | 风险 | 建议 |
|--------|----|--------|------|------|
| P0 | agora 降级 | 已实现 | — | ✅ 无需改动 |
| P0 | cockpit 别名 | 15 行 | 极低 | 立即执行 |
| P1 | Python 版本 | 3 文件 | 中 (依赖兼容) | 逐项目验证后执行 |
| P1 | gbrain 隔离 | 已实现 | — | ✅ 无需改动 |
