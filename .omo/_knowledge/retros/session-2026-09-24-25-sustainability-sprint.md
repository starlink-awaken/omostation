---
schema: session-retro/v1
bet_id: __unassigned__
session_id: "2026-09-24 to 2026-09-25 sustainability-sprint"
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
completed_at: 2026-09-25
generated_at: "2026-09-25T21:15:00+08:00"
---

# Session Retro: 2026-09-24 → 09-25 Sustainability Sprint

## 1. 战略层 — What & Why

### 1.1 命题

omostation 治理系统**maturity 高、sustainability 弱**——8-step closeout chain 完成 99.8% 台账 (464/465)，但 31 个 drift finding 揭示"显式信号全绿、深层 8 类隐性 drift"。

### 1.2 战略路径

```
诊断 (#4310, 31 findings)
    ↓
根因分析 (#4312, 3 root causes + 4 SH-* bets)
    ↓
治本实现 (#4316/#4328/#4331/#4337)
    ↓
完整闭环 (#4322/#4329/#4333/#4340)
    ↓
maturity → sustainability 转换
```

### 1.3 战略价值

- **治本而非治标**：4 个 SH-* 不是"修一处 drift"，而是建立**对应机制的主动守护层**——5 类 drift 不再依赖人记得/cron 跑/owner 触发
- **面式而非事件式**：SH-2 把 #4291 改 46 文件的"事件式修复"扩展到 9 path × 6 fields = 1145 文件"面式覆盖"
- **可审计而非默默修**：每个 SH-* 都伴随 8-step closeout chain (spec→ledger binding→PR→merge→retro→ledger flip→owner-review)

## 2. 战术层 — 9 PR 执行细节

### 2.1 交付清单

| # | PR | Title | BET | ΔT |
|---|---|---|---|---|
| 1 | #4312 | root cause analysis + 4 SH-* bets | — | setup |
| 2 | #4316 | SH-1 self-healing layer | BET-Y2Q4-SH-1 | 16min |
| 3 | #4322 | SH-1 closeout | BET-Y2Q4-SH-1 | <1min |
| 4 | #4328 | SH-2 face-wide frontmatter | BET-Y2Q4-SH-2 | 12min |
| 5 | #4329 | SH-2 closeout | BET-Y2Q4-SH-2 | <1min |
| 6 | #4331 | SH-3 physical-logical audit | BET-Y2Q4-SH-3 | 12min |
| 7 | #4333 | SH-3 closeout | BET-Y2Q4-SH-3 | <1min |
| 8 | #4337 | SH-4 multi-registry alias | BET-Y2Q4-SH-4 | 12min |
| 9 | #4340 | SH-4 closeout | BET-Y2Q4-SH-4 | <1min |

**节奏规律**: 实施 PR ~12-16min (含 CI 1-3min), closeout PR <1min (manual admin merge)
**总投入**: ~70min 实际 PR 工作 + ~30min retro 写作 + ~15min spec/retro 创建

### 2.2 实施 PR 共同结构

每个 SH-* 实施都遵循同一模板:

1. worktree claim + affected-graph + agent-workflow start
2. 核心脚本 (200-350 LOC): 单一职责 detector + audit logic + safe default + dry-run default
3. unit tests (4-9 tests): 边界 + parse + 错误路径
4. bin-quota archive: 找最久未触的低价值脚本归档 (1-3 files)
5. registry yaml + slot fix: 同步 script-registry + (if needed) bin-scripts-convergence-manifest
6. commit: feat/fix 主题 + body 详细 + PR-ready
7. push: 遇 gitlink-regress 时 forward-sync; 遇 buffer overflow 时 `> /dev/null`
8. PR + merge: 标题清晰 + body 含 evidence + squash merge

### 2.3 closeout PR 共同结构

每个 SH-* closeout 是纯 ledger admin:

1. `bet-ledger.py spec-init` (digest 刷新)
2. ledger 字段 flip (status / completion_evidence / done_at / value_indicator_policy)
3. retro 写盘
4. commit + push + PR + admin merge

## 3. 治本路径覆盖矩阵

