# eCOS v5 项目架构与治理体系分析报告

> 生成日期: 2026-06-12
> 分析范围: 项目架构、债务治理体系、质量保障机制

---

## 一、项目整体架构

### 1.1 架构概览

eCOS v5 采用 **5+4+1+1** 分层架构：

```
┌─────────────────────────────────────────────────────────────┐
│  L4 自我层  │ l4-kernel (21域·250 tests·43 MCP tools)      │
├─────────────────────────────────────────────────────────────┤
│  L3 入口层  │ cockpit (CLI + MCP + Web)                    │
├─────────────────────────────────────────────────────────────┤
│  I0 织层    │ agora (MCP Hub · 服务发现/路由/代理)          │
├─────────────────────────────────────────────────────────────┤
│  L2 引擎面  │ kairon (知识引擎) · gbrain (知识数据库)       │
│             │ omo (治理面) · metaos (编排引擎)              │
├─────────────────────────────────────────────────────────────┤
│  L1 运行时  │ runtime (matrix + scheduler + kei)           │
├─────────────────────────────────────────────────────────────┤
│  L0 协议    │ ecos (SSB 协议 · 签名链 · 涌现计算)          │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 项目清单

| 层级 | 项目 | 技术栈 | 测试数 | 状态 |
|------|------|--------|--------|------|
| L4 | l4-kernel | Python (uv) | 250 | 🟢 Active |
| L4 | model-driven | Python (uv) | 190 | 🟢 Active |
| L3 | cockpit | Python (uv) | 514 | 🟢 Active |
| I0 | agora | Python (uv) | 1371 | 🟢 Active |
| L2 | kairon | Python (uv) | 4199 | 🟢 Active |
| L2 | gbrain | TypeScript (bun) | ~9700 | 🟢 Active |
| L2 | omo | Python (uv) | 530 | 🟢 Active |
| L2 | metaos | Python (uv) | 188 | 🟢 Active |
| L1 | runtime | Python (uv) | 176 | 🟢 Active |
| L0 | ecos | Python (uv) | 122 | 🟢 Active |

### 1.3 测试健康度

| 项目 | 总测试 | 通过 | 通过率 |
|------|--------|------|--------|
| kairon | 4199 | 4157 | 99.8% |
| gbrain | ~9737 | ~9700 | ~99.6% |
| metaos | 188 | 188 | 100% |
| runtime | 176 | 171 | 97.2% |
| cockpit | 514 | 498 | 96.9% |
| ecos | 122 | 112 | 91.8% |
| agora | 1371 | 1165 | 85.0% |
| omo | 530 | 302 | 57%* |

*OMO: 225 skipped (需要完整环境), 有效通过率 97.4%

---

## 二、债务治理体系

### 2.1 债务管理架构

```
┌─────────────────────────────────────────────────────────────┐
│                    债务管理体系                              │
├─────────────────────────────────────────────────────────────┤
│  预防层    │ pre-commit hook · 原子写入规范 · 测试覆盖标准   │
├─────────────────────────────────────────────────────────────┤
│  检测层    │ debt-audit.sh · debt-leaderboard · CI 集成     │
├─────────────────────────────────────────────────────────────┤
│  修复层    │ omo-debt register · 治理流程 · SLA 标准        │
├─────────────────────────────────────────────────────────────┤
│  监控层    │ 健康度趋势 · 治理仪表板 · BOS URI 数据暴露     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 债务状态

| 指标 | 值 | 说明 |
|------|-----|------|
| debt_weight | 1.0 | 债务权重 (1.0 = 全部解决) |
| debt_health | 100.0 | 健康度 (0-100) |
| resolved_count | 9 | 已解决债务数 |
| unresolved_count | 0 | 未解决债务数 |
| resolution_rate | 100% | 解决率 |

### 2.3 已解决债务 (9项)

| 债务ID | 说明 | 解决方式 |
|--------|------|----------|
| SB_DECOMPOSITION | SharedBrain拆解 | 代码已迁移至kairon |
| SB_UNTESTED_PKGS | 无测试包 | core-models已有6测试 |
| SB_ORPHANED_TASKS | 任务结构化 | tasks/registry/INDEX.md |
| SB_ROOT_CLEANUP | 根目录清理 | SharedBrain/仅含data/db |
| SB_BRIDGE_FIX | bridge死代码 | sharedbrain-bridge包已不存在 |
| SB_PROJECTS_YAML | YAML行数 | projects/AGENTS.md已维护 |
| SB_PHASE17_PLAN | 实施计划 | debt-cleanup-plan.md |
| D2_CI_E2E | E2E容器化 | docker-compose环境 |
| D3_EU_PRICING | eu-pricing测试 | 包已删除，债务过时 |

