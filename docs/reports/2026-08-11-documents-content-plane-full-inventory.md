---
title: Documents 内容主权面全面迁移审计与资产清单
type: audit-report
lifecycle: history
owner: governance-team
last_updated: 2026-08-11
snapshot-kind: derived-report
baseline-root-commit: 35bd0757dbbb332e88b07ea51f3f19147dc0c831
captured-at: 2026-08-11T14:34:10+08:00
---

# Documents 内容主权面全面迁移审计与资产清单

## 1. 裁决

全面收敛有必要，但不能把 44,528 个候选当成同一种东西机械搬走。

最终边界如下：

- Documents 只保留数据、资料、信息、知识、文档、领域宪法、声明式契约、人工决策、可审计证据，以及明确标记为非权威且可重建的文档投影。
- KEMS 数据模型、ingest、评估、图、恢复与 promotion gate 统一归 `projects/knowledge/kairon/packages/kos/src/kos/kems/`。
- 任务状态、审批、证据与派发统一归 OMO；执行脊柱统一归 Workflow Mesh；调度、状态、缓存与运行适配统一归 Runtime。
- Cockpit 是唯一人机入口；l4-kernel 只拥有内容契约、路径策略、编译与 T0—T8 Harness。
- 家庭应用合并进现有 `projects/family-hub`，不再保留第二个家庭应用工程。
- 活跃外部代码仓归 Workspace 注册的 ToolBox/外部能力面；职业历史代码按“不可执行内容资料”保留，不搬 16 GiB 资料库。
- Zotero 数据目录迁出 Documents；Documents 只保留可阅读的导出物或附件资料，不保留 translators、SQLite 等应用运行资源。

禁止创建新的超级 KEMS、第二 workflow engine、第二家庭 Hub 或第二 CLI 平台。

## 2. 审计口径与可复现入口

基线：

```text
root worktree: /Users/xiamingxing/ws-documents-content-plane-full-convergence
root commit:   35bd0757dbbb332e88b07ea51f3f19147dc0c831
l4-kernel:     bf0bdcbe3f1510e52e1042f8c2050ae2a18b366f
Documents:     /Users/xiamingxing/Documents
captured_at:   2026-08-11T14:34:10+08:00
```

复现命令：

```bash
uv run --directory ".subtrees/l4-kernel" --group dev \
  python -m l4_kernel.cli content audit "/Users/xiamingxing/Documents" --json
```

分类器不执行任何文件、不递归目录符号链接；文件符号链接按其 legacy 路径独立审计。分类是架构初筛，不等于删除裁决。

## 3. 全量基线

扫描 321,787 个普通文件或文件符号链接：

| 分类 | 数量 | 最终策略 |
|---|---:|---|
| `content` | 276,650 | 保留 |
| `contract` | 420 | 保留并验证 |
| `projection` | 188 | 标明非 SSOT、可重建后保留或迁出 |
| `bridge` | 1 | 消费者切换后退役；最终为 0 |
| `runtime` | 7,650 | 迁移、合并、退役或内容归档 |
| `cache` | 36,878 | 迁出或重建；最终为 0 |
| **违规候选** | **44,528** | `runtime + cache` |

运行文件扩展名分布：

| 扩展名 | 数量 |
|---|---:|
| `.js` | 4,092 |
| `.py` | 1,708 |
| `.ts` | 1,192 |
| 无扩展名 | 547 |
| `.sh` | 81 |
| `.mjs` | 23 |
| `.rb` | 5 |
| `.pl` | 1 |
| `.cjs` | 1 |

## 4. 四个大面与真正活跃面

| 资产面 | runtime/cache 候选 | 物理规模 | 事实判断 | 目标处置 |
|---|---:|---:|---|---|
| `@家庭生活/family-dashboard-app` | runtime 1,411；cache 约 36k | 806 MiB | 真实 Next.js 应用；327 个非构建文件，`node_modules` 689 MiB，`.next` 114 MiB | 功能合并至 `family-hub`；构建缓存重建；切流后删除旧工程 |
| `@学习进化/_external/toolbox-staging` | runtime 2,704 | 531 MiB | 4 个干净独立 Git 仓，不是知识正文 | 迁入 ToolBox 的受管 staging/capability 面，Documents 留索引与学习笔记 |
| `@个人/_storage/职业历史` | runtime 2,553；cache 48 | 16 GiB | 美团 1,820、360 733，属于职业历史与代码资料，不是活跃 runtime | 以强校验 `CONTENT_ARCHIVE.yaml` 标为不可执行资料；不做 16 GiB 物理迁移 |
| `Zotero` | runtime 755；cache 1 | 24 MiB | Zotero 应用数据；`prefs.js` 明确把 dataDir 指向 Documents | dataDir 迁到 App Support；Documents 只留导出资料/附件 |

去掉上述四个大面后，剩余 runtime 候选正好 **227** 个。这 227 个仍混合：

