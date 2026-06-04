# Phase 4 任务规格书 v2.1（future-gated）

> 日期: 2026-05-30 | 版本: v2.1 | 依据: comprehensive-architecture-audit.md + post-phase1 governance
> 前序: Phase 3 必须验收通过，且经过 3-6 个月验证期；隐私隔离、备份 dry-run、审计追溯必须可用
> 变更: 新增 N1-N5 长期缺口（公文管线、SMB连接、媒体索引、隐私隔离、备份策略）

---

## 变更摘要

> **执行限制**: 本文件是 future-gated 规格书，不是当前执行源。SMB/NAS、媒体索引、统一备份、隐私隔离等任务必须等 Safe Mesh、数据分类、dry-run、人工确认与回滚策略全部可用后再进入 `.omo/tasks/active/`。

Phase 4 v1.0 (10 任务，持续) → Phase 4 v2.0 (15 任务)

| 来源 | 新增任务 | 说明 |
|------|---------|------|
| N1 公文模板 AI 管线 | 1 | kronos 扩展 |
| N2 SMB/NAS 连接器 | 1 | iris 扩展 |
| N3 媒体文件索引 | 1 | minerva 多媒体 |
| N4 数据隐私隔离 | 1 | ops 安全 |
| N5 统一备份策略 | 1 | ops 备份 |

---

## Agent 命令模板 — 新增任务

### N1: 公文模板库 AI 管线

```bash
task(category="unspecified-high", description="N1: Template library AI pipeline", prompt='''
Create an AI pipeline for government document templates.

Read: ~/Documents/工作文档/ and ~/Documents/公文模版/ (16 PPT categories + generic templates)

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/kronos/src/kronos/pipelines/template_pipeline.py

Requirements:
1. Template Discovery:
   - Scan 公文模版 directory for all template files
   - Classify: 报告类, 通知类, 请示类, 函类, 纪要类, etc.
   - Extract: title, category, structure, format requirements

2. Template-to-Document Generation:
   - Input: document type + topic + key points
   - Select matching template
   - Fill template with minerva-researched content
   - Output: draft document following government format

3. Auto-Formatting:
   - 公文字体 (方正小标宋/楷体/仿宋)
   - 公文格式 (红头/编号/密级/签发人)
   - Export to WPS/Word

4. Expose as MCP tool: "kronos_template_generate"
   - generate <type> <topic>: generate a draft document

5. Test: generate 1 通知 from template → verify format correct
6. Report: "Template pipeline: <N> templates discovered, <M> categories, 1 generation test: PASS"
''')

### N2: SMB/NAS 连接器

```bash
task(category="unspecified-high", description="N2: SMB connector", prompt='''
Create an iris connector for SMB/NAS (SharedDisk, 5.5TB).

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/iris/src/iris/connectors/smb_connector.py

Requirements:
1. Mount Detection:
   - Detect SharedDisk mount at /Volumes/SharedDisk
   - If not mounted, provide mount instructions
   - Periodic health check: mount alive?

2. File Indexing:
   - Scan SharedDisk directory structure
   - Index: photos (JPG/PNG/HEIC), videos (MP4/MOV), documents (PDF/DOCX), archives (ZIP/DMG)
   - Skip: system files, temporary files
   - Do NOT copy files — only index metadata (path, size, date, type, hash)

3. Incremental Sync:
   - Track changes via file modification timestamps
   - Only re-scan changed directories
   - Hash comparison for duplicate detection

4. Expose as MCP tool: "iris_smb"
   - scan: full scan of SharedDisk → index metadata to KOS Data domain
   - search <query>: search indexed files
   - status: mount status and last scan time
   - dedup: find duplicate files across the volume

5. Test: scan 1 directory → verify files indexed → search works
6. Report: "SMB connector: <N> files indexed, mount status: OK"
''')

### N3: 媒体文件索引

