---
type: ssot
description: "从产品视角对目标系统做白盒走查：构造用户场景→实跑验证→发现断点→分级报告→修复验证。适用于功能交付后的深度质量审视。"
agent: main

last-reviewed: 2026-08-26
owner: governance-team
---

# 产品视角白盒走查 · Product Perspective Walkthrough

## 触发条件

- 用户说"产品视角"、"走查"、"白盒测试"、"用户场景"
- 功能交付后做质量审视
- 用户说"再来一次，更加深度"

## 参数

| 参数 | 占位符 | 默认 | 说明 |
|------|--------|------|------|
| 目标系统 | `$ARGUMENTS` | 全 workspace | 走查范围（ecos / cockpit / kos / kairon / full） |
| 深度 | `$1` | standard | `quick`（核心路径） / `standard`（全覆盖） / `deep`（极端场景） |
| 用户画像 | `$2` | mixed | `normal`（普通用户） / `expert`（专家） / `architect`（架构师） / `mixed`（多视角） |
| 覆盖率目标 | `$3` | 90% | 功能覆盖率百分比 |

## 执行流程

### Phase 1: 发现

**扫描目标系统的全部功能入口**：

```bash
# 例：cockpit 功能发现
cd /Users/xiamingxing/Workspace/projects/cockpit
grep -r "def cli_" src/cockpit/*.py | head -30     # CLI 命令
grep -r "@app\." src/cockpit/web/*.py | head -30    # HTTP 路由

# 例：ecos 功能发现
cd /Users/xiamingxing/Workspace/projects/ecos
grep -r "def " src/ecos/l0/ src/ecos/l1/ src/ecos/l2/ src/ecos/l3/ | grep -v "__" | head -40

# 例：KOS 功能发现
cd /Users/xiamingxing/Workspace/projects/kairon/packages/kos
grep -r "def " src/kos/ --include="*.py" | grep -v "__\|test_" | head -40
```

**输出**：功能清单（编号 + 入口 + 一句话描述）

### Phase 2: 场景构造

**按用户画像构造真实使用场景**：

```
每个场景 = 用户目标 + 前置条件 + 操作步骤 + 预期结果

构造原则：
1. 用户说人话，不说技术术语
2. 包含边界条件（空数据 / 并发 / 网络断开 / 权限不足）
3. 至少 1 个"看似正常实则会出问题"的场景
4. deep 模式：构造 3+ 用户类型 × 各 3+ 场景
```

### Phase 3: 实跑验证

**每个场景必须实际执行，不允许仅阅读代码推测**：

```bash
# 实跑命令示例
cd /Users/xiamingxing/Workspace/projects/cockpit
PYTHONPATH=src uv run python3 -c "from cockpit.cli import cli; ..."  # 实跑 CLI

cd /Users/xiamingxing/Workspace/projects/ecos
uv run python -c "from ecos.l0.governance import ..."                  # 实跑 API

curl -s "http://localhost:8766/api/v1/search?q=test" | python3 -m json.tool  # 实跑 HTTP
```

**记录每个场景的真实输出**（贴命令 + 贴输出，不转述）

### Phase 4: 断点分级

```
每个断点 = 场景名 + 严重度 + 证据 + 修复建议

严重度分级：
🔴 P0 — 核心功能不可用 / 数据丢失 / 安全漏洞
🟡 P1 — 功能可用但体验差 / 错误消息不友好 / 边界条件崩溃
🟢 P2 — 优化项 / 文档缺失 / 一致性不足
```

### Phase 5: 报告

```markdown
## 🎯 产品视角走查报告 — {目标系统} v{轮次}

### 覆盖概况
- 功能总数: N
- 已验证: M (覆盖率 X%)
- 用户画像: {画像列表}

### 断点清单
| # | 断点 | 严重度 | 场景 | 证据摘要 |
|---|------|--------|------|----------|
| 1 | ... | 🔴 P0 | ... | ... |

### 修复优先级
1. （P0 必修复）...
2. （P1 应修复）...
```

### Phase 6: 修复 + 闭环（可选）

如果用户要求修复：

1. 每个断点创建一个 task
2. 按优先级顺序修复
3. 修复后**实跑同一场景**验证
4. 更新断点状态（🔴→✅）

## 关键纪律

| 纪律 | 违反 = |
|------|--------|
| 必须实跑 | 推测代替验证 = 假走查 |
| 必须贴证据 | 只写"有问题"不贴输出 = 空话 |
| 必须分级 | 所有问题同级 = 无优先级 |
| 必须覆盖边界 | 只走 happy path = 遗漏真问题 |

## 典型调用

```bash
# 全 workspace 快速走查
/product-perspective-walkthrough full quick mixed 80

# cockpit 深度走查，多用户视角
/product-perspective-walkthrough cockpit deep mixed 90

# ecos 标准走查，只看普通用户
/product-perspective-walkthrough ecos standard normal 90

# KOS 深度 + 架构师视角
/product-perspective-walkthrough kos deep architect 95
```

## 与已有资产的关系

- 不同于 `design-self-critique`（设计文档自审）— 本命令是**运行时走查**
- 不同于 `trajectory-distill`（历史会话蒸馏）— 本命令是**前瞻性验证**
- 不同于治理 gate（合规检查）— 本命令是**用户体验审视**