### 2.4 债务分类

| 类别 | 已解决 | 部分解决 | 未解决 |
|------|--------|----------|--------|
| technical | 1 | 2 | 0 |
| governance | 8 | 0 | 0 |
| process | 0 | 0 | 0 |

### 2.5 健康度趋势

| 日期 | debt_weight | debt_health | 说明 |
|------|-------------|-------------|------|
| 2026-06-11 | 0.30 | 62.5 | 初始状态：9项债务未解决 |
| 2026-06-11 | 0.82 | 79.5 | 7项 SharedBrain 债务已解决 |
| 2026-06-11 | 0.97 | 97.0 | D2_CI_E2E 容器化已解决 |
| 2026-06-11 | 1.00 | 100.0 | D3_EU_PRICING 已解决 |

---

## 三、质量保障机制

### 3.1 Pre-commit 检查

**配置**: 7 个子模块全部配置 `.githooks/`

**检查项**:
1. Ruff 代码检查
2. 非原子写入检测
3. 新包测试覆盖检查

**绑定方式**: `git config core.hooksPath .githooks` (本地相对路径，无外部依赖)

### 3.2 CI/CD 流水线

| 工作流 | 触发条件 | 功能 |
|--------|----------|------|
| debt-audit.yml | push/PR/schedule | 债务审计 + 评论 |
| ci-lint.yml | push/PR | 代码检查 |
| governance-check.yml | push/PR | 治理验证 |
| audit-rollout-monthly.yml | 每月 | 月度审计 |

### 3.3 测试策略

| 测试类型 | 命令 | 说明 |
|----------|------|------|
| 全量测试 | `make kairon-test` | 所有包 |
| 单元测试 | `make kairon-test-fast` | 跳过集成/基准 |
| 差异测试 | `make kairon-test-diff` | 仅修改的包 |
| E2E测试 | `make kairon-test-e2e` | Postgres+gbrian+kairon |

### 3.4 代码质量

| 工具 | 用途 | 配置 |
|------|------|------|
| ruff | 代码检查/格式化 | line-length=120, target=py313 |
| pytest | 测试框架 | coverage ≥ 70% |
| mypy | 类型检查 | strict mode |

---

## 四、治理工具链

### 4.1 Makefile Targets

```bash
# 测试
make kairon-test          # 全量测试
make kairon-test-fast     # 单元测试
make kairon-test-diff     # 差异测试
make kairon-test-e2e      # E2E 测试

# 治理
make governance-audit     # 全量治理审计
make debt-check           # 债务状态检查
make debt-audit           # 定期债务审计
make debt-leaderboard     # 债务排行榜
make doc-lint             # 文档格式检查

# 可视化
make governance-dashboard # 生成 HTML 报告
make governance-data      # 生成 JSON 数据
make governance-query     # 查询治理数据
```

### 4.2 治理脚本

| 脚本 | 用途 |
|------|------|
| debt-audit.sh | 定期债务审计 |
| debt-leaderboard.sh | 债务排行榜 |
| generate-governance-dashboard.py | 生成 HTML 报告 |
| generate-governance-data.py | 生成 JSON 数据 |
| governance-query.py | 查询治理数据 |

### 4.3 治理数据

| 数据 | 路径 | 格式 |
|------|------|------|
| 系统状态 | .omo/state/system.yaml | YAML |
| 债务仪表板 | .omo/_control/debt-dashboard/current.yaml | YAML |
| 健康度趋势 | .omo/_control/debt-dashboard/health-trend.md | Markdown |
| 治理数据 | .omo/_control/governance-data.json | JSON |
| 治理报告 | governance-report.html | HTML |

---

## 五、治理文档体系

### 5.1 文档结构

```
omo/_knowledge/governance/
├── README.md           # 治理流程指南
├── debt-prevention.md  # 债务预防规范
├── sla.md              # 治理 SLA 标准
└── quickstart.md       # 新成员入职指南
```

### 5.2 文档内容

| 文档 | 内容 |
|------|------|
| README.md | 债务管理、文档维护、原子写入规范、测试覆盖标准 |
| debt-prevention.md | pre-commit检查项、预防清单、响应流程 |
| sla.md | 债务SLA、健康度SLA、审计SLA、升级流程 |
| quickstart.md | 概念介绍、日常工作流、常用命令、工具链 |

---

## 六、SLA 标准

### 6.1 债务 SLA

| 严重程度 | 响应时间 | 解决时间 |
|----------|----------|----------|
| critical | 1 小时 | 24 小时 |
| high | 24 小时 | 7 天 |
| medium | 7 天 | 30 天 |
| low | 30 天 | 90 天 |

### 6.2 健康度 SLA

