---
id: aud-44-agora
title: "Agora 16服务全面审计报告"
date: 2026-05-27
tags: [audit, agora, architecture, health]
type: audit
layer: L2
phase: Phase6
status: active
version: v1.0.0
---

# Agora 16服务全面审计报告

## 一、健康度全景矩阵

| 层 | 服务 | 语言 | LOC | 测试 | 通过率 | 健康度 | 关键标签 |
|:--|:----|:---:|----:|-----:|:-----:|:-----:|---------|
| 🟢 | **sophia** | Python | 2,030 | 87/87 | 100% | **95** | 范式编译器 |
| 🟢 | **eidos** | Python | 5,667 | 141/142 | 99% | **92** | Schema验证 |
| 🟢 | **ssot-kernel** | Python | 6,369 | 50/50 | 100% | **90** | 配置真相源 |
| 🟢 | **iris** | Python | 3,231 | 66/66 | 100% | **90** | 知识连接器 |
| 🟢 | **agora** | Python | 6,321 | 470/473 | 99% | **88** | 服务治理Hub |
| 🟡 | **codeanalyze** | Python | 4,570 | 39/49 | 80% | **80** | 代码分析 |
| 🟡 | **kronos** | Python | 2,715 | 15/20 | 75% | **78** | 知识摄取 |
| 🟡 | **bos-daemon** | Python | ~3,000 | — | — | **75** | 守护进程 |
| 🟡 | **ontoderive** | Python | 18,645 | 746/747 | 99.9% | **88** | 推导引擎 |
| 🟡 | **agentmesh** | TypeScript | 201,026 | — | — | **70** | 编排引擎 |
| 🟡 | **metaos** | Python | 5,666 | 39/39 | 100% | **75** | 元操作系统 |
| 🟡 | **pallas** | Python | 935 | — | — | **65** | CLI门面 |
| 🟡 | **agent-runtime** | Python | 1,286 | 16/16 | 100% | **78** | Agent执行器 |
| 🟡 | **forge** | Python | 6,360 | 57/57 | 100% | **75** | 工具注册 |
| 🟡 | **bos-skill-cli** | Python | 1,211 | — | — | **65** | 技能管理 |
| 🔴 | **minerva** | Python | 133,157 | — | — | **55** | 深度研究 |
| 🔴 | **kos** | Python | 13,108 | 105/119 | 88% | **60** | 知识OS |

**加权平均健康度: 76/100 🟡**

## 二、按层审计

### 层1: 核心运行时 (Core Runtime)

| 服务 | 得分 | 亮点 | 问题 |
|:----|:----:|------|------|
| **agentmesh** | 70 | monorepo结构清晰, 5包严格单向依赖, build通过, 20万行TS | 测试无数据(bun test耗时), port 3000 EADDRINUSE, 维护成本高 |
| **metaos** | 75 | 5,666 LOC, 39/39测试通过, 有register_agora.py | 无独立运行入口, 依赖SharedBrain venv |
| **agora** | 88 | 470测试, 16服务注册, 架构分层清晰 | ruff 6个行过长, 模块超300行7个 |

### 层2: MCP Bus & Gateway

| 服务 | 得分 | 亮点 | 问题 |
|:----|:----:|------|------|
| **bos-daemon** | 75 | 端口7420监听中, AGENTS.md完善, 有健康检查 | 测试收集237错误(跨项目依赖), 复杂度高(SharedBrain根) |

### 层3: 知识管线 (Knowledge Pipeline)

