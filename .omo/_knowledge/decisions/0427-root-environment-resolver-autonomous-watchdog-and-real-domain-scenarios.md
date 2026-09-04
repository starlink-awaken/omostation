---
id: ADR-0427
status: archived
lifecycle: spec
owner: cockpit
last_updated: '2026-08-25'
---

# ADR-0427: 根级环境解析器、自愈看门狗与真实领域业务卡带架构

- **状态**: Accepted
- **日期**: 2026-08-25
- **决策者**: @Builder, @Sage, @Devil, @Keeper (B.D.S.K. 虚拟董事会)
- **关联**: ADR-0426 (AST Merge & SEMA), ADR-0193 (Policy-as-Code), ADR-0203 (Requirement Iteration)

---

## 1. 背景与问题陈述 (Context & Problem)

在 OMOStation 多智能体操作系统进入 Phase 8 深度演进期，系统面临以下三大物理摩擦与架构断层：
1. **多子仓环境碎片（PYTHONPATH 摩擦）**：各子仓（`projects/omo`, `projects/ecos`, `projects/cockpit`, `projects/agora`）隔离，开发者和 Agent 执行命令行时频繁遇到模块导入失败；
2. **总线服务常驻自愈盲区**：Agora 2.0 In-Memory Bus (:7432) 虽然接入了 supervisor，但缺乏独立的自愈探活看门狗，异常时无法向全局状态网格汇报；
3. **治理数据单调性与业务脱节**：Resident 自治决策系统过去积攒的 2,954 条历史提案 100% 为合成测试单点报错，缺乏真实人类垂直领域业务（如重大信息化项目评审、科技成果转化利益分配）的驱动与检验。

---

## 2. 核心架构决策 (Decisions)

### D1: 根级统一环境解析器与 CLI 网关 (`bin/_archive/2026-08-conv3/cockpit-env-resolver.py` & `bin/omostation`)
* 自动向上探测工作区根目录，动态将全仓 12 个子项目 `src/` 注入 `sys.path`；
* 提供统一根级可执行入口 `bin/omostation`，支持 `status`, `daemon`, `policy`, `resident`, `scenario`, `distill`, `watchdog` 等子命令，彻底消除跨仓调用的环境摩擦。

### D2: 守护自愈看门狗 (`bin/gac/daemon-watchdog.py`)
* 定时对 `http://127.0.0.1:7432/health` 进行毫秒级探活；
* 探测失败时自动触发自愈重启，记录事件日志至 `.omo/_delivery/watchdog.log` 并持久化状态至 `.omo/state/daemon-watchdog.json`。

### D3: 垂直领域真实业务场景卡带与全链路运行器 (`spaces/domain-scenarios/` & `bin/ssot/real-scenario-runner.py`)
* 在 `spaces/domain-scenarios/` 固化真实场景卡带（`weijian_hospital_cloud_review.yaml`、`tech_transfer_team_allocation.yaml`）；
* 通过 Policy-as-Code (`E-POL-WJ-001/002`, `E-POL-TF-001/002`) 执行严格业务规则判定；
* 将真实业务终审结果写入 Resident 决策提案收件箱（`.omo/_knowledge/decision-proposals/` 与 `evolution-proposals/`），打破合成数据单调性，形成真实战略级（`L3_STRATEGIC`）决策流。

---

## 3. 验证与防护机制 (Consequences & Verification)

* **单元与集成测试**：`tests/unit/test_phase8_unified_ecosystem.py` 5/5 全绿；
* **真实场景运行**：`./bin/omostation scenario` 完成 2 大真实领域业务端到端审查，输出 `DomainScenarioEvaluated` 决策提案；
* **门禁约束**：遵守 `governance-checks.yaml` 基线限额，维持 `make gac-local-gate` 绿线。
