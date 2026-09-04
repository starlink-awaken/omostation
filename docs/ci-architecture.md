---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# 🏗️ Monorepo CI/CD Architecture & Multi-Tier Governance Specification

> **SSOT Reference**: `CR-CI-ARCHITECTURE-V2` / `.omo/_truth/registry/ci-surfaces.yaml`  
> **Target Version**: `omostation CI v2.4` / Python 3.13 / `uv` / GitHub Actions  

---

## 1. 架构愿景与分层门禁体系 (Multi-Tier Gating Topology)

在现代化 AI 原生与多子模块（Submodule）异构单体大仓（Monorepo）中，CI 流水线扮演 **操作系统级内核门禁** 的角色。我们构建了从 `L0` 到 `L3` 的四级防御体系：

```
+-------------------------------------------------------------------------------+
|                       Level 3: Governance & Value Flow                        |
|   (gac-gate.yml / phase-gate-enforce.yml / omostation-governance.yml)        |
|   - SSOT 真理一致性校验 (Truth & Registries)                                   |
|   - 子模块指针祖先防降级 (PASW & No-Rewind)                                     |
|   - 交付物完备性与 ADR Frontmatter 闭环                                       |
+-------------------------------------------------------------------------------+
                                      ▲
                                      │ (Pass Level 2)
+-------------------------------------------------------------------------------+
|                   Level 2: Cross-Project & Topological Mesh                   |
|   (cascading-test.yml / ci-lint.yml / capability-registry-drift)              |
|   - 基于 layer-contract.yaml 的依赖拓扑级联测试 (Topological Cascading)        |
|   - Agent 技能包规范校验 (check-agent-skills.py)                              |
|   - BOS URI 路由与 Agora MCP Hub 契约一致性                                    |
+-------------------------------------------------------------------------------+
                                      ▲
                                      │ (Pass Level 1)
+-------------------------------------------------------------------------------+
|                   Level 1: Project-Level Independent Suites                   |
|   (omlxc-ci.yml / aetherforge-ci.yml / cockpit-ci.yml / agora-ci.yml ...)     |
|   - 项目级单元测试 (Pytest / Vitest) 覆盖率与断言                              |
|   - 硬件感知算力网格自检 (omlxc fabric inspect / warm)                         |
+-------------------------------------------------------------------------------+
                                      ▲
                                      │ (Pass Level 0)
+-------------------------------------------------------------------------------+
|                       Level 0: Syntax, Types & Cleanliness                    |
|   (quality.yml / pyright-sweep.yml / ci-local-fast.py)                        |
|   - Ruff AST 语法规则与 Import 排序                                            |
|   - Pyright Strict 全量类型健全性                                             |
|   - ShellCheck 脚本安全 & YAML 格式可解析性                                    |
+-------------------------------------------------------------------------------+
```

---

## 2. 核心子系统流水线清单 (Workflows Catalog)

| 工作流文件 | 监控范围 | 触发事件 | 核心职责 |
| :--- | :--- | :--- | :--- |
| **`omlxc-ci.yml`** | `projects/omlxc/**` | `push`, `pull_request` | Ruff, Pyright Strict, 1043+ Pytest 单测, 算力织网与预热冒烟 |
| **`aetherforge-ci.yml`** | `projects/aetherforge/**` | `push`, `pull_request` | AetherForge 网关与蜂群调度单测 (540+ Pytest) |
| **`cockpit-ci.yml`** | `projects/cockpit/**` | `push`, `pull_request` | Cockpit CLI / Web 后端单测与算力大盘 API |
| **`cockpit-ui-ci.yml`** | `projects/cockpit-ui/**` | `push`, `pull_request` | 前端 Vite 构建、TypeScript 类型校验与 Lint |
| **`agora-ci.yml`** | `projects/agora/**` | `push`, `pull_request` | FastMCP 工具单测与 SSE 网关存活探针 |
| **`ci-lint.yml`** | `.github/**`, `scripts/**`, `.agents/**` | `push`, `pull_request`, `cron` | Actionlint, ShellCheck, YAML Lint, **Agent Skills 校验**, SSOT 漂移 |
| **`cascading-test.yml`** | `projects/**` | `push`, `pull_request` | 基于 `affected-graph.py` 拓扑动态级联触发下游测试 |
| **`phase-gate-enforce.yml`** | `projects/**`, `bin/**` | `pull_request` | PR 合并硬阻断门禁，验证 Phase 解锁判定与度量收敛 |

---

## 3. 效能与性能优化机制 (Efficiency & Caching Principles)

1. **`uv` 依赖跨 Job 极速缓存 (`astral-sh/setup-uv@v4`)**：
   - 统一声明 `enable-cache: true` 与 `cache-dependency-glob: "projects/*/pyproject.toml"`。
   - 减少重复拉取与轮子编译开销，全量 CI Job 准备耗时从 30s 缩减至 < 3s。
2. **基于 Git Diff 的按需增量触发 (Path Filtering)**：
   - 细粒度锁定各子仓触发路径，避免单项目改动引发全仓 40+ Job 冗余运行。
3. **拓扑级联智能推导 (Topological Pruning)**：
   - `bin/gac/affected-graph.py` 依据 `docs/layer-contract.yaml` 精确推导受影响的上下游子项目，仅针对下游真实依赖执行回归测试。

---

## 4. 智能体资产与技能门禁 (Agent Skills Governance)

所有位于 `.agents/skills/*/SKILL.md` 的技能包必须满足：
- **标准 YAML Frontmatter**：包含合法的 `name`（字母/数字/中划线/下划线/冒号命名空间）与详细的 `description`。
- **静态合规命令**：
  ```bash
  # 本地与 CI 执行 Agent Skills 门禁
  python3 bin/ssot/check-agent-skills.py
  python3 bin/ssot/check-agent-skills.py --json
  ```
- **CI 集成**：已接入 `ci-lint.yml` 的 `agent-skills-lint` 阶段，任何损坏的 Frontmatter 或非法字符将立即阻断 PR。
