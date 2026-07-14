---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# X2 Standard: Freshness Rule Definition & Lifecycle

> Status: MANDATORY | Applied: P84+
> Authority: `.omo/_truth/x2-freshness-rules.yaml` + `bin/gac/x2-rule-lint.py`

## 1. 核心目的

X2 Freshness Rules 是 eCOS 抗熵机制的核心, 每条 rule 监控某个目标 (target) 是否在阈值 (threshold_days) 内更新. 任何治理资产的健康度都需要对应 X2 rule 监控, 否则会**静默腐烂** (P45 经验).

## 2. 必填字段 (X2-RULE-LINT 校验)

每条 X2 rule 必须包含以下字段, 否则 `x2-rule-lint.py` 报 error:

| 字段 | 类型 | 约束 |
|------|------|------|
| `rule_id` | str | 格式 `X2-FRESH-XXX-NNN`, 唯一 |
| `title` | str | 简短描述 (< 80 chars) |
| `type` | str | governance_loop_freshness / governance_surface_freshness / artifact_review / project_archive / commit_closure_freshness |
| `status` | str | active / deprecated |
| `target` | str/glob | 至少匹配 1 个文件 (archived 豁免) |
| `freshness.threshold_days` | int | 正整数 (> 0) |
| `freshness.action` | str enum | `warn` / `escalate` / `error` |
| `freshness.mechanism` | str | manual-review / registry-review / governance-audit / git-commit-staleness / git-working-tree-accumulation |
| `owner` | str | 负责团队 (governance-team / architecture-team) |
| `notes` | str | 解释为什么需要这条 rule |

## 3. 添加新 rule 的工作流 (P87 R2)

### 3.1 交互式 (推荐)

```bash
python3 bin/gac/x2-rule-add.py
# 按提示输入: title / type / target / mechanism / threshold_days / action / owner
# 自动分配 rule_id, 追加 YAML, 跑 x2-rule-lint 验证
```

### 3.2 非交互式 (CI 集成)

```bash
printf "X2-FRESH-NEW-001\nMy new rule\n.omo/_truth/*.yaml\n14\nwarn\n" \
  | python3 bin/gac/x2-rule-add.py --non-interactive
```

### 3.3 模板导出

```bash
python3 bin/gac/x2-rule-add.py --template
# 输出 YAML 模板, 可手动编辑后追加
```

## 4. 校验工具

| 工具 | 用途 |
|------|------|
| `bin/gac/x2-rule-lint.py` | schema 静态检查 (9 rules 全部健康) |
| `bin/gac/x2-freshness-check.py` | 运行时检查 (target age vs threshold) |
| `bin/gac/x2-rule-add.py` | 交互式添加 (P87 R2) |
| `bin/gac/governance-dashboard.py` | 统一仪表盘 (含 9 工具) |

## 5. 编号规则 (X2-FRESH-NNN)

- `X2-FRESH-OMO-GOVERNANCE-SURFACES` — `.omo` 治理面 (registry-review)
- `X2-FRESH-DEBT-EVIDENCE-INTEGRITY` — debt closure 证据 (governance-audit)
- `X2-FRESH-MOF-VERSION-BUMP` — MOF 模型版本 (manual-review)
- `X2-FRESH-DOC-LIFECYCLE` — 文档生命周期 (registry-review)
- `X2-FRESH-COMMIT-FATIGUE` — commit 累积 (git-working-tree-accumulation, P85 R1 修正 action)

新增 rule 用 `X2-FRESH-NEW-NNN` 临时编号, 首次纳入时由人类 review 后正式编号.

## 6. 反模式

❌ **action 写复合字符串** (e.g. "warn (100 files) / escalate (500 files)") — 必须是单一 enum 值, 细分逻辑放 `notes` 字段.

❌ **target glob 0 匹配** — 写 rule 时必须先 `python3 -c "from pathlib import Path; print(list(Path('.').glob('<target>')))"` 验证.

❌ **threshold_days 写 0 或负数** — 必须正整数, 含义是"超 N 天未更新触发".

❌ **type 字段乱写** — 必须是 5 种 enum 之一, 不接受自定义.

❌ **rule_id 重复** — `x2-rule-lint.py` 自动检测, 重复即 fail.

## 7. 集成

- pre-commit hook: `x2-rule-lint` (P86 R1)
- governance dashboard: `x2-rule-lint` + `x2-freshness` (P86 R4)

## 8. References

- ADR-0078 (P84 X2 freshness 引入)
- ADR-0079 (P85 X2 rule lint)
- ADR-0080 (P86 pre-commit 集成)
- ADR-0081 (P87 X2 rule add 工具)
- ADR-0082 (P88 X2 rule template 标准化)
- `bin/gac/x2-rule-add.py --template`
- `bin/gac/x2-rule-lint.py`
