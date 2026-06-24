---
name: governance-phase-orchestrator
description: Use when the user requests a governance-related task, P-phase closure, doc-lifecycle audit, frontmatter remediation, drift cleanup, or any workspace-wide convergence work. Triggers on keywords: 治理, 收敛, P 阶段, governance cycle, phase closure, drift, frontmatter, commit closure, linter saturation, 4 类分类, doc-lifecycle, RISE 循环.
---

# governance-phase-orchestrator

> **P60+ 治理方法论内化 skill** — 把 P43-P59 沉淀的 17 phase 治理经验自动化。

## 适用场景

| 触发关键词 | 场景 |
|-----------|------|
| 治理 / governance | 任何 governance 相关任务 |
| 收敛 / convergence | 知识面/治理面批量收敛 |
| P 阶段 / P60+ | 新 P 阶段收口 |
| doc-lifecycle / frontmatter | 文档生命周期治理 |
| drift / mof-drift | 漂移检测与分类 |
| commit closure / 闭环 | 强制闭环纪律 |
| linter saturation / 维度饱和 | linter 维度评估 |
| RISE 循环 | 调研-调查-策略-执行-收口 |

## 核心铁律 (5 条)

1. **强制闭环**: `bin/mof-version record` 必须与 `git commit` 在同一会话内完成
2. **frontmatter 4 字段**: `status + lifecycle + owner + last-reviewed` 必备
3. **软分层优先**: 不动路径 + frontmatter 化, 真迁移只在归档面已存在时
4. **维度饱和律**: linter ≥ 15 维度时, 新能力用独立 bin 工具
5. **批量兜底**: sed/heredoc 模板化, 失败幂等

## 工作流: RISE 循环

### R (Research) — 调研 (5 min)

```bash
# 必跑 4 步
git status --short | wc -l              # 工作树累积
bin/mof-drift 2>&1 | tail -5            # drift LOW 维度
omo governance 2>&1 | tail -5           # governance score
omo lint doc-lifecycle 2>&1 | tail -15  # frontmatter 覆盖率
```

输出: `governance-snapshot.yaml` (内部临时文件, R 步结束时写)

### I (Investigate) — 调查 (10 min)

```bash
# 异常项分析
ls .omo/_knowledge/decisions/ | tail -10  # 最新 ADR 历史
cat .omo/_truth/mof-version.yaml | tail -20  # 最近 mof-version
bin/check-cross-refs.py 2>&1 | tail -10  # 历史漂移断链 (如有)
python3 bin/status-distribution.py 2>&1 | tail -15  # status 分布
```

输出: 异常项列表 + 优先级排序

### S (Strategize) — 策略 (10 min)

**必答 3 问**:

```
1. WHY (为什么)
   - 解决了什么问题? (governance score / drift / frontmatter / closure)
   - 当前量化数据

2. WHAT (是什么)
   - 至少 3 个方案 (A 轻量 / B 中量 / C 大重构)
   - 选最低风险最高价值

3. NEXT (下一步)
   - 候选清单 (留待后续 phase)
```

输出: `strategy-decision.md` (含 GOVD- 编号)

### E (Execute) — 执行 (30-60 min)

```bash
# 标准 5 步
1. 批量处理 (sed/heredoc)
2. 写 README 标注职责
3. 更新 ADR INDEX (如涉及)
4. bin/mof-version record
5. git add . && git commit -m "..."
```

### C (Closeout) — 收口 (5 min)

```bash
omo governance 2>&1 | tail -5  # 验证 100 A+
git status --short | wc -l      # 验证闭环
git log --oneline -3            # 验证 commit 落地
```

输出: 收口报告到 `.omo/_knowledge/audits/pXX-...-closeout.md`

## 维度饱和律 (P57 ADR-0053)

```
linter 维度阈值:
├─ 0-5: 新项目
├─ 6-10: 基础治理
├─ 11-14: 成熟治理
└─ ≥ 15: 维度饱和 → 新能力用独立 bin 工具
```

**禁止**: 当 linter ≥ 15 时新增子命令。
**替代**: `bin/<tool-name>.py` (P58 check-cross-refs + status-distribution 范本)。

## 治理债务识别 (3 类)

| 形态 | 例子 | 处理 |
|------|------|------|
| 结构债 | 目录错位、断链 symlink、命名冲突 | 真迁移 + 双指针 |
| 语义债 | frontmatter 缺失、status 混乱 | 批量兜底 |
| 时序债 | 累积未提交、未归档 | git commit 闭环 |

## commit-closure-recovery (P59 教训)

**触发**: `git status --short | wc -l > 100`

**恢复流程**:

```bash
# 1. 评估改动是否分多个 phase
git status --short | wc -l  # 当前累积

# 2. 按 phase 维度分批 commit
git add <phase-files>
git commit -m "chore(governance): <phase-name> — <scope>"

# 3. 每个 commit 必含语义描述
git log --oneline -10  # 验证

# 4. 收口 commit
git commit -m "chore(governance): <phase-name> 收口"
```

