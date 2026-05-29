# Workspace Onboarding

> 新人上手指南 — 5 分钟了解全系统

## 快速开始
```bash
git clone {this-repo}
cd workspace
make setup    # 安装依赖
make test     # 全部测试
make build    # 构建所有项目
```

## 架构总览
24 个项目，按 4+1+3 架构分层:
  P0 产品界面   4 项目
  L4 自我层     2 项目
  L3 协作层     3 项目
  L2 能力层     11 项目
  L1 契约层     2 项目
  X1/X2/X3 治理 3 项目 + 运维中心

核心链路: pallas → minerva → ontoderive → sophia → eidos → KOS
运维中心: hermes-ops (20+ MCP tools)

## 常用命令
```bash
make test        # 运行所有测试
make build       # 构建所有项目
make lint        # 代码检查
hermes-ops --help  # 运维中心 CLI
```

## 关键文档
- .omo/summaries/workspace-architecture-final.md  — 完整架构
- .omo/diagrams/4-plus-1-3-architecture.md          — 架构图
- .omo/CLEANUP.md                                    — 清理策略
- AGENTS.md                                          — 项目治理
