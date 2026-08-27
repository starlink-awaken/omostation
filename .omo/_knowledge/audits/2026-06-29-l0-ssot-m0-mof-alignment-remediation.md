---
status: active
lifecycle: audit
owner: governance-team
last-reviewed: 2026-06-29
related:
  - 2026-06-29-l0-ssot-m0-mof-alignment.md
  - ../standards/doc-ssot-contract.md
---

# L0/SSOT/M0/MOF 对齐 — 修复执行手册 (2026-06-29)

> 关联: [主审计报告](2026-06-29-l0-ssot-m0-mof-alignment.md) (分析结论 + 6 处 drift).
> 本文件是**可照着执行的闭环手册**: 精确行号 + diff 预览 + 影响面 + 验证命令.
>
> 执行时机: **等工作树稳定** (当前并发 agent 46 文件 dirty). 老王/任何 agent 照本手册闭环.

---

## §0 深度验证修正记录 (诚实)

主审计报告落盘后, 深度验证 (grep + 跑工具 + 读源码) 纠正 3 处判断:

| 项 | 原判 | 修正 | 证据 |
|:---|:-----|:-----|:-----|
| **D1** | INVENTORY 死链 `../PROJECTS.yaml` | **双 SSOT 分裂** | `.omo/PROJECTS.yaml` 存在 (120 行, 停更 6-17, 无权威声明); `docs/project-registry.yaml` (212 行, 今天更新 6-29, 明写 "唯一读源 SSOT + CI 门禁"). 真问题是两表并存违背 SSOT |
| **D5** | 改 layer_enum 一行 | **改两处** (Python + YAML) | `gac-validate.py:44` 硬编码 `LAYER_ENUM` set (实际校验用), `governance-checks.yaml:128` 仅声明. 只改 YAML 不生效 |
| **治本** | 新建 `X2-FRESH-NAV-DOC-META` content rule | **KISS 降级** (改文档 + X2 时间 review) | X2 freshness mechanism 是 `threshold_days+action` (时间), 非 content-pattern. content-check 作用域限定复杂. 遵 YAGNI: 待 D2 类漂移 ≥3 次再建机器 check |
| **D4** | mof-manage 漏注册 | **mof-manage 跑不通** (更深, P1) | `bin/mof-manage status` 抛 `ComposerError`: mof-capabilities.yaml 多文档 (line1 frontmatter `---` + line6 正文 `---`), mof-manage:16 用 `safe_load` (单文档) 读崩. 根因 P45 frontmatter 化 vs P47 mof-manage 实施时序断裂. 需 `safe_load_all` 修复 (见 §4.4) |

---

## §1 D1 双 SSOT 分裂 (P1, 最严重)

### 1.1 真相

| 维度 | `.omo/PROJECTS.yaml` | `docs/project-registry.yaml` |
|:-----|:---------------------|:-----------------------------|
| 行数 | 120 | 212 |
| 最后更新 | 2026-06-17 (**停更 12 天**) | 2026-06-29 (**今天**, 活) |
| 权威声明 | ❌ 无 (自述"只记录稳定身份") | ✅ "唯一读源 SSOT + CI 门禁 doc-ssot-lint + drift 检测 gen-project-registry" |
| 引用方 | INVENTORY + `.omo/_knowledge/design/` 老文档 (MASTER-BLUEPRINT/INSIGHTS/phase5-*/sharedbrain-*) | ARCHITECTURE/README/CLAUDE/CONTRIBUTING/LAYER-INDEX (所有入口) |

### 1.2 修复方案

**决策**: `docs/project-registry.yaml` 是真 SSOT (权威声明 + 活 + CI 门禁锚定). `.omo/PROJECTS.yaml` 遗留.

**三步**:

1. **INVENTORY.md 改指针** (5 处 `../PROJECTS.yaml` → `../../docs/project-registry.yaml`):
   ```bash
   # 路径算: .omo/_truth/INVENTORY.md → ../../docs/project-registry.yaml
   sed -i '' 's|\.\./PROJECTS\.yaml|../../docs/project-registry.yaml|g' .omo/_truth/INVENTORY.md
   ```

