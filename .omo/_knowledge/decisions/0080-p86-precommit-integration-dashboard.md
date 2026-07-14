---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0080: P86 pre-commit 集成 4 治理工具 + governance dashboard

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P86
- **Extends**: ADR-0079 (P85 X2 rule lint + adr-coverage)
- **Superseded by**: (无)

## Context and Problem Statement

P85 收口后, P86 调研 2 项治理闭环补全, 全部实施:

1. **pre-commit 治理工具零集成**: P83-P85 新增 6 个治理工具 (governance-history-insight, drift-history-insight, mof-m2-coverage, x2-freshness-check, x2-rule-lint, adr-coverage) 均无 pre-commit 集成, 治理质量靠"agent 自觉跑"
2. **治理工具输出分散**: 6 个工具各自独立输出, 无统一仪表盘, agent 难以快速判断整体健康度

## Decision

### D1: pre-commit 集成 4 治理工具 (P86 R1-R3)

**新增 4 个 pre-commit hooks** (`.pre-commit-config.yaml`):

| Hook ID | 工具 | 触发场景 | 阻塞行为 |
|---------|------|----------|----------|
| `x2-rule-lint` | bin/gac/x2-rule-lint.py | 修改 x2-freshness-rules.yaml 时 | 字段错配阻塞 |
| `mof-m2-coverage` | bin/mof/mof-m2-coverage.py | 修改 m1/m2 yaml 时 | 真正孤儿增加阻塞 |
| `adr-coverage` | bin/adr/adr-coverage.py | 修改 decisions/ 时 | 编号/INDEX 错乱阻塞 |
| `governance-dashboard` | bin/gac/governance-dashboard.py | 每次 commit | 任一治理工具失败阻塞 |

**总 hooks 数**: 22 → **26** (P86 +4)

**关键设计**:
- `pass_filenames: false` 适用于所有 4 个 (全局检查, 非单文件)
- 失败阻塞, 不只是 warn (因为治理质量是 P0 红线)
- 不需要修改 `files:` 模式 (默认全部 .py/.yaml 触发)

### D2: bin/gac/governance-dashboard.py (P86 R4)

**新工具** (`bin/gac/governance-dashboard.py`):
- 统一调用 7 个治理工具 (P83-P86):
  - governance-history-insight (P83)
  - drift-history-insight (P83)
  - x2-freshness-check (P84)
  - x2-rule-lint (P85)
  - adr-coverage (P85)
  - mof-m2-coverage (P84)
  - management-cross-ref-check (P82+P83)
- 用 subprocess 调用, 失败继续 (避免单点失败)
- 输出: 单页 dashboard, 包含每个工具 OK/FAIL 状态
- 支持 `--tools` 子集调用
- 支持 `--json` 输出

**实测**:
- 7/7 工具全部通过 ✓
- 仪表盘: "🎉 所有治理工具通过!"

### D3: 收口统计

**P86 工具数**: 28 → **29** 独立 bin 工具 (+1)
- `bin/gac/governance-dashboard.py` (新, 统一仪表盘)

**pre-commit hooks 数**: 22 → **26** (P86 +4)
- 4 个新治理 hook 全部集成

**ADR 数**: 39 → **40** (P86 +1)

**治理闭环补全**:
- 历史洞察 (P83): governance-history / drift-history
- 死链治理 (P82+P83): cross-ref scope/status/gitignore
- X2 抗熵 (P84+P85): freshness check + rule lint
- M2 schema 治理 (P84): coverage 修正版
- ADR 治理 (P85): 编号/INDEX/frontmatter 三维度
- **统一仪表盘 (P86)**: 单点入口聚合 7 工具
- **pre-commit 集成 (P86)**: 4 工具阻塞回归

## Consequences

**正面**:
- 治理工具全部接入 pre-commit, 任何 commit 自动验证, 防止治理质量静默回退
- governance-dashboard 统一入口, 1 行命令查看 7 工具健康度
- 4 新 hooks 形成完整治理门禁网
- "agent 自觉跑" 变成 "framework 强制跑", 减少治理漂移

**负面**:
- pre-commit 变长 (26 hooks), commit 时间可能 +2-3s
- governance-dashboard 串行执行 7 subprocess, 启动开销 ~3-5s
- 任一 hook 失败阻塞 commit, 紧急 commit 需要 `git commit --no-verify` 绕过 (符合预期)

**关联**:
- ADR-0079 → ADR-0080: 工具 (P85) → 集成 (P86) → 完整治理门禁
- governance-dashboard 是所有治理工具的统一抽象, 后续 P87+ 新增工具自动加入 dashboard

## Validation

```bash
# P86 R4: governance dashboard
python3 bin/gac/governance-dashboard.py
# 期望: 7/7 工具全部通过, "🎉 所有治理工具通过!"

# pre-commit hook 验证
grep -A4 "x2-rule-lint:" .pre-commit-config.yaml
grep -A4 "mof-m2-coverage:" .pre-commit-config.yaml
grep -A4 "adr-coverage:" .pre-commit-config.yaml
grep -A4 "governance-dashboard:" .pre-commit-config.yaml
# 期望: 4 个新 hook 全部注册

# 单工具验证
python3 bin/gac/x2-rule-lint.py       # 9 rules, 0 issues
python3 bin/adr/adr-coverage.py       # 38 ADRs, 100% 健康
python3 bin/mof/mof-m2-coverage.py    # 47 M2 / 1196 M1, 95.7% coverage

# ruff 验证
ruff check bin/gac/governance-dashboard.py
# 期望: All checks passed!

# pre-commit yaml 验证
python3 -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))"
# 期望: 无异常
```

## References

- P82 R1-R4: cross-ref scope/status 感知 (active:0, archived:23)
- P83 R1-R3: governance-history + drift-history 洞察 + gitignore 感知
- P84 R1-R3: M2 coverage 修正 + X2 freshness + DEBT-EVIDENCE rule 修正
- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- `.pre-commit-config.yaml`: 26 hooks
- ADR-0079: P85 治理闭环

---

*最后更新: 2026-06-25 · P86 pre-commit 集成 4 治理工具 + governance dashboard 收口*
