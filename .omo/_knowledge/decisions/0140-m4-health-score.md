---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0132-l0-mof-m4-metamodel.md
  - 0129-state-projection-plane-phase3.md
  - ../../../../bin/m4-health-score.py
  - ../../../projects/ecos/.omo/_derived/m4-health.json
supersedes: []
---

# ADR-0140: M4 Health Score 量化与派生面落地 (Round 3b)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

把 `bin/mof-bootstrap.py all` 升级为**量化分数** + 派生面 JSON + 与 OMO `health_score` 平行。
当前基线: 99.17 / 100 (mof-validate 98.62% × 60% 权重 + 4-check 30/30 + meta mapping 5/5 + ADR accepted 5/5)。

**关键设计**:
- 与 OMO `health_score` (system.yaml) **平行**, 不替代 (后者是 workspace-wide score)
- 派生面 `.omo/_derived/m4-health.json` 跟随 ADR-0129 范式 (子模块内, gitignored)
- 4 个 metric 维度: mof-validate (60%) + 4-check (30%) + meta mapping (5%) + ADR accepted (5%)
- 1 个 bonus: 回归测试 (单独展示, 不计入 overall)

---

## 1. 触发

`mof-bootstrap.py all` 仅输出 PASS/FAIL, 不能:
- 量化 M4 治理成熟度
- 历史对比 (退化检测)
- 被 OMO 雷达 cron 纳入监控

OMO governance-evolution-roadmap 提到"operating-rhythm 8 个 initiative 推进 60→80/100", M4 是其一。
本 ADR 把 M4 分数独立成可观察量。

---

## 2. 分数规则

```
overall_score (0-100) =
  mof-validate 通过率 × 60%        (60 分)
  + 4-check strict PASS × 30%      (30 分)
  + 8+4+4 映射完整 × 5%             (5 分)
  + 9 个 M4 ADR 全 ACCEPTED × 5%    (5 分)

bonus (单独展示, 不计入 overall):
  regression_tests 40 通过率 × 100% (0-100)
```

设计意图:
- mof-validate 60% — 模型驱动工程核心指标, 数据校验通过率
- 4-check 30% — 模型自反验证通过率
- meta mapping 5% — 元模型桥接完整度
- ADR accepted 5% — 治理纪律合规度

---

## 3. 实施产物

### 3.1 bin/m4-health-score.py (主仓根脚本)

5 命令:
- 默认: 人类可读分数 + 详情
- `--json`: JSON 输出
- `--emit`: 写派生面 `.omo/_derived/m4-health.json`
- `--compare`: 与上次派生面对比, 退化警告
- `--with-live-tests`: 跑 40 tests 覆盖 bonus 字段 (避免循环依赖)

### 3.2 派生面 schema

`projects/ecos/.omo/_derived/m4-health.json` (gitignored via submodule .gitignore):

```json
{
  "version": "1.0.0",
  "generated_at": "ISO-8601",
  "workspace": "...",
  "git_sha": "...",
  "branch": "...",
  "metrics": {
    "mof_validate": { "passed": 1361, "total": 1380, "rate": 98.62, "score": 59.17, "weight": 60 },
    "four_check_strict": { "all_pass": true, "score": 30, "weight": 30 },
    "meta_mapping_8x4x4": { "all_mapped": true, "score": 5, "weight": 5 },
    "adr_accepted_9": { "accepted": 8, "total": 8, "score": 5, "weight": 5 }
  },
  "bonus": { "regression_tests_40": { "passed": 40, "total": 40, "rate": 100 } },
  "overall_score": 99.17,
  "adrs": { "closed_when": "overall_score == 100 AND all main ADRs ACCEPTED" }
}
```

### 3.3 OMO 集成 (后续, 本 ADR 不实施)

`bin/omo-state-cleanup.py` 可读 `.omo/_derived/m4-health.json` 嵌入 governance-evolution-roadmap report。
本 ADR 仅产出派生面, 后续治理整合是 Round 3+ 工作。

---

## 4. 循环依赖陷阱

`m4-health-score.py` 内部需要**确认 tests 通过**。但直接 sub-process 跑 `tests/integration/m4_metamodel/run_all.py` 会反向调用 `m4-health-score CLI`(T41 测试),**形成无限递归**。

**解决**:
- `score_40_tests()` 默认**回放**派生面中的 bonus 字段(无 recursion)
- `score_40_tests_live()` 单独命令行调用(开发者主动跑)
- 操作顺序: 先 `python tests/integration/m4_metamodel/run_all.py` 写 m4-health.json → 再 `python bin/m4-health-score.py` 回放

---

## 5. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| 健康分计算 | `bin/m4-health-score.py` | 99.17/100 |
| 派生面 gitignored | `git -C projects/ecos check-ignore -q .omo/_derived/m4-health.json` | rc=0 ✓ |
| 42 测试全过 | `tests/integration/m4_metamodel/run_all.py` | 42/42 PASS |
| 4-check strict 不破 | `bin/mof-bootstrap.py all` | 0/0/0/0 |

### 当前 99.17/100 与目标 100/100 差距分析

- mof-validate: 1361/1380 通过率 = 98.62% × 60% = 59.17/60, **失 0.83 分**
- 失分根因: 19 个 MCPTOOL 节点的 `tool_name` + `server` 占位空字符串
- 治本路径: Round 3+ ADR 单独处理 (不在本 ADR 范围)

---

## 6. 不在本 ADR 范围

- ❌ 自动 rebuild 派生面 (后续 cron hook 在 Round 3+)
- ❌ 修 mof-validate 98.62% → 99% (Round 3d 任务)
- ❌ 改 OMO health_score SSOT (workspace-wide score, 与 M4 是平行, 不联动)
- ❌ 改 mof-bootstrap.py (PASS/FAIL 输出保持, 分数是上层建筑)

---

## 7. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (主决策)
- [ADR-0137](./0137-derived-plane-relocation.md) (派生面路径规范, 本 ADR 沿用)
- [ADR-0129](./0129-state-projection-plane-phase3.md) (派生面范式)
- [ADR-0139](./0139-model-driven-8stage-revival-rejected.md) (本 ADR 前一步, Round 2c 拒回)

---

## 8. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 3b, 99.17/100 baseline) |