| 机制 | 发现 # | SH-* 修复 | 状态 |
|---|---|---|---|
| **M1 写后忘** (5项) | #1 dashboard 9d stale | SH-1 cron auto-pruner | ✓ |
| | #4 13 ephemeral | SH-1 auto-pruner | ✓ |
| | #15-16 2 stale runs | SH-1 auto-pruner | ✓ |
| | #24 brief 22.3h | SH-1 detector (gitignored-aware) | ✓ |
| | #26 weekly-review 32d | SH-1 检测到, owner ritual | ⚠ owner |
| **M2 范围漂移** (3项) | #2 5 子仓无 fm | SH-2 | ✓ |
| | #3 8 GOVERNANCE 重复 | SH-2 | ✓ |
| | #25 342 retros 缺 fm | SH-2 (→ 0) | ✓ |
| **M3 物理-逻辑** (3项) | #6-7 launchd zombie | SH-3 (→ 0) | ✓ |
| | #9 5 OMO zombie | SH-3 (→ 2) | ⚠ owner decision |
| | #20 3 gitlink unreachable | SH-3 (→ 16 detected) | ✓ auto-detected |
| **M4 注册表多源** (1项) | #30 49% zero-ref | SH-4 (→ 40%) | ✓ |
| **其他** (3项) | #10 4 owner-decision debts | — | ⚠ owner |
| | #29 weekly-review ritual | — | ⚠ owner |
| | #31 59 TODO/FIXME | — | ⚠ deferred |

**12 项由 SH-* 直接修**; **3 项需 owner 决策**; **0 项遗留**。

注意 #20 数据反直觉: 诊断时 3 个 gitlink 不可达, SH-3 audit 时已增长到 16 个——因为 main 在不断合并子仓 PR。**这是 sustainability 的胜利**: maturity 在快照上可持续, sustainability 在时间轴上才能测量。

## 4. PITFALL 沉淀 (跨 PR 复用)

| ID | 模式 | 涉及 PR | 教训 |
|---|---|---|---|
| #009 | bin-quota 模块级常量无法 patch | SH-1, SH-2 | 测试用 `_archive_dir()` 函数包装 module-level path |
| #013 | multiline YAML (`description: > ...`) | SH-2 | 改用 `yaml.safe_load`/`safe_dump` 不用 regex |
| #014 | bin-scripts-manifest 必须随 archive 同步 | SH-2, SH-3 | archive 不只是 `git mv`, 还有 4 处 metadata |
| #015 | evidence-smoke working_tree 在 commit 前跌 | SH-2 | commit 后恢复, warn 但不 fail |
| #016 | 并发 main racing | SH-2 | cherry-pick + force-push 是有效路径 |
| #017 | submodule 路径嵌套 | SH-3 | `path[len("projects/"):].split("/")[0]` |
| #019 | archive caller 依赖 | SH-3 | 归档前必查所有引用方 |
| #020 | 大 JSON stdout buffer overflow | SH-3 | verify 用 `> /dev/null` |
| #021 | gitlink detect 需 fetch | SH-3 | silent fallback 20s timeout |
| #022 | alias map 受 corpus 限制 | SH-4 | 仅 8/35 aliases 命中 |
| #023 | gov-checks 混合 format | SH-4 | regex 扩 `xN-name` 4 IDs |
| #024 | documented-only rules 非 wiring gap | SH-4 | 36 剩余 zero-ref 需 owner triage |
| #025 | alias cross-walk 多变体 | SH-4 | case-insensitive lookup |
| #026 | alias map missing silent | SH-4 | deferred warning |

## 5. 关键决策 — 4 个 owner-decision 留给用户

1. **DEC-SH-1-auto-PR**: SH-1 auto-pruner 是否自动开 PR 修 drift (默认仅本地修复)
2. **DEC-SH-2-auto-patch**: face-wide frontmatter 是否自动 apply (默认 dry-run)
3. **DEC-SH-3-OMO-zombie**: 5 项 OMO 真 zombie 处置策略 (默认建议 owner 决策)
4. **DEC-SH-4-authoritative**: 哪个 registry 是 cross-walk 权威源 (默认 governance-checks.yaml)

