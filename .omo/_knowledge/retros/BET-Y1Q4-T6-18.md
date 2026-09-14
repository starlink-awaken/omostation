---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T6-18 Closeout Retro — 架构健康度 6 维度周报
bet_id: BET-Y1Q4-T6-18
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T6-18 Closeout Retro

> **TL;DR**: 交付 `bin/arch-health-meter.py` (6 维度数据采集) + `bin/ops/architecture-health-weekly.sh` (周报 wrap) + `.omo/standards/architecture-health-six-dim.md` (SSOT) + `bin/ops/launchd/com.omostation.arch-health-weekly.plist` (launchd 示例) + 实时报告 `docs/reports/architecture-health-weekly.md`. verify: arch-health-meter exit 0; weekly wrap exit 0 写 9.2KB 报告; gac-local-gate 57 checks ALL GREEN (含 script-registry VALIDATION PASSED 611 scripts registered).

## Deliverables

- `bin/arch-health-meter.py` (270 LOC, 可执行) — 6 维度数据采集器 (场景/架构/进化/运维/防腐/感知), `--json` 或 `--week` 模式
- `bin/ops/architecture-health-weekly.sh` (28 LOC, 可执行) — wrap 上面 + 写 `docs/reports/architecture-health-weekly.md` + snapshot
- `bin/ops/launchd/com.omostation.arch-health-weekly.plist` (37 LOC) — launchd snippet, 周一 9:00 跑
- `.omo/standards/architecture-health-six-dim.md` (110 LOC) — 6 维度 SSOT 定义
- `docs/superpowers/specs/2026-09-05-t6-18-architecture-health-weekly-design.md` (85 LOC) — 专用 spec
- `docs/reports/architecture-health-weekly.md` + `docs/reports/architecture-health-weekly-20260906.md` — 实时报告 + snapshot
- `bin/_registry/scripts/governance/arch-health-meter.yaml` + `bin/_registry/scripts/observability/architecture-health-weekly.yaml` — 2 脚本登记
- `.omo/_truth/registry/governance-checks.yaml` — script_baseline 585→587 (+2)
- `docs/plans/3y-bet-ledger.yaml` — T6-18 entry 补 spec binding + write_surfaces + CE matrix + status flip
- `.omo/_knowledge/retros/BET-Y1Q4-T6-18.md` — 本 retro

## Q1 实际耗时 vs appetite?

Appetite 2 days。本轮 ~1.5h (meter 写 + spec + 登记 + 模板 + 自动化 wrap + 修 gac gate baseline delta 错算)。

## Q2 done_when 是否全部通过?

| 条目 | 结果 |
|------|------|
| 6 维度指标定义文档 | **PASS** (`.omo/standards/architecture-health-six-dim.md` 110 行, 6 维度表 + 互独立性 + 现有 4 health_score 关系) |
| 数据采集脚本 | **PASS** (`bin/arch-health-meter.py` 270 行, 6 dim 函数 + JSON/markdown 输出) |
| 周报模板 + cron 接入 | **PASS** (`bin/ops/architecture-health-weekly.sh` wrap + launchd plist snippet; 实测跑出 9.2KB markdown) |
| `test -f docs/reports/architecture-health-weekly.md` | **PASS** |
| `make gac-local-gate` | **PASS** (57 checks ALL GREEN) |

## Q3 过程中发现的与 plan 不符的事实（打假）?

### 1. 6 维度定义在原 plan 中是抽象概念, 具体口径要落地到 4 类数据源
原 plan 写 "场景/架构/进化/运维/防腐/感知 6 维度" 但未指定每个维度的具体数据源和计算方式. 落地后发现:
- **场景**: 扫 `docs/scene-cards/*.yaml` frontmatter 统计 lifecycle 分布
- **架构**: 调 `bin/gac/check-sfop-slots.py --json` + `check-execution-chain.py --json` 拿 SFOP 槽位 + DFSQ 链路 OK 状态
- **进化**: 解析 `docs/plans/3y-bet-ledger.yaml` 拿 done/total + 30d done_at 增量
- **运维**: 读 `.omo/state/system.yaml` 的 `runtime.daemons` 段拿 online/total (本 worktree 0 daemons 是因为 submodules 没 init)
- **防腐**: 调 `bin/gac/meta-doctor.py --json` + `bin/ssot/ssot-guardian.py` 拿 drift count
- **感知**: 解析 `.agents/skills/INDEX.md` (regex "共 N 个 skills") + 数 `.omo/_truth/registry/agent-workflows/*.yaml`

