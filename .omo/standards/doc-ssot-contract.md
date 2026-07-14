---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-29
---

# 文档 SSOT 正交契约 (Doc SSOT Orthogonal Contract)

## 问题

同一事实散布在 28+ 文件中，改一处要改几十处。例如：
- "5+4+1+1" 出现在 28 个文件
- "kairon 16 包" 出现在 8 个文件
- "Python 3.13+" 出现在 11 个文件

打补丁式修复不可持续。需要正交拆分。

## 正交原则

**每个文档类型只 own 一个维度，禁止跨维度复制。**

### 维度定义

| 维度 | 内容 | 稳定性 | Owner 文档 |
|------|------|--------|-----------|
| **事实层 (SSOT)** | 易变数字: 包数/测试数/工具数/Phase/健康分/版本号 | 高频漂移 | 机器可读文件 (yaml/pyproject.toml/代码) |
| **架构层** | 稳定原则: 分层定义/依赖方向/BOS域划分/治理规则 | 低频变化 | ARCHITECTURE.md / PANORAMA.md |
| **操作层** | 开发命令: build/test/lint 命令/约定/gotchas | 中频变化 | AGENTS.md / CLAUDE.md |
| **边界层** | 接口定义: BOS URI/依赖方向/入口/端口 | 低频变化 | BOUNDARY.md |
| **入口层** | 快速开始/导航/README | 中频变化 | README.md |

### 规则

1. **禁止 markdown 包含易变数字** — 包数、测试数、工具数、LOC、Phase、健康分
   - 这些值的唯一读源见下方 SSOT 映射表
   - markdown 中用指针替代: "见 `docs/project-registry.yaml`" 或 "以实际为准"

2. **允许 markdown 包含稳定架构概念** — "5+4+1+1"、"L0-L4"、"eCOS v6" 这些是架构定义，不是易变数字
   - 但架构版本 ("v6") 只应出现在架构层文档中，不应出现在每个项目的 AGENTS.md 里
   - 项目级文档只需说 "见根 ARCHITECTURE.md" 即可

3. **项目元数据统一读源** — `docs/project-registry.yaml` 是项目层/包数/工具数/Python版本的唯一读源
   - 该文件本身从实际代码 (pyproject.toml, 代码 grep) 派生

## SSOT 映射表

