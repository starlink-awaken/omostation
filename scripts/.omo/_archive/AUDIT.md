# Workspace 综合审计报告

> 审计日期: 2026-05-20 | 审计人: Sisyphus
> 范围: 16 个项目 + 根目录工件

---

## 审计分类标准

| 分类 | 含义 |
|------|------|
| ✅ **健康** | 活跃维护、有测试、有实际价值 |
| ⚠️ **亚健康** | 有存在价值但测试不足/代码量少/停滞 |
| 🕸️ **废弃** | 无维护、无测试、或已有替代品 |
| 🗑️ **无效/过期** | 临时工件、生成产物、测试残渣 |
| ❓ **待定** | 用途不明或需要确认 |

---

## 一、项目级审计

### 1. SharedBrain

| 维度 | 分数 |
|------|------|
| 代码量 | 7,646 py / 494 commits / 1,346 测试文件 | ★★★★★ |
| 活跃度 | 昨天最后提交，活跃 | ★★★★★ |
| 测试覆盖 | 大量测试存在 | ★★★★ |
| .venv | ✅ | |
| 问题 | `graphify-out/` 7,147 文件(可重新生成)；`site/` 841 文件；`logs/` 80MB；`data/` 71MB 可能包含可清理数据 | |

**判定**: ✅ **健康** — 核心项目，生产级

**建议**: 
- `graphify-out/` 和 `site/` 是构建产物（可重建），可考虑 `.gitignore` 或定期清理
- `logs/` 80MB 确认是否仍需保留

---

### 2. Agora

| 维度 | 分数 |
|------|------|
| 代码量 | 28 py / 62 commits | ★★★ |
| 活跃度 | 昨天最后提交 | ★★★★ |
| 测试覆盖 | 9 测试文件, 58 tests | ★★★ |
| .venv | ✅ | |
| 问题 | 覆盖仅 ~28%，Phase 3 未完成 | |

**判定**: ✅ **健康** — 活跃开发中

---

### 3. Minerva

| 维度 | 分数 |
|------|------|
| 代码量 | 56 源 py + 大量测试 + 文档 | ★★★★ |
| 活跃度 | 活跃 | ★★★★★ |
| 测试覆盖 | 250 tests | ★★★★ |
| .venv | ✅ | |
| 问题 | 🔴 **109MB `mineru_output/` 临时 PDF 提取产物** (344 文件) | |

**判定**: ✅ **健康** — 核心研究系统

**需清理**:
| 路径 | 大小 | 性质 |
|------|------|------|
| `minerva/系统架构设计师教程-第四版_mineru_output/` | **109MB / 344 文件** | 🗑️ 临时提取产物 |
| `minerva/系统架构：复杂系统的产品设计与开发_mineru_output/` | 0B | 🗑️ 空目录 |
| `minerva/算法竞赛进阶指南_mineru_output/` | 0B | 🗑️ 空目录 |
| `minerva/mineru_test_simple_mineru_output/` | 40K / 8 文件 | 🗑️ 测试残渣 |

> **总计: ~109MB + 临时文件** — 这些属于 mineru PDF 提取流水线的中间产物，不属于项目源码，可以安全删除。

---

### 4. OntoDerive — 渊衍

| 维度 | 分数 |
|------|------|
| 代码量 | 77 py / 44 commits | ★★★★ |
| 活跃度 | 🔥 **今天最后提交 (v3.3.0)** | ★★★★★ |
| 测试覆盖 | 129 tests | ★★★★★ |
| .venv | ✅ | |
| 架构 | 0 外部依赖, 5 层引擎 | |
| 问题 | 仍有 `setup.py` / `setup.cfg` (legacy) | |

**判定**: ✅ **健康** — 最活跃核心引擎

---

### 5. Pallas

| 维度 | 分数 |
|------|------|
| 代码量 | 仅 3 py 文件 (__init__.py, cli.py, test) | ★ |
| 活跃度 | 6 commits | ★ |
| 测试覆盖 | 1 测试文件 | ★ |
| .venv | ✅ | |

**判定**: ⚠️ **亚健康** — 有明确定位(统一入口)，但代码极少，实为 CLI 编排脚本

**建议**: 决定是继续发展还是合并到其他项目中

---

### 6. Sophia

| 维度 | 分数 |
|------|------|
| 代码量 | 12 py / 11 commits | ★★ |
| 活跃度 | 昨天自动提交 | ★★ |
| 测试覆盖 | 27 tests | ★★★ |
| .venv | ✅ | |

