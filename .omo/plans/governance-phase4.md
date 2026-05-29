# Governance Phase 4 — 能力增强（滚动执行）

> 周期: 2026-06-08 起滚动 | 负责人: sisyphus (P9)
> 目标: 废弃清理、文档补齐、持续集成

---

## Wave 4.A — 文档体系补齐（P8: prometheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T054 | 更新 README.md：从项目目录索引改为使用指南 | 新用户读完后知道输入 `workspace demo` | 30min |
| T055 | 为每个活跃项目补一句话简介 + 入口命令 | `workspace help` 展示所有项目 + 用途 | 30min |
| T056 | agora API 参考文档更新到最新 | `/docs/API_REFERENCE.md` 反映 v1.5 实际 API | 30min |

## Wave 4.B — CI 基线建立（P8: prometheus + P7: epimetheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T057 | GitHub Actions: ruff check on push | PR 有 ruff 自动检查 | 30min |
| T058 | GitHub Actions: pytest 自动运行 | 每次 push 跑 `make test` | 30min |
| T059 | GitHub Actions: `make check-config` 自动执行 | 配置被污染时 CI 失败 | 15min |

## Wave 4.C — 技术债清理（P8: prometheus）

| Task ID | 描述 | 验收标准 | 预估 |
|---------|------|---------|------|
| T060 | Forge 补最少测试（核心功能路径） | `cd Forge && pytest -q` 至少 3 个测试通过 | 30min |
| T061 | kronos 测试覆盖核心摄取路径 | 至少覆盖 L0/L2 基础路径 | 30min |
| T062 | codeanalyze 测试覆盖增加到 10+ | 核心分析路径有测试 | 30min |

## 依赖关系

```
T054/T055/T056 (可并行)
T057/T058/T059 (可并行)
T060/T061/T062 (可并行)
```
