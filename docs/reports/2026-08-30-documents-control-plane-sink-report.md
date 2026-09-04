---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
---

# Documents 控制面残留下沉 — implementation evidence（④②① 三事务）

## 事务记录（全部 run 20260830T065121Z-bet-execution-c648875e）

| # | scope | files | bytes | quarantine 包 | manifest |
|---|-------|-------|-------|---------------|----------|
| ④ | `.codex-optimize-log` oneoff 修复脚本 | 3 | 16257 | `documents-root-codex-tools-20260830` | ✅ 含 sha256 |
| ② | `@学习进化/_control/executors` runtime 文件 | 9 | 45024 | `documents-learning-control-runtime-20260830` | ✅ 含 sha256 |
| ① | KEMS `.kems/_scripts` staging toolkit | 10 | 33617 | `documents-learning-kems-scripts-20260830` | ✅ 含 sha256 |

## 接管与收口

- **kems-toolkit ×10 已 git 托管**：omostation-runtime#70 `scripts/kems-toolkit/`（MERGED 2026-08-30T07:45:47Z），字节级等价（quarantine manifest hash 对照）。
- **主仓 gitlink bump**：projects/runtime → `cc28486a7`（fetch 后 origin/main 头，指针 bump 契约）。
- **registry**：learning-runtime glob 扩展（`.kems/_scripts/**`）+ 2 条 control_plane_transactions；root-oneoff-assets glob 扩展（`.codex-optimize-log/**`）+ 1 条 transactions。
- **消费者硬门**：fresh receipt（188 consumers，forbidden_executors=0，unmatched=0）。`kems` CLI/MCP 从未部署到 `~/.local/bin`，零消费风险。

## 已知残留与 gap

1. **`kems-mcp`（@学习进化/_control/executors/）**：Python MCP server 入口，mode 644 无扩展名，L4 分类器未判为 runtime → **分类器 gap**，未随事务下沉。契约上不私自搬（audit 选集即事务集），留待分类器口径修正或专项事务。
2. **learning-runtime owner parity**：learning_decay/orphans owner jobs 只覆盖衰减巡检；rename-check/repair/validate/vault-search/minerva-ingest/v5-bootstrap/kems-global ×8 的 Workspace owner 命令与 exit-code parity 未验证。文件已隔离（rollback 可用），功能重建需求登记待办。
3. **root-oneoff-assets evidence_gap 未变**：8 个历史源路径的 manifest 缺失依旧；本次 codex ×3 事务 manifest 完整。
4. **bridge 复核通过**：`@公共/_runtime/kems-materialize.py` 为 643B `workspace-bridge` 薄壳（execv 转发 Workspace 正本），bridge 分类语义正确，**保留**（spec 非目标）。

## Documents ↔ Workspace 协同范式（从 bridge 薄壳的启示）

bridge 薄壳模式（Documents 留指针壳，Workspace 承载执行）已在本仓验证可行，可作为
"内容面留 Documents、控制面进 Workspace"的通用协同机制，后续 BET 单独设计。

## 增补（2026-08-30 晚，#2714 后续）

- **kems-mcp gap 已闭环**：l4-kernel#9（shebang→runtime）与 #10（.fuse_hidden/.nfs
  审计跳过）合并后，新分类器 dry-run 选集精确为 executors/kems-mcp（1 文件/5112B），
  事务完成入包 `documents-learning-control-runtime-t2-20260830`（manifest 完整）。
- Documents `@学习进化/_control/executors/` 目录已空。控制面残留终局：
  **仅剩 bridge 薄壳（ADR-0441 原语 1 首实例）**。
- registry 已 round-trip 追加第 3 条 control_plane_transactions。
- 教训入档：治理 SSOT 的编辑一律走 yaml round-trip（本报告期内字符串手术三连炸，
  根因均为插入内容的缩进层级与锚行后继行的实际层级不匹配）。

## T10-69 终局（2026-08-30 晚）

principal 放弃 iCloud 追查。物理下沉已完成并实证，recoverable 契约因数据丢失不可满足：
T10-69 状态以 #2718 principal 批量授权的 done 为准；recoverable 缺口转 D-8 重建债（事实记录面）。
registry public-runtime evidence_gap 更新为 FINAL 终局，重建路由 debt D-8。
