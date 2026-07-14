---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0081: P87 god-module 拆解 roadmap + X2 rule 交互式添加

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P87
- **Extends**: ADR-0080 (P86 pre-commit 集成)
- **Superseded by**: (无)

## Context and Problem Statement

P86 收口后, P87 调研 2 项治理 UX 工具 + 1 项 god-module 重构支持, 全部实施:

1. **god-module 14 error 文件无 roadmap**: 14 个 >1500L 文件 (gbrain doctor.ts 4825L, omo_lint.py 1560L 等), 缺乏结构化拆解路线图
2. **X2 rule 添加靠手写 YAML**: x2-rule-lint (P85) 能检测错配, 但新增 rule 仍需手写 YAML, 容易引入新错配
3. **governance-dashboard 工具覆盖不完整**: P86 仪表盘 7 工具, P87 新增 2 工具未集成

## Decision

### D1: bin/ssot/god-module-roadmap.py (P87 R1)

**新工具** (`bin/ssot/god-module-roadmap.py`):
- 解析 Python 文件 (AST) 和 TypeScript 文件 (正则启发式)
- 输出 top-level 函数/类列表 (按行数排序)
- 给出 candidates 优先级 (短函数 + 有 docstring + 少参数 → 高优先级)
- 5 步骤拆解建议 (拆 imports → 拆大类 → 抽小函数 → 验证 → 循环)

**实测**:
- `omo_lint.py` (1560L, 31 functions, 39 imports): 5 candidates 排序
- `gbrain/src/cli.ts` (1735L, 20 functions): TS 解析
- Python 实测: 1560L → 列出 top 5 函数, 27 小函数可拆
- TS 实测: TS 函数 lines 算不准 (0), 仅可看声明顺序

### D2: bin/gac/x2-rule-add.py (P87 R2)

**新工具** (`bin/gac/x2-rule-add.py`):
- 交互式 prompt 5 字段: rule_id / title / target / threshold_days / action
- 也支持 `--non-interactive` 模式 (stdin 5 行)
- 也支持 `--template` 打印 YAML 模板
- 自动分配下一个 rule_id (X2-FRESH-NEW-001, NEW-002 ...)
- 验证必填字段 (target, freshness.threshold_days/action)
- 验证 target glob 命中 (archived 豁免)
- 追加到 YAML 文件末尾 (YAML 允许多文档, `---` 分隔)
- 写完跑 `x2-rule-lint.py` 验证 (新规则必须 0 issues)

**实测**:
- 非交互模式添加 X2-FRESH-NEW-001 (target=.omo/_truth/registry/*.yaml, threshold=7, action=warn)
- 自动追加 298 bytes 到文件末尾
- x2-rule-lint 验证: 10 rules, 0 issues ✓
- 已回滚测试 rule (不污染 X2 规则库)

### D3: governance-dashboard 扩展 (P87 R3)

**新增 2 工具到 dashboard**:
- `x2-rule-add` (template 模式, 快速验证工具健康)
- `god-module-roadmap` (示例文件 `omo_lint.py`, 展示拆解能力)

**总工具数**: 7 → **9** (P87 +2)

### D4: 收口统计

**P87 工具数**: 29 → **31** 独立 bin 工具 (+2)
- `bin/ssot/god-module-roadmap.py` (新)
- `bin/gac/x2-rule-add.py` (新)

**ADR 数**: 40 → **41** (P87 +1)

**governance-dashboard 覆盖**: 7 → 9 工具

## Consequences

**正面**:
- god-module 14 error 文件有结构化拆解入口, 降低重构门槛
- X2 rule 添加零手写 YAML, 字段错配在交互阶段就被拦截
- 9 工具统一 dashboard, 单点查看全治理健康度
- X2 rule 模板可复制 (`.omo/_knowledge/standards/` 后续可收纳)
- governance-dashboard 工具数量从 7 增至 9, 治理覆盖更广

**负面**:
- TS 函数 lines 算不准 (brace_depth 启发式), 优先级排序对 TS 不如 Python 准
- X2 rule 模板不含 mechanism 全集 (6 种), P88+ 可补
- god-module-roadmap 没集成到 pre-commit (按需调用, 不阻塞)

**关联**:
- ADR-0080 → ADR-0081: 治理门禁 (P86) → 治理 UX 工具 (P87)
- god-module-roadmap 是 omo-srp-refactor skill 的"前置扫描"工具
- x2-rule-add 是 x2-rule-lint 的"对偶"工具 (lint 静态检查, add 动态生成)

## Validation

```bash
# P87 R1: god-module roadmap
python3 bin/ssot/god-module-roadmap.py projects/omo/src/omo/omo_lint.py --top 5
# 期望: 1560L, 31 functions, 27 candidates

# P87 R2: X2 rule add (template)
python3 bin/gac/x2-rule-add.py --template
# 期望: 打印 YAML 模板

# P87 R2: X2 rule add (check)
python3 bin/gac/x2-rule-add.py --check
# 期望: 9 rules 全部健康

# P87 R3: governance dashboard
python3 bin/gac/governance-dashboard.py
# 期望: 9/9 工具全部通过

# ruff 验证
ruff check bin/ssot/god-module-roadmap.py
ruff check bin/gac/x2-rule-add.py
# 期望: All checks passed!
```

## References

- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- P87 R1-R3: god-module-roadmap + x2-rule-add + dashboard 扩展
- 14 god-module error 文件: gbrain (10), omo (2), ecos (1), aetherforge (1)
- ADR-0080: P86 governance dashboard

---

*最后更新: 2026-06-25 · P87 god-module 拆解 roadmap + X2 rule 交互式添加 收口*