- 真实活跃调度器和工具；
- KEMS 重复实现与域级符号链接；
- 一次性修复脚本；
- `_archive`、`_storage`、历史设计稿中的代码资料；
- 模板代码和教学示例。

因此最终动作必须是逐族判定，而不是批量按后缀搬迁。

## 5. 域级分布

| 根域 | runtime | cache | 主要构成 | 目标 owner/处置 |
|---|---:|---:|---|---|
| `@家庭生活` | 1,437 | 36,395 | Next 应用、11 个 KEMS 链接、医疗小工具、历史静态代码 | `family-hub`；Kairon/Runtime；内容归档 |
| `@学习进化` | 2,737 | 19 | 4 个外部仓、KEMS `.kems/_scripts`、daemon/executor、concept-weave | ToolBox；Kairon；Runtime；内容归档 |
| `@个人` | 2,553 | 48 | 职业历史代码资料 | `CONTENT_ARCHIVE.yaml`，execution=deny |
| `Zotero` | 755 | 1 | translators + sqlite | Zotero App Support |
| `@工作文档` | 90 | 398 | 域控制器、OCR、索引、报告生成、KEMS 链接、历史交付脚本 | Runtime domain adapters；Kairon；内容归档 |
| `@公共` | 59 | 13 | 跨域治理、ingest、桥、KEMS、审计 | l4-kernel/Cockpit/ECOS/OMO/Runtime，按职责拆分 |
| `@驾驶舱` | 9 | 2 | 旧驾驶舱 runtime 与生成器 | Cockpit；投影保持非 SSOT |
| `@OPC` | 2 | 0 | codebase-memory 安装/启动脚本 | ToolBox/Workspace setup 文档 |
| `@创意创作` | 2 | 0 | 归档安装脚本、模板 Python | 内容归档 |
| `_inbox` + Documents 根 | 6 | 2 | 一次性修复脚本和 SQLite | 证据归档/退役；缓存迁出 |

## 6. KEMS 专项事实

### 6.1 正式 owner

| 职责 | 唯一 owner |
|---|---|
| KEMS Method/Profile/ontology/rubric 正文 | Documents |
| DomainManifest、路径规则、内容审计、Harness | l4-kernel |
| ingest/evaluation/graph/recovery/promotion gate | Kairon/KOS `kos.kems` |
| task/approval/evidence state | OMO |
| worker execution | Workflow Mesh + Runtime |
| human/CLI/Web entry | Cockpit |

`projects/domain-kems` 是根仓追踪但未注册、无正式消费者的旁路原型；不能扶正为第二 runtime。有价值的领域关键词/控制器只能吸收到 Kairon 的 domain adapter 或 Runtime 的受管执行器，随后退役该目录。

### 6.2 Documents 残余

完整相对路径包含 `kems` 的 runtime 候选为 **46**，这是下界，不包含名称未带 `kems` 的 validator、controller、OCR 与调度脚本。

重复实现事实：

- `@公共/_runtime/kems-v2/`：12 个 Python 实现；
- 家庭、卫健委、国转中心、规自委四组绝对符号链接：共 46 个文件链接，均指向公共实现；
- `kems-init`、`kems-snapshot`、`kems-toolkit` 各有 5 个字节相同副本/链接；
- `check-kems-update` 有 3 个相同实现/链接；
- Phase 0 已把一个完全重复的 `kems-materialize.py` 替换为 Workspace 薄桥，最终仍需在消费者切换后退役。

### 6.3 活跃消费者

当前真实消费者不是推测：

- crontab 每日 08:00 运行 `@工作文档/卫健委/_runtime/check-kems-update.py`；
- `@工作文档/卫健委/CLAUDE.md` 把该命令定义为强制 Step 1；
- `@驾驶舱/_control/async-tasks.yaml` 登记该任务及 OCR 增量任务；
- Claude Scheduled 的 `weijian-daily-health`、`monday-vault-health`、`vault-daily-health`、`l4-governance-weekly` 仍引用 Documents runtime；
- `com.learningevolution.concept-weave.monthly` 已加载，ProgramArguments 指向 `@学习进化/_control/scripts/run-monthly-weave.sh`；
- 当前未发现正在执行这些目标脚本的常驻进程。

## 7. 调度与真实入口

### 7.1 crontab 中仍指向 Documents 的运行任务

公共治理面：

1. `watch-dispatch.py`（每分钟）
2. `domain-sync.py`
3. `bridge-refresh.py`
4. `signals-rotate.py`
5. `session-brief.py`
6. `async-audit.py`
7. `check-convergence.py`
8. `control-plane-freshness-audit.py`
9. 周日 KOS ingest（读取 Documents 内容，执行器本身不在 Documents）

卫健委面：

1. `check-kems-update.py`
2. `_control/controller.py`
3. `_control/predictor.py`
4. `_runtime/cron/ocr-incremental.sh`
5. `/tmp/gen_index.py`（当前是不可恢复的临时脚本依赖，必须 fail closed 并替换）

### 7.2 launchd

