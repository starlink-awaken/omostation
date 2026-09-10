# omostation · 智能体协作设定（项目版）

> 本文件承载 omostation 项目特有的知识互通路由与项目事实。
> 委托人通用设定（身份/沟通协议/工作纪律/红线）见全局 `~/.claude/PROFILE.md`，此处不复制。
> version: 2.0 · last-reviewed: 2026-09-10 · owner: xiamingxing

## 0. 与全局版的关系

- 全局版管"人"；本文件管"这个仓"——冲突时本文件更具体、优先
- 本文件遵守 doc-ssot-contract：**不硬编码易变数值**（端口/服务数/健康分/项目数），一律指向 SSOT

## 1. 项目事实（只写不变的）

| 域 | 事实 | 易变细节看哪 |
|---|---|---|
| 形态 | macOS monorepo `~/Workspace`，17+ git 子模块 | `docs/project-registry.yaml` |
| 架构 | eCOS v6：5+4+1+1 分层 · X1-X4 治理轴 · BOS URI 路由 · 道法术器(DFSQ)+脊面(SFOP) | `ARCHITECTURE.md` |
| 栈 | Python/uv · TS/bun · Docker · launchd | 各子项目 AGENTS.md |
| 治理 | BET 台账 · GaC 规则注册表 · P74 沉默检测 · 场景卡五档生命周期 | `.omo/standards/` |

## 2. 会话加载协议（本项目）

```bash
make agent-workflow-bootstrap   # SSOT 运行时事实
make omo-status                 # 多 agent 状态快照 (开工前必看)
make agent-workflow-compliance  # P74 合规
```

- 需求迭代先 `agent-workflow.py start`（ADR-0203），再改文件
- 不知做啥 → 读台账（`bet-ledger.py list --claimable`），不自拟任务
- 编辑架构相关文件前过 §B.0.5 约束检查（场景卡生命周期/业务域/脚本配额/SSOT 引用）

## 3. 知识读路由（按场景）

| 场景 | 先查 | 兜底 |
|---|---|---|
| 冷启动对齐历史决策 | KOS 查询序列（BRIEF.md → ADR-0124/0125 → 实体表） | funes 会话记忆 |
| 踩坑预判 | `.omo/_knowledge/pitfalls/` + `_knowledge/patterns/` | auto-memory MEMORY.md |
| 选活 | BET 台账 claimable | 能力缺口台账（debt.yaml 扩展） |
| 改治理物 | GaC 注册表 / write-owners / services 三表 | `.omo/standards/` |
| 断言"X 不存在" | 五处查证：ADR(migrate/superseded) + archive + _control/-dashboard + mutation-surfaces + ingress delivery | — |

## 4. 知识写回流（教训必须落库）

| 类型 | 落点 | 工具/规则 |
|---|---|---|
| 环境/工具坑 | `.omo/_knowledge/pitfalls/{category}/` | `bin/gac/error-knowledge.py record`（自动 dedup 计数） |
| 可复用模式 | `.omo/_knowledge/patterns/` | retro 提炼 → 独立 pattern 文档 |
| 架构决策 | ADR 编号体系 | ADR 模板 + `make adr-number-check` |
| BET 教训 | `.omo/_knowledge/retros/<BET-ID>.md` | complete 前必写（台账 DoD） |
| 跨会话偏好 | auto-memory | 按"无记忆审计"标准写 |

**闭环铁律**：同类 pitfall 第二次出现 → 必须升级为 pattern 或机制修复，不许无限计数。

## 5. 协作拓扑（本项目落地）

- **多 agent 并行**：orca 编排（含 codex 子代理），适度提并行度
- **监督环**：验证目标为多智能体控制系统本身 → Orca supervised loop + 独立 verifier（blueprint §9）；Codex TUI 下每个 provider 批准**必须本人手点**
- **并行纪律**（血泪换来的）：
  - 共享树做完一块立即 commit+push（reset 会吃未推工作）
  - BET 认领走 claim-bet 广播（防同号竞速）
  - 清理器有引用保护（cleanup-guard：未推/open-PR/活跃认领跳过）——但别依赖它兜底
  - 并发 agent 抢改同文件：快速连续操作被回滚/吸收 → 停下协调，别硬怼

## 6. 项目红线（补充全局版）

- eCOS 部分子仓 auto-commit 是设计（L0 萃取依赖），别关
- `.omo/` 顶层新增文件/目录必须登记 omo-governance-surfaces.yaml
- launchd 修复走 ADR-0435 模式：services.yaml + tracked wrapper + 生成器 `--write`，**严禁手改 plist**
- 凭据只在 `~/.config/`（如 spine/smtp.json），仓库零凭据
- gitlink 悬空是 CI 红常见根因——bump 后跑 `bin/ssot/sync-submodules-push.sh`

## 7. 完成标准（本项目 DoD）

- `make gac-local-gate` · `make ssot-guardian` 绿；改啥跑对应 check（scene-card/journey/adr）
- BET：completion_evidence 的 receipt 指向**主仓 tracked 文件**（CI 无子模块检出）
- 台账状态真实；done 必有 retro + 可指认证据

## 8. 生命周期

- 本文件随体系演进由 agent 提 PR 更新（路由表/工具名变化）；稳定语义变更需 owner 确认
- 与全局 PROFILE.md 同审（无记忆审计时）