2. **`.omo/PROJECTS.yaml` 处置** — 两条路:
   - **A (归档)**: 移到 `.omo/_archive/PROJECTS.yaml.legacy` + 留 redirect pointer
   - **B (转 pointer)**: 内容替换为单行 `> 已迁移至 docs/project-registry.yaml, 本文件废弃`
   - 老王建议 **B** (KISS, 保留路径不破坏老引用, 内容指新 SSOT)

3. **老 design 文档引用** (`.omo/_knowledge/design/` 11 处): 标 `legacy` 不强改 (历史文档, 渐进), 或批量 sed (若 owner 评估值得)

### 1.3 验证

```bash
grep -rn "PROJECTS\.yaml" .omo/_truth/INVENTORY.md    # 应 0 (或只剩 pointer 引用)
python3 bin/doc-ssot-lint.py                           # 应仍 0 冲突
python3 bin/check-cross-refs.py 2>&1 | tail            # INVENTORY 引用全可达
```

---

## §2 D2 INVENTORY 版本号漂移 (P1)

### 2.1 精确过时点 (grep 确认就 2 行)

`.omo/_truth/INVENTORY.md:15-16`:
```
> **P43 收口状态**: governance 100 A+, 9 子项目 ruff 全 0,
> mof-version v0.0.12, c2g→omo→mof 闭环模式文档化
```

### 2.2 修复

删硬编码运行时声称, 改指针:

```diff
-> **P43 收口状态**: governance 100 A+, 9 子项目 ruff 全 0,
-> mof-version v0.0.12, c2g→omo→mof 闭环模式文档化
-> (`.omo/_knowledge/patterns/p43-closed-loop-pattern.md`)。
+> 运行时状态 (governance score / mof-version / lint) 见各自 SSOT:
+> `bin/mof-version show` / `.omo/_truth/mof-version.yaml`.
+> P43 闭环模式文档化: `.omo/_knowledge/patterns/p43-closed-loop-pattern.md`.
```

同时 `last-reviewed` bump 2026-06-29.

### 2.3 验证

```bash
grep -E "v0\.0\.[0-9]+|governance 100" .omo/_truth/INVENTORY.md   # 应 0
bin/mof-version show                                              # 确认 SSOT 真值
```

---

## §3 D3 ssot-7-domain-schema 过时 (P2)

### 3.1 过时点 (grep 确认)

| 行 | 内容 | 实际 |
|:---|:-----|:-----|
| 10 | `日期: 2026-05-30 \| 版本: v1.0` | bump 2026-06-29 |
| 11 | `convergence.yaml` (顶层路径) | 实际 `.omo/_knowledge/convergence.yaml` (路径漂移) |
| 42,138 | `tasks/active/*.yaml` ×2 | 实际 `tasks/planned/` (archive/archived/blocked/done/planned/registry/remediation) |
| 59,61,62,143,155,246 | `convergence.yaml` ×6 | 路径漂移 (非死链, 文件在 _knowledge/) |
| 76 | `KOS baseline 7327 (2026-05-30)` | 运行时声称, 改指针或删 |

### 3.2 修复

```bash
# tasks/active → tasks/planned
sed -i '' 's|tasks/active/|tasks/planned/|g' .omo/standards/ssot-7-domain-schema.md

# convergence.yaml 路径修正 (顶层 → _knowledge/)
sed -i '' 's|`convergence\.yaml`|`.omo/_knowledge/convergence.yaml`|g' .omo/standards/ssot-7-domain-schema.md

# 日期 bump
sed -i '' 's|2026-05-30|2026-06-29|g; s|版本: v1.0|版本: v1.1|' .omo/standards/ssot-7-domain-schema.md

# KOS baseline 运行时声称 → 指针 (行 76 手动)
```

### 3.3 验证

```bash
grep -c "tasks/active" .omo/standards/ssot-7-domain-schema.md     # 应 0
grep "convergence.yaml" .omo/standards/ssot-7-domain-schema.md    # 路径含 _knowledge/
ls .omo/_knowledge/convergence.yaml                                # 确认存在
```

---

