---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-29
---

# ADR Process Standard

> Architecture Decision Records (ADR) 流程标准。
> 模板和完整规则见 `.omo/_knowledge/decisions/README.md` (MADR 风格)。
> 索引见 `.omo/_knowledge/decisions/INDEX.md`。

## 1. 何时写 ADR

以下场景必须记录 ADR:

- 架构层 (L0-L3) 的新增、拆分、合并
- 跨项目接口变更
- 技术选型 (框架、协议、数据格式)
- 治理规则 (GaC/X1-X4) 的新增或变更
- Phase 关闭时的重大决策回顾

以下场景不需要 ADR:

- 单项目内部重构 (记录在项目 CHANGELOG)
- Bug 修复 (记录在 commit message)
- 文档修订 (记录在 git diff)

## 2. 生命周期

```
PROPOSED → ACCEPTED → DEPRECATED
                │
                └──→ SUPERSEDED by ADR-NNNN
```

| Status | 含义 |
|--------|------|
| `PROPOSED` | 提案中, 评审通过后改为 `ACCEPTED` |
| `ACCEPTED` | 已接受并实施, 当前生效 |
| `DEPRECATED` | 仍有效但不推荐用于新场景 |
| `SUPERSEDED` | 已被新 ADR 替代, 必须填 `Superseded by: ADR-NNNN` |

**规则:**
- 不允许删除 ADR 文件 (仅可标记 `DEPRECATED` 或 `SUPERSEDED`)
- 新 ADR 编号取 INDEX.md 中最大编号 + 1
- 每个 Phase 关闭前, 治理 Agent 必须检查是否有未记录的架构决策

## 3. 模板

完整 MADR 模板见 `.omo/_knowledge/decisions/README.md`。

最小必填章节:

1. **Context and Problem Statement** — 2-4 段背景
2. **Decision Drivers** — 驱动决策的因素
3. **Considered Options** — 备选方案
4. **Decision Outcome** — 选定方案 + 理由 + 后果
5. **Confirmation** — 如何验证决策生效

## 4. 文件命名

- 路径: `.omo/_knowledge/decisions/NNNN-<kebab-case-title>.md`
- 编号: 4 位 zero-padded 全局递增 (0001, 0002, ...)
- 标题: 动词 + 宾语

## 5. 验证工具

```bash
# ADR frontmatter 完整性检查
uv run --with "pyyaml" python bin/adr-coverage.py

# ADR drift 检查 (检测 ADR 中引用的文件/路径是否漂移)
uv run --with "pyyaml" python bin/adr-drift-check.py

# ADR 趋势分析
uv run --with "pyyaml" python bin/adr-trend-insight.py
```

## 6. 关联文件

| 文件 | 角色 |
|------|------|
| `.omo/_knowledge/decisions/README.md` | ADR 模板和完整维护规则 (MADR 风格) |
| `.omo/_knowledge/decisions/INDEX.md` | ADR 索引表 |
| `bin/adr-coverage.py` | Frontmatter 完整性检查 |
| `bin/adr-drift-check.py` | ADR 内容漂移检测 |
| `bin/adr-trend-insight.py` | ADR 趋势分析 |
