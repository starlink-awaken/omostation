# Pitch: 合并 llm-gateway 到 aetherforge，完成 AetherForge 三位一体收敛

> **Upstream**: MS-ARCHITECTURE-CONVERGENCE — 消除 eCOS v6 中 AetherForge 能力双轨制，统一 LLM 网关入口
> **Appetite:** 1 Week

## 🎯 The Why (Problem & Opportunity)

当前 eCOS v6 中，`llm-gateway`、`compute-mesh`、`swarm-engine` 三个项目的能力已被 AetherForge 以 workspace 形式复制到 `projects/aetherforge/packages/{gateway,mesh,swarm}/`，但原独立项目仍在并行维护。这种"双轨制"导致：

1. **代码漂移风险**：`llm-gateway` 与 `aetherforge/packages/gateway/` 能力高度重叠但文件数不一致（26 vs 35），双向修改易造成回归；
2. **入口碎片化**：外部调用方可能同时使用 `llm-gateway` CLI 和 `aetherforge gateway` CLI；
3. **维护成本**：独立子模块需要独立 CI、独立依赖管理、独立文档；
4. **架构叙事不一致**：AetherForge README 已将 gateway 列为三包之一，但 `llm-gateway` 仍以独立项目存在。

本次聚焦**最低风险、最高杠杆**的 `llm-gateway` → `aetherforge/packages/gateway/` 合并，为后续 `compute-mesh`、`swarm-engine` 的合并建立范本。

## 🚧 The What (Solution Overview)

1. **能力归并**：将 `llm-gateway/src/llm_gateway/` 中独有的能力迁移到 `aetherforge/packages/gateway/src/llm_gateway/`，统一以 `aetherforge-gateway` 包对外提供；
2. **入口收敛**：保留 `aetherforge gateway *` CLI，废弃 `llm-gateway *` CLI；
3. **L0 模型更新**：将 `BOSROUTE-KAIRON-llm-gateway` 的 `realized_by` 从 `kairon` 修正为 `aetherforge`，并补充 `COMP-WS-aetherforge` 的子能力引用；
4. **X1-X4 治理更新**：记录合并审计、更新价值栈归属、标记 `llm-gateway` 为 archived；
5. **配置与 CI 清理**：更新 `agora` BOS 路由、清理根 Makefile 与 CI workflow；
6. **旧项目归档**：在 `llm-gateway/` 创建 `ARCHIVED.md`，`pyproject.toml` 标记 inactive；
7. **文档刷新**：更新根文档、项目 `ARCHITECTURE.md` / `BOUNDARY.md` 等交叉引用。

## 📏 Boundaries & Appetites

- **Appetite:** 1 Week（中等复杂度，高架构影响）。
- **Scope:** 仅 `llm-gateway`；不合并 `compute-mesh`、`swarm-engine`、`aetherforge-swarm-ext`。
- **No-Gos:** 不删除 `llm-gateway` 仓库历史；不破坏现有 `bos://capability/forge/*` 调用契约；不修改 LLM Provider 核心实现逻辑，只调整归属与入口。

## ⚠️ Rabbit Holes & Risks

- **代码分叉差异**：`aetherforge-gateway` 比原 `llm-gateway` 多 9 个文件，需逐一确认哪些是新增能力、哪些是重构，避免覆盖；
- **BOS URI 兼容性**：`bos://kairon/llm-gateway` 等旧路由需保留 deprecated alias 至少一个 Phase；
- **依赖方影响**：`compute-mesh`、`aetherforge-mesh`、`runtime` 等可能依赖 `llm-gateway` 包，需改为 `aetherforge-gateway`；
- **MOF 校验链**：任何 M1 节点改动必须通过 `mof-schema-validate --strict`、`mof-derive`、`mof-bridge-sync`。

## ✅ 验收标准

1. `cd projects/aetherforge && make test` 通过；
2. `cd projects/agora && uv run pytest tests/ -k bos` 通过；
3. `cd projects/ecos && uv run python src/ecos/ssot/tools/mof-schema-validate.py --strict` 退出码 0；
4. `llm-gateway/ARCHIVED.md` 存在，`pyproject.toml` 标记 inactive；
5. `docs/PANORAMA.md` 不再将 `llm-gateway` 列为独立活跃项目；
6. 生成并提交 C2G Bet 与 OMO Task。