```bash
task(category="unspecified-high", description="N3: Media file indexing", prompt='''
Create media file indexing with computer vision for photos/videos.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/minerva/src/minerva/media/media_indexer.py

Requirements:
1. Photo Indexing (via local model or Apple Photos library):
   - Read photos from: ~/Pictures/, /Volumes/SharedDisk/Photos/
   - Use Apple Photos library if accessible (via PhotosKit/AppleScript)
   - Extract EXIF: date, location, camera, dimensions
   - Generate description: use a lightweight local vision model to describe image
   - Tag: people (if face recognition available), objects, scenes
   - Convert to Media domain entities

2. Video Indexing:
   - Read videos from: ~/Movies/, /Volumes/SharedDisk/Videos/
   - Extract metadata: duration, resolution, codec
   - Generate thumbnail
   - Tag: category (家庭视频/工作录像/下载)

3. Music Indexing:
   - Read from: ~/Music/
   - Extract: artist, album, genre, year
   - If Apple Music library accessible: use its metadata

4. Expose as MCP tool: "minerva_media_index"
   - index_photos: scan and index photo library
   - search_photos <query>: natural language photo search
   - timeline: chronological photo timeline

5. Test: index 1 photo album → verify: EXIF extracted, description generated, searchable
6. Report: "Media indexer: <N> photos, <M> videos, <K> music files indexed"
''')

### N4: 数据隐私隔离

```bash
task(category="unspecified-high", description="N4: Data privacy isolation", prompt='''
Implement data privacy isolation between work, family, and personal domains.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/ops/src/ops/data_isolation.py

Requirements:
1. Data Classification:
   - Personal: Obsidian vaults, AI experiments, personal notes
   - Work: government documents, client data, contracts
   - Family: member profiles, health records, education plans
   - System: architecture docs, governance, tool registries

2. Isolation Rules:
   - Work domain data: NOT shared to Family domain
   - Family domain data: NOT shared to Work domain
   - Cross-domain queries: check caller's purpose before allowing
   - RBAC enforcement: different roles for different data domains

3. Access Control:
   - Work data: only accessible by "work" role
   - Family data: only accessible by "family" role
   - System data: Admin only
   - Personal data: default (User) role

4. Audit Trail:
   - All cross-domain access attempts → logged
   - Suspicious: Agent accessing Family data during Work hours → flagged

5. Expose as MCP tool: "ops_data_isolation"
   - classify <file_path>: classify a file's data domain
   - check <source_domain> <target_domain>: check if data movement is allowed
   - audit: show recent cross-domain access log

6. Test: attempt work→family data access → denied → logged
7. Report: "Data isolation: 4 domains classified, cross-domain access control: operational"
''')

### N5: 统一备份策略

```bash
task(category="unspecified-high", description="N5: Unified backup strategy", prompt='''
Implement unified backup strategy for SSD, iCloud, and SharedDisk.

Create: /Users/xiamingxing/Workspace/projects/kairon/packages/ops/src/ops/backup_strategy.py

Requirements:
1. Backup Sources + Targets:
   Source                              Target
   ~/Documents/Obsidian/             → iCloud (automatic) + SharedDisk (weekly)
   ~/Workspace/ (omostation code)     → GitHub (automatic) + SharedDisk (weekly)
   ~/Documents/工作文档/              → SharedDisk (weekly)
   ~/Documents/公文模版/              → SharedDisk (weekly)
   /Volumes/SharedDisk/ (photos)     → iCloud Photos (automatic) + local copy
   ops databases (SQLite)             → SharedDisk (daily)

2. Backup Schedule:
   - Daily: ops DB → SharedDisk/Backups/
   - Weekly: full Documents + Workspace → SharedDisk/Backups/
   - Monthly: full backup verification (restore test)

3. Health Checks:
   - Verify backup integrity (SHA-256 check)
   - Check available space on all targets
   - Alert if: backup fails, space <10%, no backup for >48h

4. Expose as MCP tool: "ops_backup"
   - status: show backup status for all sources
   - run <source>: trigger immediate backup
   - verify <source>: verify last backup integrity
   - history: show backup history

5. Test: trigger 1 backup → verify file copied → verify SHA-256 → success
6. Report: "Backup strategy: <N> sources configured, 1 test backup: PASS"
''')
```

---

## Phase 4 v2.0 验收清单 (新增条目)

```
□ P4.7 — 长期缺口 (N1-N5)
  □ N1 模板管线: template discovered, generate test: PASS
  □ N2 SMB连接: SharedDisk indexed, search works
  □ N3 媒体索引: photos indexed with EXIF + descriptions
  □ N4 隐私隔离: cross-domain access denied + logged
  □ N5 备份策略: all sources configured, test backup verified

□ P4.1-P4.6 — v1.0 全部 (保留)
  □ 辅助自主度: metrics dashboard, feedback loop
  □ 系统分发: install.sh, configure.sh, auto-docs
  □ 健康监控: health scorer, anomaly detector
  □ 能力边界: SharedWork catalog, protocol watch
  □ 安全+质量: 10 laws, RBAC, EU economy, immune audit
  □ 人类控制: emergency stop, quarterly review, guardrail audit
```
