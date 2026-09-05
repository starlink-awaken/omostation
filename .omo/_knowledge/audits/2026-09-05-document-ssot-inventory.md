# 文档 SSOT 清单 — 2026-09-05

## 统计

| 指标 | 值 |
|------|-----|
| .md 文件总数 | 4181 |
| 总行数 | 430,906 |
| 声明 type=ssot | 2,163 (大部分不是真 SSOT) |
| 关键治理文档 | 7 个 |
| 子仓 AGENTS.md | 15 个 |
| 子仓 CLAUDE.md | 14 个 |

## 关键治理文档 SSOT 映射

| 文档 | 行数 | SSOT？ | 指向 |
|------|------|--------|------|
| AGENTS.md | 246 | ✅ 是 | 本仓操作指南 |
| CLAUDE.md | 238 | ✅ 是 | AI 启动协议 |
| README.md | 199 | ✅ 是 | 入口导航 |
| ARCHITECTURE.md | 203 | ✅ 是 | 架构契约 |
| GOVERNANCE.md | 109 | ✅ 是 | 治理政策 |
| LAYER-INDEX.md | 48 | ✅ 是 | 分层索引 |
| .omo/standards/doc-ssot-contract.md | 157 | ✅ 是 | SSOT 合同 |

## 膨胀风险 TOP 5

| 文档 | 行数 | 风险 | 建议 |
|------|------|------|------|
| AGENTS.md | 246 | 持续增长 | 保持 <300 行，超则拆分 |
| CLAUDE.md | 238 | 引用多 | 保持 <250 行 |
| README.md | 199 | 引用多 | 保持 <200 行 |
| ARCHITECTURE.md | 203 | 引用多 | 保持 <200 行 |
| docs/CLI-REFERENCE.md | 1854 | 过大 | 拆分为子命令文档 |

## 子仓文档对齐

大部分子仓 AGENTS.md 引用主仓（`main_ref=True`），这是正确的。
例外：metaos, omlxc（未引用主仓，可能需要补充指针）。

## 建议

1. **短期**: AGENTS.md 保持现状（246 行，可控）
2. **中期**: CLI-REFERENCE.md 拆分为子命令文档
3. **长期**: 定期审计（每季度），防止膨胀

---
审计人: Kimi Code CLI
