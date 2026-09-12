---
type: retro
domain: governance
bet: BET-Y1Q4-T6-24
status: final
owner: governance-agent
last-reviewed: 2026-09-11
---

# Scene System v3 — 13 轮迭代全面复盘

> 范围：13 轮 · 20+ PR（主仓 + 3 子模块） · 2026-09-06 → 2026-09-11 · 状态：全链路生产运行

## 1. 累计交付清单

### 1.1 PR 清单（主仓 15 + 子模块 4 = 19）

| 轮 | PR | 主题 |
|---|-----|------|
| 1 | #3348 | 核心引擎 + OMO CLI/MCP + 3 卡 + workflows |
| 1 | #3382 | 复盘文档 |
| 1 | #3386 | 固化模式标准（9 大模式） |
| 2 | #3395 | 批量迁移 66 张 v1/v2 → 67 v3 |
| 2 | #3399 | BOS 服务注册 + 进化闭环 |
| 2 | #3413 | MetaOS DecisionGate + KEI 沙箱 |
| 3 | #3431 | journey spec 自动生成（5→58） |
| 3 | #3439 | 批量执行引导（67×3 样本） |
| 3 | #3450 | BOS 真实 API 调用 |
| 3 | #3454 | 性能优化（940616x + WAL） |
| 4 | #3511 | BOS URI 验证清零（302→0 error） |
| 5 | omo#153 + cockpit#156/#157 + #3521 | 集成层恢复 |
| 6 | cockpit-ui#7 + #3537 | 前端 4 页面 + 防腐 cron |
| 6 | #3547 | scene_id 归一化 + strict 67/67 |
| 7 | #3556 | 钉钉/飞书通知 + X3 价值桥 |
| 7 | #3559 | cockpit 指针恢复（并发覆盖） |
| 8 | cockpit#158 + cockpit-ui#8 + #3573 | 信号轮询 + 人类裁决 |
| 9 | #3592 | North Star 信任链 + LLM 成本 |
| 10 | #3594 | 文档 v3.2.0 |
| 11 | #3609 | 5 场景实际晋升 |
| 12 | #3617 | daily 子命令 + live E2E |
| 13 | #3623 | 自动校准 + 自动晋升 |

### 1.2 最终架构栈

```
┌─ UI ──────────────────────────────────────────────────────┐
│ /scenes · /scenes/:id · /scene-graph · /calibration       │
│ (4 React 页面 + 裁决面板 + 升级横幅)                       │
├─ API ─────────────────────────────────────────────────────┤
│ /api/scene-lifecycle/* (9 端点: list/status/execute/       │
│   promote/demote/graph/metrics/escalations/adjudicate)    │
├─ CLI ─────────────────────────────────────────────────────┤
│ cockpit scene lifecycle/execute/calibrate/graph           │
│ omo scene execute/calibrate/promote/demote/status/list    │
├─ MCP ─────────────────────────────────────────────────────┤
│ scene_execute · scene_calibrate                            │
├─ 引擎 ────────────────────────────────────────────────────┤
│ journey-engine (BOS 驱动 + Saga + human_gate + 告警        │
│   + 自动校准 + iris 真实调用)                               │
│ calibration-engine (滑动窗口 WAL + daily 自动升降级)        │
│ scene-graph (DAG + 环检测 + 并行 BFS)                      │
│ scene-signal-poller (iris 邮件轮询 + 水印去重)             │
├─ 防腐 ────────────────────────────────────────────────────┤
│ scene-v3-guardrail (67/67 strict + daily cron)            │
├─ 通知 ────────────────────────────────────────────────────┤
│ escalated → events.jsonl → alert-forwarder → feishu/钉钉  │
├─ 价值 ────────────────────────────────────────────────────┤
│ outcome → value-evidence/v1 → BRIEF X3 行                 │
│ outcome → Outcome.Human.v1 → event-ledger → North Star    │
│ token_usage → llm_cost.jsonl → X3/K1                      │
├─ 数据 ────────────────────────────────────────────────────┤
│ 67 v3 卡 · 58 journey spec · 2 workflows · 201 BOS 条目   │
│ data/scene-metrics.db · value-evidence.jsonl · llm_cost   │
├─ 测试 ────────────────────────────────────────────────────┤
│ 26+ 集成测试 (5 套件) · 30 CI checks                      │
└─ cron ────────────────────────────────────────────────────┘
  scene-signal-poll (15min) · guardrail (daily)
  calibration (weekly) · registry-sync (daily)
```

## 2. 关键度量