## §4 D4 mof-capabilities 元数据漂移 (P2)

### 4.1 过时点

- `updated_at: "2026-06-20"` (停 9 天) + `version: "2.0"` (静态, 不反映 mof-version v0.0.107)
- `tools` 段缺 `mof-manage` 注册 (bin/mof-manage 实体存在, P47 R1 implemented, 自指悖论: mof-manage 管理 registry 但自己没注册)

### 4.2 修复

`tools` 段补注册 (插 `mof-enforce` 之后):

```yaml
  mof-manage:
    path: bin/mof-manage
    description: MOF 能力注册表管理 (查看/验证/更新 mof-capabilities.yaml)
    commands: [status, validate, update]
    usage: "bin/mof-manage status"
```

frontmatter bump:

```diff
-version: "2.0"
-updated_at: "2026-06-20"
+version: "2.1"
+updated_at: "2026-06-29"
```

**注**: `mof-reason` 注册路径指 `projects/ecos/src/ecos/ssot/tools/mof-reason.py` (非 bin/), 命名一致但入口分散 — 保留 (ecos 承载 MOF 元模型, mof-reason 是 ecos 内工具, 合理). 不改.

### 4.3 验证

```bash
bin/mof-manage status                           # 工具可跑
python3 bin/gac-mof-validate.py                 # 应仍 132✓ (不校验 tools 段, 无风险)
grep "mof-manage" .omo/_truth/registry/mof-capabilities.yaml   # 注册存在
```

### 4.4 mof-manage bug (深度验证发现 — D4 真核心, 升级 P1)

**症状**: `bin/mof-manage status` 抛 `yaml.composer.ComposerError: expected a single document in the stream`.

**根因**: `mof-capabilities.yaml` 是**多文档** (line 1 frontmatter `---` + line 6 正文 `---`), `bin/mof-manage:16` 用 `yaml.safe_load()` (单文档) 读 → 遇第二个 `---` 崩.

**时序断裂**: P45 (frontmatter 化) 给 mof-capabilities.yaml 加 frontmatter, P47 R1 (mof-manage 实施) 写读代码没跟进 `safe_load_all`. 对比正确范式 — `gac-validate.py:48-52` 注释明写 "用 `safe_load_all` 取正文 (最后非 None 文档), 同 c2g strip_frontmatter 模式".

**修复** (`bin/mof-manage:16`):
```python
# 修前 (崩):
return yaml.safe_load(REGISTRY_FILE.read_text())

# 修后 (多文档兼容, 同 gac-validate 范式):
docs = list(yaml.safe_load_all(REGISTRY_FILE.read_text()))
return next((d for d in reversed(docs) if d is not None), {})
```

**重要**: 修后 `bin/mof-manage status` 才能跑 (§4.3 验证依赖此 fix). 这是 D4 比"漏注册"更严重的问题 — **工具本身跑不通**, 不只是元数据漂移. 修复顺序: **先 fix mof-manage (§4.4) → 再补注册 (§4.2) → 再 status 验证 (§4.3)**.

**附带检查 (2026-06-29 扫描实证)**: 同类时序断裂潜伏风险 — bin/ 里 `safe_load(` + 读 `_truth/` 的 **5 候选**:

| 工具 | 状态 |
|:-----|:-----|
| `bin/mof-manage` | 🔴 **已实证崩** (mof-capabilities.yaml frontmatter) |
| `bin/mof-act` | ⚠️ 待核查 (读哪个 _truth 文件 + 有无 frontmatter) |
| `bin/gac-m1-sync` | ⚠️ 待核查 |
| `bin/mof-version` | 🟢 疑假阳性 (mof-version.yaml 无 frontmatter, safe_load OK) |
| `bin/agent-workflow.py` | ⚠️ 混合用 safe_load + safe_load_all, 待核查具体读法 |

**正确范式对照** (用 `safe_load_all`): `adr-coverage` / `agent-workflow` / `gac-bootstrap` / `gac-executor` / `gac-gc` / `gac-drift` / `gac-export-agents` / `gac-hook-pre-edit`.

