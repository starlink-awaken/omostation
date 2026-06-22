# DOC-LIFECYCLE — `.omo/` 文档生命周期规则 (P45)

> **生效日**: 2026-06-22
> **Owner**: governance-team
> **Status**: active (沿用 omo_lint 第 14 维度 `cmd_lint_doc_lifecycle` 机器校验)
> **SSOT**: 本文件 (no 复制)
> **Version**: v1.0.0

---

## 1. 目的

`.omo/` 现有 1214 个 .md + 775 个 .yaml 散落在 6 个平面（`_control/_delivery/_knowledge/_log/_truth/_archive`）+ 12 个顶层目录。所有文档目前缺统一生命周期管理——**写完就成死文档**是当前最大浪费。

本文件定义 **4 类文档 + frontmatter schema + 引用规则**，让机器能识别每类文档的状态。

---

## 2. 4 类文档

| 类别 | 含义 | 路径模式 | 例子 |
|------|------|---------|------|
| **SSOT** | 机器 SSOT (被代码 load) | `.omo/_truth/*.yaml` + `.omo/_truth/registry/*.yaml` + `projects/ecos/.../L0-constraints.yaml` | x1-x4, mutation-surfaces, mof-version |
| **CONTRACT** | 人+工具契约 (标准/规范) | `.omo/standards/*.md` + `.omo/standards/*.yaml` | omo-governance-surfaces.md, task-yaml-rules.md |
| **PATTERN** | 可复用模式 (模板) | `.omo/_knowledge/patterns/*.md` | p43-closed-loop-pattern.md, p44-closed-loop-pattern.md |
| **ARCHIVE** | 历史档案 (决策追溯) | `.omo/_archive/`, `.omo/_knowledge/audits/`, `.omo/_knowledge/management/`, `.omo/_knowledge/decisions/` | 31 个 phase closeout reports |

> **关键**：路径模式是**参考**而非强约束。**frontmatter 的 `lifecycle:` 字段才是权威**。

---

## 3. frontmatter Schema

每个 `.md` / `.yaml` 文件**必须**（建议）有 frontmatter：

```yaml
---
status: active | deprecated | archived | experimental
lifecycle: ssot | contract | pattern | history | state
owner: <domain>
last-reviewed: YYYY-MM-DD
superseded-by: <file>  # 可选, status=deprecated 时填
---
```

### 3.1 status 状态机

```
active ──→ deprecated ──→ archived
   ↓           ↓
   └→ archived  (立即归档)
```

| status | 含义 | 行为 |
|--------|------|------|
| `active` | 当前生效 | lint OK |
| `deprecated` | 失效但保留 (compat) | lint WARN + 提示 superseded-by |
| `archived` | 仅供追溯 | lint OK (但应物理位于 _archive/) |
| `experimental` | 实验性 | lint OK (标注 alpha) |

### 3.2 lifecycle 类别

| lifecycle | 含义 | 必有 status |
|-----------|------|------------|
| `ssot` | 机器 SSOT | `active` 或 `deprecated` |
| `contract` | 契约 (人+工具) | `active` 或 `deprecated` |
| `pattern` | 模板 (可复用) | `active` 或 `archived` |
| `history` | 历史 (决策追溯) | `archived` |
| `state` | 运行时状态 (机器写) | 自动 (无需 frontmatter) |

### 3.3 owner 域

允许值（按现有 omo worker policy）：
- `governance-team` (L0/治理)
- `architecture-team` (架构)
- `cockpit-team`, `omo-team`, `kairon-team`, `agora-team`, `gbrain-team`, `metaos-team`, `runtime-team`, `ecos-team`
- `human-product` (用户面向)
- `unassigned` (无主，需认领)

---

## 4. 引用规则

### 4.1 SSOT 引用约束 (硬约束, omo lint ERROR)

- 任何改 `.omo/_truth/x[1-4]*.yaml` 必须有 commit msg `[X1-X4-CHANGE]`
- 任何引用 SSOT 路径的代码改时必须 grep 全部引用方
- 当前 SSOT load 方: 7 处 (mof-state-bridge.py × 4 + c2g/task_builder.py × 4 + c2g 其它)

### 4.2 CONTRACT 引用约束 (软约束, omo lint WARN)

- standards 0 引用 + 缺 status = WARN
- 建议加 `status: deprecated` 或移 `_archive/`
- 不强制（保留人类判断权）

### 4.3 PATTERN 引用约束 (软约束)

- 模式被 `.omo/_knowledge/` 下其他文档引用 ≥ 1 次 = active
- 否则 WARN 提示归档

### 4.4 ARCHIVE 引用约束 (无约束)

- 不 lint 引用
- 物理位于 `.omo/_archive/` + `.omo/_knowledge/audits/` + `.omo/_knowledge/management/`
- 不需 frontmatter

---

## 5. omo lint 维度

