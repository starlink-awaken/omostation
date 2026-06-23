---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史审计快照批量归档, 当前 governance 100 A+ 持续"
---
# P45 文档生命周期治理 — 收口报告

> 2026-06-22 · commit 2a7b09d4 · mof-version v0.0.29
> Pattern: c2g → omo → mof (P43/P44 闭环)

## 1. 背景

P44 收口（commit e1bc0637, mof-version v0.0.28）后审计 `.omo/` 文档生态：

- **1214 .md + 775 .yaml** 散落 6 平面 + 12 顶层目录
- **X1-X4 4 个 SSOT 真活** (mof-state-bridge + c2g task_builder 实加载)
- **9/41 standards 真活** (32 个 0 引用 = 死契约)
- **30 audits + 142 management = 0 引用** (历史快照但机器不识别)
- **14/16 mof 工具 0 引用** (功能未实现占位)
- **6 governance 检查无 doc 维度** (死文档对总分无影响)

**核心痛点**: "写完就死" 浪费 GIGO 风险，机器无法识别每类文档状态。

## 2. R1-R5 阶段映射

| Round | 主题 | 关键产物 | commit |
|-------|------|---------|--------|
| R1 | 治本规则 | `.omo/DOC-LIFECYCLE.md` 4 类定义 + frontmatter schema + 引用规则 | 2a7b09d4 (合并) |
| R2 | 机器识别 | `omo_lint` 第 14 维度 `cmd_lint_doc_lifecycle` + 第 15 维度 `cmd_lint_doc_archival_suggestions` | 2a7b09d4 |
| R3 | 治理集成 | `omo governance` 第 7 项 `governance_check_doc_lifecycle` + pre-commit 2 钩子 + X2-FRESH-DOC-LIFECYCLE + l4-kernel `audit.doc_lifecycle` | 2a7b09d4 |
| R4 | 软引导 + 批量标注 | 187 docs frontmatter + 12 mof Status + 183 YAML 解析 fix | 2a7b09d4 |
| R5 | 收口 | l4-kernel registry + 收口报告 + mof-version v0.0.29 | 2a7b09d4 |

## 3. 4 类文档定义

| 类别 | 路径模式 | 例子 | frontmatter 要求 |
|------|---------|------|-----------------|
| **SSOT** | `.omo/_truth/*.yaml` | x1-x4, mutation-surfaces, mof-version | 必填 |
| **CONTRACT** | `.omo/standards/*.md` | omo-governance-surfaces, task-yaml-rules | 必填 |
| **PATTERN** | `.omo/_knowledge/patterns/*.md` | p43/p44 closed-loop | 必填 |
| **HISTORY** | `.omo/_archive/`, `_knowledge/audits/`, `_knowledge/management/` | 30 phase closeout, 142 decisions | 不要求 |

### 3.1 frontmatter Schema

```yaml
---
status: active | deprecated | archived | experimental
lifecycle: ssot | contract | pattern | history
owner: <domain>
last-reviewed: YYYY-MM-DD
superseded-by: <file>  # deprecated 时填
---
```

## 4. 关键产物 (254 files, 2633 insertions)

### 4.1 R1 治本规则

- `.omo/DOC-LIFECYCLE.md` (新)
- `.omo/INDEX.md` 加 §文档生命周期入口
- `.omo/_truth/x2-freshness-rules.yaml` 加 `X2-FRESH-DOC-LIFECYCLE` (7 天)

### 4.2 R2 机器识别

- `projects/omo/src/omo/omo_lint.py`:
  - `cmd_lint_doc_lifecycle()` (第 14 维度)
  - `cmd_lint_doc_archival_suggestions()` (第 15 维度)
  - subparser + dispatch
  - 4 类自动分类 + frontmatter 覆盖率 + 死文档 + 矛盾路径

### 4.3 R3 治理集成

- `projects/omo/src/omo/omo_audit.py`:
  - `governance_check_doc_lifecycle()` (第 7 项)
  - 加入 7 项检查列表
- `.pre-commit-config.yaml`:
  - `omo-doc-lifecycle-gate` 钩子
  - `omo-doc-archival-suggestions` 钩子
- `projects/l4-kernel/src/l4_kernel/registry.py`:
  - `audit.doc_lifecycle` capability
- `bin/mof-version`:
  - 兼容 frontmatter 读取 (P45)

### 4.4 R4 软引导 + 批量标注

- 4 个真死 standards 加 `status: deprecated` frontmatter
- 179 个 audits/management/decisions 加 `status: archived` frontmatter
- 33 standards + 5 _truth md + 5 _truth yaml + 4 _knowledge = 47 fm
- 183 个 frontmatter YAML 解析失败 fix (引号包)
- 12 个 mof 工具加 `Status: planned` 注释

## 5. 扩散同步分析