**教训**: 6 维度数字化的口径在 spec 阶段就要落, 不能留到实现时才定.

### 2. `bin-quota-diff` 校验在主仓 `bin/` 净增 1 须删 1 (加 baseline 同步)
新增 2 脚本 (arch-health-meter.py + architecture-health-weekly.sh) 必须 `script_baseline` 同步 +2, 否则 gac gate fail. 这次踩坑: 第一次只加 1 (585→586), gate 报 "baseline_delta=1" 仍 fail; 加到 2 (586→587) 才 pass. 教训: gac gate 用 git HEAD 而非 working tree, 改完需先 commit 再 check.

### 3. `script-registry validate` 对未 commit 的新脚本报 orphan
validator 跑 `git ls-tree HEAD bin/`, 未 commit 的新脚本在 HEAD 看不到, 报 orphan. 教训: 写新 bin 脚本后立即 stage + commit, 否则 registry validate fail.

### 4. launchd snippet 的 plist 拼写陷阱
ProgramArguments 数组里 `-c` 后必须用 `string` 而非 array 元素. 写错会被 launchd 拒载. 这次按 Apple 官方 plist 模板写, 验证 OK.

### 5. `meta-doctor.py` 的 JSON 字段名因版本而异
不同版本的 `meta-doctor.py` 返回 `drift_count` 或 `findings` 列表, 字段名不一致. meter 用 `or` 链 fallback 多字段, 但应统一上游. 后续需 governance-surfaces 拉齐 meta-doctor 输出 schema.

### 6. system.yaml runtime.daemons 在 worktree 里是 0
本 bet 在 worktree 跑, submodules 没 init, 没有运行时 daemon 进程, system.yaml 的 `runtime.daemons = {}`. meter 报 `0/0 在线 (0%)` 不是 bug, 是真实状态. 在 main 仓跑会显示真实 daemon 数.

## Q4 净增减

- 新文件 8: arch-health-meter.py, architecture-health-weekly.sh, com.omostation.arch-health-weekly.plist, six-dim.md (standard), spec, weekly report + snapshot, 2 脚本登记
- 改文件 3: 3y-bet-ledger.yaml (T6-18 entry), governance-checks.yaml (script_baseline bump), 2 retrofit commits
- 工作区外: 0

## Q5 下一个认领本 track 的 agent 需要知道什么?

1. **6 维度在 main 仓才会显示真实数据**: 本 bet 在 worktree 跑, submodules 没 init, 多数维度显示 0. 真机跑应能看到 skill 数 40+, workflow 31+, bet done 数 8/325, etc.

2. **周报 cron 不自动注册**: launchd plist 是示例, 需人手动 `cp ~/Library/LaunchAgents/` + `launchctl load`. 周报不跑不影响其他工具.

3. **6 维度 vs 4 health_score**: 本 bet 的 6 维度是周报视角 (诊断), 不替代 health_score (单值治理). 两者平级, 不合并. 在 `.omo/standards/health-metrics-semantics.md` 顶部 SSOT 不变.

4. **维度间故意正交**: 不要合并为 weighted_score, 会丢失诊断能力. 6 维度平行展示, 异常维度单独分析.

5. **后续候选 bet**:
   - T6-18a: 趋势图 (用 `docs/reports/architecture-health-weekly-*.md` 历史数据画 SVG 折线)
   - T6-18b: 维度间相关性分析 (哪些维度同步升降)
   - T6-18c: 接入 cockpit `cockpit health six-dim` 子命令

6. **dependency 满足**: T6-17 (文档 SSOT 治理) 已 done, 本 bet 依赖满足. 后续调用 `arch-health-meter.py` 的工具 (Cockpit, weekly-report) 可依赖本 bet.

## Closeout refs

- run: `20260906T004630Z-project-code-change-ef151ba4`
- branch: `work/bet-y1q4-t6-18`
- spec: `docs/superpowers/specs/2026-09-05-t6-18-architecture-health-weekly-design.md` (accepted)
- verify: arch-health-meter.py exit 0 (JSON + markdown), weekly wrap exit 0 写 9.2KB 报告, gac-local-gate 57 checks ALL GREEN, script-registry 611 scripts PASSED
- dependency: BET-Y1Q4-T6-17 (done, 文档 SSOT 治理)
- 被依赖: 未来 cockpit `health six-dim`, weekly-report 自动消费, trend-visualization bet
