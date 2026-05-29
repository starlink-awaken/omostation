# Workspace Onboarding

> 新人上手指南 — 5 分钟了解 omostation

## 快速开始

```bash
git clone git@github.com:starlink-awaken/omostation.git
cd omostation
make setup       # 安装依赖
make test        # 运行 kairon 全量测试
```

## 架构总览

5 个项目，分两层：

**omostation 根仓库**（统一入口 + 治理 + CI/CD）
```
omostation/
├── projects/
│   ├── kairon/          ← Python monorepo, 17 包
│   ├── SharedBrain/     ← 数字化生命 OS, 71K 行
│   ├── agentmesh/       ← Agent SDK, TS monorepo
│   ├── gbrain/          ← 知识脑, Postgres
│   └── _archived/       ← 22 项备份
├── README.md / AGENTS.md / Makefile / convergence.yaml
└── .omo/                ← 治理知识库
```

**核心链路**: kairon（内部 pip 依赖）+ SharedBrain（MCP/subprocess）+ agentmesh（MCP/HTTP）+ gbrain（Postgres）

## 常用命令

```bash
# kairon 全量测试
cd projects/kairon && make test

# 单个包测试
cd projects/kairon/packages/<name> && python -m pytest tests/ -q

# Docker 服务
docker compose up -d

# 治理知识库
cd .omo/ && ls  # 探索治理文档
```

## 项目结构

| 命令 | 作用 |
|------|------|
| `make setup` | 全量安装依赖 |
| `make test` | 运行 kairon 17 包测试 |
| `make lint` | ruff 代码检查 |
| `make clean` | 清理缓存 |
| `docker compose up -d` | 启动服务 |

## 关键文档

- `.omo/INDEX.md` — 治理知识库导航
- `.omo/STATE.md` — 当前架构状态
- `.omo/INVENTORY.md` — 全系统资产清单
- `.omo/CLI-MCP-SPEC.md` — CLI & MCP 规范
- `AGENTS.md` — 项目治理边界
- `README.md` — 项目总览

## 历史背景

2026-05 中旬，原系统由 43+ 独立 git 仓库组成，硬编码路径耦合严重。
经过两轮收敛（kairon monorepo + omostation 统一入口），
当前为 5 项目的清晰结构，每项目为独立 git 仓库，通过 omostation 协调。

---

*维护: 2026-05-29*