**建议**: 修 mof-manage 后, 逐一跑其余 4 候选的命令, 确认潜伏风险数 (预期 1-2 个真崩, mof-version 假阳性).

---

## §5 D5 L4 治理盲区 (P1)

### 5.1 双定义真相

```python
# bin/gac-validate.py:44 (实际校验用, 硬编码 Python set)
LAYER_ENUM = {"M0", "L0", "L1", "L2", "L3", "I0", "X", "meta"}   # ← 无 L4
```

```yaml
# .omo/_truth/registry/governance-checks.yaml:128 (仅声明, gac-validate 不读)
layer_enum: [M0, L0, L1, L2, L3, I0, X, meta]   # ← 无 L4
```

后果: 任何 `layer: L4` 规则 → `gac-validate.py:82` `if rule["layer"] not in LAYER_ENUM: errors.append` → 校验失败 → 所以 **0 条 L4 规则** → l4-kernel 整层游离 GaC.

### 5.2 修复 (两条路, 老王建议 B)

#### 路 A: 补 L4 + 补规则
```python
# gac-validate.py:44
LAYER_ENUM = {"M0", "L0", "L1", "L2", "L3", "L4", "I0", "X", "meta"}
```
```yaml
# governance-checks.yaml:128
layer_enum: [M0, L0, L1, L2, L3, L4, I0, X, meta]
```
+ 为 l4-kernel 补 Stage/Gate / boundary / freshness 规则 (与其他层对齐).

#### 路 B (KISS + YAGNI, 老王推荐): 补 enum + 显式豁免 ADR
同上改两处 enum, 但**不补规则**, 记 ADR-0114 声明豁免:

**ADR-0114 草稿**:
```markdown
# ADR-0114: L4 自我层 GaC 强约束豁免

## 状态
accepted (2026-06-29)

## 背景
gac-validate LAYER_ENUM 历史漏 L4 → 0 条 L4 规则 → l4-kernel 整层游离 GaC.
5+4+1+1 架构演进时, L4 (自我层) 后加, enum 未跟上.

## 决策
1. LAYER_ENUM 补 L4 (gac-validate.py:44 + governance-checks.yaml:128), 允许未来按需加规则
2. 当前 L4 不补强约束规则, 显式豁免

## 理由
- l4-kernel 变更频次低 (自我层管理面, 非业务热路径)
- l4-kernel 自身 CI (projects/l4-kernel/) 已守质量
- 当前 0 条 L4 规则, 执行层全绿 (GaC drift 0), 无盲区事故
- YAGNI: 待 l4-kernel 变更频次升 / 出事故, 再补规则

## 后果
- l4-kernel 变更不触发 GaC 规则 (靠项目自身 CI)
- 未来加 L4 规则无需再改 enum
```

### 5.3 验证

```bash
python3 bin/gac-validate.py 2>&1 | tail    # enum 改后 schema 校验仍过 (纯扩展)
python3 bin/gac-drift.py                    # 应仍 0 drift
# 补一条 layer:L4 测试规则 → gac-validate 应通过 (验证 enum 生效) → 删测试规则
```

---

## §6 治本 (KISS 降级版, 防复发)

### 6.1 方案: 改文档 (治标) + X2 时间 review (软约束)

遵 [[architecture-overengineering-lesson]]: 不建复杂 content-pattern 机器 check (YAGNI), 用已有 X2 freshness 软约束.

**新增 X2 rule** (`.omo/_truth/x2-freshness-rules.yaml`):

```yaml
  - rule_id: X2-FRESH-NAV-DOC-REVIEW
    title: 导航/契约文档定期 review 运行时声称
    type: nav_doc_freshness
    status: active
    created: '2026-06-29'
    target: .omo/_truth/INVENTORY.md
    freshness:
      mechanism: registry-review
      threshold_days: 14
      action: warn
    owner: governance-team
    notes: >
      INVENTORY 等导航文档易内嵌过时运行时声称 (版本号/分数/计数).
      14 天 review 一次, 确保运行时声称要么指针化, 要么刷新.
      注: 本 rule 是时间软约束 (owner 定期 review), 非内容机器 check.
      若 D2 类 (内嵌版本号) 漂移反复出现 ≥3 次, 再升级为 doc-ssot-lint
      content-pattern check (STALE_PATTERNS 加 mof-version vX.Y.Z 正则).
```