### 5.1 第 14 维度: `omo lint doc-lifecycle`

```bash
uv run --directory projects/omo python -m omo.cli lint doc-lifecycle
```

输出:
- 死文档清单 (path + 0 引用 + 缺 status)
- frontmatter 覆盖率统计
- 矛盾路径清单
- 建议归档清单

**WARN only** (不阻塞 commit)

### 5.2 第 15 维度: `omo lint doc-archival-suggestions`

```bash
uv run --directory projects/omo python -m omo.cli lint doc-archival-suggestions
```

输出软建议: "💡 建议 `X.md` 加 `status: deprecated` 或移 `_archive/`"

### 5.3 omo governance 第 7 项: `check_doc_lifecycle`

```bash
cd projects/omo && uv run omo governance
```

第 7 项评分:
- frontmatter 覆盖率 > 80% = 100 分
- 死文档占比 < 30% = 100 分
- 矛盾路径 = 0 = 100 分
- 加权进总分

---

## 6. 扩散同步 (Diffusion Sync)

### 6.1 AGENTS.md (根工作区)

新增 §SSOT 治理表:
```markdown
| 文档类别 | 路径模式 | 引用方 | 状态机 |
|---------|---------|--------|--------|
| SSOT | .omo/_truth/* | mof-state-bridge / c2g / omo | status: active\|deprecated |
| CONTRACT | .omo/standards/* | omo_lint / AGENTS.md | status: active\|deprecated |
| PATTERN | .omo/_knowledge/patterns/* | (新模式开新文件) | status: active\|archived |
| ARCHIVE | .omo/_archive/ + audits/ + management/ | (决策追溯) | status: archived |
```

### 6.2 .omo/INDEX.md (总入口)

新增 4 类入口:
```markdown
## SSOT (机器)
- X1-X4 governance, X2 freshness, X3 value, X4 consistency
## CONTRACT (人+工具)
- 41 standards
## PATTERN (模板)
- P43/P44 closed-loop
## ARCHIVE (历史)
- 30 audits + 142 management
```

### 6.3 MCP 自动发现 (agora mcp.py:321)

**兼容扩展**：现有 `bos_discovery: discovered URIs from AGENTS.md` 机制保留。**新增** status 字段：
- AGENTS.md 中加 `<!-- doc-status: active -->` 行
- agora mcp 解析时一并暴露 status 给客户端

### 6.4 BOS URI 兼容

**零影响**：所有现有 `bos://memory/`, `bos://governance/`, `bos://analysis/`, `bos://persona/`, `bos://capability/` 域不变化。doc-lifecycle 是**文件级元数据**而非 URI 变更。

### 6.5 cockpit CLI 兼容

**零影响**：cockpit 是唯一人类入口，doc-lifecycle 输出由 `omo lint` 命令暴露，cockpit 通过 `governance` 命令间接看。

---

## 7. 演进规则

### 7.1 新增文档

```
1. 选 lifecycle 类别 (ssot/contract/pattern/history)
2. 加 frontmatter (status=active 起步)
3. 提交时 omo lint doc-lifecycle 必过
4. pre-commit 钩子自动跑
```

### 7.2 文档退役

```
1. status: active → deprecated (在 frontmatter 改)
2. 加 superseded-by: <新文件> (如有)
3. last-reviewed: 当前日期
4. 通知引用方: c2g brainstorm 主题变化 / AGENTS.md 更新
```

### 7.3 文档归档

```
1. status: deprecated → archived
2. git mv 到 .omo/_archive/ 或 .omo/_knowledge/management/
3. 加 .omo/_archive/INDEX.md 条目
4. c2g radar 季度审计
```

---

## 8. 关联

- **Pattern**: `.omo/_knowledge/patterns/p44-closed-loop-pattern.md`
- **治理宪章**: `.omo/standards/omo-governance-surfaces.md`
- **L0 约束**: `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`
- **X1 治理策略**: `.omo/_truth/x1-governance-policies.yaml`
- **X2 保鲜规则**: `.omo/_truth/x2-freshness-rules.yaml`
- **omo_lint 14 维度**: `projects/omo/src/omo/omo_lint.py:cmd_lint_doc_lifecycle`
- **omo governance 第 7 项**: `projects/omo/src/omo/omo_governance.py:check_doc_lifecycle`
- **pre-commit 钩子**: `.pre-commit-config.yaml:omo-doc-lifecycle-gate`
- **l4-kernel capability**: `projects/l4-kernel/src/l4_kernel/registry.py:audit.doc_lifecycle`
- **AGENTS.md SSOT 治理表**: `AGENTS.md:§SSOT 治理`
- **MCP 自动发现**: `projects/agora/src/agora/server/mcp.py:321` (兼容扩展)

---

## 9. 版本

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0.0 | 2026-06-22 | P45 R1 初版 (4 类 + frontmatter + 引用规则) |
