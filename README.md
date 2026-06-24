# OMO — OS for AI Agents

eCOS v5 L2 引擎面 · 治理中枢 · Phase/Task/Debt/Audit 全生命周期管理。

## 核心能力

- **债务管理**: 15 模块债务注册/分发/修复/度量/审批 (omo_debt_*)
- **治理引擎**: 审计同步/去重 (omo_audit_*)、健康检查 (omo_health)、自愈引擎 (omo_self_healing_*)
- **BOS 服务**: 注册/schema/分发/度量 (omo_bos_*)
- **Worker 调度**: 核心/分发/状态/晋升 (omo_worker_*)
- **跨层桥接**: model-driven、agora pool、LLM BOS bridge
- **基础设施**: AppendOnlyLog + 原子写 + fcntl 跨进程锁 (omo_io)

## 快速开始

```bash
cd projects/omo
make test     # 530 tests (有效通过率 97.4%)
make lint     # ruff check
make fmt      # ruff format
make install  # uv sync
```

## CLI

```bash
omo bos status       # BOS invoke metrics
omo bos discover     # 注册表
omo bos health       # 健康报告
omo governance       # 治理审计
omo governance surfaces  # `.omo` 顶层治理面巡检
omo governance ingress-goal BET-001 "标题" "描述" --ingress-plane projects/c2g
omo governance ingress-task task.yaml --ingress-plane projects/c2g
omo governance ingress-debt debt.yaml --ingress-plane projects/aetherforge
omo goal create --id G44.1 --desc "治理入口收敛" --source-ref reviewer:goal:g44.1
omo goal progress --id G44.1 --pct 75
omo task create --title "治理任务" --source-doc docs/spec.md --test-plan "uv run pytest -q"
omo task done TASK-1234
omo lint direct-omo-io         # 非 broker 直接改 `.omo` / `spaces` 拦截
omo lint sensitive-governed-writes  # system/goals/tasks/capabilities broker-only 落盘拦截
omo lint ingress-registry      # 强制校验 .omo/_delivery/ingress/registry.yaml 结构 / 反向映射 / 落盘一致性
omo lint mutation-surfaces     # broker 写入入口清单 vs truth registry 对齐校验
omo lint internal-write-profiles # worker/internal 运行时写路径 vs truth registry 对齐校验
omo lint self-evolution-approval # OPC P6 self-evolution 审批红线校验
omo lint task-policy self-evolution-approval # 单条规则校验
omo lint task-policy human-approval-ref      # 单条规则校验
omo lint task-policy active-review-ref       # active review 审查工件存在性
omo lint task-policy done-directory-status   # done/ 目录状态一致性
omo lint task-policy modern-done-completion-marker # 新式 done packet 完成标记
omo lint task-policy modern-done-evidence-paths # 新式 done packet 证据文件存在性
omo lint task-policy remediation-review-note # remediation review 审查笔记
omo lint task-policy --all                   # 执行全部已注册 task policy
omo event emit       # 事件发射
omo observability    # 可观测性
```

### 持久化 ingress

- `omo governance ingress-goal`: 受审计写入 `.omo/goals/current.yaml`
- `omo governance ingress-task`: 受审计写入 `.omo/tasks/planned/<id>.yaml`
- `omo governance ingress-debt`: 受审计写入 `.omo/debt/items/<id>.yaml`
- `omo goal create`: 人类友好的 goal 脚手架入口，底层改走 `create_goal()` broker
- `omo goal progress`: 人类友好的 goal 更新入口，底层改走 `update_goal_progress()` broker
- `omo task create`: 人类友好的低风险 planned-task 脚手架入口，底层仍走 `create_planned_task()` broker
- `omo task done`: 人类友好的 done 归档入口，底层改走 `complete_task()` broker
- `omo task refresh-evidence`: done task 证据路径修复入口，底层改走 `update_done_task_evidence_paths()` broker
- `omo-capability capability scan/register`: capability registry 入口，底层改走 `write_capability_registry_bundle()` / `write_manual_capabilities()` broker
- 三者都会同时落审计/交付副产物到 `.omo/_delivery/ingress/`
- `planned -> active` 的 queue move 现在也通过 ingress transition broker 收口；worker 侧只保留 promotion envelope 与 sync/rollback 编排

