---
name: system-index-distill
description: "Deep workspace analysis to find information silos and create unified navigation. Use when the workspace has many projects/SSOT sources and agents struggle to find things. Produces a SYSTEM-INDEX.md with pure pointers — no data duplication."
---

# System Index Distill — 信息孤岛分析与导航整合

> 从本次会话蒸馏：SYSTEM-INDEX.md 创建全过程（2026-07-03）

## When To Use

- Workspace 有 10+ 项目/SSOT 源，agent 进入时不知道去哪找信息
- 文档之间引用链断裂，找不到某个信息的权威来源
- 新 agent 需要读 6+ 个文件才能理解全局
- 想做"系统级调研"但不知道从哪下手

## 核心原则

1. **不创建新数据源** — 只做指针，不复制
2. **不重复已有** — 已有的生成文件/索引够用就不再造
3. **最小化新增** — 一个文件解决导航问题
4. **SSOT 合规** — 不违反 doc-ssot-contract 的"禁止跨维度复制"

## 5-Phase 工作流

### Phase 1: Inventory（资产盘点）

扫描 workspace 的所有信息源：

```bash
# 项目数
ls -d projects/*/ | wc -l

# 工具数
ls bin/*.py | wc -l
ls scripts/*.py scripts/*.sh | wc -l

# 治理资产
ls .omo/_truth/registry/*.yaml | wc -l
ls .omo/_knowledge/decisions/*.md | wc -l
ls .omo/_knowledge/audits/*.md | wc -l
ls .omo/standards/ | wc -l

# Skills
ls -d .agents/skills/*/ .mimocode/skills/*/ .mimocode/commands/ 2>/dev/null

# 每个项目的文档矩阵
for proj in projects/*/; do
  echo "$(basename $proj): $(ls $proj/AGENTS.md $proj/CLAUDE.md $proj/README.md $proj/ARCHITECTURE.md $proj/BOUNDARY.md $proj/CALLCHAIN.md 2>/dev/null | wc -l)/6 docs"
done
```

输出：资产清单表（类别 | 数量 | 位置 | 性质）

### Phase 2: Gap Analysis（差距分析）

识别信息孤岛：

```bash
# 哪些 SSOT 没有被引用？
rg -l "project-registry.yaml" *.md docs/*.md 2>/dev/null | wc -l  # 引用数
rg -l "port-registry.yaml" *.md docs/*.md 2>/dev/null | wc -l

# 哪些文档之间没有交叉引用？
# 检查 ARCHITECTURE.md 是否引用了 project-registry.yaml
# 检查 AGENTS.md 是否引用了 ARCHITECTURE.md
# 检查 LAYER-INDEX.md 是否引用了 generated 文件

# 是否有重复信息？
# 检查 markdown 中是否有硬编码数字（违反 doc-ssot-contract）
rg "\b\d+ (包|个|条|项|工具|服务)\b" *.md docs/*.md 2>/dev/null | head -20
```

输出：问题清单（问题 | 影响 | 根因）

### Phase 3: Existing Assets Check（已有资产检查）

**关键步骤**：在创建新文件之前，先检查是否已有等价物：

```bash
# 检查是否已有生成的索引
ls docs/generated/
cat docs/generated/project-layer-index.md | head -10
cat docs/generated/agent-gac-rules.md | head -10

# 检查 .omo 中是否已有索引
cat .omo/_knowledge/decisions/INDEX.md | head -10
cat .omo/_truth/registry/INDEX.md | head -10
cat .omo/_knowledge/INDEX.md | head -10

# 检查 doc-ssot-contract 的职责矩阵
grep -A20 "文档类型职责矩阵" .omo/standards/doc-ssot-contract.md
```

**如果已有等价物 → 不要重复创建，只做指针。**

### Phase 4: Design（设计）

基于 Phase 1-3 的发现，设计导航文件：

**设计决策树**：

```
需要导航吗？
├─ 已有统一入口？ → 不需要新文件
├─ 已有分散索引？ → 创建 1 个入口文件做指针
├─ 没有索引？ → 评估是否需要（可能只是没发现）
└─ 确实需要新索引？
   ├─ 数据来自 SSOT？ → 脚本生成，不手写
   ├─ 是分类/视图？ → 检查是否违反"禁止跨维度复制"
   └─ 是纯指针？ → 可以手写
```

**设计检查清单**：

- [ ] 不包含任何硬编码数值
- [ ] 不复制已有 SSOT 的数据
- [ ] 所有指针指向实际存在的文件
- [ ] 不违反 doc-ssot-contract 的职责矩阵
- [ ] 如果是 GaC 体系，检查是否需要新规则（通常不需要）

### Phase 5: Implement & Validate（实施与验证）

```bash
# 1. 创建文件（如果是纯指针，手写即可）
# 2. 验证所有指针路径存在
grep -oP '\[.*?\]\((.*?)\)' SYSTEM-INDEX.md | while read -r link; do
  path=$(echo "$link" | grep -oP '\((.*?)\)' | tr -d '()')
  test -e "$path" || echo "BROKEN: $path"
done

# 3. 运行 GaC 检查
make gac-local-gate

# 4. 运行 SSOT 检查
python3 bin/doc-ssot-lint.py --json

# 5. 提交（注意 change-lane-check：docs/ 和根目录分两个 commit）
```

## 反模式（避免）

| 反模式 | 为什么错 | 正确做法 |
|--------|---------|---------|
| 创建 INDEX-PROJECTS.md 复制 registry 数据 | 违反"禁止跨维度复制" | 指向 `docs/generated/project-layer-index.md` |
| 创建 INDEX-TOOLS.md 列出所有工具 | 违反"禁止 markdown 包含易变数字" | 指向 `bin/README.md` 或 `ls bin/*.py` |
| 创建 INDEX-KNOWLEDGE.md 复制 ADR 列表 | 已有 `decisions/INDEX.md` | 指向已有索引 |
| 为索引创建新的 GaC 规则 | 过度治理 | 用已有 `CR-X4-DOC-SSOT` 足够 |
| 索引文件包含"最新更新: 2026-07-03" | 硬编码日期，会过期 | 只写维护规则，不写日期 |

## 与 GaC 的集成

如果 workspace 有 GaC 体系（governance-checks.yaml）：

- **不需要**为索引创建新 GaC 规则
- **不需要**为索引创建新 executor
- 索引文件遵循现有 `CR-X4-DOC-SSOT` 规则即可
- 如果索引漂移被 `doc-ssot-lint.py` 检测到，它会自动报错

## Output Format

```
## 系统索引分析报告

### 资产盘点
| 类别 | 数量 | 位置 |
|------|------|------|
| ... | ... | ... |

### 差距分析
| 问题 | 影响 | 根因 |
|------|------|------|
| ... | ... | ... |

### 已有等价物
| 我想创建 | 已有等价物 | 决策 |
|----------|-----------|------|
| INDEX-PROJECTS | project-layer-index.md | 指向已有，不创建 |
| ... | ... | ... |

### 最终产出
| 文件 | 行数 | 用途 |
|------|------|------|
| SYSTEM-INDEX.md | ~80 | 统一导航入口 |
```
