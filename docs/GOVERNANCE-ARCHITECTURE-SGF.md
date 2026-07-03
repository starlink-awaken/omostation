# Starlit Self-Governance Framework (SGF-v1) — 大仓全栈自律治理框架设计书

> **最后更新**: 2026-07-03
> **架构定位**: 将大仓现有的松散、硬编码的 23 项 Gate 检测，系统性地重构为基于 **「元数据驱动」** 与 **「注意力折叠」** 的大统一治理框架。实现信息、架构、功能、注意力的四大收敛，以及规则、引擎、契约的三大机制转型。

---

## 🗺️ 架构大统一蓝图 (Grand Unified Architecture)

```mermaid
graph TD
    subgraph SSOT Declarative Layer (Rules as Data)
        A1[governance-policies.yaml]
        A2[submodule-manifests.yaml]
        A3[doc-freshness-rules.yaml]
    end
    
    subgraph Stateless Engine Layer (Data-Driven Execution)
        B1[gac-local-gate.py] -->|Loads YAML| A1
        B2[change-lane-check.py] -->|Loads YAML| A1
        B3[doc-ssot-lint.py] -->|Loads YAML| A3
        B4[submodule-reachability.py] -->|Loads YAML| A2
    end
    
    subgraph Attention & Presentation Layer (Cognitive Folding)
        B1 & B2 & B3 & B4 -->|FAIL / Needs-Human JSON| C[generate-brief.py]
        C -->|High-Priority Inbox| D[BRIEF.md 置顶待决策箱]
        C -->|Quiet Mode Folding| E[GAC 健康度折叠详情]
    end
    
    subgraph Test Protection Layer (TDD Safeguards)
        T1[test-gac-engine.py] -->|Asserts| B1
        T2[test-mcp-kos.py] -->|Asserts| B2
    end
```

---

## 💎 四大收敛原则 (The Four Convergence Principles)

### 1. 信息收敛 (Information Convergence)
* **现状痛点**: 冗长的 Gac Gate 校验日志（每次输出 100+ 行 `[PASS]`）稀释了屏幕空间，掩盖了真实错误。
* **收敛方案**: 
  - 启动 **「静默模式 (Quiet Mode)」**：当门禁全部通过时，终端仅输出单行 `GaC local gate: PASS (23/23 checks, ALL GREEN)`。
  - **异常回溯**：只有在发生 `FAIL` 时，才将该单项检查的 StackTrace 与 **「人工干预命令 (How-to-Heal)」** 打印输出，过滤掉 99% 的无用 PASS 信息。

### 2. 架构收敛 (Architectural Convergence)
* **现状痛点**: 挂载子模块、前台 SPA（`cockpit-ui`）与外部扩展服务（`toolbox`）在分层层面上存在松散定义与孤立悬挂。
* **收敛方案**: 
  - 所有项目实体（嵌入式、子模块或外部调用域）统一回归到 **L0 至 L∞ 的标准分层架构体系**。
  - 将 `cockpit-ui` 正式归为 `Layer L3`（表现面），将 `toolbox` 外部实例划归 `L1-L3`，消灭一切模糊的“Layer X（悬挂）”状态。

### 3. 功能收敛 (Functional Convergence)
* **现状痛点**: `gac-validate`、`gac-drift`、`ssot-guardian` 与 `omo-debt` 各自拥有独立的 CLI，甚至存在重复的读写 IO 冲突。
* **收敛方案**: 
  - 将所有治理工具的功能接口收拢至 `bin/agent-workflow.py` 的统一调度下。
  - 提供 `workflow bootstrap`、`workflow status` 和 `workflow verify`，使得外界 Agent 无论调用什么功能，都在同一个“进程沙箱”下运行，防止并发竞态。

### 4. 注意力收敛 (Attention Convergence)
* **现状痛点**: 开发者和 Agent 在拉起会话时，需要人肉去查阅 spaces、tasks 以及 docs 漂移。
* **收敛方案**: 
  - 以 `BRIEF.md` 里的 **「待决策收件箱 (Decision Inbox)」** 作为注意力漏斗。
  - 当健康分 $\ge 90$ 时，折叠一切系统防卫细节，逼迫 AI 仅将算力与上下文 Token 聚焦于**「置顶的 Needs-Human 决策项」**与**「X3 价值创作指标」**上。

---

## ⚙️ 三大工程机制 (The Three Engineering Mechanisms)

### 1. 规则数据化 (Rules as Data)
* 所有的校验边界、分流判定、写所有者、分支映射，全部定义为 YAML 文件，归档在 `projects/ecos/src/ecos/ssot/mof/m1/`。
* 严禁在 python 脚本中硬编码文件列表。规则是静态的数据，可以被版本控制与跨大仓分发。

### 2. 引擎配置化 (Stateless Engines)
* `change-lane-check.py` 等脚本只做“无状态断言处理器”。
* 运行时动态载入 YAML 数据，并生成对应的运行图。引擎的代码保持长期静默与不变，降低因修改引擎代码而产生的副作用。

### 3. 契约强测试 (TDD Safeguards)
* 每一个核心治理引擎都拥有专属的 `bin/test-*.py` 自测试用例。
* 测试用例自动检查 JSON-RPC 兼容性、写操作安全拦截，并直接接入 Gac local gate，保障大仓自律系统的自身健壮性。

---

## 📅 演进 Roadmap

| 阶段 | 治理项目 | 落地动作 | 验收指标 |
|------|----------|----------|----------|
| **Phase 1 (T+1)** | 元模型收敛 | 编写 `governance-policies.yaml` 与 `check-cockpit-ui-dist` 并上线。 | `make gac-local-gate` 100% 绿灯。 |
| **Phase 2 (T+30)** | 子模块收敛 | 重构 `submodule-reachability` 引擎，读取 `submodule-manifests.yaml` 代替硬编码。 | 彻底消灭 sub-module 漂移假报。 |
| **Phase 3 (T+60)** | 文档时效收敛 | 重构 `doc-ssot-lint`，读取 `doc-freshness-rules.yaml` 刷新时效分。 | 简报中可根据配置自适应算分。 |
| **Phase 4 (T+90)** | 注意力全面收拢 | 在 `BRIEF.md` 中集成 needs-human JSON 的自动收集和折叠。 | 任何门禁失败都会自动生成决策卡。 |