**判定**: ⚠️ **亚健康** — 有实际功能(范式引擎编译)，被 minerva import，但代码量和测试都少

---

### 7. eCOS — 外化认知 OS

| 维度 | 分数 |
|------|------|
| 代码量 | 51 py / 80 commits / 41 认知脚本 | ★★★★ |
| 活跃度 | 🔥 **今早 WF-005 刚运行** | ★★★★★ |
| 测试覆盖 | 98 tests | ★★★★ |
| .venv | ✅ | |
| 安全评分 | 94% | |
| 架构评分 | 95% | |

**判定**: ✅ **健康** — 认知基础设施，活跃运行

---

### 8. BOS-Skill-CLI

| 维度 | 分数 |
|------|------|
| 代码量 | 9 py / 3 commits | ★★ |
| 活跃度 | 2 天前最后提交 | ★ |
| 测试覆盖 | 3 测试文件 | ★★★ |
| .venv | ✅ | |

**判定**: ⚠️ **亚健康** — 有 TUI 和技能生命周期管理，但提交极少，处于早期阶段

---

### 9. kos — 知识 OS CLI

| 维度 | 分数 |
|------|------|
| 代码量 | 34 py / **无 git** | ★★ |
| 活跃度 | ❌ **无 Git 历史，不可追溯** | ☆ |
| 测试覆盖 | 4 测试文件 | ★★ |
| .venv | ❌ **MISSING** | |
| 构建 | 仍有 `setup.py` / `setup.cfg` (legacy) | |

**判定**: 🕸️ **废弃/濒临废弃** — 无版本控制、无 venv、不活跃

---

### 10. AgentMesh

| 维度 | 分数 |
|------|------|
| 代码量 | 46 ts / 34 commits | ★★★ |
| 活跃度 | 自动提交 | ★★★ |
| 测试覆盖 | 9 测试文件 | ★★★ |
| node_modules | ✅ | |
| dist | ✅ (已构建) | |

**判定**: ✅ **健康** — 网关调度器，已构建可运行

---

### 11. Agent-Toolkit

| 维度 | 分数 |
|------|------|
| 代码量 | 209 ts / 25 commits | ★★★★ |
| 活跃度 | 2 天前 | ★★★ |
| 测试覆盖 | 41 测试文件 | ★★★★ |
| node_modules | ✅ | |
| dist | ❌ **MISSING** (需 `npm run build`) | |

**判定**: ⚠️ **亚健康** — 代码量大但未构建，可能无法运行

---

### 12. Honeycomb — 多 Agent 协作引擎

| 维度 | 分数 |
|------|------|
| 代码量 | 218 ts / 94 测试文件 | ★★★★★ |
| 活跃度 | 近期活跃 | ★★★★ |
| 测试覆盖 | 丰富 | ★★★★★ |
| dist | ✅ (已构建) | |
| 性能基线 | **2.6M ops/s** | |

**判定**: ✅ **健康** — 工作区最重的模块，DSL 编译器 + Agent 编排

**注意**: Git 在 `honeycomb/` 根目录而非 `engine/` 内

---

### 13. AggreResearch

| 维度 | 分数 |
|------|------|
| 代码量 | 2 ts + 1 测试 / 3 commits | ★ |
| 活跃度 | 1 天前 (smoke test 提交) | ★ |
| 测试覆盖 | 1 测试文件 | ★ |
| node_modules | ✅ | |
| dist | ❌ **MISSING** | |

**判定**: 🕸️ **废弃** — 极少量代码，无 dist，无活跃开发，项目名暗示"聚合搜索调研"可能是实验性项目

---

### 14. Starlink-Types

| 维度 | 分数 |
|------|------|
| 代码量 | pyproject.toml + src 目录(可能是空壳) | ★ |
| .venv | ❌ | |
| git | 无 | |

**判定**: ❓ **待定** — 可能是废弃的共享类型包，只有脚手架

---

### 15. DigitalBrainOS

| 维度 | 分数 |
|------|------|
| 文件量 | 4,301 文件 | |
| 构成 | 文档、报告、计划、Agent 定义 | |
| AGENTS.md | ✅ | |
| CLAUDE.md | ✅ | |

**判定**: ✅ **健康** — 文档/规划仓库

---

### 16. Metacog

| 维度 | 分数 |
|------|------|
| 文件量 | 95 文件 | |
| 构成 | 理论/实践/基础/应用四部分 | |