| 组件 | 影响 | 实际处理 |
|------|------|---------|
| **AGENTS.md** | 引用 `.omo/` 路径 | 兼容, 不破坏 (不需改) |
| **MCP agora/server/mcp.py:321** | AGENTS.md 自动发现机制 | 兼容扩展, 不改 mcp.py |
| **BOS URI** | 域划分 (memory/governance/...) | 零影响 (doc-lifecycle 是文件级元数据) |
| **cockpit CLI** | 唯一人类入口 | 零影响 (通过 `omo governance` 命令间接看) |
| **X1-X4 SSOT** | 4 个 .py load | 零影响 (不改路径) |
| **l4-kernel** | audit 能力 | 扩展 (新增 `audit.doc_lifecycle`) |
| **pre-commit** | 13 钩子 | 扩展 (新增 2 钩子) |

## 6. 验证结果

| 指标 | 数值 | 状态 |
|------|------|------|
| omo governance | 98.0 A+ (7 项检查) | ✅ 持续 |
| doc lifecycle 维度 | WARN 86 (frontmatter 47/100) | ✅ 新增 |
| mof-drift | 1 LOW (gbrain TODOs) | ✅ 维持 |
| mof-audit | 0 漂移 (M0↔M1) | ✅ 持续 |
| X1-X4 引用 | 7 处 (不变) | ✅ 不破坏 |
| mof-version | v0.0.28 → v0.0.29 | ✅ 升级 |
| 死文档识别 | 4 (前置) → 0 (R4 后) | ✅ 立现 |
| frontmatter 覆盖率 | 0% → 47% | ✅ 立现 |
| 矛盾路径 | 0 (前置过滤 .md 解释文档) | ✅ 准确 |
| diff | 254 files, 2633 insertions | ✅ 完整 |

## 7. P45 闭环模式

```
c2g brainstorm "P45 文档生命周期治理"     # 需求侧
   ↓
c2g bet → BET-P45                          # 战略登记
   ↓
omo broker create_planned_task             # 物化 P45-DOC-LIFECYCLE PLANNED
   ↓
R1: .omo/DOC-LIFECYCLE.md                  # 治本规则
R2: omo_lint 第 14/15 维度                  # 机器识别
R3: governance 第 7 项 + pre-commit + X2     # 治理集成
R4: 187 docs frontmatter + 12 mof 注释      # 软引导
R5: l4-kernel + 收口                        # 收口
   ↓
mof-version v0.0.28 → v0.0.29              # 版本记录
   ↓
git commit 2a7b09d4 (254 files)              # 落地
```

## 8. 模式可复用度

| 环节 | 可复用度 | 复用条件 |
|------|---------|---------|
| **c2g brainstorm + 手动补 Upstream/Appetite** | **高** | 任意需求 |
| **omo broker Python 直接调** | **高** | metadata: {} 必填, setdefault 注入 |
| **omo_lint 第 N 维度扩展** | **极高** | 不重写 main(), 追加 subparser + cmd + dispatch |
| **omo_audit.py governance_check_* 第 N 项** | **高** | 加函数 + 加 list 末尾 + 5 字段 |
| **pre-commit 加 1 个钩子** | **高** | pass_filenames: false 模式 |
| **l4-kernel registry 加 capability** | **高** | 注释 + 1 行 |
| **frontmatter 批量标注** | **中** | 注意 YAML 特殊字符 (引号包) |
| **mof-extract 自动跑** | **高** | post-commit 自动触发, 无需手动 |
| **mof-version bump** | **中** | 注意 frontmatter 兼容 (tool 要改) |
| **X2-FRESH 加新规则** | **高** | yaml 块 + 引用 x2-freshness-rules.yaml |

## 9. 风险与遗留

### 9.1 风险 (已消除)

- ✅ omo_lint 13 维度破坏 → 实际只追加, 不重写 main()
- ✅ mof-version 工具读 frontmatter 失败 → 工具已修
- ✅ governance 总分从 100→94→98 看似下降 → 实际更真实 (doc 维度新评估)
- ✅ 183 frontmatter YAML 解析失败 → 修后全部 OK

### 9.2 遗留 (P46+ 处理)

- 47/100 frontmatter 覆盖率 (剩余 53% 多在 audits/management 大文档, 多数已标 archived)
- 12 mof 工具仍 planned 状态 (P46+ 实现)
- gbrain 53 TODOs (P44 DEFER-GBRAIN-TODOS 已 PLANNED)

## 10. 关联

- **Pattern**: `.omo/_knowledge/patterns/p44-closed-loop-pattern.md`
- **SSOT**: `.omo/DOC-LIFECYCLE.md` (本文件无复制)
- **L0 约束**: `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`
- **X2 规则**: `.omo/_truth/x2-freshness-rules.yaml:X2-FRESH-DOC-LIFECYCLE`
- **l4-kernel capability**: `audit.doc_lifecycle`
- **omo_lint 14 维度**: `projects/omo/src/omo/omo_lint.py`
- **omo governance 第 7 项**: `projects/omo/src/omo/omo_audit.py:governance_check_doc_lifecycle`
- **pre-commit 钩子**: `.pre-commit-config.yaml:omo-doc-lifecycle-gate`
- **P45 PLANNED task**: `.omo/tasks/planned/P45-DOC-LIFECYCLE.yaml`
- **P44 闭环模式**: `.omo/_knowledge/patterns/p44-closed-loop-pattern.md`

## 11. 版本

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0.0 | 2026-06-22 | P45 R5 初版 (4 类 + 第 14/15 维度 + 第 7 项 + 254 files) |
