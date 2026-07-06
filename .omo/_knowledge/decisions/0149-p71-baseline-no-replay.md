---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-06
related:
  - 0146-8stage-stability-declaration.md
  - 0148-round-trip-playbook.md
  - ../../patterns/p71-baseline-recovery-pattern.md
  - ../../audits/2026-07-02-p0-baseline-recovery-closeout.md
supersedes: []
---

# ADR-0149: P71 Baseline 防重做 (Round 5d)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

P71 baseline-recovery pattern (2026-07-02) 已经在
`.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md` 形式存在。
本 ADR-0149 把它**提升为正式 ADR**, 防 P71 历史踩坑**重做**:

- 3 类声明/执行鸿沟 (类 A 路径错位 / 类 B 工具未接 / 类 C CI 永红) 已识别, 4 GaC 规则已修复
- 未来若发现 P71 类症状, 必先 cite P71 pattern + ADR-0149, 走 5 阶段恢复流程,
  **而不是径直 "新增 X" 或 "修补 Y"**

**这是 P72 守门的反向应用**: 不重做历史决策 ≠ 不重做历史模式还原 (recovery)。

---

## 1. 触发与历史

### 1.1 2026-07-02 P71 事件

P71 实证的 3 类"声明绿/执行红"漂移:

| 类 | 案例 | 修复 |
|----|------|------|
| **A. 路径错位** | PR#4 baseline 漂移 (声明在 tracked SSOT, 实际写 gitignored) | **4 GaC 规则** (X1/L0/META-CR-X1-EVIDENCE-RUNNABLE 等) |
| **B. 工具未接** | 9 check-* scripts 0 caller | 集成到 gac-local-gate.py CI skip matrix |
| **C. CI 永红** | doctor + project-layer-index 检查失败 | commit hook + 增量修复 |

**5 阶段恢复流程**:
1. 症状捕获 (CI 红灯、用户报警)
2. 根因分类 (3 类)
3. 短期堵漏 (单 commit fix)
4. 长期治理 (GaC 规则入 registry)
5. 守门安装 (CI hook 拦 regression)

### 1.2 4 GaC 守门规则

P71 治本后 4 个 GaC 规则永久在线:

- **CR-X1-EVIDENCE-RUNNABLE**: SSOT 声明的工具必须能在工作树跑
- **CR-L0-BOS-DOMAIN-NORM**: BOS 域命名规范化 (类 A 防)
- **CR-META-BIN-NAMING**: meta bin 命名规范 (类 B 防)
- **CR-META-BIN-ORPHAN**: meta bin 0 caller 检测 (类 B 防)

---

## 2. 决策

### 2.1 P71 pattern 提级 ADR

`.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md` 不变,本 ADR
建立** ADR 索引反向 chain**, 让 P71 模式可发现 (不被遗忘):

```
未来 P71 类症状
  ↓ 搜索 ".omo/_knowledge/decisions/" 找 ADR-0149 (本 ADR)
  ↓ cite pattern + ADR-0149, 走 5 阶段恢复
```

### 2.2 防重做的具体动作

| 防动作 | 谁负责 | 何时触发 |
|--------|--------|----------|
| 4 GaC 规则在线 | bin/gac-local-gate.py | 每次 commit + push |
| CR-META-BIN-ORPHAN | bin/check-toolbox-ssot.py | CI per commit |
| CR-X1-EVIDENCE-RUNNABLE | governance-evolution validate | 每次 pre_release |
| AGENTS.md §8.1 已引 P71 pattern | (持续) | (持续) |

### 2.3 反向 review 流程

未来若发现 P71 类症状:

```
□ cite .omo/_knowledge/patterns/p71-baseline-recovery-pattern.md
□ cite ADR-0149 (本 ADR)
□ 走 5 阶段: 症状 → 根因 → 短期 → 长期 → 守门
□ 不绕过 CI hook (no --no-verify 除非 P72 原则 2 紧急情况)
□ 不写 "快速修补" PR 直接 commit (走 PR review)
```

---

## 3. 与其他 ADR 关系

| ADR | 关系 |
|-----|------|
| ADR-0146 | 8 阶段稳定性声明 (R5a) — 也是反向 review 类型 (本 ADR 同模板) |
| ADR-0148 | Round-Trip 7 步 (R5c) — P71 防重做嵌入 round-trip 第 5 步 (ADR review) |

---

## 4. 不在本 ADR 范围

- ❌ 改 P71 pattern 文件 (现有规范)
- ❌ 改 4 GaC 规则 (已守门)
- ❌ 改 gac-local-gate.py skip 矩阵

---

## 5. 关联

- [.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md](../../patterns/p71-baseline-recovery-pattern.md) (pattern SSOT)
- [.omo/_knowledge/audits/2026-07-02-p0-baseline-recovery-closeout.md](../../audits/2026-07-02-p0-baseline-recovery-closeout.md) (P71 实证 closeout)
- [ADR-0148](./0148-round-trip-playbook.md) (Round 7 步嵌入 P71 守门)
- [.omo/_knowledge/standards/adr-process.md](./../../../.omo/_knowledge/standards/adr-process.md) (通用 ADR 流程)

---

## 6. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (R5d, P71 baseline 防重做 ADR 提级) |
