# omostation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> Workspace 整合了所有知识工程与研究项目。
>
> **Phase 17**: 进行中 | [治理面板](.omo/MASTER-BLUEPRINT.md)

## 结构

```
omostation/
├── projects/               # 所有项目（独立 git 仓库）
│   ├── kairon/             # 知识工程与研究栈（31 包 monorepo）
│   ├── gbrain/             # Postgres 原生知识脑（TypeScript）
│   ├── hermes-console/     # Hermes 控制台
│   ├── agentmesh/          # Agent SDK（已归档）
│   └── _archived/          # 已迁移旧项目备份（24 项）
│
├── data/                   # 共享数据层
│   ├── db/                 # SQLite 数据库
│   ├── kos/                # KOS 搜索索引
│   ├── sharedbrain/        # SharedBrain 数据持久层（数据库+备份）
│   └── backups/            # 数据备份
│
├── .omo/                   # 治理层（目标/状态/标准/审计/知识面）
├── spaces/                 # 用户空间 / 租户边界
│
├── scripts/                # 治理自动化
│   ├── omo/                # OMO Python 工具集（CLI + 50 模块）
│   └── shell/              # Shell 脚本
│
├── bin/                    # 可执行工具
├── tests/integration/      # 集成测试
├── runtime/                # 运行时残留
├── agent-runtime/          # Hermes Agent 日志（gitignored）
│
├── Makefile                # 跨项目构建/测试/部署
├── docker-compose.yml      # 服务编排
│
├── README.md               # 项目总览
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
| `hermes-console` | TypeScript | 137 MB | Hermes 控制台 | 🟡 待评估 |
| `SharedBrain` | Python | 已归档 | 代码迁移至 kairon，数据层在 `data/sharedbrain/` | ⚪ Archived |
| `agentmesh` | TypeScript | 已归档 | 100% 迁移至 kairon | ⚪ Archived |
| `_archived` | — | 24 项 / 6.3 GB | 已迁移旧项目备份 | ⚪ Archived |

## License

MIT
