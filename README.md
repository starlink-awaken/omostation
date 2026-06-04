# omostation

> Workspace 整合了所有知识工程与研究项目。
>
> **Phase 17**: 进行中 | [治理面板](.omo/MASTER-BLUEPRINT.md)

## 结构

```
omostation/
├── projects/               # 所有项目（独立 git 仓库）
│   ├── kairon/             # 知识工程与研究栈（31 包 monorepo）
│   ├── gbrain/             # Postgres 原生知识脑（TypeScript）
│   ├── agentmesh/          # Agent SDK（TypeScript，已归档）
│   ├── hermes-console/     # Hermes 控制台
│   └── _archived/          # 已迁移旧项目的统一备份（含 SharedBrain、agentmesh 等 24+ 项）
│
├── .omo/                   # 治理层（目标/状态/标准/审计）
├── spaces/                 # 用户空间 / 租户边界
├── data/                   # 共享数据库
│
├── Makefile                # 跨项目构建/测试/部署
├── docker-compose.yml      # 服务编排
├── convergence.yaml        # 融合治理状态
│
├── README.md               ← 你在这里
├── AGENTS.md               # 开发指南
├── CLAUDE.md               # AI 助手规则
├── LAYER-INDEX.md          # 4-Layer 架构索引
├── CONTRIBUTING.md         # 贡献指南
├── CODE_OF_CONDUCT.md      # 行为准则
└── LICENSE                 # MIT
```

## 快速开始

```bash
# kairon 全量测试（31 包）
cd projects/kairon && make test

# 单个包测试
cd projects/kairon/packages/eidos && python3 -m pytest tests/ -q

# 集成测试
bash tests/integration/run-all.sh

# E2E 全链路测试
python3 tests/integration/test-e2e-phase1.py
```

## 项目总览

| 项目 | 栈 | 规模 | 说明 | 状态 |
|------|-----|------|------|------|
| `kairon` | Python | 31 包 monorepo | 知识工程与研究栈 | 🟢 Active |
| `gbrain` | TypeScript | 74 工具 + memU 引擎 | Postgres 知识脑 | 🟢 Active |
| `SharedBrain` | Python | 2.0 GB | 数字化生命 OS | 🟡 已归档（代码迁移至 kairon） |
| `agentmesh` | TypeScript | 9.3 MB | Agent SDK | ⚪ 已归档（100% 迁移至 kairon） |
| `hermes-console` | TypeScript | 137 MB | Hermes 控制台 | 🟡 待评估 |
| `_archived` | — | 24 项 / 6.3 GB | 已迁移旧项目备份 | ⚪ 归档 |

## License

MIT