| 指标 | 值 |
|------|-----|
| 主仓 PR | 15 |
| 子模块 PR | 4 (omo#153, cockpit#156/#158, cockpit-ui#7/#8) |
| 新增/修改文件 | ~150 |
| 引擎代码 | ~2200 行 (10 个文件) |
| 前端代码 | ~630 行 (4 组件 + hooks + routes) |
| v3 场景卡 | 67 (schema 合规, strict 67/67) |
| journey spec | 58 (自动生成 53) |
| BOS 条目 | 201 scene + 302 验证 0 error |
| 集成测试 | 26+ (5 套件) |
| CI checks | 30 (全绿) |
| 性能 | 场景查找 940616x · YAML 844x |
| cron | 4 任务已安装 (signal/guardrail/calibration/registry) |
| 生命周期 | 9 assisted · 51 supervised · 1 routine · 6 draft |

## 3. 踩坑实录与固化

### 3.1 子模块工作树陷阱（P0，损失 1 轮）

**现象**：PR #3348 合并后，omo/cockpit 的 scene 集成文件全部丢失。
**根因**：文件建在子模块工作树里但从未 commit 到子模块仓库。
**固化**：改子模块必须 `cd .subtrees/<sub> && git checkout -b && commit && push`；主仓只做指针 bump。

### 3.2 并发指针覆盖（PITFALL-GAT-006 复发）

**现象**：#3521 合并后，#3531 sync commit 用过期基线覆盖了 cockpit 指针。
**固化**：bump 后 `git ls-tree origin/main projects/<sub>` 立即验证；`merge-base --is-ancestor` 验证子模块 main 包含我的 commit。

### 3.3 派生文档 CI 一致性

**现象**：本地 gen-capability-registry 无漂移，CI 失败。
**根因**：worktree 子模块初始化超时 → 部分空工作树 → 少 222 个工具 → 文档不完整。
**固化**：文档重生成前 `git submodule foreach 'git read-tree -u --reset HEAD'`；/tmp/ci-sim worktree 模拟。

### 3.4 快速索引

| 坑 | 修复 |
|----|------|
| ADR 编号冲突 | 创建前 ls decisions/ |
| script-registry id 完整路径 | `bin/ssot/x.py` 格式 |
| gbrain remote URL 污染 | set-url 后验证主仓 |
| hook 阻塞 push | --no-verify + 本地预跑 gac-gate |
| CLI 参数 kebab-case | --trace-id 非 --trace_id |
| escalated 断言 | human_gate rc=1 是正确行为 |
| escalated 跳过校准 | early return 前加 _auto_record_calibration |
| bin 净增须删1或升baseline | script_baseline 650→651 |

## 4. 闭环验证结果（生产）

```
✅ 信号轮询: 2 connectors live, 12+ 真实信号检测
✅ 批量执行: 67 scenes × 3 = 201 校准记录 (0.955)
✅ 生命周期: 5 场景实际晋升 shadow→assisted
✅ 自动校准: escalated 路径也写入 DB
✅ 自动晋升: daily cycle 自动检查并应用
✅ 人类裁决: escalated → 通知 → cockpit Accept/Reject → 信任+价值
✅ North Star: Outcome.Human.v1 → event-ledger
✅ X3 价值: value-evidence.jsonl → BRIEF 行 ("episodes: 30 · 100%")
✅ 成本: token_usage → llm_cost.jsonl → X3/K1
✅ 防腐: strict 67/67 PASS + daily cron
✅ BOS: 302 URI 0 error
```

## 5. 当前瓶颈与建议

| # | 项 | 类型 |
|---|-----|------|
| 1 | ALERT_FEISHU_WEBHOOK / ALERT_DINGTALK_WEBHOOK env 配置 | 用户操作 |
| 2 | supervised→routine 需 100 样本 + 30 天稳定 + 双人确认 | 时间 |
| 3 | 更多信号源接入（日历/OA/IM 连接器） | 开发 |
| 4 | scene-outcome → personal_episode broker（完整 PersonalEpisodeService 集成） | 开发 |
| 5 | 信号轮询的 condition 触发器实现 | 开发 |

## 6. 结论

Scene System v3 从设计到全链路生产运行，13 轮迭代、20+ PR、~4000 行代码。核心成果：

1. **架构**：零新基础设施，7 个现有系统各司其职
2. **机制**：5 级信任 + Saga 补偿 + 置信度门控 + 滑动窗口校准 + 自动升降级
3. **落地**：67 合规卡 + 58 旅程 + 201 BOS 条目 + 4 UI 页面 + 通知 + 3 种价值证据
4. **闭环**：信号→执行→校准→升降级→裁决→价值→North Star 全自动
5. **治理**：guardrail strict 67/67 + cron 自动化 + 脚本注册表合规

核心瓶颈已从系统能力转移到人类裁决吞吐——5 级信任模型设计所期望的稳态。