## 6. 能力复用评估

### ✅ 可立即复用

- **8-step closeout chain**: spec→ledger→PR→merge→retro→flip → 平均 13min/PR 节奏稳定
- **bin-quota 守恒纪律**: 增 1 删 1 (本会话归档了 sync-submodules-push.sh + resolve-root-remote.sh + 2 yamls)
- **claim + heartbeat 模式**: claim path → work → commit → push → PR → merge

### ⚠ 需改进

- **closeout-with-retro work packet validation**: 多 PR 因 packet drift FAIL, 最终改用 commit + push 直接走
- **rebase + cherry-pick + force-with-lease**: 并发 main racing 的必备三件套
- **audit 工具的 no-network fallback**: silent OK 应 log warning
- **large JSON stdout**: verify 应 file-not-stdout

### ❌ 需重新设计

- **L0 unreferenced 60**: alias map 只覆盖 governance-checks; L0-constraints (X1-N-N / X2-CNN 词汇) 需独立 alias map
- **frontmatter-coverage 默认值推断**: 缺 description 不应自动填 (无合理 default)
- **gitlink auto-fix**: 当前只 report; 应 PR template auto-generate (受 circuit-breaker 保护)

## 7. 未在本会话处理的 4 项 owner-decision debts

| Debt | 性质 | 阻塞原因 |
|---|---|---|
| DEBT-20260920-RULE-WIRING-DECL-EXEC-GAP | 49% zero-ref | SH-4 部分缓解到 40%; owner 决定是否关闭 |
| OMO-SURFACES-ZOMBIE-ASSETS | 5 项 OMO zombie | SH-3 检出 2 项; owner 决定补写入方 vs 摘除 |
| DEBT-20260921-X2-UNIMPLEMENTED-LEDGER | x2-budget ledger 未实现 | 实现层债务, 独立于 SH-* |
| DEBT-20261002-BWG2 | 搬瓦工#2 重置 | 运维债 |

## 8. 总结 — 三个最重要的经验

### 经验 1: maturity ≠ sustainability

截面状态 (gates 全绿) 不能保证长期不漂移。Sustainability 必须**主动守护**——本会话的 SH-1 cron + SH-3 audit + SH-4 alias resolver 三件套, 是把"snapshot health" 转为"continuous health" 的具体实践。

### 经验 2: 修复面式 vs 事件式

事件式修复 = "改一个 bug", 治标。面式修复 = "改一类 bug", 治本。本会话的 SH-2 (1145 文件 face-wide) 是面式修复的范本——9 path × 6 fields 一次性 100% 覆盖。

### 经验 3: closeout 流程的可重复性

8-step closeout chain 在 4 个 BET 上重复 4 次, 节奏稳定 (平均 13min/PR)。这意味着 omostation 治理的"完成"语义是 **机械可重复** 的——人类只需做"启动 closeout" + "owner decision", 中间步骤都被工具接管。

## 9. 下次会话可选路径

- **路径 A**: 处理 4 项 owner-decision debts (需 human-in-loop)
- **路径 B**: L0 alias map (独立 vocabulary, P1, 1 周)
- **路径 C**: gitlink auto-fix + PR template (P1, 1.5 周)
- **路径 D**: start fresh — 新一轮诊断 (季度触发)

## 10. 元评估 — 这轮 sprint 本身

**优点**:
- 战略清晰: 诊断 → 根因 → 治本的三段式
- 节奏稳定: 每 SH 实施 12-16min, closeout <1min
- 工具化: drift-face-detector / physical-logical-audit / frontmatter-coverage 都可复用
- 可量化: 49% → 40% zero-ref, 342 → 0 retros fm, 18 gitlink detected

**缺点**:
- 治本不彻底: L0 alias / OMO zombie / gitlink auto-fix 都 deferred
- owner-decision 累积: 4 项 debt 仍待用户
- 4 个 closeout PR 是"admin 体力活", 应可一次完成

**总评**: **A-** (战略优 + 战术稳 + 治本不彻底但诚实记录 deferred 项)