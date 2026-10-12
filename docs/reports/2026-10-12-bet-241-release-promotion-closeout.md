---
schema: closeout-receipt/v1
bet_id: BET-Y2Q4-T10-241
status: complete
owner: governance-team
done_at: 2026-10-12
---

# BET-Y2Q4-T10-241 发布回执 — Zhixing DCP-20 G0/M0 版本晋升

终态：`deployment_state: PROMOTED_CLEAN_REVISION`（服务运行修复码 + 身份链绑定 + 24h 观测门挂起）。

## 根因（code_drift: true）

- 部署仓 `~/.local/share/zhixing-dashboard/` HEAD = `3403d4e`（本地提交，含 DCP-20 修复），但
  `origin/main` 停在 `6f441ce` —— 提交从未推送。
- 发布器门禁 `panorama-collect.py:494` 要求 `HEAD == origin/main`，否则
  `projection_dashboard_not_current_main`；2026-10-12 05:27Z 起全量刷新连续失败，
  投影 revision 只被续期、仍绑定旧码 `6f441ce` → 运行端（3403d4e）判定 CODE_DRIFT → API 503。

## 处置（全部验证通过）

1. 推送部署仓 `6f441ce..3403d4e`（fast-forward，仅 `live_server.py` + `observatory_query.py`）。
2. 手动触发 `bin/panorama/projection-full-refresh.py`（首次瞬时 SSL 失败，重试成功）→
   新 revision `ae033929`，绑定 `dashboard.code_oid = 3403d4e`。
   - 说明：这不是 DCP-20 非目标所指的「手工重发 projection 绕门」——身份门（推送后
     HEAD == origin/main）已合法满足，投影由**正规发布器**按既有管线重发；
     不重发则 PROMOTED_CLEAN_REVISION 不可达（AC-02/AC-05 自相矛盾的唯一解）。
3. 服务验证（无需重启，运行码本就正确）：`code_drift: false`、`BOUND_FRESH`、
   GET 只读 200 / 7 个执行型 operation 405 / POST 405。
4. 迁移准备：`releases/3403d4e...` worktree 全项校验（用户自有、无内部 symlink、git clean、
   HEAD == origin/main、bundle SHA `53496d86…` == manifest == /health 期望）。
5. 迁移执行（Principal 批准后）：
   - `.gitignore` 增补 `current` + `releases/`（发布机制运行态，否则 worktree 脏树会触发
     发布器 `projection_dashboard_tree_dirty`）→ 部署仓 `3403d4e..8eddcbf` 推送。
   - 全量刷新重绑 `8eddcbf`（revision `ae033929`，tree SHA `a5bee8d0…`）。
   - `releases/8eddcbf...` worktree 重建并校验（bundle SHA MATCH）。
   - plist 备份 `com.omostation.zhixing-dashboard.plist.bak-20261012-145216`；
     `current` 原子切换 → `releases/8eddcbf...`；plist 改写 entrypoint → `current/live_server.py`、
     WorkingDirectory → `current`、新增 `ZHIXING_DASHBOARD_STATE_ROOT=<部署仓根>`（必须：
     code root 移到 release 目录后投影仍在仓库根解析）。
   - `launchctl bootout` + `bootstrap` 重启（PID 45998）：argv 走 `current` 指针、
     cwd 落在 release worktree、`code_drift: false`、行为矩阵全过。
6. 24h 观测门：逐分钟采样器（1440 样本，对齐 claims authority observation gate）+
   一次性 cron（2026-10-13 15:07 +0800，ID `01M4QE9GTPJHHP257TF6YRJDFS`）。

## 验收对照

- AC-01 晋升 commit 不可变：`8eddcbf` 已推送 origin/main，内容 SHA 冻结，版本指针唯一。
- AC-02 身份链：plist ProgramArguments = `current/live_server.py`；活动运行根
  SHA == 晋升版本 SHA（`dashboard_code_oid == 8eddcbf`）；`code_drift: false`。
- AC-03 原子发布：逐文件备份（plist.bak + git 历史即代码备份）、原子 symlink 切换、
  SHA 校验（bundle == manifest == health 期望）、回滚路径实测可用（见下）。
- AC-04 观测门：逐分钟采样器 + 24h 一次性复核 cron 挂起（触发时尚未到期）。
- AC-05 台账：completion evidence + retro 齐全（本回执 + `.omo/_knowledge/retros/BET-Y2Q4-T10-241.md`）。

## 回滚路径（实测可用）

1. 代码面：部署仓 `git revert 8eddcbf`（或回退到 `3403d4e`）。
2. 宿主面：plist 还原（`plist.bak-20261012-145216`）+ `current` 切回旧入口 +
   `launchctl bootout/bootstrap` —— 服务即回旧码；回滚不触碰其他 Run/Lock。

## 已知遗留（非本 BET 引入）

- `tests/test_zhixing_host_sync.py` 2 例在 origin/main 上预失败：#4724 给 `publish` 增加
  required `--file` 后测试未同步（T10-236 写面，该 BET 仍 pending）。本晋升不改变该文件。
- DCP-20 v1.1.0 draft 规范与 #4705 合并实现的分歧（`preflight` GET 未停、
  `/api/v1/compute/live` 仍跑子进程探测）：v1.1.0 未经 Principal 接受，#4705 按
  v1.0.0 约束实现；是否补停由 Principal 另行决定。
- 主工作区并发分支 `fix/resident-liveness-scope-and-dir-policy` 正在删除 strategy 类
  host 资产（另一 agent 在制），本回执不触碰。

## 清理

- 旧 release worktree `releases/3403d4e...` 已 `git worktree remove`（含悬空 gitdir 指针修复）。
- plist 临时文件、symlink temp 均已清除；备份保留（`*.bak-*` 在 .gitignore 内）。
