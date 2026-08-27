---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: omo-cicd-stack-2026-06-10.md
deprecated-since: 2026-06-23

---

# §14 omo 仓 CI/CD 全栈 — 集成 + 自动化 (Round 31 起步)

> **状态**: 起步 (Round 31 P0)
> **作者**: 老王
> **定位**: omo 仓**所有 workflow + pre-commit + cron** 的 SSOT 入口
> **目的**: 让 reviewer 5 分钟看清 omo 仓 CI/CD 全栈, 跨仓 owner 看到模板可复用
> **链接**: §11.2 (omo_audit/omo_io) + §11.4 (omo_lint 起步) + §12.5.1 (跨仓 baseline 同步) + §13 (omo_lint 工具家族)

---

## §14.0 一句话总结

omo 仓 CI/CD 全栈 = **4 个 GitHub Action workflow + 2 个 cron + 1 个 pre-commit 链**, 自动化覆盖"代码质量 / 跨仓同步 / X1 审计契约守门" 3 大主题, 让任何代码提交到 main 前必过 5 段守门.

## §14.1 4 GitHub Action workflows (omostation 根)

| Workflow | 文件 | 触发 | Job 数 | 主题 |
|----------|------|------|-------|------|
| `ci-lint.yml` | `.github/workflows/ci-lint.yml` | push / PR / cron 周一 | 5 (R12+R15) | actionlint / check-yaml / shellcheck / omo-logs-audit / **omo-lint-schemas** |
| `audit-rollout-monthly.yml` | `.github/workflows/audit-rollout-monthly.yml` | cron 每月 1 号 01:00 UTC | 1 (R28) | 跨仓 baseline 聚合 |
| (其他 17 个 workflow) | `agora-ci.yml` / `cockpit-ci.yml` / `ecos-ci.yml` / `gbrain-ci.yml` / ... | 各仓 CI | 1+ | 项目级 CI (omostation 根视角不归 §14 范畴) |
| (各仓 workflow) | `projects/<repo>/.github/workflows/*.yml` | 各仓 CI | 1+ | 子项目 CI |

`ci-lint.yml` 详情 (R12 P1 起步 + R15 P1 加 5th job + R21 加 3 规则 + R29 加规则 4 + R30 加规则 5):

```yaml
# 5 jobs (R12-30 累积):
# 1. actionlint — GitHub Actions YAML 静态分析
# 2. check-yaml — 所有 .yml/.yaml 可解析
# 3. shellcheck — scripts/*.sh 静态安全检查
# 4. omo-logs-audit — JSONL 漂移检测 (Round 12 P0 接力)
# 5. omo-lint-schemas — 4-5 规则 X1 审计契约守门 (Round 15-30 累积)
```

## §14.2 2 个 GitHub Action workflow (omo 仓)

| Workflow | 文件 | 触发 | Job | 主题 |
|----------|------|------|------|------|
| `ci.yml` | `projects/omo/.github/workflows/ci.yml` | push / PR | N | omo 仓 CI 基础 (原有, 不属 §14 范畴) |
| `audit-baseline-monthly.yml` | `projects/omo/.github/workflows/audit-baseline-monthly.yml` | cron 每月 1 号 00:00 UTC | 1 (R28) | omo 仓 baseline 月度自动 refresh |

`audit-baseline-monthly.yml` 详情 (R28 P0):
```yaml
# 月度自动 refresh baseline:
# 1. checkout v4 + setup-python 3.13 + pip install uv
# 2. 跑 `omo logs audit --baseline-init` (写新 baseline)
# 3. commit + push (baseline 漂移变化才 commit, 避免空 commit)
# 4. 漂移无变化 → exit 0 跳过 commit
```

## §14.3 pre-commit 链

`.pre-commit-config.yaml` (R12 P1 起步 + R13 P1 加 omo-logs-audit):

| Hook | 引入 | 校验 |
|------|------|------|
| `check-yaml` (pre-commit-hooks v5.0.0) | R12 P1 | 所有 .yml/.yaml 可解析 |
| `omo-logs-audit` (local) | R12 P1 / R13 P1 | baseline-check 模式, 增量 fail |

pre-commit 触发: `git commit` 前自动跑, fail 即拒绝 commit.

