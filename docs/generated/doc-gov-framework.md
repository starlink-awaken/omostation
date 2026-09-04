---
type: derived
---

# 文档治理框架 (DocGov Framework)

> SSOT: docs/generated/doc-gov-framework.md
> Version: 1.0 | 2026-09-03

## 1. 文档分类体系

### 1.1 SSOT 文档 (单一真相来源)

| 类别 | 文档 | 更新频率 | Owner |
|------|------|----------|-------|
| 架构 | ARCHITECTURE.md | 架构变更时 | architecture-team |
| 治理 | governance-checks.yaml | 规则变更时 | governance-team |
| 策略 | harness-policy.yaml | 策略变更时 | governance-team |
| 标准 | .omo/standards/*.yaml | 标准变更时 | governance-team |
| 注册 | .omo/_truth/registry/*.yaml | 注册变更时 | governance-team |

### 1.2 派生文档 (从 SSOT 派生)

| 类别 | 来源 | 指针 |
|------|------|------|
| 项目 AGENTS.md | 根 AGENTS.md | 添加 source_ref |
| 子项目 CLAUDE.md | 根 CLAUDE.md | 添加 source_ref |
| 报告 | 各类 SSOT | 添加 data_source |
| 计划 | 各类 SSOT | 添加 based_on |

### 1.3 一次性文档

| 类别 | 生命周期 | 归档规则 |
|------|----------|----------|
| 报告 | 产出即归档 | >90 天归档 |
| 计划 | 完成即归档 | 完成后归档 |
| ADR | 永久保留 | superseded 时标记 |

## 2. 文档模板

### 2.1 SSOT 文档模板

```markdown
---
type: ssot
version: "1.0"
status: active
owner: <team>
last_updated: <date>
---

# <标题>

> 描述: <一句话描述>
> SSOT: <路径>

## 内容
```

### 2.2 派生文档模板

```markdown
---
type: derived
source: <SSOT 路径>
last_synced: <date>
---

# <标题>

> 本文件从 [SSOT](source) 派生
```

## 3. 自动化检查

### 3.1 CI 检查项

- [ ] SSOT 文档格式正确
- [ ] 派生文档包含 source_ref
- [ ] 无过期文档 (>180 天)
- [ ] 无重复内容 (MD5 检查)

### 3.2 告警规则

| 条件 | 告警 |
|------|------|
| SSOT >30 天未更新 | 提醒 owner |
| 派生文档不同步 | 标记 stale |
| 文档 >500 行 | 建议拆分 |

## 4. 导航索引

### 4.1 自动生成

```bash
# 生成文档索引
make docs-index
```

### 4.2 索引结构

```
docs/generated/
├── index.md           # 主索引
├── ssot-map.md        # SSOT 地图
├── derived-map.md     # 派生文档地图
└── stale-list.md      # 过期文档清单
```

## 5. 治理流程

### 5.1 新建文档

1. 确定文档类型 (SSOT/派生/一次性)
2. 使用对应模板
3. 添加 frontmatter
4. 注册到索引

### 5.2 更新文档

1. 检查 source_ref
2. 同步派生文档
3. 更新索引

### 5.3 归档文档

1. 标记状态为 archived
2. 移动到 .omo/_archive/
3. 更新索引
