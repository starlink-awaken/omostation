---
description: "Review a design document against existing contracts (doc-ssot-contract, GaC rules, NORTH-STAR invariants) and produce a simplified version. Anti-over-engineering pattern."
---

# Design Self-Critique — 设计方案自审与简化

## 触发条件

- 刚写完一个设计方案/架构文档
- 准备实施前想确认"这真的是最优解吗"
- 用户问"保持 SSOT 了吗？是最优解吗？"

## 3-Step 流程

### Step 1: 对照契约检查

读取以下文件，逐条检查设计方案是否违反：

```bash
# 必读的契约文件
cat .omo/standards/doc-ssot-contract.md    # 文档正交原则
cat .omo/_knowledge/gac/NORTH-STAR.md      # GaC 不变量（如有）
cat .omo/_truth/registry/governance-checks.yaml | head -60  # GaC 规则
```

**检查清单**：

| 契约 | 检查项 | 违反 = |
|------|--------|--------|
| doc-ssot-contract 规则 1 | 设计是否包含硬编码易变数字？ | 违反 SSOT |
| doc-ssot-contract 规则 2 | 设计是否"禁止跨维度复制"？ | 违反正交 |
| doc-ssot-contract 规则 3 | 项目元数据是否只从 registry 读？ | 数据孤岛 |
| NORTH-STAR 不变量 | 设计是否需要新 GaC 规则？ | 可能过度治理 |

### Step 2: 查已有等价物

**在创建新文件之前**，先检查是否已有等价物：

```bash
# 检查 docs/generated/ 下的生成文件
ls docs/generated/

# 检查 .omo/_knowledge/ 下的索引
ls .omo/_knowledge/*/INDEX.md 2>/dev/null

# 检查是否有人已经做过类似工作
rg "INDEX\|index\|导航\|navigation" docs/*.md .omo/_knowledge/*/INDEX.md 2>/dev/null | head -10
```

**决策规则**：

```
已有等价物？
├─ 是 → 不创建，只做指针
├─ 部分重叠 → 合并到已有，不新建
└─ 没有 → 继续设计
```

### Step 3: 简化

问自己三个问题：

1. **砍到最简**：如果只能留 1 个文件，留哪个？
2. **砍到零新增**：如果完全不创建新文件，能解决吗？
3. **砍到纯指针**：如果新文件只包含指向已有 SSOT 的链接，够用吗？

## 输出格式

```markdown
## 自审报告

### 契约检查
| 契约 | 结果 | 问题 |
|------|------|------|
| ... | ✅/❌ | ... |

### 已有等价物
| 我想创建 | 已有 | 决策 |
|----------|------|------|
| ... | ... | 保留/合并/指向 |

### 简化结果
| 维度 | 原设计 | 简化后 |
|------|--------|--------|
| 文件数 | N | M |
| 数据源 | N | M |
| GaC 规则 | N | M |
```

## 反模式

| 反模式 | 后果 |
|--------|------|
| 不查已有就创建 | 重复造轮子，违反 SSOT |
| 设计完直接实施 | 可能过度设计 |
| 用"未来可能需要" justify 复杂度 | YAGNI 违反 |
| 不对照契约 | 违反已有治理规则 |
