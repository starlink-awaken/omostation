# omostation

> Workspace 整合了所有知识工程与研究项目。

## 结构

```
omostation/
├── projects/               # 所有项目（独立 git 仓库）
│   ├── kairon/             # 知识工程与研究栈（17 包 monorepo）
│   ├── SharedBrain/        # 数字化生命 OS（71K 行 Python）
│   ├── agentmesh/          # Agent SDK（TypeScript monorepo）
│   ├── gbrain/             # Postgres 原生知识脑（TypeScript）
│   └── _archived/          # 已迁移旧项目的统一备份
│
├── Makefile                # 跨项目构建/测试/部署
├── docker-compose.yml      # 服务编排
├── convergence.yaml        # 融合治理状态
│
├── README.md               ← 你在这里
├── CONTRIBUTING.md         # 贡献指南
├── CODE_OF_CONDUCT.md      # 行为准则
└── LICENSE                 # MIT
```

## 快速开始

```bash
# kairon 全量测试（17 包）
cd projects/kairon && make test

# 单个包测试
cd projects/kairon/packages/ontoderive && python3 -m pytest tests/ -q

# Docker 服务
docker compose up -d
```

## 项目总览

| 项目 | 栈 | 规模 | 说明 |
|------|-----|------|------|
| `kairon` | Python | 17 包 | 知识摄取/推理/研究/治理/认知 |
| `SharedBrain` | Python | 71K 行 | 数字化生命 OS |
| `agentmesh` | TypeScript | monorepo | 多 Agent SDK |
| `gbrain` | TypeScript | — | Postgres 知识脑 |
| `_archived` | — | 22 项 | 已迁移旧项目备份 |

## License

MIT
