---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-73
---

# Documents Weijian dangling symlink quarantine — implementation evidence

## Scope and commands

- Source scope: `~/Documents/@工作文档/卫健委/_runtime` 悬空软链集合 (no-follow, 不重建缺失的 public-runtime 目标)。
- Target scope: `~/Workspace/runtime/quarantine/documents-weijian-symlinks-20260829/` (protected, `.gitignore: runtime/quarantine/*/`)。
- Owner: `lib/documents_runtime_quarantine.py` (symlink no-follow 语义 + link-target/metadata receipts)。
- Test command: `uv run --with pyyaml --with pytest python -m pytest tests/test_documents_runtime_quarantine.py -q`。
- Consumer command: `lib/documents_consumer_audit.py --json` (新鲜证据 receipt: status=ok, active=188, forbidden_executors=0, unmatched=0, errors=0)。
- Transaction command: `lib/documents_runtime_quarantine.py --apply`。

## L4 inventory (stable)

- Scoped L4 inventory 恰好识别 12 个悬空软链 (node_type=symlink, link_target 指向
  `@公共/_runtime/kems-v2/*` 等已消失的 public-runtime 目标), 无常规文件混入。
- 收口日复核 (2026-08-30): `_runtime` 目录递归软链计数 = 0 — 源集合已全部迁出, 集合稳定。

## Transaction (manifest 回执)

- Manifest: `runtime/quarantine/documents-weijian-symlinks-20260829/manifest.json`
  (status=completed, completed_at=2026-08-29T17:00:00Z)。
- Files: 12 (bytes=0 — symlink 元数据回执含 link_target/mode, no-follow)。
- consumer_summary: active=191, families=cockpit-runtime 18 / family-dashboard-app 35 /
  public-runtime 105 / learning-* 等。
- rollback manifest 在案; permanent_deletion=False。
- Postflight: 软链源缺席 (0 残留)、目标 link identity 由 manifest link_target 字段持有、
  常规文件/健康与工作内容面未动。

## RED → GREEN 与 negative

- Owner 的 symlink no-follow 测试覆盖 12 用例 (`tests/test_documents_runtime_quarantine.py`)。
- 新鲜消费审计负例: forbidden_executors=0, unmatched=0, errors=0 — 无不安全执行器。