### 持久化治理红线

- 特殊任务红线统一注册在 `src/omo/omo_task_policy.py`
- 机器可读注册表在 `.omo/_truth/registry/task-policies.yaml`
- 统一执行入口是 `omo lint task-policy <name>`
- 全量执行入口是 `omo lint task-policy --all`
- OMO 人类/桥接 mutation surface 的机器可读注册表在 `.omo/_truth/registry/mutation-surfaces.yaml`
- OMO worker/internal runtime 写路径的机器可读注册表在 `.omo/_truth/registry/internal-write-profiles.yaml`
- 历史 direct-io 存量基线在 `.omo/_truth/registry/direct-io-baseline.yaml`
- 统一执行入口是 `omo lint mutation-surfaces`
- 统一执行入口是 `omo lint internal-write-profiles`
- 当前已登记 surface 包括:
  - `omo goal create/progress`
  - `omo task done`
  - `omo governance ingress-goal/task/debt`
  - `omo bridge --format ...`
  - `python3 projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py --m1-to-omo`（仅 broker 导入 proposed/planned → `.omo/tasks/planned/`）
  - `c2g` 的 `save_bet/save_task`
- 当前已登记 internal write profiles 包括:
  - `worker-dispatch/status/promotion`
  - `worker-approval-runtime`
  - `worker-rollout-runtime`
  - `worker-experience-runtime`
  - `worker-overlay-runtime`
- 当前持久化门禁链:
  - 本地提交前: `.pre-commit-config.yaml`
  - CI 合并前: `.github/workflows/governance-check.yml`
- 治理巡检: `omo governance surfaces` + `omo lint ingress-registry` + `omo lint mutation-surfaces` + `omo lint internal-write-profiles`
- direct-io gate 使用 baseline 仅冻结已知历史脚本债务；新增 `.omo` / `spaces` 直写仍然必须被拦截
- 当前 baseline 已清零；`omo lint direct-omo-io` 会要求 `direct-io-baseline.yaml` 保持 `entries: []`
- 新增红线时只允许:
  - 在 `TaskPolicy` 注册表加规则
  - 补对应测试
  - 补 README / 标准文档
- 不允许再新增平行的 ad-hoc `.omo` 手工检查脚本

## 架构

```
src/omo/
├── cli.py                    # CLI 入口 (26+ 子命令)
├── mcp_server.py             # MCP Server (10+ tools)
├── omo_io.py                 # AppendOnlyLog + 原子写 + fcntl
├── omo_paths.py              # 统一路径管理
├── omo_debt_*.py             # 债务管理 (15 模块)
├── omo_audit_*.py            # 审计 + 同步 + 去重
├── omo_bos_*.py              # BOS 服务
├── omo_self_healing_*.py     # 自愈引擎
├── omo_worker_*.py           # Worker 调度
├── omo_governance_*.py       # 治理叠加
├── omo_governance_surfaces.py# 治理面 / ingress registry 校验
├── omo_task_policy.py        # 可复用 task policy 检查器
├── model_driven_bridge.py    # model-driven 桥接
└── omo_agora_pool.py         # Agora 连接池
```

## 依赖

- 运行时: httpx, aetherforge-gateway, openai, pyyaml
- 跨项目: aetherforge-gateway (本地路径)
- 逻辑依赖: agora (BOS URI), kairon (KOS), runtime (成本)

## 测试

```bash
uv run pytest tests/ -q              # 全量
uv run pytest tests/ -m fast -q      # 快速测试
uv run pytest tests/ -m integration  # 集成测试
```

225 个测试因环境依赖被跳过，实际可运行 305 个，有效通过率 97.4%。
