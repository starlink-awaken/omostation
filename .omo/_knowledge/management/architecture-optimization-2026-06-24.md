---
category: workflows
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-24
---

# 整体架构优化建议 — 2026-06-24

> 基于当前 workspace 状态扫描:
> - omo governance audit: 100.0 A+
> - omo state health: 12 services, 7 healthy, 2 failed, 3 unmanaged
> - BOS invocations (24h): 0
> - git submodule dirty: 14/18 子模块有未提交修改
> - omo lint direct-omo-io: PASS (刚修复)
> - code_freeze: true

## 优先级矩阵

| 优先级 | 领域 | 问题 | 影响 | 建议动作 |
|:------:|------|------|------|----------|
| P0 | 子模块治理 | 14/18 子模块 dirty,部分删除大量文件未提交 | 代码丢失、指针不可重现、CI 失败 | 立即批量提交或回滚 |
| P0 | 运行时服务 | agentmesh-gateway / gbrain-index failed; kos/runtime-mcp/sharedbrain-bos-mcp unmanaged | 跨层调用失效,BOS invocations=0 | 修复失败服务,纳入管理 |
| P1 | 真实流量 | BOS 24h invocations = 0 | 系统健康但无实际使用,可能是自嗨 | 启动端到端 smoke test,确保至少 1 条真实路径 |
| P1 | 代码冻结执行 | code_freeze=true,但子模块仍有大量修改 | 冻结名存实亡 | 强化 freeze gate,或明确解冻窗口 |
| P2 | 技术债务 | debt items 目录为空,但 system.yaml 仍引用 9 项未解决 debt | debt SSOT 不一致 | 清理或重激活 debt registry |
| P2 | CI 集成 | SSOT guardian 只在 pre-commit + cron,未进 CI | 新 clone 可能绕过 | 在 ci-lint.yml / governance-check.yml 加 guardian job |
| P3 | 可观测性 | 健康分 100 但无法区分"真的健康"和"没有流量" | 假阳性 | 增加活性指标(active smoke calls/min) |
| P3 | 文档 | 新增 ssot-guardian 机制未在 AGENTS.md 显式引用 | 新 Agent 不知道 | AGENTS.md 增加 SSOT 维护章节 |

## 详细说明

### 1. 子模块治理 (P0)

当前 14/18 子模块有未提交修改,典型例子:
- `projects/aetherforge`: 57 个 dirty,大量删除 `llm_gateway/_legacy/`
- `projects/gbrain`: 23 个 dirty,删除 `admin/` 目录
- `projects/agora`: 修改 mcp 核心文件,新增 `mcp_proxy/health.py`
- `projects/omo`: ruff format 后未提交

风险:
- 根仓库指针指向的 commit 与实际工作树不一致
- 其他开发者 clone 后得到的是旧代码
- CI 在子模块干净状态下运行,可能与本地行为不同
- 历史 `FLOW-OMC-REVERT` 教训:未提交修改可能静默丢失

建议:
1. 开一个 "submodule dirty cleanup" bet,逐个审查 dirty 子模块.
2. 对每个子模块:要么提交 + bump 指针,要么 `git checkout -- .` 回滚.
3. 在 `.pre-commit-config.yaml` 或 cron 中加 `git submodule foreach 'git status --short'` 检查,dirty 时告警.

### 2. 运行时服务健康 (P0)

`omo state health` 显示:
- failed: `agentmesh-gateway`, `gbrain-index`
- unmanaged: `kos`, `runtime-mcp`, `sharedbrain-bos-mcp`

同时 `omo bos status` 显示 24h invocations = 0.

这说明:
- 要么服务没真正跑起来
- 要么没有 Agent/流程在使用 BOS URI
- 健康分 100 只是静态检查通过,不代表系统活着

建议:
1. 修复 `agentmesh-gateway` 和 `gbrain-index`.
2. 把 3 个 unmanaged 服务纳入 runtime 监管 (register + health probe).
3. 跑一条真实端到端 smoke test: `cockpit` -> `agora` -> `gbrain` 或类似路径,确认 BOS invocations > 0.

### 3. 真实流量 (P1)

治理健康分 100 但 BOS 调用量为 0,这是典型的"健康但 dead"状态.

建议:
- 在 `omo governance audit` 中增加 "BOS invocations > 0 in last 24h" 检查.
- 设置 cron 每日至少跑 1 次端到端 smoke test,并写入 evidence.

### 4. 代码冻结 (P1)

`system.yaml` 显示 `code_freeze: true`,但子模块大量修改未提交.

可能解释:
- freeze 只约束根仓库 `.omo/`,不约束子模块?
- 或者 freeze 已被自动化进程绕过?

建议:
- 明确 freeze 范围并写入 `.omo/standards/code-freeze-policy.md`.
- 若 freeze 包含子模块,则加 gate:dirty submodule 禁止提交.

### 5. 技术债务 Registry (P2)

`system.yaml` 仍引用 9 项未解决 debt:
- D2_CI_E2E, D3_EU_PRICING
- SB_DECOMPOSITION, SB_UNTESTED_PKGS, SB_ORPHANED_TASKS, SB_ROOT_CLEANUP, SB_BRIDGE_FIX, SB_PROJECTS_YAML, SB_PHASE17_PLAN

但 `.omo/debt/items/` 目录不存在(或为空).

建议:
- 确认这些 debt 是否仍然有效.
- 若有效,重建 items 文件.
- 若已解决,更新 `system.yaml` 的 `debt_weight_items`.

### 6. CI 集成 SSOT Guardian (P2)

当前 guardian 机制:
- pre-commit hook (本地)
- 每日 cron (本地)

缺失:
- GitHub Actions CI 中没有 `ssot-guardian` job.

建议:
- 在 `.github/workflows/ci-lint.yml` 或 `governance-check.yml` 中加:
  ```yaml
  - name: SSOT guardian
    run: python3 bin/ssot-guardian.py
  ```

### 7. 可观测性增强 (P3)

当前健康分只反映静态检查.建议增加:
- 活性指标: `bos_invocations_1h`, `smoke_test_pass_rate_24h`
- 服务在线时长 (uptime)
- 真实端到端 latency

### 8. AGENTS.md 更新 (P3)

新增 `ssot-guardian` 机制后,应在 `AGENTS.md` 中增加:
- "SSOT 维护" 章节
- 引用 `.omo/standards/ssot-guardian.md`
- 说明 Agent 修改 `.omo/state/`, `.omo/goals/`, `.omo/tasks/registry/` 后必须跑 guardian

## 建议的下一步

1. **立即**: 处理子模块 dirty 状态(提交或回滚).
2. **本周**: 修复 agentmesh-gateway / gbrain-index,跑通 1 条 BOS smoke test.
3. **下周**: 清理 debt registry,将 ssot-guardian 进 CI.
4. **持续**: 监控 BOS invocations,把活性指标加入 audit.