### 6.2 验证

```bash
python3 bin/x2-freshness-check.py           # 新 rule 可执行
python3 bin/x2-rule-lint.py                 # rule schema 合法
python3 bin/gac-local-gate.py               # CI 门禁过
```

### 6.3 为什么不建机器 content-check (YAGNI 论证)

| 方案 | 工作量 | 风险 | 触发条件 |
|:-----|:------|:-----|:---------|
| X2 时间 review (本方案) | 低 (加 1 rule) | 软约束, 靠 owner | 立即可做 |
| doc-ssot-lint content-pattern | 中 (扩 STALE_PATTERNS + 作用域限定 lifecycle:ssot/contract) | 可能误 flag audit 报告 (audit 合法含版本号作证据) | D2 类漂移 ≥3 次 |

老王判: 当前 D2 类漂移就 INVENTORY 1 处, 不满足 ≥3 次门槛. 先软约束, 够用.

---

## §7 闭环验证 (全部修复后)

```bash
# 文档 SSOT
python3 bin/doc-ssot-lint.py                    # 0 冲突
python3 bin/check-cross-refs.py 2>&1 | tail     # 死链/路径漂移清
grep -rn "PROJECTS\.yaml" .omo/_truth/          # INVENTORY 改指 project-registry

# GaC
python3 bin/gac-validate.py                     # L4 enum 改后仍过
python3 bin/gac-drift.py                        # 0 drift
python3 bin/gac-mof-validate.py                 # 132✓

# MOF
bin/mof-version show                            # v0.0.107 (SSOT 真值)
bin/mof-manage status                           # mof-manage 注册后可跑
python3 bin/mof-m2-coverage.py                  # 19✓

# 治本
python3 bin/x2-freshness-check.py               # X2-FRESH-NAV-DOC-REVIEW 生效
python3 bin/x2-rule-lint.py                     # rule schema 合法

# 证据回路
python3 bin/evidence-smoke.py                   # resolve 仍 1.0
python3 bin/mof-drift                           # governance 趋势回升 (工作树清后)
```

---

## §8 执行顺序 (等工作树稳定后)

```
1. D1 INVENTORY 改指针 (5 处 sed) + .omo/PROJECTS.yaml 转 pointer     [5min]
2. D2 INVENTORY 删版本声称 (2 行 edit)                                [3min]
3. D3 ssot-7-domain sed (tasks/active + convergence 路径 + 日期)      [5min]
4. D4 mof-manage fix: safe_load → safe_load_all (bin/mof-manage:16)  [10min] ← 先修工具
5. D4 mof-capabilities 补 mof-manage 注册 + bump                      [5min]
6. D5 gac-validate.py:44 + governance-checks.yaml:128 加 L4           [5min]
7. D5 ADR-0114 L4 豁免 (新建)                                         [10min]
8. 治本 X2-FRESH-NAV-DOC-REVIEW (x2-freshness-rules.yaml 加 rule)     [5min]
9. 跑 §7 全套验证                                                     [5min]
10. commit (精确 git add 本手册涉文件, 不沾并发 dirty)                [按需]
```

**预计**: ~45min 闭环 (D1-D5 + 治本 + 验证 + commit).

---

## §9 关联

- 主审计: [2026-06-29-l0-ssot-m0-mof-alignment.md](2026-06-29-l0-ssot-m0-mof-alignment.md)
- 契约: [`doc-ssot-contract.md`](../../standards/doc-ssot-contract.md)
- 模式: [`doc-presentation-pattern.md`](../../standards/doc-presentation-pattern.md)
- 教训: [[architecture-overengineering-lesson]] (治本 KISS 降级依据)

---

*手册作者: 老王 (laowang-engineer) | 深度验证: grep + 7 工具 + 源码读 (gac-validate.py:44 / x2-rule-lint.py / doc-ssot-lint.py) | 执行前提: 工作树稳定 (并发 agent 46 文件 dirty 清后)*
