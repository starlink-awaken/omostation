# 深度审计报告：Ecosystem层 + CLI/Tools层 + Inactive层

**审计日期**: 2026-05-27  
**审计范围**: ~/Workspace/ 下 3 层 9 项目  
**方法论**: 代码规模/结构扫描 + 架构合约(AGENTS.md)校验 + 依赖图分析 + 安全扫描

---

## 层5：生态工具 (Ecosystem)

---

### SharedBrain — 数字化生命OS

#### 核心设计模式/优劣
**模式**: 分形微内核架构 (Z-Spore → Z-Microkernel → Z-Core → Organs) + BOS-URI 跨域通信  
**优**: 架构理论完备，层隔离通过 `validate_layer_isolation.py` 强制执行；AGENTS.md 治理体系极其成熟（每子目录独立AGENTS.md + context_compiler验证）；16578 测试用例覆盖单元/集成/E2E/混沌/模糊测试  
**劣**: 
- **过度设计严重**: 29 个 D-* 器官域（含 D-Continuity/D-Harness/D-Extension/D-Test 等实验性域），大量空壳或低活跃域
- **架构复杂度过高**: 3823 核心 Python 文件，60MB 测试数据，耦合在 `cognitive_bus.py`/`capability_registry.py` 形成隐式 God Objects
- **认知负载极高**: 新人要理解 "BaseMembrane"+"Z-Spore interfaces"+"bos:// 协议"+"FederationLedger" 才能改一行代码

#### 依赖关系健康度
- 层内依赖清晰（Layer L0→L1→L2 箭头无反向），有自动化验证
- **但 8 个 Git Worktree 存在**（各 ~190MB），导致代码冗余 9x（如 full_system_demo.py 出现 15 次副本）
- 外部依赖: 0 导入者（不与 CLI/Tools 层共享代码）— 符合 AGENTS.md 声明但浪费了潜在的复用机会

#### AGENTS.md 一致性检查
✅ **高度一致**: 每个子目录有 AGENTS.md，声明与实际结构吻合  
✅ 治理测试（test_script_artifact_hygiene.py 等）强制 facade→workflows 委托规则  
❌ **版本声明矛盾**: AGENTS.md 说 "已清理 343 个 .session_* 文件"，但 data/ 下仍有 96M 运行期产物  
❌ **大小声明严重低估**: AGENTS.md 写 "2.1G 总大小"，实际 **3.7G**（.worktrees 1.4G + .git 425M 未计入）

#### 代码规模合理性
| 维度 | 数值 | 评估 |
|------|------|------|
| 核心 Python 文件 | 3823 文件 / 28MB | ❌ 严重偏大 |
| 测试用例 | 16578 函数 | ✅ 覆盖极好但冗余 |
| .git 大小 | 425MB pack | ❌ 含 87MB JSON + 48MB SQLite + 45MB webpack cache |
| .worktrees | 8 × ~190MB = 1.4G | ❌ 废弃工作树未清理 |
| 核心代码 (organs+nucleus+bin) | ~76MB | 偏大但部分合理 |

#### 测试覆盖率
✅ **优秀**: 16578 测试函数，含架构约束测试 + 混沌工程 + 属性测试  
✅ 治理测试强制 facade 委托、层隔离、符号链接完整性  
⚠️ 但测试本身占用 59MB（含 52MB DB fixture），部分为冗余快照

#### 架构债务
1. **P0 - Git Bloat 极高**: .git 含 87MB impl-manifest.json + 48MB HIVE_CORE.db + 45MB webpack cache → 必须 `git filter-branch` 清除
2. **P0 - 废弃 Worktree 未清理**: 8 个工作树 1.4G 空间完全浪费  
3. **P1 - 过度设计**: 29 个器官域中 D-Continuity/D-Harness/D-Extension/D-Test 为空壳或刚创建
4. **P1 - full_system_demo.py 泛滥**: 同一文件副本 15 份（worktrees + site + docs）
5. **P2 - Data/ 未清理**: 96M data/ 包含运行期产物和快照

