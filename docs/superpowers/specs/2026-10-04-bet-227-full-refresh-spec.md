---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y2Q4-T10-227 全量投影数据周期刷新通道
bet_id: BET-Y2Q4-T10-227
status: accepted
lifecycle: contract
owner: engineering-agent
last-reviewed: 2026-10-04
---


# BET-Y2Q4-T10-227 Spec — 全量投影数据周期刷新通道

- bet: BET-Y2Q4-T10-227
- date: 2026-10-04
- owner: engineering-agent
- workflow: dashboard-evolution

## 背景

T10-223 的 republisher 只做租约续期（重打 generated_at/fresh_until, 保留
data_observed_at）。投影内容的观测龄期因此随时间单调增长——workflow runs、台账、探针、
事件等 collector 数据越来越旧, 页面上「最后观测」时间戳老化, 最终影响 dashboard 作为
运行态事实面的可信度。

全量 publisher `bin/panorama/panorama-collect.py` 的身份校验
（`collect_code_root_health`, :1696-1768）要求 PANORAMA_CODE_ROOT == origin/main 且
完全洁净。主树 ~/Workspace 是 agent 共享工作区, 常年有 WIP 与运行时脏文件 → 自动发布
通道实际不存在（T10-223 已实证）。

## 方案

### 组成

1. **持久专用检出** `~/.local/opt/omostation-publisher`
   - GitHub origin（starlink-awaken/omostation）浅克隆 `--depth 200`;
   - 子模块 `--depth 1` 浅初始化（publisher 采集覆盖 projects/ 下内容）;
   - 机器属主, 不属于 `~/ws-*` worktree 卫生面, 不被 hygiene-audit 扫描;
   - 复用 ADR-0456 install_root (~/.local/opt/omostation) 的目录惯例。

2. **driver** `bin/panorama/projection-full-refresh.py`（workspace, 随主仓演进）
   - 文件锁 `flock` 防重入（运行中第二次触发直接跳过并日志）;
   - remote 卫生校验: origin URL 必须以 `starlink-awaken/omostation.git` 结尾
     （防 9-13 remote 污染类事故）;
   - `git fetch origin` → `git reset --hard origin/main` → `git clean -fdx`
     （检出内无在制工作, 安全）→ `git submodule sync` + `submodule update --init --depth 1`;
   - 以检出为 `PANORAMA_ROOT` / `PANORAMA_CODE_ROOT` / `ZHIXING_DASHBOARD_STATE_ROOT` /
     `ZHIXING_DASHBOARD_CODE_ROOT` 环境, 运行**检出内** `bin/panorama/panorama-collect.py`
     （用检出内版本, 与 origin/main 同步演进）;
   - publisher 自带 workspace 身份 + deploy 身份双校验, 任何一步失败 fail-closed
     （退出非零 + 日志, 旧 revision 仍由 republisher 续期, 读端不受影响）;
   - 全程 JSON 行日志到 `~/.local/log/projection-fullrefresh.log`。

3. **调度** services.yaml 注册 `omostation.zhixing-projection-fullrefresh`
   （generate: true, interval 21600s=6h, RunAtLoad: true）, plist 由
   `bin/mof/gen-service-configs.py --write` 生成, 不手写。

### 时序

```
republisher (480s) ── 续旧 revision ──► pointer 原子切换 ──► 续新 revision
fullrefresh (6h)   ── 5~14min 采集+发布新 revision ──┘
```

发布期间读端全程 200（读的是旧 revision 直至 pointer 切换）。

## 验收

见台账 done_when。额外实测：连续两轮调度日志（第二轮锁防重入或正常顺序执行）;
失败注入（临时改检出 remote URL）退出非零且 dashboard 可用。

## 风险

- 首克隆耗时长/占盘: 浅克隆+浅子模块控制;
- publisher 失败: fail-closed, republisher 保底, 无可用性风险;
- 检出漂移: 每次运行 reset --hard origin/main, 无累积漂移。
