---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-02
related:
  - 0114-l4-gac-exemption.md
  - 0115-bin-governance-rationalize.md
  - 0120-runtime-health-semantics-fix.md
  - ../audits/2026-07-02-p0-baseline-recovery-closeout.md
---

# P71 Baseline Recovery Pattern — 5 阶段声明/执行鸿沟修复

> **Generated**: 2026-07-02 (post-PR#6/#7/#8)
> **SSOT**: `.omo/_truth/registry/governance-checks.yaml` (P71-CR 全集) + `bin/gac-local-gate.py` (CI skip 矩阵)
> **Purpose**: 抽象"声明绿/执行红"漂移的标准恢复流程, 防"修了一处漏了 N 处"

## 1. 模式识别 (3 类 declaration-execution gap)

```text
类 A — 路径错位 (Git-ignored SSOT)
  症状: declare 在 X (tracked), 实际写 Y (gitignored)
  案例: PR#4 c5fb0c8e 把 dependency-baseline 从 .omo/ 迁到 runtime/omo/ + 加 .gitignore:58
        → CI fresh checkout 拿不到 → dependency-baseline-drift 报 52 项
  检测: gen-dependency-baseline.py --check (CI_ONLY)

类 B — 工具未接 (文件存在 ≠ 能跑)
  症状: 工具 .py 文件存在, 但 0 caller, 0 evidence 落盘
  案例: 9 个 check-* 工具 (check-god-module/check-boundary/...) + 5 个 B 类 executor
        → 文件在, 无 caller, "声明绿/执行红"
  检测: gac-executor.py 扩展 caller 检查 + CR-X1-EVIDENCE-RUNNABLE

类 C — CI 永远红 (环境不匹配)
  症状: 工具/检测依赖 .venv/CLI/generated artifact, CI fresh checkout 无
  案例: agent-workflow-doctor 查 omo/c2g/cockpit 集成健康, CI 永红
        project-layer-index --check 找 docs/generated/ (gitignored), CI 永红
  检测: pre-commit hook 报红但本地 strict 模式绿
```

## 2. 5 阶段恢复流程

### Phase 1: 根因定位 (Path-First, 不治标)

```bash
# 1a. 跑 evidence-smoke 量化鸿沟
python3 bin/evidence-smoke.py --quiet
# 期望: 78.9 / 100 (BOS 60% + tree 20% + feedback 20%)

# 1b. 跑 mof-drift 看架构层 drift
uv run --with "pyyaml" python bin/mof-drift
# 期望: 🟡 MEDIUM < 3, 🔵 LOW < 5

# 1c. 跑 gac-drift 看 GaC 自洽
uv run --with "pyyaml" python bin/gac-drift.py
# 期望: 0 drift
```

**输出**:`evidence_health_score` + drift 列表 → 标识 A/B/C 哪类。

### Phase 2: 治本修复 (不补丁, 找 SSOT)

| 类 | 治本方向 | 工具 |
|---|---|---|
| A 路径错位 | SSOT 路径与 broker 写入路径一致 (`.omo/_truth/` ↔ omo broker `find_omo_dir`) | `bin/gen-dependency-baseline.py` 改 `BASELINE_YAML` + `.gitignore` 修 |
| B 工具未接 | 接入 `gac-local-gate.py::CHECKS` 或标 `bin/_archive/` + GaC `deprecated` | `bin/gac-local-gate.py` + `governance-checks.yaml` |
| C CI 永远红 | `CI_SKIP_CHECKS` / `CI_ONLY_CHECKS` 矩阵, 本地 strict 照跑 | `bin/gac-local-gate.py` 顶部 `os.environ.get("GITHUB_ACTIONS")` 探针 |

**关键原则**:
- ❌ 不在 CI 上"加 sleep" / "skip check" 来治标
- ❌ 不"加环境变量默认值" 来掩盖缺依赖
- ✅ 找 SSOT, 把声明/执行对齐到同一条真理
- ✅ 区分**本地运维 check** (doctor) 与 **CI contract check** (gac-gate), 各自归类

### Phase 3: lane 守门 (commit 粒度)

`.omo/standards/doc-ssot-contract.md` + `bin/change-lane-check.py`:
- 每个 commit 只改一个 lane (governance_state / code / governance_code / docs / runtime_snapshot)
- 5 lane 混合 → **manual merge** (ISC-22), 不 squash 自动合
- pre-commit hook 拦下混 lane commit, 强制人 split

**典型 lane 划分** (P71 实证):

| 文件 | Lane |
|------|------|
| `.omo/state/system.yaml` | governance_state |
| `.omo/state/system_health.yaml` | runtime_snapshot |
| `.omo/standards/*.md` | governance_state |
| `.omo/_truth/registry/governance-checks.yaml` | governance_code |
| `bin/*.py` | code |
| `docs/project-registry.yaml` | code |
| `AGENTS.md` / `CLAUDE.md` | docs |

### Phase 4: 守护规则化 (防复发)

每类根因 → 1 条 GaC 规则:

| 根因 | 守护规则 |
|------|---------|
| 路径错位 | `CR-L0-SSOT-PATH-NORM` (待加) — verify `BASELINE_YAML` 与 `find_omo_dir` 路径一致 |
| 工具未接 | `CR-META-BIN-ORPHAN` (P3-1 加) — 0 caller 工具标 ghost |
| 声明未跑 | `CR-X1-EVIDENCE-RUNNABLE` (P2-1 加) — executor 必须有 evidence 落盘 |
| CI 环境漂移 | `CR-META-CI-SKIP-MATRIX` (待加) — verify `CI_SKIP_CHECKS` ∪ `CI_ONLY_CHECKS` 覆盖所有 CI 不适用项 |

### Phase 5: 元治理递归 (GaC 治 GaC)

`gac-drift.py` + `gac-executor.py` + `gac-bootstrap.py` 三件套, 检测 GaC 自己的漂移:
- 注册表规则 vs 实际执行
- 规则声明 executor vs 文件存在
- M1/M2 schema 与 instance 一致

**关键元规则**:
- 任何 P 阶段修复 → 必加 1 条 GaC 规则
- 任何 GaC 规则加 → 必跑 `gac-validate --gate` 验证
- `gac-validate` 必跑 (CI_ONLY 时 strict 兜底)

## 3. 与既有模式的关系

- **P43 Closed-Loop Pattern** — 7 阶段模型, P71 嵌入 Phase 4 (DEPLOYMENT) → 5 阶段 recovery
- **P44 Closed-Loop Pattern** — 审计循环, P71 Phase 1 + Phase 5 对应"症状发现"和"自愈"
- **GaC 7 机制** (NORTH-STAR.md) — P71 是机制 4 (drift + 自愈) 的实例化
- **CR-X4 一致性集中度** (X4 占 60/139 规则) — P71 加的新规则是 X4/X1(meta 层), 治本必须加重 X4

## 4. 复用清单 (Recovery 时 Checklist)

```markdown
- [ ] Phase 1: 跑 evidence-smoke + mof-drift + gac-drift 量化鸿沟
- [ ] Phase 2: 找 SSOT, 不在 CI 上治标
- [ ] Phase 3: 每个 commit 单 lane, pre-commit hook 守门
- [ ] Phase 4: 每根因 → 1 条 GaC 规则
- [ ] Phase 5: gac-validate + gac-drift + gac-executor 三件套
- [ ] 验证: make gac-local-gate + bin/evidence-smoke.py (PASS + score ↑)
- [ ] PR: squash merge, body 含 commit-by-commit 解释
- [ ] 持久化: 写 pattern (本文件) + audit (closeout) + AGENTS.md pointer
```

## 5. 失败模式 (反模式)

- ❌ "在 CI 上加 sleep" / "改 ignore 规则绕过" — 治标, 漂移会复现
- ❌ "忽略 drift warning" — GaC 价值在于"看见", 不是"忽视"
- ❌ "修一个文件多 commit" — 拆 commit 应按 lane, 不按文件大小
- ❌ "在 PR body 写 'fixes everything'" — PR body 是审计证据, 应 commit-by-commit
- ❌ "用 untracked 文件" — SSOT 应 tracked, runtime artifact 应 gitignore (二选一)