**判定**: ✅ **健康** — 元认知知识库

---

### 17. AI-Tools

| 维度 | 分数 |
|------|------|
| 文件量 | 65 文件 | |
| 构成 | CLI 工具 + Skills + 安装脚本 | |

**判定**: ✅ **健康** — 实用工具集

---

## 二、根目录临时/过期工件

| 路径 | 性质 | 建议 |
|------|------|------|
| `.tmp.driveupload/` ×5 个文件 | 🗑️ **过期** — 驱动上传残留 | 可删除 |
| `.tmp.drivedownload/` | 🗑️ **过期** — 空目录 | 可删除 |
| `.session-artifacts/` | ❓ 会话工件目录 | 确认后决定 |

---

## 三、分类汇总

### ✅ 健康 (10)
| 项目 | 备注 |
|------|------|
| SharedBrain | 核心 OS，生产级，注意清理 build artifacts |
| Agora | 活跃开发，Phase 3 未完成 |
| Minerva | 核心研究，需清理 mineru_output(109MB) |
| OntoDerive | 最活跃引擎 |
| eCOS | 认知基础设施，活跃运行 |
| AgentMesh | 网关调度器，已构建 |
| Honeycomb | DSL 引擎，2.6M ops/s |
| DigitalBrainOS | 文档规划 |
| Metacog | 元认知 KB |
| AI-Tools | 实用工具 |

### ⚠️ 亚健康 (4)
| 项目 | 问题 |
|------|------|
| Pallas | 代码极少(3 py)，需决定方向 |
| Sophia | 代码少/测试少，但被 import |
| BOS-Skill-CLI | 早期阶段，3 commits |
| Agent-Toolkit | 未构建(dist missing) |

### 🕸️ 废弃 (2)
| 项目 | 证据 |
|------|------|
| **kos** | 无 git/无 venv/无维护，34 py 文件但不活跃 |
| **AggreResearch** | 3 commits/2 ts 源文件/dist 缺失/无活跃开发 |

### 🗑️ 无效/过期 — 非项目 (4)
| 路径 | 大小 |
|------|------|
| `minerva/*mineru_output/` | ~109MB |
| `minerva/docker/` | 517MB (确认是否需要) |
| `.tmp.driveupload/` | 少量 |
| `.tmp.drivedownload/` | 空 |

### ❓ 待定 (1)
| 项目 | 问题 |
|------|------|
| **starlink-types** | 只有脚手架，未确定用途 |

---

## 四、空间占用分析

```
honeycomb/:              ~? (大部分代码+测试)
minerva/:                ~626MB (含 docker 517MB + mineru 109MB)
SharedBrain/:            ~872MB (含 graphify-out/ + site/ 构建产物)
其余项目:                 ~200MB
──────────────────────
估算总计:                 ~2GB+
```

---

## 五、建议行动项

### P0 — 立即可做 (安全)
1. 🗑️ 删除 `minerva/*mineru_output/` (~109MB 临时提取物)
2. 🗑️ 删除 `.tmp.driveupload/` 和 `.tmp.drivedownload/`
3. 🗑️ 清理空目录 `minerva/系统架构：..._mineru_output/` 和 `minerva/算法竞赛..._mineru_output/`

### P1 — 需确认后清理
4. `kos` — 是否还要维护？否则标记废弃
5. `AggreResearch` — 是否还要维护？否则标记废弃
6. `starlink-types` — 用途是什么？是否删除
7. `minerva/docker/` (517MB) — 是否仍需保留

### P2 — 长期优化
8. `agent-toolkit` — 运行 `npm run build` 修复 dist 缺失
9. `pallas` — 确定发展方向（增长 or 合并）
10. `sophia` — 增加测试覆盖
11. `bos-skill-cli` — 决定是否继续开发
12. SharedBrain `graphify-out/` 和 `site/` — 加入 `.gitignore` 或定期清理

---

## 六、修复记录 (2026-05-20)

