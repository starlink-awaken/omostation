# AetherForge OMO 台账

> eCOS Phase X / AetherForge 持续迭代
> 创建: 2026-06 | 状态: 🟢 活跃

---

## 当前 Phase 概览

| 维度 | 定义 |
|:-----|:------|
| **Phase** | P1 — 产品化完善 (当前) |
| **目标** | 从"能用"到"好用"，补齐产品级体验缺失 |
| **Sprint** | 3-5 天一个迭代 |
| **状态** | 🟢 按计划推进 |

---

## 债务追踪

| ID | 债务 | 优先级 | 状态 | 备注 |
|:---|:-----|:------:|:----:|:-----|
| DEBT-001 | pip install aetherforge 一键安装 | 🔴 P0 | 📋 待办 | 需要发布到 PyPI |
| DEBT-002 | 错误信息不友好 (用户见 stack trace) | 🔴 P0 | ✅ 已修复 | _safe_run 包装 |
| DEBT-003 | README 缺少 elevator pitch | 🔴 P0 | ✅ 已修复 | 已重写 |
| DEBT-004 | 无 demo 命令 | 🟡 P1 | ✅ 已修复 | `aetherforge demo` |
| DEBT-005 | Provider 之间 default_model 不一致 | 🟡 P1 | ✅ 已修复 | ABC 统一 |
| DEBT-006 | 统一 CLI --ssot 不传参 | 🟡 P1 | ✅ 已修复 | parse_known_args |
| DEBT-007 | YAML 模板变量未标记 | 🟡 P1 | ✅ 已修复 | UNCONFIGURED 状态 |
| DEBT-008 | swarm CLI 入口缺失 | 🟡 P1 | ✅ 已修复 | 3 个基础命令 |
| DEBT-009 | gateway --help 无子命令列表 | 🟡 P1 | ✅ 已修复 | parse_known_args |
| DEBT-010 | 静态节点 network_zone 错误 | 🟡 P1 | ✅ 已修复 | local_daemon 自动 local |
| DEBT-011 | 无 CI/CD | 🟡 P2 | 📋 待办 | GitHub Actions |
| DEBT-012 | Provider 插件化 (社区贡献) | 🟢 P3 | 📋 待办 | Provider 插件 SDK |

---

## L0 融合路线图

详见 `ROADMAP-L0.md` 完整规划。

| Sprint | 范围 | 状态 |
|:-------|:-----|:----:|
| **Sprint 4** | compute_node + hardware_asset + network_zone 接入 | 📋 待开始 |
| **Sprint 5** | model pricing + 成本路由 | 📋 规划完成 |
| **Sprint 6** | credentials DB + quotas + constraints | 📋 规划完成 |

---

## 迭代计划

### Sprint 1 (当前) — 产品化基础

| Wave | 任务 | 状态 | 交付 |
|:-----|:-----|:----:|:-----|
| W1 | README 重写 + elevator pitch | ✅ | 产品导向 README |
| W2 | 统一 CLI parse_known_args 修复 | ✅ | gateway --ssot 透传 |
| W3 | Provider ABC default_model 统一 | ✅ | 9/9 Provider 对齐 |
| W4 | YAML 模板标记 + zone 覆盖 | ✅ | UNCONFIGURED 状态 |
| W5 | HITL default_model 修复 | ✅ | 不崩溃 |
| W6 | swarm CLI 3 命令 | ✅ | auction/chat/run |
| W7 | demo 命令 | ✅ | 10 秒体验 |
| W8 | 错误信息友好化 | ✅ | 无 stack trace |
| W9 | 补充测试 18 项 | ✅ | GroupChat/GraphWorkflow/ObjectStore |

### Sprint 2 — 发布准备

| Wave | 任务 | 预估 |
|:-----|:-----|:----:|
| W1 | PyPI 发布: `pip install aetherforge` | 1d |
| W2 | GitHub Actions CI/CD (lint + test + publish) | 1d |
| W3 | GitHub 仓库初始化 + CONTRIBUTING.md | 0.5d |
| W4 | 5 个端到端示例代码 (examples/) | 2d |
| W5 | 文档站搭建 (GitHub Pages / mkdocs) | 1d |

### Sprint 3 — 功能补全

| Wave | 任务 | 状态 | 交付 |
|:-----|:-----|:----:|:-----|
| W1 | Provider 插件化 (自定义 Provider 注册) | ✅ | `plugins.py` entry_points + API |
| W2 | `gateway generate` 流式输出支持 | ✅ | `--stream` / `-s` 参数 |
| W3 | `mesh generate` 多轮对话上下文 | ✅ | `--context` / `-c` + `--stream` |
| W4 | Swarm 健康检查 + 监控 API | ✅ | `SwarmMonitor` heartbeat + report |
| W5 | K8s Helm Chart 生产部署 | ✅ | `charts/aetherforge/` (Deployment/Service/Ingress/HPA/ConfigMap/ServiceMonitor) |

---

## 指标追踪

| 指标 | 当前 | Sprint 2 目标 | Sprint 3 目标 |
|:-----|:----:|:-------------:|:-------------:|
| 测试总数 | 57 | 80+ | 120+ |
| Provider 数量 | 9 | 12 | 15 |
| CLI 命令 | 16 | 20 | 25 |
| MCP Tools | 6 | 8 | 10 |
| 示例代码 | 0 | 5 | 10 |
| PyPI 下载量 | 0 | 100+/周 | 1000+/周 |

---

## 更新日志

| 日期 | 变更 |
|:-----|:------|
| 2026-06 | 台账创建，Sprint 1 完成 (9/9 Waves) |
