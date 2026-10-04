---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-223 投影租约自动续期与孤儿 revision 治理
bet_id: BET-Y2Q4-T10-223
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-03
---


# BET-Y2Q4-T10-223 — 投影租约自动续期与孤儿 revision 治理

## 背景与问题（2026-10-03 第 3 次实证）

zhixing-dashboard (:43191) 采用 revision-bound projection 读取协议：读端
（`~/.local/share/zhixing-dashboard/runtime_paths.py`）要求
`fresh_until - generated_at <= 15min`，过期即全站 503 `projection_stale`。

唯一全量 publisher（`bin/panorama/panorama-collect.py`）受两道强约束：

1. **身份校验**：发布时工作区必须 `HEAD == origin/main` 且完全洁净
   （`collect_projection_producer_identity`），生产主树常年有 WIP → 发布失败；
2. **采集耗时**：完整采集 5~14min，压不住 15min 新鲜度窗口。

部署侧 `~/.local/share/zhixing-dashboard/panorama-collect.py` 是 2026-09-22 旧版
（无 `publish_projection_revision`），launchd 定时跑的正是它 —— **revision 发布通道
在生产根本不存在**。503 复发 3 次，均由人工手动复制 revision + 重打 manifest 时间戳
临时修复，15~900min 后再次过期。

实证数据：revision 目录 631 个孤儿占用 9.9GB，无任何 GC。

## 方案

新增 `bin/panorama/projection-republisher.py`（纯续期工具，非 publisher 替代）：

- 读当前 pointer → 上一 revision（manifest sha256 经 pointer 交叉校验）；
- 逐字继承工件与 provenance（producer/dashboard/source_hashes/claims/artifacts），
  仅重打 `generated_at`/`fresh_until`（+10min，与 publisher 同语义）；
- `revision_id = sha256(canonical_json(basis))`，新目录落盘，原子替换 pointer；
- 剩余租约 >180s 跳过；flock 防并发；工件哈希复核不过则 fail-closed；
- 锁文件置于 `revisions/` 内（该目录已被 deploy 侧 .gitignore 覆盖），
  **避免在 state root 顶层产生未跟踪文件触发读端 CODE_DRIFT 启动失败**
  （2026-10-03 实证：顶层 stray lock → repo dirty → 服务无法启动）；
- `--gc --keep N` 清理孤儿 revision（默认 48，≈6.4h 回滚窗）。

调度注册：`.omo/_truth/registry/services.yaml` 新增
`omostation.zhixing-projection-republisher`（generate: true，launchd
StartInterval=480s，RunAtLoad 覆盖睡眠唤醒场景），plist 由
`bin/mof/gen-service-configs.py` 生成，不手写。

## 不做（non-goals）

- 不修改读端 `runtime_paths.py` 的 15min 上限语义（安全约束不动）；
- 不替代全量 publisher 的数据刷新职责（观测数据更新仍由 panorama-collect 承担）；
- 不改动 deploy 侧 `panorama-collect.py`（43910 全景站仍由旧版提供服务）；
- 不做全量 publisher 的专用洁净 worktree 发布通道（另立 BET）。

## 验证

- 续期后 `:43191` `/`、`/api/v1/manifest`、`/api/v1/summary`、search 全 200；
- 连续观察 ≥2 个调度周期（16min）无 503，revision 链正常滚动；
- GC 后 revisions ≤ keep+1，磁盘占用从 9.9GB 降至 <1GB；
- `git status` 于 state root 为空（读端启动洁净要求保持成立）。
