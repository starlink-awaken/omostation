---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# management/ INDEX — P77 物理迁移后结构

> P77 R1: 144 文件按 P75 category 物理迁移到 3 子目录
> 迁移时间: 2026-06-23
> 只做管理文档导航；control/truth SSOT 指向 `../_truth/` 与 `../_control/`

## 子目录结构

| 子目录 | 数量 | 关键词 (P75 自动分类) |
|--------|-----:|----------------------|
| `workflows/` | 127 | audit / closeout / hardening / playbook / migration / phase / final-state / optimization / bet- / report / snapshot |
| `playbooks/` | 5 | append-only-log / schemas / ssot / manifest / defensive / replay / node / mvp |
| `guides/` | 12 | architecture / explainer / analysis / deep / layer / modeling / intro |

**总计**: 144 文件

## workflows/ (127)

```bash
ls .omo/_knowledge/management/workflows/ | head -20
```

主要分类:
- **审计报告** (audit): bet-38c6-p0-triage-report, omorift-audit, bos-perf-baseline 等
- **closeout 报告** (closeout): P37/P45/P47 各种收口
- **架构文档** (architecture): layer-deep-architecture, final-state, etc
- **hardening 报告** (hardening): deep-defensive-hardening 等
- **Bet 系列报告** (bet-): bet-38c6, bet-f478 等
- **Phase 报告** (phase): phase16, phase29 等

## playbooks/ (5)

```bash
ls .omo/_knowledge/management/playbooks/
```

- `append-only-log-cross-repo-manifest-2026-06-10.md`
- `append-only-log-cross-repo-ssot-2026-06-11.md`
- `append-only-log-pattern-2026-06-09.md`
- `append-only-log-schemas-2026-06-09.md`
- `append-only-log-cross-repo-ssot-2026-06-11.md`

**主要**: append-only-log 系列 (5 个)

## guides/ (12)

```bash
ls .omo/_knowledge/management/guides/
```

主要分类:
- **架构分析** (architecture-analysis): architecture-pure-analysis, health-snapshot-phase16, etc
- **5+3+1 框架** (5+3+1): full-audit, layer-deep-architecture
- **债务分析** (debt): DEBT-ANALYSIS, debt-systems-analysis
- **其他指南** (guide): 各种 explainer

## 工具

| 工具 | 用途 | 阶段 |
|------|------|------|
| `bin/management-categorize.py` | 加 category 字段 | P75 |
| `bin/management-migrate.py` | 物理迁移 | P77 |
| `bin/cross-submodule-check.py` | 跨子仓联动 | P78 |

## 双指针 (P53 简化版)

- 迁移后: 文件仅在新子目录 (P77 简化版, 不需要原位 deprecated)
- P53 严格: 原位 deprecated + 新位 active (双份)
- P77 简化: 因 P75 已加 category 字段, 不需要原位

## 关联

- **ADR-0071**: P77 物理迁移 (P77 R1 决策)
- **ADR-0069**: P75 management 分类 (P75 R1 决策)
- **ADR-0053**: P53 双指针 (设计原则)

## 后续

- 跨子仓联动 (ecos/agora/cockpit 联动检查)
- management 子目录自动洞察
- alert-history 自动关联
- graphify 实际扫描 (需 OPENAI_API_KEY)

---

*最后更新: 2026-06-23 · P77 management 物理迁移完成*