#### 安全风险
⚠️ SharedBrain 自身有安全层（immunity_guard.py, security_sanitizer.py），但代码臃肿增加了攻击面扫描难度  
⚠️ Ruff S 扫描报 31615 个安全问题（含大量误报，因为 site/ 和 archive/ 中的数据）  
⚠️ **单点故障**: `cognitive_bus.py` + `capability_registry.py` 是隐式 God Object — 被所有器官域依赖

#### **SharedBrain 分数: 55/100**
关键风险: (1) Git bloat 紧急清理 (2) 废弃 worktree 清理 (3) 过度设计的域裁剪

---

### hermes-webui — Hermes Agent Web 界面

#### 核心设计模式/优劣
**模式**: Python 后端 (FastAPI?) + vanilla JS 前端，单体架构  
**优**: 
- 646 个 Python 文件 / 6.96MB — 规模合理
- 600+ 测试文件覆盖详细（约 60 个测试文件）
- 独立的 server.py 和 bootstrap.py 入口清晰

**劣**:
- **server.py 是超大单文件**: server.py + api/routes.py(474KB) + api/streaming.py(292KB) + api/config.py(214KB) — 后端核心集中在少数超级文件中
- 无 TypeScript/前端框架 — 可能是优点（vanilla JS 零依赖）也可能是维护负担
- 缺少架构文档中明确定义的核心运行时边界

#### 依赖关系健康度
✅ 依赖简单（Python 标准库 + ~少量 pip 包），无明显危险依赖  
⚠️ 与 SharedBrain/KOS 的集成关系不明确 — AGENTS.md 未定义跨层依赖

#### AGENTS.md 一致性检查
✅ AGENTS.md 存在，定义了 agent 入口规范、开发流程和测试约定  
✅ 文档完善（ARCHITECTURE.md, TESTING.md, CONTRIBUTING.md, CONTRACTS.md 等）  
⚠️ 但称为 "166K LOC Python" — 实测 6.96MB 代码 + 测试（纯 Python 约 100K LOC 左右）

#### 测试覆盖率
✅ ~600 测试（约 60 文件），覆盖了 UI/UX、SSE、Session、Provider 等核心路径  
✅ 多数测试文件按 issue/功能命名（test_issue_xxx.py），便于溯源

#### 架构债务
- **P1 - 超大 API 文件**: api/routes.py(474KB) + api/streaming.py(292KB) 应拆分为模块
- **P2 - 测试文件膨胀**: test_gateway_sync.py(79KB) 单文件过大
- **P2 - 缺少正式测试覆盖率报告**: 无 `--cov` 配置

#### 安全风险
⚠️ security_redaction.py 存在（专门的测试文件），表示有安全意识  
⚠️ 后端处理用户会话数据 + MCP 工具调用 — 输入注入风险需验证

#### **hermes-webui 分数: 68/100**
关键风险: (1) 超级文件拆分 (2) 跨层集成测试缺失 (3) 测试文件膨胀

---

## 层6：CLI / 工具 (CLI & Tools)

---

### kos — 知识操作系统 CLI

#### 核心设计模式/优劣
**模式**: 分层 CLI 架构（commands/indexer/ontology/collab/minerva）  
**优**: 
- 109 个 Python 文件 / 453KB — 规模合理
- 8 个模块组织清晰（commands + indexer + ontology + collab + minerva + self + web + adapters）
- pyproject.toml 现代化配置（hatchling 构建，可选依赖分组完善）

**劣**:
- 106 测试函数 vs AGENTS.md 声明 "14 测试" — **实际测试更多但官方文档低估**
- indexer 模块 (`kos/indexer/engine.py`) 是核心逻辑但缺少架构解耦
- AGENTS.md 不存在 — 仅有层6 AGENTS.md 中的一行描述

