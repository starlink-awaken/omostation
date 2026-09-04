---
type: ephemeral
created: 2026-09-03
---

# 2026-08-15 系统落地复盘：全仓子模块秒级更新与 Auto-PR 自动化流水线

> **责任模块**：CI/CD 协作流水线 & 多子仓治理 (BET-Y1Q2-T1-20 & BET-Y1Q1-T1-08)  
> **关联 PR**：主仓 #1530, #1534, #1538 / omlxc #34 / cockpit #61  
> **核心指标**：指针更新延迟由 ~94s 降低至 ~11s（90% 耗时优化），19 个子仓 100% 具备全自动提 PR 能力。

---

## 1. 背景与核心瓶颈

在 `starlink-awaken/omostation` 多模块工程体系中，过去的子模块指针更新存在两个严重瓶颈：
1. **耗时过长**：全量 `git submodule update --init --recursive` 单次耗时约 94 秒。
2. **D2 独占锁阻塞**：多 Agent 协作下，必须等待全量检出完成才能释放锁，造成 Agent 间严重的并发争用与等待。

根据战略评估，虽然坚决否定了破坏隔离边界的 monorepo 迁移方案，但确立了**底层 cacheinfo 秒级快进 (`bump-fast`) + GitHub Actions Reusable Auto-PR 流水线**的演进路径。

---

## 2. 核心架构与落地全景

### 2.1 Reusable Workflow 集中托管
* **主仓文件**：[`.github/workflows/reusable-submodule-bump-pr.yml`](file:///Users/xiamingxing/workspace/.github/workflows/reusable-submodule-bump-pr.yml)
* **核心机制**：
  - 检出主仓并载入 Python 3.13。
  - 调用 `bash bin/gac/gac-worktree.sh bump-fast <submodule_path>` 完成秒级指针快进与远端 SHA 可达性校验。
  - 自动创建 `auto-bump/<submodule>-<short_sha>` 分支并使用 `gh pr create` 发起标准 PR。
  - 自动注入 `submodule-bump` 标签，触发全量 CI 门禁（`ci-local-fast`, `gac-gate`, `phase-gate`）。

### 2.2 19 个子模块自动化覆盖
* **分发脚本**：[`bin/_archive/2026-08-t6-05/distribute-submodule-workflows.sh`](file:///Users/xiamingxing/workspace/bin/_archive/2026-08-t6-05/distribute-submodule-workflows.sh)
* **各子仓薄工作流**：`.github/workflows/bump-main-pr.yml`，统一 `uses: starlink-awaken/omostation/.github/workflows/reusable-submodule-bump-pr.yml@main`。
* **密钥安全分发**：通过 GitHub API 为 19 个子仓批量注入具备最小权限（`repo`, `workflow`）的 `OMOSTATION_BOT_TOKEN`。

---

## 3. 端到端实测验证矩阵

| 子模块 | 触发方式 | Actions 运行耗时 | PR 状态 | 门禁通过率 |
|---|---|---|---|---|
| `projects/omlxc` | `workflow_dispatch` (Run #31884284483) | **11s** | 幂等校验通过 | 100% PASS |
| `projects/cockpit` | `workflow_dispatch` (Run #31885697505) | **14s** | PR #1538 自动创建并合并 | 100% PASS |

---

## 4. 关键踩坑与打假记录 (Q3 Lessons Learned)

1. **Reusable Workflow 的 Checkout 目标陷阱**：
   - 跨仓库调用 Reusable Workflow 时，`actions/checkout` 默认会检出调用者子仓，导致找不到主仓的 `bin/gac/gac-worktree.sh`。
   - **修复**：显式声明 `repository: starlink-awaken/omostation`（已在 PR #1534 合并）。
2. **GitHub Label 不存在导致 PR 创建失败**：
   - 当 `gh pr create --label "submodule-bump"` 中的 label 在主仓未预先定义时，GitHub API 会抛非 0 异常。
   - **修复**：主仓预置 `#0E8A16` 的 `submodule-bump` 官方标签。
3. **单元测试全局代理污染**：
   - 本地 `ALL_PROXY=socks5://127.0.0.1:7890` 导致 `httpx.AsyncClient` 缺失 `socksio` 抛异常。
   - **修复**：在 `tests/conftest.py` 注入代理隔离 fixture（`omlxc` 982 tests 100% 纯绿）。

---

## 5. 操作规范与 Agent 指令

- **所有 Agent 严格遵循**：
  1. 严禁运行全量 `git submodule update`。
  2. 指针更新统一使用 `bash bin/gac/gac-worktree.sh bump-fast`。
  3. 子模块发布走 Release Tag 或 Action 手动触发，保留主仓人工/管理员合并闸门。
