---
status: deprecated
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
deprecated-since: 2026-06-23
original-path: "/Users/xiamingxing/Documents/学习进化/2-knowledge/基建架构/eCOS-v5-Architecture-SSOT.md"
break-reason: "P55 R1: 外部 symlink 断链 (目标文件已移至 phase6-完成化/pat-45-eCOS-v5-architecture.md, 实际位置已不可达)"
superseded-by: "docs/PANORAMA.md (eCOS v6 5+4+1+1 全景) + docs/ARCHITECTURE-DIAGRAM.md"
current-version: "eCOS v6 (5+4+1+1)"
---

# eCOS v5 Architecture SSOT (DEPRECATED · BREAK-LINK)

> ⚠️ **DEPRECATED** — 原 symlink 目标 `/Users/xiamingxing/Documents/学习进化/2-knowledge/基建架构/eCOS-v5-Architecture-SSOT.md` 已不可达。

## 历史

- 创建时间: 早期 Phase (P28 之前)
- 原意图: 把 eCOS v5 (5+3+1) 架构宪法文档作为 `.omo/_knowledge/management/` 下的 SSOT 指针
- 实现方式: symlink → `~/Documents/学习进化/2-knowledge/基建架构/eCOS-v5-Architecture-SSOT.md`

## 失效原因

1. **断链**: 目标文件已从原位置移走 (P35 后)
2. **版本演进**: 当前系统已演进至 **eCOS v6 (5+4+1+1)**, v5 已成历史
3. **替代权威**:
   - 系统全景: `docs/PANORAMA.md`
   - 架构图: `docs/ARCHITECTURE-DIAGRAM.md`
   - 5+4+1+1 视图: `LAYER-INDEX.md` / `AGENTS.md`

## 处理 (P55 R1)

- 删除原 symlink 文件
- 本 README 替代原 symlink, 标注 deprecated + 给出权威替代

## 引用清理

引用 `eCOS-v5-Architecture-SSOT.md` 的文档需改为引用 PANORAMA.md / ARCHITECTURE-DIAGRAM.md:

| 引用位置 | 旧 | 新 |
|---------|----|----|
| `.omo/_knowledge/management/plan-phase30-architecture-maturity.md` | eCOS-v5-Architecture-SSOT | docs/PANORAMA.md |
| `.omo/_knowledge/design/diagrams/4-plus-1-3-architecture.md` | eCOS-v5-Architecture-SSOT | docs/PANORAMA.md |

---

*最后更新: 2026-06-23 · P55 R1 治理收敛 · 删除悬空 symlink*