#### AGENTS.md 一致性检查
❌ 无独立 AGENTS.md — 仅在层6汇总表中有两行  
⚠️ pyproject.toml 声明的 name="kos" vs 项目管理文档中 "知识操作系统 CLI" 概念一致

#### 测试覆盖率
⚠️ 106 测试函数 — 相对 12.8K LOC 偏少（~8:1 LOC:test 比例）  
⚠️ 仅有 4 个测试文件（tests/ 下），无集成测试

#### 架构债务
- **P1 - 少测试核心路径**: CLI 核心命令缺少测试覆盖
- **P2 - adapter 层耦合**: `kos/adapters/__init__.py` 尝试导入 `kos_adapters`（外部包名），可能造成运行时错误
- **P2 - _legacy/ 残留**: 目录下有未跟踪的遗留代码

#### **kos 分数: 62/100**
关键风险: (1) 测试覆盖不足核心路径 (2) 适配器层耦合 (3) 缺少架构文档

---

### bos-skill-cli — 技能发现/激活 TUI

#### 核心设计模式/优劣
**模式**: Python CLI + Textual TUI 状态机（staged/promoted/rejected）  
**优**: 
- 9 个 Python 文件 / 72KB — **最小的项目之一，恰到好处**
- 状态机设计清晰（search→stage→promote/reject）
- AGENTS.md 定义完善，含 agent 操作规范、提交检查清单

**劣**:
- 仅 4 个测试文件，4 个测试函数（AGENTS.md 自述 "14 测试" 但实际 grep 显示更少）
- TUI (Textual) 层测试几乎为零 — UI 逻辑不可测

#### AGENTS.md 一致性检查
✅ AGENTS.md 定义清晰，含 7 个章节（目标/操作顺序/约束/代码触点/文档触点/检查清单/变更规则）  
✅ 状态机语义与声明一致（staged activation 强制）

#### 测试覆盖率
❌ 严重不足 — 4 测试函数，仅覆盖 CLI + service 基础路径  
⚠️ 无 TUI 测试（Textual 应用的硬伤）

#### **bos-skill-cli 分数: 58/100**
关键风险: (1) 测试覆盖率极低 (2) TUI 层不可测 (3) 活跃度 🟡 有停滞风险

---

### Forge — 内部工具注册与发现

#### 核心设计模式/优劣
**模式**: SSOT 数据模型 + 知识图谱 + MCP Server + 反熵三层  
**优**: 
- **项目宪法(CLAUDE.md)极其完善** — 6 条宪法 + 4 层架构 + 3 用户场景 + 优先级矩阵
- 27 个 Python 文件 / 192KB — 规模合理
- tools-registry.json 唯一真实来源（SSOT）设计正确
- 24 个运维脚本完善（sniff/sediment/entropy/verify）
- 知识图谱 423 节点 / 634 边
- 5 个 verify 脚本 100% 通过
- Forge + Agora 事件总线 + Hermes 激活 — 生态集成已完成

**劣**:
- 仅 1 个测试文件（tests/test_basic.py）— **完全不可接受**
- 知识图谱数据 (tools-registry.json + 图谱) 是二进制/JSON 数据，无版本化方案
- scripts/ 目录下 24 个 Shell 脚本几乎不可测

#### AGENTS.md 一致性检查
⚠️ 无 AGENTS.md — 用 CLAUDE.md 替代。CLAUDE.md 声明了完整的架构理念和 Phase 状态。  
✅ Phase 1-3 均已完成（120 条注册表 / schema v1.2 / MCP Server / Event Bus）  
✅ 与 AGENTS.md 层 6 声明的 ✅ 状态一致

#### 测试覆盖率
❌ **极低**: 仅 1 个测试文件，1 个测试函数（test_basic.py）  
⚠️ verify-phase1/2/3.sh 作为替代验证方案，但不是自动化 CI 测试