## 关联资源

### L0 强制约束 (5 条)
- `L0-constraints.yaml:CR-GOV-CLOSED-LOOP-01` — 强制闭环
- `L0-constraints.yaml:CR-GOV-FRONTMATTER-SCHEMA-01` — frontmatter 4 字段
- `L0-constraints.yaml:CR-GOV-DOC-CATEGORY-01` — 4 类生命周期
- `L0-constraints.yaml:CR-GOV-DIMENSION-SATURATION-01` — 维度饱和
- `L0-constraints.yaml:CR-GOV-COMMIT-FREQUENCY-01` — 工作树累积预警

### L0 Agent 工程纪律 (CR-ENG-* 8 条 · P60+ 复盘物化)

> 来源: 近期实战 (mypy 清零/bug 链/kronos flaky/radar/omo_ingress 拆分) 提炼.
> 作用: 遇到对应场景 **自动套规律**, 不靠"记住".

| CR-ID | 触发场景 | 自主决策 |
|-------|----------|----------|
| `CR-ENG-MYPY-TRUTH-01` | 看到 mypy "strict 通过" | 用 `MYPYPATH=src`/`make typecheck-report` 验证真相, 不信退出码; targeted Any 改动验证留存 |
| `CR-ENG-SSOT-POINTER-01` | 改 health/phase 等易变值 | 改 system.yaml SSOT, 文档用指针 (禁硬编码数字多处) |
| `CR-ENG-BUG-CHAIN-01` | 修 bug | 洋葱诊断 (修一见下一个), 治本 (消错误路径, 禁加 fallback 层) |
| `CR-ENG-CWD-ABSOLUTE-01` | Bash 跨项目操作 | 用绝对路径 (防 `cd X` 后 cwd 漂移, 相对路径空返回) |
| `CR-ENG-TOOL-GREP-01` | 调未知 CLI 工具 | 先 grep argparse/用法 (防 `--help` 误触发副作用如 record) |
| `CR-ENG-SRP-INCREMENTAL-01` | 拆 God Module (>1000 行) | 渐进: 纯函数先 → 核心后; 每步验证才下一步 |
| `CR-ENG-TEST-ISOLATION-01` | 写单元测试 | monkeypatch 隔离外部依赖 (禁 flaky); conditional xfail + strict (禁无条件 xfail) |
| `CR-ENG-LOOP-HONESTY-01` | 同操作反复 3+ 次 | 元认知: 思维循环 → stop/compact (禁装懂/原地反复) |

**自主决策三要素**: 感知 (关键词/CR 匹配) → 判断 (规律) → 行动 (治本). 详见 `L0-constraints.yaml` 末尾 CR-ENG-* 段.

### X1-X4 规则 (3 条)
- `X1-AUD-COMMIT-LOOP` — mof-version vs git commit 配对
- `X2-FRESH-COMMIT-FATIGUE` — 工作树累积检测
- `X4-CONS-DRIFT-VS-GOVERNANCE` — drift vs governance 一致性

### L4 capabilities (6 个)
- `gov.frontmatter_audit`
- `gov.drift_monitor`
- `gov.commit_closure`
- `gov.dimension_saturation`
- `gov.adr_index_integrity`
- `gov.rise_cycle`

### M0 桥接
- M3: `LifecycleStage.GOVERNANCE_MAINTENANCE`
- M2: `GovernanceDecision` schema
- M1: `GOV-MAINTENANCE-PHASE.yaml`

## ADR 沉淀 (P60+)

每个 RISE 循环产出 ≥ 1 个 ADR, 遵循:
- 3 段必填 (WHY / WHAT / NEXT)
- 至少 1 个被拒方案
- evidence 引用审计报告

## 失败模式 (避免)

| 失败 | 后果 | 避免 |
|------|------|------|
| mof-version 无 commit | P59 类失闭环 | 强制 commit 在 E 步第 5 步 |
| 改路径不动 frontmatter | 引用链断裂 | frontmatter 必带 |
| linter 新增子命令 | 维度饱和 (P57) | 用 bin 工具 |
| 收口无 ADR | 决策链断裂 | 必写 ADR |

## 验证清单

RISE 循环结束时必答:
- [ ] `bin/mof-version record` 已执行
- [ ] `git commit` 已落地
- [ ] 收口报告已写到 `.omo/_knowledge/audits/`
- [ ] `omo governance` = 100 A+
- [ ] 工作树累积 ≤ 50 文件
- [ ] ADR INDEX 更新 (如涉及)
- [ ] L4 capability 注册 (如涉及)

---

*最后更新: 2026-06-23 · P60 governance-phase-orchestrator skill · 沿用 P43-P59 沉淀*