# Phase 30 — 架构成熟度自动化 (Architecture Maturity Automation)

> **状态**: ✅ 已完成 (P30, 2026-06-06)
> **实施摘要**: kairon 23→20 包, 5→6 项目, omo 吸收 kairon-governance
> **见**: `decision-p30-architecture-final.md` + `.omo/_delivery/phase30-verify-report.md`
>
> ⚠️ **SUPERSEDED** by `.omo/_knowledge/management/decision-p30-architecture-final.md` (2026-06-06)
> 原计划: 4 规则架构合规检查
> 实际: 改为物理拆分 + 治理整合 (见 decision-p30)

> 目标: 建立自动化的架构合规检查，阻止 5+3+1 文档与代码的偏差持续扩大
> 优先级: P1 | 预估: 2-3 周
> 依赖: Phase 29 (工具体系基座)

---

## 一、需求分析

### 1.1 问题陈述

当前架构成熟度完全靠人工判断：健康评分 100 不意味着系统好，只意味着已知债务全清。架构文档与代码的偏差没有自动检测手段。

| 偏差类型 | 示例 | 当前检测方式 |
|---------|------|-------------|
| 层归属偏差 | Agora 定义为 I0 但代码在 kairon/packages/ | 无，仅靠文档标注 |
| 协议定义偏差 | L0 注册表中 16 协议但有 14 个无运行时 | 已加 validate_protocol_message 但非自动化 |
| 测试覆盖偏差 | 核心包测试低于安全基线 | 无自动检测 |
| 依赖偏差 | 跨包通信绕开 Agora | BYPASS-001~009 已修，但无回归检测 |

### 1.2 用户故事

- **作为架构师**，我希望每次 Phase 结束时自动收到一份"架构合规检查报告"
- **作为开发者**，我希望提交代码时知道是否违反了架构约束（如直接调用 L2 层 API）
- **作为治理系统**，我希望健康评分 100 真正意味着"架构文档与代码一致"

### 1.3 验收标准

- [ ] 创建 `scripts/architecture-compliance-check.sh` — 一键运行全量架构规则
- [ ] 至少覆盖: 层依赖规则、协议注册表完整性、核心包测试基线、Agora 总线唯一性
- [ ] 接入 CI (meta-model-check.yml 的扩展)
- [ ] 输出 JSON 格式报告供 .omo/ 治理系统消费

---

## 二、实施计划

### Wave 1: 架构规则定义 (2h)
- [ ] 从 5+3+1 SSOT 文档提取可自动化的规则
  - L0: 协议必须有运行时验证
  - L1: 所有服务必须在 Runtime Matrix 注册
  - L2: 三平面间通信必须走 I0 (Agora)
  - I0: Agora 是唯一集成织层
- [ ] 定义规则优先级: ERROR(阻止提交) / WARN(报告) / INFO(记录)
- [ ] 输出: `.omo/standards/architecture-rules.yaml`

### Wave 2: 检查器实现 (4h)
- [ ] 创建 `scripts/architecture-compliance-check.sh`
  - 规则 1: 检查所有包的 import 是否有跨层直接调用（禁止从 L2 直接调 L2 的另一个平面）
  - 规则 2: 检查 protocol 注册表中的每个协议是否有 `implementations` 字段
  - 规则 3: 检查核心包 (core-models, cron-service, engine-core) 测试文件数 > 10
  - 规则 4: 检查 .omo/state/system_health.yaml 中各服务是否在 Matrix 中
- [ ] 输出: JSON + 人类可读报告

### Wave 3: CI 集成 (1h)
- [ ] 扩展 `meta-model-check.yml` 为 `architecture-compliance.yml`
- [ ] 每次 PR 自动运行
- [ ] 失败时在 PR 上评论违规详情

---

## 三、参考

- 架构 SSOT: `~/Documents/学习进化/2-knowledge/基建架构/eCOS-v5-Architecture-SSOT.md`
- 当前 CI: `.github/workflows/meta-model-check.yml`
- 规则模板: `.omo/standards/`
