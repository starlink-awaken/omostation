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
omo event emit       # 事件发射
omo observability    # 可观测性
```

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