| 事实类型 | 唯一读源 | 禁止出现在 |
|---------|---------|-----------|
| Phase / 健康分 / 任务数 | `.omo/state/system.yaml` | 所有 markdown |
| 项目包数 / 工具数 / 源文件数 | `docs/project-registry.yaml` | 所有 markdown |
| 项目分层索引 | `docs/project-registry.yaml` → `docs/generated/project-layer-index.md` | README / AGENTS / ARCHITECTURE / LAYER-INDEX |
| Python 版本 | `docs/project-registry.yaml` ← `pyproject.toml` | 所有 markdown |
| BOS 服务数 / 域数 | `projects/agora/etc/bos-services.yaml` | 所有 markdown |
| 端口号 | `protocols/port-registry.yaml` | 所有 markdown |
| MOF M1/M2 节点数 | `projects/ecos/src/ecos/ssot/mof/` | 所有 markdown |
| L0 约束规则 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` | 所有 markdown |
| X1-X4 治理规则 | `.omo/_truth/x1-*.yaml` ~ `x4-*.yaml` | 所有 markdown |
| GaC 规则 | `.omo/_truth/registry/governance-checks.yaml` | 所有 markdown |
| Agent-facing GaC digest | `docs/generated/agent-gac-rules.md` ← `governance-checks.yaml` | `AGENTS.md` pointer only |
| 测试通过率 | 各项目本地 CI / pytest / bun test | 所有 markdown |

## CI 门禁

`bin/ssot/doc-ssot-lint.py` 扫描所有 markdown 文件，检测:

1. **硬编码数字冲突** — markdown 中的数字与 `project-registry.yaml` 冲突 (e.g. markdown 说 "19 包" 但 registry 说 16)
2. **缺失指针** — markdown 提到项目元数据但未引用 registry
3. **过期架构版本** — markdown 中出现 "eCOS v5" 或 "5+3+1"

运行方式:
```bash
python3 bin/ssot/doc-ssot-lint.py              # 检测, 有冲突返回 1
python3 bin/ssot/doc-ssot-lint.py --fix        # 自动修复已知模式 (v5→v6 等)
python3 bin/ssot/doc-ssot-lint.py --json       # 机器可读 JSON (gac-healthcheck 消费)
```

## GaC 规则绑定 (ADR-0106)

本契约由 GaC 规则 `CR-X4-DOC-SSOT` 强制执行 (声明式注册 + 泛化执行器):

| 维度 | Owner | 内容 |
|------|-------|------|
| 契约 (人类可读) | 本文件 (`.omo/standards/doc-ssot-contract.md`) | 正交原则 + 禁止行为清单 |
| GaC 规则 (机器注册) | `.omo/_truth/registry/governance-checks.yaml::CR-X4-DOC-SSOT` | dimension=X4, layer=meta, executor=ci_gate |
| 执行器 (CI 门禁) | `bin/ssot/doc-ssot-lint.py` | 检测硬编码冲突, `--json` 供仪表盘 |
| 生成物 | `docs/generated/project-layer-index.md` / `docs/generated/agent-gac-rules.md` | 由对应 bin 脚本生成, Markdown 入口只保留指针 |
| 元治理自检 | `bin/gac/gac-healthcheck.py` | doc_ssot 块 (ok/conflicts/files_scanned) |

三者正交, 各 own 一个维度: 契约改 → 更新本文件; 执行逻辑改 → 更新 doc-ssot-lint.py; 规则注册改 → 更新 governance-checks.yaml。禁止跨维度复制 (本契约 own 正交定义, 不复制 GaC 规则字段)。

## 文档类型职责矩阵

| 文档 | 事实层 | 架构层 | 操作层 | 边界层 | 入口层 |
|------|:------:|:------:|:------:|:------:|:------:|
| project-registry.yaml | **OWN** | — | — | — | — |
| system.yaml | **OWN** | — | — | — | — |
| ARCHITECTURE.md | ref | **OWN** | — | — | — |
| AGENTS.md | ref | ref | **OWN** | — | — |
| CLAUDE.md | ref | ref | **OWN** | — | — |
| BOUNDARY.md | ref | ref | — | **OWN** | — |
| CALLCHAIN.md | ref | ref | — | ref | — |
| README.md | ref | ref | ref | — | **OWN** |
| LAYER-INDEX.md | ref | **OWN** | — | — | — |
| PANORAMA.md | ref | **OWN** | — | ref | — |

**OWN** = 该文档拥有此维度 (写入权)  
**ref** = 该文档引用此维度 (只读指针)  
**—** = 该文档不应涉及此维度

## 禁止行为清单

1. ❌ 在 CLAUDE.md 写 "kairon 16 包" → 应写 "见 `docs/project-registry.yaml`"
2. ❌ 在 AGENTS.md 写 "Phase 42" → 应写 "见 `.omo/state/system.yaml`"
3. ❌ 在 README.md 写 "1200 tests" → 应写 "以实际 CI 结果为准"
4. ❌ 在 BOUNDARY.md 写 "10+ tools" → 应写 "以实际为准"
5. ❌ 在项目级 AGENTS.md 写 "eCOS v6" → 应写 "见根 ARCHITECTURE.md"
6. ✅ 在 project-registry.yaml 写 "packages: 16" → 这是 SSOT 写入点
7. ✅ 在 ARCHITECTURE.md 写 "5+4+1+1 架构" → 这是架构层 OWN

## 实施路径

1. ✅ `docs/project-registry.yaml` — 已创建，项目元数据 SSOT
2. ✅ `.omo/standards/doc-ssot-contract.md` — 本文件，正交契约定义
3. `bin/ssot/doc-ssot-lint.py` — CI 门禁脚本 (检测硬编码冲突)
4. 根文档更新 — CLAUDE.md / AGENTS.md 引用本契约
5. 子项目文档清理 — 逐步将硬编码指针化 (本批次已完成大部分)