`omo-logs-audit` hook 详情 (R12-R13 累积):
```yaml
- id: omo-logs-audit
  name: omo logs audit (baseline check, 0 增量才通过)
  entry: uv run --directory projects/omo python -m omo.cli logs audit --baseline-check .omo/_knowledge/_audit_baseline.json
  language: system
  pass_filenames: false
  stages: [pre-commit]
```

## §14.4 omo_lint schemas 5 规则 (R15-30 累积)

`uv run --directory projects/omo python -m omo.cli lint schemas` 跑 5 段校验:

1. **schema-kwarg-missing** (R15 P0) — 7 consumer `.append()` 都传 `schema=`
2. **missing-z-timestamp** (R21 P0) — 8 schema 都继承 `ZTimestampModel`
3. **no-required-fields** (R21 P0) — 8 schema 都有 ≥1 必填字段
4. **missing-from-all** (R29 P0) — `omo_io_schemas.__all__` 含 8 class 全名
5. **cross-consumer-import** (R30 P0) — 7 consumer 互不依赖, 仅依赖底层 SSOT

详见 §13 章节.

## §14.5 跨仓 baseline 同步 (R26-28 累积)

| 步骤 | 工具 | 状态 |
|------|------|------|
| 各仓 baseline 文件 | `<repo>/.omo/_knowledge/_audit_baseline.json` (lock-file) | omo 已就位 |
| 每月 1 号 cron | `audit-baseline-monthly.yml` (omo 仓) + `audit-rollout-monthly.yml` (omostation 根) | 已配置 |
| 跨仓聚合工具 | `omo audit-rollout` CLI (R27 P0) | 已就位 |
| rollout 报告目录 | `.omo/_delivery/audit-rollout/<date>.json` | 自动创建 |

详见 §12.5.1.

## §14.6 自动化总览 (Round 31 final)

```
[代码 commit]
   ↓
[pre-commit omo-logs-audit] → baseline-check 0 增量 → 允许 commit
   ↓
[git push]
   ↓
[ci-lint.yml 5 jobs] → actionlint + check-yaml + shellcheck + omo-logs-audit + omo-lint-schemas
   ↓
[PR merge to main]
   ↓
[每月 1 号 00:00 UTC: audit-baseline-monthly.yml] → omo 仓 baseline refresh + commit
   ↓
[每月 1 号 01:00 UTC: audit-rollout-monthly.yml] → 跨仓 audit-rollout + 写报告
```

5 个守门点, 任何 1 个 fail 都阻断代码流转.

## §14.7 §11 / §12 / §13 / §14 关系

- **§11** = AppendOnlyLog 模式实现 (10 段 + 7 段收口)
- **§12** = 跨仓契约 (13 子节 + baseline 同步)
- **§13** = omo_lint 工具家族 (6 子节 5 规则)
- **§14** = CI/CD 全栈 (本节, 5 守门点)

§14 整合 §11/§12/§13 散落各 workflow 段, 收口成"o 5 守门点"总览.

## §14.8 Round 31+ 候选

- [x] §14.0 起步 (本 commit)
- [x] §14.1 omostation 根 4 workflows 索引
- [x] §14.2 omo 仓 2 workflows 索引
- [x] §14.3 pre-commit 链
- [x] §14.4 omo_lint 5 规则 (引用 §13)
- [x] §14.5 跨仓 baseline 同步 (引用 §12.5.1)
- [x] §14.6 自动化总览
- [x] §14.7 §11/§12/§13 关系
- [x] §14.8 Round 31+ 候选
- [ ] §14.9+ 实施 §13.3 规则 8 (sort-keys-default) — R30+ 留, 治本价值低

---

**§14 章节总览** (Round 31 起步):

| 子节 | 主题 | 状态 |
|------|------|------|
| §14.0 | 一句话总结 | ✅ Round 31 |
| §14.1 | omostation 根 4 workflows | ✅ Round 31 |
| §14.2 | omo 仓 2 workflows | ✅ Round 31 |
| §14.3 | pre-commit 链 | ✅ Round 31 |
| §14.4 | omo_lint 5 规则 | ✅ Round 31 |
| §14.5 | 跨仓 baseline 同步 | ✅ Round 31 |
| §14.6 | 自动化总览 | ✅ Round 31 |
| §14.7 | §11/§12/§13 关系 | ✅ Round 31 |
| §14.8 | Round 31+ 候选 | ✅ Round 31 |
| **总** | **§14 9 子节** | ✅ 起步 |
