# CLAUDE.md — OMO v5 治理内核

> eCOS v5 L2 引擎面 · 治理中枢 · Phase/Task/Debt/Audit 全生命周期管理
>
> 工作区总览与跨层约束请优先阅读 [`../AGENTS.md`](../AGENTS.md)。

---

## 项目身份

`projects/omo` 是 OMO OS 的**执行内核**，区别于工作区根目录下的 `.omo/` 实例数据层。

- **.omo/**：state plane，承载治理状态、任务、债务、审计证据（不要在此直接写代码）
- **projects/omo/**：kernel plane，实现 schema、audit、sync、promotion、task policy 等执行逻辑
- **projects/c2g/**：唯一战略入口 (ingress plane)，只能向 `.omo/tasks/planned/` 和 `.omo/goals/current.yaml` 物化

权威治理面定义：`.omo/standards/omo-governance-surfaces.md`
权威注册表：`.omo/_truth/registry/omo-governance-surfaces.yaml`

---

## 核心职责

1. **Phase / Task / Debt 生命周期** — `omo_worker_*`、`omo_debt_*`、`omo_audit_*`
2. **治理审计与门禁** — `omo_governance_surfaces.py`、`omo_audit*.py`
3. **任务策略红线** — `omo_task_policy.py` + `omo_lint.py`
4. **BOS 服务注册与度量** — `omo_bos_*`
5. **AppendOnlyLog 基础设施** — `omo_io.py`（7 consumers 共享同一物理层）
6. **model-driven 桥接** — `model_driven_bridge.py`

---

## 核心模块

```
src/omo/
├── cli.py                    # CLI 入口 (26+ 子命令)
├── mcp_server.py             # MCP Server (10+ tools)
├── omo_io.py                 # AppendOnlyLog + 原子写 + fcntl 跨进程锁
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

---

## Agent 操作约束

### 1. 不要直接修改 `.omo/`

`.omo/` 是 K0 数据层。所有状态变更必须通过 `omo-cli`、MCP 工具或 `projects/c2g/` 入口。

### 2. 推荐入口

```bash
# 治理审计 (目标 100.0 A+)
uv run python -m omo.cli governance audit --output json

# 治理面巡检
uv run python -m omo.cli governance surfaces --workspace-root ../../.. --json

# 非 broker 直接写拦截
uv run python -m omo.cli lint direct-omo-io

# ingress registry 一致性
uv run python -m omo.cli lint ingress-registry --workspace-root ../../..

# task policy 红线 (self-evolution-approval / human-approval-ref)
uv run python -m omo.cli lint task-policy self-evolution-approval --workspace-root ../../..
```

### 3. C2G 物化流程

- 战略意图先在 `projects/c2g/` 沙箱中沉淀为 Pitch
- Pitch 头部需包含 frontmatter：
  ```markdown
  > **Upstream**: MS-XXX
  > **Appetite:** N days
  ```
- 通过 `c2g bet <pitch.md>` 转换为 Bet 并生成 Planned Task
- 不要手动创建 `.omo/tasks/planned/*.yaml`

### 4. model-driven 桥接铁律

- M3 标准定义以 `projects/model-driven/src/model_driven/mof/m3_extended.py` 为准
- 任何新增阶段/门禁必须同步：model-driven 源 + M2 schema + M1 节点 + 校验工具
- 详见根 `AGENTS.md` §Model-Driven Bridge

---

## 快速命令

```bash
cd projects/omo

# 全量测试
make test

# 治理审计
uv run python -m omo.cli governance audit

# lint
make lint
make fmt
```

---

## GPTCHAS

1. **不要在此生成 `.omo/` 运行时数据** — 本仓库只放执行内核
2. **AppendOnlyLog 是 SSOT** — 7 consumers 共享同一物理 JSONL，新增 consumer 只需 import + SCHEMA_REGISTRY 登记
3. **task policy 可扩展** — `omo_task_policy.py` 用注册表承载新红线，不要把规则散落到单独脚本
4. **OMO CLI 是内部程序接口** — 人类用户请使用 `cockpit`
5. **治理审计必须 100.0 A+** — 任何非 A+ 需要注册 OMO Debt 并修复
