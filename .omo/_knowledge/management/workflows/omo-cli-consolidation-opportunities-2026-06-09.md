---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: omo-cli-consolidation-opportunities-2026-06-09.md
deprecated-since: 2026-06-23

---

# omo-cli 固化机会扫描 — 2026-06-09

> 范围: `scripts/` (18 .py = 4044L + 8 .sh) + `omo-cli` 现有 30+ 子命令
> 目的: 识别可沉淀为 `omo <verb> <noun>` 的散装操作, 减少脚本散落 + 统一 reporting

---

## 一、omo-cli 现状 (2026-06-09)

cli.py 路由 30+ 子命令 (line 7-167):

| 类别 | 现有子命令 |
|------|-----------|
| 服务 | serve, daemon, sse-daemon |
| 治理 | governance, audit, history, x-axis, sop? |
| 状态 | state, health, inspect, dashboard |
| 知识 | knowledge, bos, delivery, evidence, ledger |
| 任务 | task, bridge, cards, gc, alert |
| 成本 | cost, observability, log, metric |
| 能力 | capability, registry, scenario, pkg |
| 元 | metacognition, phase14-16, i0, healing |

---

## 二、scripts/ 散装操作清单

### 2.1 check 系列 (5 个, 878L) — 最高价值固化

| 文件 | 行数 | 现有归属 | 建议命令 |
|------|------|----------|----------|
| `check-vault-paths.py` | 283 | X-Plane 战役 | `omo check vault-paths` |
| `check-port-registry.py` | 95 | X-Plane 战役 | `omo check ports` |
| `check-interfaces.py` | 215 | X-Plane 战役 | `omo check interfaces` |
| `check-cross-deps.py` | 74 | 5+3+1 审计 | `omo check cross-deps` |
| `check-index-coverage.py` | 211 | 文档治理 | `omo check index-coverage` |
| `check-state-goals-alignment.py` | 104 | 治理对齐 | `omo check state-goals` |

**统一价值**:
- 共享 `--json` / `--quiet` / `--fix` 标志
- 集中 reporting 到 `.omo/_delivery/omo-check-<date>.md`
- pre-commit 钩子只需注册 `omo check all`

### 2.2 sop 系列 (2 个, 915L) — 治理 SOP 闭环

| 文件 | 行数 | 建议命令 |
|------|------|----------|
| `sop_precheck.py` | 476 | `omo sop precheck` |
| `sop_check_format_version.py` | 439 | `omo sop check-format-version` |

**价值**: SOP 是 5+3+1 治理宪章的执行入口, 散在 scripts/ 没人用, 升级为 omo 子命令后被 cockpit 调度。

### 2.3 sync/validate 系列 (4 个, 804L)

| 文件 | 行数 | 建议命令 | 说明 |
|------|------|----------|------|
| `sync_omo_state.py` | 539 | `omo sync state` | 已存在于 omo 治理 (governance audit 关联), 收敛 |
| `validate_protocol_registry.py` | 76 | `omo validate protocols` | 新增 |
| `test-report.py` | 118 | `omo test report` | 已有 `omo audit`, 视为其 alias |
| `cross_repo_stdio_smoke.py` | 71 | `omo smoke cross-repo` | 新增 |

### 2.4 demo/scenario 系列 (3 个, 699L) — 演示收敛

| 文件 | 行数 | 建议命令 | 说明 |
|------|------|----------|------|
| `demo-bos-system.py` | 110 | `omo demo bos-system` | 已有 omo scenario, 收敛 |
| `llm_bos_demo.py` | 181 | `omo demo llm-bos` | 同上 |
| `llm_healthwork_scenario.py` | 408 | `omo scenario healthwork` | 收敛 |

**风险**: demo 脚本一次性价值高, 固化为 schema 后需先抽 `DemoSpec` Pydantic 模型。

### 2.5 一次性 phase 脚本 (4 个, 407L) — 不建议固化

| 文件 | 行数 | 说明 |
|------|------|------|
| `phase3_acceptance.py` | 249 | 一次性 P3 验收 |
| `p60_refactor_dispatch.py` | 93 | P60 dispatch 一次性 |
| `p61_action_mapping.py` | 118 | P61 action mapping |
| `p63_daemon_stdin.py` | 116 | P63 daemon stdin |

**理由**: phase-specific, 复用率为 0, 固化为 omo 子命令会污染命名空间。

### 2.6 shell 脚本 (8 个) — 保留 shell

| 文件 | 用途 | 建议 |
|------|------|------|
| `ci_local.sh` | CI 模拟 | 保留 |
| `perf-bos-baseline.sh` | BOS 性能 | 保留 |
| `agent_doc_review_check.sh` | Agent 文档审查 | 保留 |
| `preserve-m1-files.sh` | M1 节点保护 | 保留 |
| `p63_plist_smoke.sh` | launchd 烟测 | 保留 |
| `p66_plist_retry.sh` | launchd 重试 | 保留 |
| `release.sh` | 多仓库发布 | **可选** Python 重写为 `omo release` |
| `check-interfaces.py` 等 | 已列 2.1 | (混淆, 实际是 .py) |