| 服务 | 得分 | 亮点 | 问题 |
|:----|:----:|------|------|
| **sophia** | **95** | 87/87测试全绿, 14文件2K LOC精简, 架构5层清晰 | 无 |
| **eidos** | **92** | 141/142测试, MCP server可用, 10 schema定义完整 | 1个跳过 |
| **ontoderive** | 88 | 746/747测试(99.9%), 57模块, 73工具匹配 | 1个test_cli_derive断言失败, 18K LOC较大 |
| **kronos** | 78 | 15/20测试, 5层抓取引擎, ARCHITECTURE完善 | 5个跳过(依赖外部API) |
| **minerva** | **55** | 133K LOC最大项目 | 无法运行测试(无pytest), MCP tool完整性待验证, 体量最大但验证最少 |
| **pallas** | 65 | 935 LOC薄层, 职责清晰 | 测试收集错误, 依赖ontoderive/agora |

### 层4: 数据基础设施 (Data Infrastructure)

| 服务 | 得分 | 亮点 | 问题 |
|:----|:----:|------|------|
| **ssot-kernel** | **90** | 50/50全绿, 6,369 LOC, 有版本一致性pattern | 位置在~/Workspace/SSOT/不是预期路径 |
| **iris** | **90** | 66/66全绿, 6个connector, 7个MCP工具, 文档完善 | V0.1只读, 未双向同步 |
| **kos** | **60** | 13K LOC活跃开发, 6域MCP | **14测试失败** ⚠️ |

### 层5: 生态工具 (Ecosystem)

| 服务 | 得分 | 亮点 | 问题 |
|:----|:----:|------|------|
| **codeanalyze** | 80 | 39/49测试, 12个CLI命令, FastMCP server | 10个跳过 |
| **forge** | 75 | 6,360 LOC, 24脚本, 120工具注册表, 423节点图谱 | pytest不可运行 |
| **agent-runtime** | 78 | 1,286 LOC, 16/16测试, 有HTTP auth | 体量小, 功能精简 |
| **bos-skill-cli** | 65 | 1,211 LOC, TUI界面, staged activation | 无测试数据 |

## 三、P0/P1 关键发现

| 严重度 | 服务 | 问题 | 建议 |
|:-----:|:----|------|------|
| **P0** | **kos** | 14测试失败(88%通过率) | 需修复测试后确认架构稳定 |
| **P0** | **minerva** | 133K LOC最大项目但无测试验证 | 最小: 安装pytest跑一遍 |
| **P1** | **pallas** | 测试收集错误 | 修复test_cli.py导入路径 |
| **P1** | **ontoderive** | 1个test_cli_derive断言失败 | 调试后修复 |
| **P1** | **agentmesh** | port 3000冲突, 无测试报告 | 检查端口占用, 收集bun test结果 |
| **P2** | **metaos** | 依赖SharedBrain venv, 无法独立验证 | 创建独立venv |
| **P2** | **forge** | pytest不可运行 | 安装pytest到venv |

## 四、层级对齐检查

```
4+1+2递归架构 vs 实际注册:
                                   
L4 Self            kos(60)  minerva(55)                    ← 最弱
L3 Collaboration   eidos(92)  ontoderive(88)  sophia(95)   ← 最强  
L2 Capability      iris(90)  kronos(78)  forge(75)
                   codeanalyze(80)  agent-runtime(78)
L1 Contract        ssot-kernel(90)  agora(88)
                   bos-daemon(75)
S1 Cross-cutting   metaos(75)                               
S2 Cross-cutting   agentmesh(70)
```

**关键发现**: L4 Self层(kos+minerva)是最大瓶颈, L3 Collaboration层最强。

## 五、修复优先级

| 优先级 | 服务 | 内容 | 工作量 |
|:-----:|:----|------|:------:|
| 🔴 P0 | kos | 修复14个测试失败 | 30min |
| 🔴 P0 | minerva | 安装pytest, 跑一次基线 | 10min |
| 🟡 P1 | pallas | 修复测试收集错误 | 10min |
| 🟡 P1 | ontoderive | 修复1个断言失败 | 15min |
| 🟡 P1 | agentmesh | 解端口冲突, 收集测试 | 20min |
| 🟢 P2 | forge | 安装pytest到venv | 5min |
| 🟢 P2 | metaos | 独立venv | 5min |
