---
title: INDEX
type: doc
status: active
---

# `kairon/.omo/` — Kairon 项目治理层

> Kairon 项目专属治理层，链接到工作区根级 `.omo/` 治理体系。
>
> 治理规划：`docs/governance_plan.md`（Phase 1~4）
> 当前完成：Phase 1（基础治理）✅ · Phase 2（架构清理）✅ · Phase 3（治理体系落地）🔄

---

## 目录结构

```
.omo/
  ├── INDEX.md              ← ★ kairon 治理导航（当前文件）
  ├── registry/             ← 包治理注册表
  │   └── packages.yaml     ← 26 包治理状态
  ├── state/                ← kairon 状态快照
  │   └── status.yaml       ← 健康分、债务、测试覆盖率
  ├── standards/            ← kairon 专属标准
  │   ├── ruff.toml         ← 引用根级配置
  │   └── import-rules.md   ← 跨包依赖边界
  └── tests/                ← kairon 质量门禁结果
      └── gate-results/     ← CI gate 运行历史
```

---

## 快速入口

| 目标 | 路径 |
|------|------|
| 包治理状态总表 | [registry/packages.yaml](registry/packages.yaml) |
| 系统健康分与债务 | [state/status.yaml](state/status.yaml) |
| Ruff 配置引用 | [standards/ruff.toml](standards/ruff.toml) |
| 跨包依赖边界规范 | [standards/import-rules.md](standards/import-rules.md) |
| 治理规划全文 | `docs/governance_plan.md` |
| 架构审计报告 | `docs/architecture_audit.md` |

---

## 治理阶段进度

| Phase | 状态 | 交付物 |
|-------|------|-------|
| Phase 1：基础治理 | ✅ 已完成 | Ruff 标准化、LLM 统一、4 核心包测试基线、6 包提交、版本修复 |
| Phase 2：架构清理 | ✅ 已完成 | engine-core 清理、EventBus 提取、Phase 17 W1 迁移、5 包测试 ≥60% |
| Phase 3：治理体系落地 | ✅ 已完成 | 治理目录 ✅、包注册表 ✅、全量测试 ~5800+ ✅、5 包深度分析 ✅、CI 门禁 ✅（ruff 0/mypy 0/format 0）、mypy 3118→0 ✅ |
| Phase 4：持续演进 | 📋 计划中 | 季度审计、债务看板、ADR、成熟度自动评估、metaos 版本治理 |

---

## 与根级 `.omo` 的关系

| 维度 | 根级 `.omo` | `kairon/.omo` | 关系 |
|------|------------|---------------|------|
| 健康分 | `state/system.yaml` → health_score | `state/status.yaml` | kairon 进展影响根级健康分 |
| 债务追踪 | `debt/`（9 项 unresolved） | `state/status.yaml` → debts | kairon 专项债务，同步到根级 |
| 治理标准 | `standards/` | `standards/` 引用 | kairon 扩展根级标准 |
| 阶段规划 | `plans/`（Phase 1~17） | `docs/governance_plan.md` | kairon 治理是 Phase 17 执行分册 |
| 包治理 | 无包级注册 | `registry/packages.yaml` | 首次建立包级治理维度 |

---

## 治理规则摘要

### 硬性门禁（Hard Gate）
- Ruff 零错误：`ruff check packages/` 必须通过
- 测试全部通过：`pytest packages/` 通过率 100%
- 版本一致性：`__version__` vs `pyproject.toml` 必须一致
- 格式一致性：`ruff format --check` 无差异

### 强烈建议（Soft Gate）
- 新包 ≥3 个测试文件
- 跨包 import 需 ADR
- 包成熟度登记
- 重大变更需 ADR

---

*维护: 2026-06-02 · 初始版本 v1.0*