**shell 保留理由**: 多数是 CI/diagnostic one-liner, Python 重写 ROI 低。`release.sh` 是真候选。

---

## 三、固化优先级 (按 ROI 排序)

### P0 - 立即固化 (重复 + 高频)

1. **`omo check all`** — 统一 6 个 check-*.py, 用户只记一个命令
   - 复用 omo_audit 的 reporting + 退出码语义
   - pre-commit 钩子简化: `omo check all --fix`
   - 工作量: 半天

2. **`omo sync state`** — 收敛 sync_omo_state.py
   - 已半集成 omo governance, 只差 CLI 入口
   - 工作量: 1h

### P1 - 中期固化 (价值/工作量平衡)

3. **`omo sop {precheck, check-format-version}`** — 治理 SOP 闭环
   - 工作量: 半天

4. **`omo validate protocols`** — 协议注册表验证
   - 工作量: 2h

5. **`omo smoke cross-repo`** — 跨仓库 stdio 烟测
   - 工作量: 2h

### P2 - 后期固化 (演示)

6. **`omo demo {bos, llm-bos, healthwork}`** — 演示收敛
   - 需先抽 `DemoSpec` schema
   - 工作量: 1d

### P3 - 不建议固化

- phase3_acceptance / p60-66_*.py — 一次性脚本
- 5 个 check-state-*.py 类 — 已归到 P0

---

## 四、固化设计原则 (KISS + DRY)

### 4.1 命令族命名

```
omo <verb> <noun>
omo check {all|vault-paths|ports|interfaces|cross-deps|index-coverage|state-goals}
omo sop {precheck|check-format-version}
omo validate {protocols|...}
omo sync {state}
omo smoke {cross-repo|...}
omo demo {bos|llm-bos|healthwork}
```

### 4.2 共享标志

```python
@dataclass
class CheckResult:
    name: str
    status: Literal["ok", "warn", "error"]
    violations: list[Violation]
    fix_suggestion: str | None = None
    elapsed_ms: int = 0
```

所有 check 命令输出统一结构, JSON / table / quiet 三模式。

### 4.3 reporting 集中

固化后所有 check/sop/validate 结果统一落到:
- `.omo/_delivery/omo-{verb}-{date}.md` (Markdown 报告)
- `.omo/_delivery/omo-{verb}-{date}.json` (机读)

### 4.4 pre-commit 钩子

固化后 `.git/hooks/pre-commit` 简化为:
```bash
uv run --directory projects/omo python -m omo check all --fix
```

---

## 五、风险

1. **omo-cli 体积膨胀**: 当前 30+ 子命令, 再加 4-5 个 verb 会到 40+。需重构为 plugin 架构。
2. **scripts 散落仍存在**: 固化后旧 .py 仍可调, 需 deprecation 周期 (3-6 个月)。
3. **测试覆盖**: 6 个 check 脚本需统一测试基线 (≥80% coverage)。

---

## 六、行动建议

| 阶段 | 任务 | 估时 | 价值 |
|------|------|------|------|
| W3 | 抽出 `omo check` 框架 (base + 1 个 check) | 0.5d | 高 |
| W3 | 迁移 5 个 check-*.py 到 omo_check/ | 0.5d | 高 |
| W3 | `omo sync state` CLI 入口 | 1h | 中 |
| P3+ | sop/validate/smoke 固化 | 1d | 中 |
| P3+ | demo 收敛 (需 DemoSpec) | 1d | 低 |

---

## 七、与 W3 声明式 BOS URI 关系

W3 里程碑 (BOS URI 声明式注册 + 可观测性) 的产物是 `bos://` schema + 监控钩子, **可观测性部分** 天然适合走 `omo check bos` (`omo check bos-registry-freshness` / `omo check bos-stdio-timeout` 等), 形成声明式 + 检查式闭环。

---

## 附: 排除清单 (经查不需要固化)

- `.omo/_delivery/*.md` (107 个) — 一次性交付物, 不是工具
- `.omo/_knowledge/{design,decisions,drafts,process,reference,usage}/` — 沉淀文档
- `.omo/_control/{governance-overlay,debt-dashboard,task-center}/` — 控制面 SSOT
- `.omo/_archive/` — 历史归档

> 结论: scripts/ 18 .py 中 **6 个 check 系列 + 4 个 sync/validate/smoke 系列** 是高价值固化对象, 累计工作量 ≈ 2.5d, 价值是统一入口 + pre-commit 闭环 + reporting 集中。