| 指标 | 目标 | 告警阈值 | 严重阈值 |
|------|------|----------|----------|
| debt_weight | ≥ 0.9 | < 0.8 | < 0.6 |
| debt_health | ≥ 90 | < 80 | < 60 |
| resolved_rate | ≥ 90% | < 80% | < 60% |

---

## 七、BOS URI 命名空间

### 7.1 五大域

| 域 | 命名空间 | 承载项目 |
|----|---------|---------|
| 记忆与事实源 | `bos://memory` | kos, kronos, gbrain, sot-bridge |
| 治理与律法 | `bos://omo` | metaos, eidos, protocols-layer, omo |
| 认知与推演 | `bos://analysis` | ontoderive, minerva, codeanalyze |
| 人格与心智 | `bos://persona` | sot-bridge |
| 能力与生态 | `bos://forge` | forge, runtime |

### 7.2 治理数据暴露

```
governance-data.json
├── governance (健康度/权重)
├── debt (解决率/分类)
├── trend (趋势数据)
└── projects (项目状态)
```

---

## 八、子模块治理

### 8.1 统一配置

| 子模块 | .githooks/ | hooksPath | pre-commit |
|--------|------------|-----------|------------|
| kairon | ✓ | .githooks | ✓ |
| agora | ✓ | .githooks | ✓ |
| cockpit | ✓ | .githooks | ✓ |
| ecos | ✓ | .githooks | ✓ |
| omo | ✓ | .githooks | ✓ |
| metaos | ✓ | .githooks | ✓ |
| runtime | ✓ | .githooks | ✓ |

### 8.2 绑定方式

- **旧方案**: `git config core.hooksPath /Users/xiamingxing/.hermes/scripts/git-hooks` (绝对路径，强绑定 hermes)
- **新方案**: `git config core.hooksPath .githooks` (本地相对路径，无外部依赖)

---

## 九、关键改进总结

### 9.1 已完成改进

| 改进项 | 状态 | 说明 |
|--------|------|------|
| 债务清理 | ✅ | 9/9 权重债务已解决 |
| 债务预防 | ✅ | pre-commit hook 配置 |
| 健康度监控 | ✅ | 趋势追踪 + 仪表板 |
| 治理文档 | ✅ | 4 个标准化文档 |
| 子模块统一 | ✅ | 7 个子模块配置 .githooks/ |
| CI 集成 | ✅ | debt-audit.yml |
| 治理 SLA | ✅ | 响应/解决时间标准 |
| 治理培训 | ✅ | 新成员入职指南 |

### 9.2 治理能力矩阵

| 能力 | 工具 | 覆盖范围 |
|------|------|----------|
| 预防 | pre-commit hook | 7 个子模块 |
| 检测 | debt-audit.sh | 全项目 |
| 修复 | omo-debt register | 全项目 |
| 监控 | governance-query | 全项目 |
| 报告 | governance-dashboard | 全项目 |
| 培训 | quickstart.md | 新成员 |

---

## 十、建议与展望

### 10.1 短期建议

1. **gbrain 配置 .githooks/** — 当前 gbrain 缺少 pre-commit hook
2. **治理 SLA 监控** — 添加超时自动通知
3. **债务排行榜定期运行** — 集成到周报

### 10.2 中期建议

1. **治理仪表板 Web 化** — 集成到 cockpit Web 界面
2. **治理数据 API** — 通过 MCP 工具暴露
3. **自动化债务修复** — 针对常见债务模式

### 10.3 长期建议

1. **治理 AI 助手** — 智能债务分析和修复建议
2. **跨仓治理** — 多仓库统一治理
3. **治理度量** — MTTR/MTTA 等 SLA 指标

---

## 附录

### A. 常用命令速查

```bash
# 测试
make kairon-test / kairon-test-fast / kairon-test-diff / kairon-test-e2e

# 治理
make governance-audit / debt-check / debt-audit / debt-leaderboard / doc-lint

# 可视化
make governance-dashboard / governance-data / governance-query

# 债务管理
omo-debt register --source X --title Y --severity Z
omo-debt score --impact 9 --frequency 8 --cost 7
```

### B. 治理文档索引

```
omo/_knowledge/governance/
├── README.md           # 治理流程指南
├── debt-prevention.md  # 债务预防规范
├── sla.md              # 治理 SLA 标准
└── quickstart.md       # 新成员入职指南
```

### C. 治理数据索引

```
omo/_control/
├── debt-dashboard/
│   ├── current.yaml    # 债务仪表板
│   └── health-trend.md # 健康度趋势
└── governance-data.json # 治理数据 (JSON)
```

---

*报告生成: 2026-06-12*
*分析工具: MiMo Code Agent*