#### **Forge 分数: 70/100**
关键风险: (1) 测试覆盖率极低 (2) Shell 脚本不可测 (3) 需要 CI 集成

---

### codeanalyze — 代码与文档分析工具集

#### 核心设计模式/优劣
**模式**: CLI 12 命令 → Domain Adapter → Knowledge Graph → Export Format  
**优**: 
- 30 个 Python 文件 / 168KB — 规模合理
- 架构模式清晰（CLI→Adapter→KG→Export）
- AGENTS.md 完善（含 Red Team 发现、安全约束、路径验证规则）
- 49 测试函数，4 个测试文件 — **覆盖较好**

**劣**:
- 依赖 4 个外部工具（Graphify, GitNexus, Docling, MinerU）— 部分可能是 ffi/子进程调用
- `analyze` full pipeline 依赖外部工具可用性 — CI 中难验证

#### AGENTS.md 一致性检查
✅ AGENTS.md 完整定义：项目概览、关键文件表、架构图、CLI 命令表、开发规则、数据模型、Red Team 结果  
✅ Red Team 报告两次（REDTEAM.md + REDTEAM_V2.md）— 安全意识充分  
✅ 路径校验、Cypher 转义、XML 安全解析、ZIP 大小限制等约束已执行

#### 测试覆盖率
✅ 49 测试函数，覆盖基本路径  
⚠️ 集成测试依赖外部工具，可能不稳定

#### **codeanalyze 分数: 78/100**
关键风险: (1) 外部工具依赖稳定性 (2) 缺少性能测试

---

### ai-tools — Shell 工具集

#### 核心设计模式/优劣
**模式**: Shell 脚本集合 + YAML 配置驱动（config/tools.yaml + config/rules.yaml）  
**优**: 
- 8.2K Shell LOC 全部在 736KB 内 — 紧凑
- skills/Workflows/ 目录定义了 Scan/List/Config/Route 4 个 workflow
- 参数解析通过 `core/yaml-parser.sh` + `core/config-validator.sh` 实现

**劣**: 
- **零测试** — 8.2K LOC Shell 脚本完全无测试
- 无 CI 集成（.github/workflows/ci.yml 存在但未运行）
- Shell 脚本天生难维护、难调试、难测试
- .git 目录下有 gitbutler 数据（but.sqlite + virtual_branches.toml）— 不是标准 git

#### AGENTS.md 一致性检查
❌ 无 AGENTS.md 或 CLAUDE.md — `README.md` 是唯一文档  
⚠️ 与 AGENTS.md 层 6 声明的 🟡 状态一致 — 确实需要关注

#### 测试覆盖率
❌ **零测试**: 0 测试函数，8.2K Shell 脚本完全依赖手动验证  
❌ 无自动化验证脚本

#### **ai-tools 分数: 30/100**
关键风险: (1) 零测试覆盖 (2) Shell 脚本维护性差 (3) gitbutler 非标准 git 数据 (4) 🟡 低活跃

---

### wksp — Workspace CLI 工具

#### 核心设计模式/优劣
**模式**: CLI 入口 + Commands 模块化 + Storage 抽象层  
**优**: 
- 35 个 Python 文件 / 190KB — 规模合理
- 最近刚经过 Phase A-D 重构（解耦+文档+抽象层+模块拆分）
- 66 测试函数，15 个测试文件 — 覆盖较好
- commands/ 按功能拆分（research/importer/profile/status/governance/contracts）

**劣**:
- setup.py + pyproject.toml **重复配置**（version 0.1.0 vs 0.2.0, packages find 配置不同）
- `_fix_tests.py` 残留 — 重构修复脚本未被清理
- storage.py(190KB) + cli.py 是超大文件 — 重构未完成模块拆分

#### AGENTS.md 一致性检查
❌ 无 AGENTS.md — 完全依赖层6汇总表