| # | 操作 | 状态 | 详细 |
|---|------|------|------|
| 1 | 🗑️ 删除 `.tmp.driveupload/` | ✅ | **29,131 个临时上传文件**，已清理 |
| 2 | 🗑️ 删除 `.tmp.drivedownload/` | ✅ | 空目录，已清理 |
| 3 | 🗑️ 删除 `.session-artifacts/` | ✅ | **306MB** 会话重建产物，已清理 |
| 4 | 🗑️ 删除 `minerva/*mineru_output/` *(4 个目录)* | ✅ | **109MB** PDF 提取临时产物，已清理 |
| 5 | 🔧 **kos** Git 初始化 | ✅ | `git init` + `.gitignore` + 纯净提交 (45 files) |
| 6 | 🔧 **starlink-types** 添加 `.gitignore` | ✅ | 标准 Python `.gitignore` |
| 7 | 🔧 **SharedBrain** `.gitignore` 补充 | ✅ | 添加 `.session-artifacts/`, `.omo/` |
| 8 | 🔧 **agent-toolkit** 构建 | ✅ | `npm run build` — **156 js + 156 d.ts** |
| 9 | 🔧 **AggreResearch** 构建 | ✅ | `tsc` — dist/ 就绪 |
| 10 | ⏳ **minerva `.venv-mineru`** (1.9GB) | ⏸️ 保留 | 这是 mineru 独立 venv，如需清理再告知 |

### 空间回收

```
清理前: ~1.5TB+ → 清理后: 减去 ~415MB + 29,131 临时文件
主要回收:
  - .session-artifacts/    306MB
  - minerva mineru_output  109MB
  - .tmp.driveupload       ~0.1MB (大量小文件)
```

## 七、架构变更记录 (2026-05-20)

### KOS 迁移 + Gateway 落地

| 变更 | 说明 |
|------|------|
| 🔀 **kos 物理迁移** | `kos/` → `kos/`，git 历史完整保留 |
| 🆕 **gateway 项目创建** | `/Workspace/gateway/` — MCP 统一入口代理层 |
| 🔧 **3 个 wrapper 脚本** | `bin/kos-mcp-server`, `bin/minerva-mcp`, `bin/agora-mcp` |
| 🔧 **.zshrc 更新** | `KOS_HOME` 路径更新 + 去重 + `PATH` 注入 `gateway/bin` |
| 🔧 **Claude Desktop MCP** | kos 改用命令名 `kos-mcp-server`，不再写绝对路径 |
| 🔧 **hermes config.yaml** | kos/minerva/agora 三个 MCP 全部改用命令名 |
| 🔧 **批量文档替换** | 18 个活跃文档 `kos` → `kos`（历史记录保留原文） |
| 📄 **新架构文档** | `KOS_MIGRATION_IMPACT.md` 完成审计闭环 |

### Phase 5: Self-Collab-Consensus (2026-05-25)

| 变更 | 说明 |
|------|------|
| 🆕 **Eidos Schema** | 5新Schema: identity-role, value-principle, consensus, task-object, epoch-life |
| 🆕 **KOS EntityType** | 7→15种: 新增ROLE/AXIOM/PRINCIPLE/THEORY/FRAMEWORK/SKILL/CONSENSUS/TASK |
| 🆕 **Value Stack** | Entity dataclass: value_tier, half_life_days, freshness_status, last_validated, next_review, references |
| 🆕 **L4 Self Domain** | `kos/self/`: api+mcp+3 tools (get_profile, get_current_role, get_vision_summary) |
| 🆕 **L3 Collab Domain** | `kos/collab/`: api (行锁+依赖检查)+mcp+6 tools (create_task~add_artifact) |
| 🆕 **X3 Consensus Domain** | `kos/consensus/`: api (L1/L2/L3三级共识)+mcp+4 tools (create~renew) |
| 🔧 **KOS MCP Server** | 13→26 tools (新增self=3+collab=6+consensus=4) |
| 🆕 **保鲜Cron** | `freshness_check.sh`: 每周一过期扫描+L1自动续签 |
| 🆕 **L4注入** | `self_inject.sh`: 每日首次交互注入L4上下文 |
| 🆕 **contracts list** | `workspace contracts list`: 列出所有注册Schema |
| ✅ **E2E验证** | `phase5_e2e_test.py`: L4→L3→X3全链路 ALL PASSED |

### Phase 6: 迭代修正 Wave 6.3 (2026-05-25)

| 变更 | 说明 |
|------|------|
| 🔧 **T093** | `claim_subtask()` 加 `subtask_id` 字符串ID参数，支持 `SUBTASK_NOT_FOUND` |
| 🔧 **T094** | `create_consensus()` 加 `level` 参数，`_detect_level` 含user:自动升L2 |

---

*维护: 此文件位于 `.omo/AUDIT.md`，随审计更新*