- 活跃：`com.learningevolution.concept-weave.monthly` 指向 Documents；
- 已归档：`com.antigravity.daily-mesh-runner` 仍包含旧 Documents 路径，但位于 `.archived-20260808`，只作为历史证据；
- `com.l4.governance.watch` 已指向 Workspace，方向正确。

## 8. Cockpit 入口漂移

当前安装入口 `/Users/xiamingxing/.local/bin/cockpit` 来自 Cockpit v0.4.0 的旧 detached checkout，`cockpit context`、`cards --check`、`kems status/domains` 均因 `cockpit.scripts.cockpit_mcp` 缺失而 fail closed。

仓库事实更糟也更明确：`cockpit_mcp` 已在历史提交中移除，但 `commands/l4bridge.py`、`commands/kems.py`、`commands/health.py`、`commands/brief.py` 和 dashboard routes 仍有遗留 import。Phase 0 的 `kems scan` 已正确委派 l4-kernel audit，但“唯一人机入口”还没有在安装态成立。

全面收敛必须先修复源代码适配器，再从 accepted release/worktree 重装并执行 installed smoke；仅测试源码 worktree 不算完成。

## 9. 家庭应用收敛

Documents 内 `family-dashboard-app` 是成熟 Next.js 应用，含大量页面、API route、搜索、任务、健康、成长、资产、时间线、AI、备份和写入保护；现有 `projects/family-hub` 只有较小的 Python/FastMCP、Express API 和 Vite quest UI。

正确动作不是删除前者，也不是保留双应用，而是：

1. 把 Next dashboard 作为 `family-hub` 的 dashboard app 合并；
2. 保留 family-hub 的任务/积分/API/MCP owner；
3. 把 Documents 访问改成显式 `FAMILY_DOCUMENTS_ROOT` 只读输入，所有 SQLite、索引、缓存和构建物写到 Workspace runtime state；
4. Cockpit `api_domain_apps.py` 只暴露 `family-hub`，移除 `family-dashboard-app` 第二 contract；
5. 在 Workspace 版本通过单测、构建、E2E 与读写边界测试后切流；
6. 旧工程只在另行确认、哈希清单和回滚包完成后删除。

## 10. 外部仓与 Zotero

### 10.1 四个外部 Git 仓

四仓当前均 clean 并跟踪 `origin/main`：

| 仓 | origin | HEAD | 处置 |
|---|---|---|---|
| DeepTutor | `HKUDS/DeepTutor` | `b7283548…` | ToolBox 受管 education staging |
| ai-engineering-from-scratch | `rohitg00/ai-engineering-from-scratch` | `c8b9b924…` | ToolBox 受管 education staging |
| BMAD-METHOD | `bmad-code-org/BMAD-METHOD` | `3dd88943…` | ToolBox methodology/capability staging |
| gstack | `garrytan/gstack` | `11de390b…` | ToolBox skills/capability staging |

迁移必须保留完整 `.git`、remote、HEAD 和工作树哈希；Documents 只保留说明、使用笔记和 `bos://capability/...`/ToolBox 指针。

### 10.2 Zotero

`~/Library/Application Support/Zotero/Profiles/c2ap8dvs.default/prefs.js` 当前明确记录：

```text
extensions.zotero.dataDir=/Users/xiamingxing/Documents/Zotero
extensions.zotero.useDataDir=true
extensions.zotero.sync.storage.watcher.fsEventsStoragePath=/Users/xiamingxing/Documents/Zotero/storage/
```

Zotero 当前未运行。迁移前必须：关闭/确认无进程、备份 SQLite、校验附件和 translators 数量、复制到 App Support、更新配置、启动 Zotero 验证库和附件、保留可回滚副本；删除旧目录需要单独确认。

## 11. 最终门禁

全面落地的完成证据必须同时满足：

1. Documents 全量 audit 中 `runtime=0`、`cache=0`、`bridge=0`；
2. 合法代码资料由 schema-valid `CONTENT_ARCHIVE.yaml` 归类为 `content_archive`，且无可执行位、无活动调度/消费者；
3. 所有活跃 crontab、LaunchAgent、Claude Scheduled、Cockpit contract 和域 CLAUDE 指向 Workspace owner；
4. family-hub 单一应用 contract、生效安装态与 E2E 通过；
5. Zotero 从新 dataDir 正常打开并能访问附件；
6. KEMS 的 ingest/eval/graph 只从 Kairon/KOS 暴露，任务/审批只经 OMO，执行只经 Workflow Mesh/Runtime；
7. 每个域 T8 通过，然后 T8 加入默认 profile；
8. 每次物理迁移均有前后 SHA-256、文件数、消费者证明和回滚记录。

## 12. 危险操作边界

本报告不授权以下动作：删除 `node_modules/.next`、删除 Documents legacy scripts/symlinks、移动四个外部仓、复制/删除家庭应用、改 Zotero dataDir、删除任何缓存或大目录。

上述动作必须在实施波次到达时输出精确 target、字节数、文件数、哈希/备份位置、消费者切换证据和回滚步骤，并再次获得明确确认。