#### 测试覆盖率
✅ 66 测试函数覆盖 CLI + Storage 核心路径  
⚠️ E2E 测试（test_e2e_journey.py）存在但可能不够

#### **wksp 分数: 72/100**
关键风险: (1) setup.py/pyproject.toml 重复配置 (2) storage.py 超大 (3) 重构残留文件需清理

---

## 层7/8：停滞/辅助 (Inactive)

---

### eCOS — 认知脚本集

#### 核心设计模式/优劣
**模式**: 活体架构文档系统 (LADS) + SSB事件溯源 + 三态运行模式  
**优**: 
- AGENTS.md 极其完善 — 含核心规则、项目结构、系统状态面板、三态运行模式
- 41 脚本 + 98 测试函数 （实测 83 def test_）
- 12 个 Cron 在线任务
- SSB 5,234 事件，HMAC 签名 100%
- 红蓝对抗 v6 体系

**劣**: 
- 52 个 Python 文件 / 428KB — 但对于 "认知脚本集" 偏大
- **脚本 vs 可维护设计失调**: 41 个 scripts/ 顶层脚本，大量是一次性或 facade
- _legacy/ 和大量临时脚本未清理
- 系统状态面板显示 "安全 94%" 和 "架构 95%" — 具体指标需验证
- WF-005 持续交接 — 持续性的任务交接暗示架构不稳定

#### AGENTS.md 一致性检查
✅ AGENTS.md 极其详尽（7 章节 + 3 运行模式 + 外部系统映射）  
✅ GENOME.md + STATE.yaml + HANDOFF 活体架构体系设计先进  
❌ 系统状态面板宣称 "74 commits, 130+ files" — 提交频率低

#### 测试覆盖率
✅ 83 测试函数 — 相对 428KB 代码覆盖合理  
⚠️ 含红蓝对抗测试 (test_redteam_v3.py) — 安全验证意识好

#### **eCOS 分数: 65/100**
关键风险: (1) 长期停滞趋势 (2) WF-005 交接持续 (3) scripts/ 膨胀需清理

---

### metacog — 元认知知识库

#### 核心设计模式/优劣
**模式**: 纯 Markdown 知识库（无可执行代码）  
**优**: 
- ~8600 LOC Markdown，872KB — 规模适中
- 结构清晰：01-theories / 02-practices / 03-foundations / 04-applications
- 含个人本体建模 (personal-ontology)、元协议 (meta-protocol)、认知细胞 (cognitive-cell) 等理论框架

**劣**:
- **无测试、无代码、无架构合约** — 纯文档项目，符合 "知识库" 定位
- 与 SSOT 项目有潜在内容重复（配置/元认知 vs SSOT 知识管理）
- 10K LOC 但无版本化控制文档的机制

#### AGENTS.md 一致性检查
❌ 无 AGENTS.md — 符合 "文档类" 声明（层8）

#### **metacog 分数: 75/100**（作为文档项目评估）
关键风险: (1) 与 SSOT 内容潜在重叠 (2) 缺少更新治理 (3) 低活跃

---

## 层间问题分析

### 重复功能
1. **P1 - Forge vs KOS 工具发现**: Forge 做工具注册与发现（120 条 tools-registry.json），KOS 做知识索引 — 边界模糊，Forge 的 "知识图谱 423 节点" 与 KOS 的 "6 域, 7,503 文档" 有关联但未桥接
2. **P2 - SharedBrain vs eCOS 认知体系**: SharedBrain 的 committee/council 体系与 eCOS 的 5 模型委员会概念重叠
3. **P2 - metacog vs SSOT**: metacog 的元认知知识库与 SSOT 的配置/状态管理在 "元知识" 维度有潜在重叠

