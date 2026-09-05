---
id: ADR-0428
status: archived
lifecycle: spec
owner: cockpit
last-reviewed: '2026-08-26'
type: ssot
---

# ADR-0428: L3 单一人类入口收敛与 Cockpit 全域网关固化

- **状态**: Accepted
- **日期**: 2026-08-26
- **决策者**: @Builder, @Sage, @Devil, @Keeper (B.D.S.K. 虚拟董事会)
- **关联**: ADR-0427 (Root Resolver & Watchdog), ADR-0394 (Script Quota), ADR-0203 (Requirement Iteration)

---

## 1. 背景与问题陈述 (Context & Problem)

在前期工程演进中，为了快速解决 14 个 Git 子仓的多项目跨仓导入（`sys.path` 断裂）与根目录执行摩擦，曾引入了 `bin/omostation` 这一根脚本。虽然该脚本在工程层面实现了跨项目调用，但在系统架构纯洁性与治理契约上产生了以下反模式：
1. **违反单一人类入口契约（Single Human Entrypoint Contract）**：依据 DFSQ（道法术器）与 `ARCHITECTURE.md`，L3 唯一的人类与总控入口是 `cockpit`，引入 `omostation` 凭空创造了平行入口与第二品牌，增加了开发者和智能体的心智负担；
2. **根目录命名与路径冲突**：根目录历史存在 `bin/cockpit/` 子目录（存放生成工具），导致在某些 Shell PATH 环境下敲 `cockpit` 会尝试执行该目录从而报错 `permission denied`；
3. **能力分散与重复维护**：部分新能力（如业务场景审查 `scenario domain`、守护探针 `watchdog`）挂在外围脚本，未与 `projects/cockpit` 原生 CLI 的命令注册、参数解析及渲染树（Rich/TUI）深度融合。

---

## 2. 核心架构决策 (Decisions)

### D1: 彻底收敛到 Cockpit 原生体系
- 将 `env_resolver.py` 内置至 `projects/cockpit/src/cockpit/env_resolver.py`，并在 `cockpit/__init__.py` 与 `cockpit.cli` 初始化时自动注入全仓 14 个子项目的源码路径，使得任何地方 `import cockpit` 或执行 `cockpit` 均天然具备全仓上下文；
- 将 `watchdog`（守护犬探针）、`policy`（Policy-as-Code 审查）、`scenario domain`（真实业务审查）等完整实现为 `cockpit` 原生子命令（`cockpit watchdog`, `cockpit policy`, `cockpit scenario domain`）。

### D2: 消除目录冲突与根入口规范化
- 清理 `bin/cockpit/` 子目录，将其中的生成工具（`gen-capability-registry.py`, `gen-help-docs.py`）迁移至 `bin/ssot/`；
- 在根目录建立可执行脚本 `bin/cockpit`，透明委托到 `cockpit.cli:main`，彻底实现终端 `cockpit` 与 `./bin/cockpit` 统一无缝调度；
- 彻底废除并删除 `bin/omostation` 平行入口。

### D3: 严格遵循脚本配额守恒（ADR-0394 / ADR-0423）
- 删除 `bin/omostation` (-1)、清理 `bin/_archive/2026-08-conv3/cockpit-env-resolver.py` (-1)，新增 `bin/cockpit` (+1)，迁移 2 个脚本至 `bin/ssot/`，净脚本增量为负数（-1），完美满足零膨胀与减法治理要求。

---

## 3. 验证与防护机制 (Consequences & Verification)

1. **统一入口测试**：`tests/unit/test_phase8_unified_ecosystem.py` 9/9 全部 PASS，验证 `bin/cockpit --help` 与各子命令；
2. **Cockpit 全量子仓测试**：`projects/cockpit` 1,359 项单元与集成测试 100% 通过；
3. **脚本注册表一致性**：`python3 bin/ssot/script-registry.py validate` 493 项脚本全量合规通过；
4. **配额守恒校验**：`python3 bin/gac/check-bin-quota-diff.py --base origin/main` 确认增量守恒；
5. **子模块指针状态**：14 个子模块全量对齐（0 DIVERGED）。
