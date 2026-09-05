---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y2Q1-T10-01
risk_level: L3
human_gate: true
value_indicator_policy: false
type: ssot
---

# T10-01 零知识加密冷备份与单键还原脚本设计

## 1. 目标

构建全仓代码、台账、KEMS 知识库、SEMA 信念、个人 LoRA 权重的每日定时
零知识加密增量快照体系，并提供单键冷启动还原脚本。**100% 离线自主可控，
不依赖任何第三方云服务。**

## 2. In scope

1. `bin/ops/cold-backup-drill.sh`（新文件）：
   - 增量快照（rsync hardlink / tar 增量，本地目标目录或外接介质挂载点）。
   - GPG 对称加密（AES-256，口令来自环境变量或 keychain，不落盘）。
   - 快照不锁死主工作区（只读复制，无写回）。
   - `--dry-run` 预检模式与清单输出（文件数/字节量/digest）。
   - 覆盖面：Workspace git 仓 + 台账/retro + runtime KEMS/SEMA 数据 +
     LoRA 适配器目录；排除 .git 内部锁、缓存与 ignored 临时文件。
2. `bin/ops/restore-cold-snapshot.sh`（新文件）：
   - 单键还原：解密 → 校验 manifest digest → 恢复 git 仓与数据目录 →
     子模块 init → 依赖 bootstrap 提示（uv/pnpm 安装指令打印）。
   - `--verify-only` 模式：不落盘，仅校验备份完整性。
3. launchd/cron 示例片段（文档注释内，不自动安装）。

## 3. Out of scope

- 不购买/配置任何云服务；不做远端同步。
- 不自动安装 launchd/cron（由人执行安装，spec 只提供片段）。
- 真机裸机 15 分钟还原演练需要 human_gate 人工执行，本 spec 交付脚本与
  drill 流程，实测结果记 retro。

## 4. 验收（对齐 ledger done_when）

1. 增量快照 dry-run 秒级完成，不写主工作区（pre/post 工作区 digest 不变）。
2. `restore-cold-snapshot.sh --verify-only` 在加密快照上通过 manifest 校验。
3. GPG 加密在无口令输入环境下 fail-closed（不静默跳过加密）。
4. 裸机 15 分钟全量重建实测由 human 执行后记 retro（本 bet 内以
   `--verify-only` + dry-run drill 为交付验收）。