### 接口不一致
1. **P1 - CLI 入口命名不一致**:
   - kos → `kos` (pyproject.toml entry point)
   - bos-skill-cli → 无统一入口名
   - Forge → `forge` (MCP server) + scripts 接口
   - codeanalyze → `codeanalyze` CLI
   - wksp → `workspace` (入口名 vs 项目名 wksp 不一致)
2. **P1 - AGENTS.md 格式不统一**: SharedBrain 使用 YAML frontmatter 风格，eCOS/KOS 使用 Markdown 表格，bos-skill-cli/Forge/codeanalyze 使用纯 Markdown
3. **P2 - 依赖管理策略不统一**: pyproject.toml (KOS/Forge/codeanalyze) vs setup.py (wksp) vs 无配置 (ai-tools)

### 边界越界
1. **P1 - eCOS 越过 KOS 边界**: `eCOS/scripts/` 下 10+ 文件直接 import `kos` 或调 KOS MCP — 虽然通过 MCP 桥接，但多处有硬编码路径耦合（如 `from kos_indexer import`）
2. **P2 - SharedBrain 过度封装**: 29 个器官域中部分职责与外部项目重叠（如 D-Gateway vs agora, D-Memory vs KOS）
3. **P3 - ai-tools 未暴露标准 CLI 接口**: 无 pyproject.toml entry_points，不符合 AGENTS.md 第 4 条治理原则

---

## 总分汇总

| 项目 | 分数 | 层 | 关键风险 |
|------|------|-----|---------|
| SharedBrain | **55** | 5 | Git bloat, 过度设计, worktrees 未清理 |
| hermes-webui | **68** | 5 | 超级文件拆分, 缺少跨层集成测试 |
| **层5平均** | **61.5** | | |
| kos | **62** | 6 | 测试不足核心路径, 适配器耦合 |
| bos-skill-cli | **58** | 6 | 测试极低, TUI不可测 |
| Forge | **70** | 6 | 测试极低(1个), Shell不可测 |
| codeanalyze | **78** | 6 | 外部工具依赖 |
| ai-tools | **30** | 6 | 零测试, Shell维护性, 无架构文档 |
| wksp | **72** | 6 | setup/pyproject重复, 超大storage.py |
| **层6平均** | **61.7** | | |
| eCOS | **65** | 7 | 停滞趋势, scripts膨胀 |
| metacog | **75** | 8 | 内容重叠风险(文档类) |
| **层7/8平均** | **70** | | |

### 跨层总分: 63/100

### 全局风险排序（P0→P2）

| 优先级 | 风险 | 影响项目 | 建议行动 |
|--------|------|---------|---------|
| **P0** | SharedBrain .git bloat (87MB artifact + DB) | SharedBrain | git filter-branch + .gitignore 清理 |
| **P0** | 8 个废弃 worktree 1.4G | SharedBrain | 确认后删除 `.worktrees/` |
| **P0** | ai-tools 零测试 + gitbutler 非标准 git | ai-tools | 评估是否废弃或重构为 Python |
| **P1** | Forge/bos-skill-cli 测试覆盖 < 5% | Forge, bos-skill-cli | CI 强制测试门禁 |
| **P1** | eCOS 硬编码耦合 KOS (10+ 文件) | eCOS, KOS | 统一通过 MCP 桥接 |
| **P1** | hermes-webui api/routes.py 474KB 超级文件 | hermes-webui | 按 endpoints 拆分 |
| **P1** | CLI 入口名混乱（workspace vs wksp vs kos） | 所有 CLI 项目 | 统一命名规范 |
| **P1** | SharedBrain 29 个器官域过度设计 | SharedBrain | 裁剪空壳域，合并低活跃域 |
| **P2** | setup.py + pyproject.toml 重复配置 | wksp | 统一使用 pyproject.toml |
| **P2** | AGENTS.md 格式不统一 | 全项目 | 推广 SharedBrain YAML frontmatter 标准 |
| **P2** | metacog vs SSOT 内容潜在重叠 | metacog, SSOT | 内容审计 + 归并 |
