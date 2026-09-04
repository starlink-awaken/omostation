---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0194: Dual-Plane Truth Canvas 轻量态势看板与全域混沌对抗演练架构

- **状态**: `ACCEPTED`
- **日期**: 2026-08-17
- **作者**: Builder (建造者) & Devil (批判者) & Keeper (观察者)
- **关联架构**: ADR-0191, ADR-0192, ADR-0193

---

## 1. 背景与业务痛点 (Context & Problem)

1. **事实真源可视化缺失**：经过 ADR-0192 治理后，`Documents/@工作文档/` 沉淀了标准 YAML 事实真源，但业务人员与主管缺乏直观的可视化看板来查看保鲜度、SLA 倒计时及生命周期状态。
2. **反脆弱验证不足**：各工程（ecos, omlxc, runtime）各自具备静态规则，但缺乏主动注入“畸变流量”与“攻击负载”的端到端红蓝对抗演练机制。
3. **架构踩坑经验未结构化**：开发过程中遇到的 AST 拦截限制、目录边界污染等陷阱容易在未来的迭代中被遗忘或重犯。

---

## 2. 架构设计与决策 (Decision & Architecture)

### 2.1 Dual-Plane Truth Canvas Web UI
- **轻量零依赖**：基于 Python 标准库 `http.server.HTTPServer` 实现单文件轻量 Web 服务器，内嵌现代深色模式响应式 CSS SPA。
- **动态 REST API**：
  - `GET /api/facts`：聚合扫描多领域事实真源，返回保鲜 SLA 状态、剩余保鲜天数、生命周期分布。
  - `POST /api/facts`：提供安全表单反向写回（Safe Form Writeback），写盘前强制通过 `FactInspector` 校验，非法数据自动回滚拒绝。
- **启动命令**：`ecos-constraint facts serve [--port 8765]` 或 `make canvas-serve`。

### 2.2 全域混沌注入演练套件 (`make chaos-drill`)
`bin/ssot/chaos-governance-drill.py` 自动化注入 4 种变异场景：
1. **Documents Plane Invasion Mutation**：向 Documents 写入 `.py` / `.venv` / `node_modules`，验证 `PathBoundaryInspector` 100% 阻断。
2. **Corrupted & Stale Fact Mutation**：注入非法 Schema 与 60 天过期事实，验证 `FactInspector` 成功识别并拦截。
3. **Policy Red-Line Bypass Mutation**：注入高额超限无论证方案与低收益比方案，验证 `PolicyComplianceInspector` 拦截率 100%。
4. **Compute Fabric VRAM & Thermal Shock**：模拟 128k 极端上下文与 HEAVY 极端温控，验证 `ContextCompactor` 压缩 (>40%) 与 `ThermalGuard` 降权惩罚。

### 2.3 Agent 架构避坑知识库 (`PitfallInspector`)
- 归档已知踩坑模式于 `.omo/_knowledge/pitfalls/`。
- `PitfallInspector` 静态扫描代码中的已知反模式（如 `PITFALL-001` Gatekeeper 直接写盘、`PITFALL-002` Documents 脚本污染）。
- 纳入日常静态扫描：`ecos-constraint pitfall scan`。

---

## 3. 治理命令一览 (Commands)

```bash
# 1. 启动事实态势大盘
make canvas-serve
# 或
ecos-constraint facts serve --port 8765

# 2. 运行混沌红蓝对抗演练
make chaos-drill
make chaos-drill-strict

# 3. 架构避坑扫描
ecos-constraint pitfall scan .
ecos-constraint pitfall list
ecos-constraint pitfall explain PITFALL-001
```

---

## 4. 架构成果与影响 (Consequences)

- 实现了领域事实的“零门槛可视化浏览与合规写回”。
- 将系统鲁棒性从“被动防御”提升为“主动混沌演练与常态对抗”，达成 100% 自愈与拦截验证。
- 固化避坑知识库，彻底阻断历史隐患与反模式的再次复发。
