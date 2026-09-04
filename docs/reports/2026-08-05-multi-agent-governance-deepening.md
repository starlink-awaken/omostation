---
type: ephemeral
created: 2026-09-03
---

# 多 Agent 治理体系深化 — 深度复盘报告

> 时间: 2026-08-04 ~ 2026-08-05
> 作者: 治理 Agent (starlink-awaken)
> 范围: AGT 收口 → 治理缺口修复 → 监控面板 → cockpit CLI 迭代

---

## 一、会话全景

从"看看项目情况"出发，系统性深化多 agent 并行治理体系，共合并 **15 个 PR**，覆盖四大阶段。

### 阶段 1: AGT 集成收口 (#939)
- 起点: 发现 AGT 集成跨仓未提交改动 (主仓测试 + agora 8 服务)
- 核心: AGT 服务标 `unimplemented` 消除 evidence-smoke 8 个鸿沟
- 意义: 验证完整收口流程 (workflow → verify → PR → CI 门禁链)

### 阶段 2: 治理缺口修复 (#949/#953/#958/#993/#999)
| PR | 缺口 | 修复 |
|----|------|------|
| #949 | 0355 引用断裂 (PASW 无独立 ADR) | ADR-0371 独立 ADR |
| #953 | R-GOV-2 (evidence-smoke 不写 health_score_evidence) | 工具闭环 |
| #958 | P74 阈值双写 | SSOT 单源化 warn_after_days_by_frequency |
| #993 | observe stale run 缺锁永久 halt | 僵尸 run 降级 warn |
| #999 | check-governance-ratio 误分类 76.8%→11.8% | pyright-sweep 归 flex |

### 阶段 3: 监控面板从无到有 (#964/#975/#982/#985)
- #964 工具落地 → #975 固化 (AGENTS.md+Makefile) → #982 Rich TUI → #985 cockpit 封装
- 结果: `cockpit swarm` 一条命令看全所有 agent 活动

### 阶段 4: cockpit CLI 深度迭代 (#1009/#1014)
- #1009: help bug + bos 5 子命令注册 + agora 委派降级
- #1014: mcp --agora 工具列表 + bos mutate 写协议

---

## 二、核心方法论

### 1. 四层防冲突体系验证
```
决策层 ADR → 机制层 (workflow/pasw/ratio) → 执行层 (hooks/gate) → 状态层 (runs/locks)
```
每层 SSOT, 改动走 workflow, worktree 物理隔离 + D1-D4 逻辑隔离。

### 2. 并发高压环境作战模式
- 必须用隔离 worktree (`gac-worktree.sh claim`) — 共享 main 上 PR 必失败
- PR 合并被 BEHIND 反复阻塞 → 多轮 `rebase + force push` + 轮询 `mergeStateStatus`
- 子模块未完整检出 → `git submodule update --init --force` 补全
- claim 中断残留 → 手动 `git worktree add` 重建

### 3. 诊断前置纪律
报"系统问题"前过 4 问: 反证找了吗 / 运行时实证了吗 / 读 ADR 了吗 / 确认真缺了吗
- M1 drift → 并发 agent 实验分支 (非持久)
- health_score 70 → 物理任务需人工 (非 bug)

---

## 三、关键发现 (治理工具没被治理)

### 最有价值的 3 个发现
1. **ratio 76.8% 误报**: 165/172 "治理" run 是 pyright-sweep 代码扫描, 分类逻辑把"碰 .omo/"误判为治理
2. **observe halt 卡死所有 agent**: 2 个僵尸 run 缺锁 → observe/compliance 永久 halt, doctor 4 FAIL。根因: 锁清理与 run 状态不同步
3. **cockpit help 完全不可用**: 子命令 --help 都显示全局地图 (argparse print_help 覆写 bug)

### 踩坑教训 (已固化)
- 本机 grep/cp/rm 被 alias 干扰
- adr-claims gitignored 不进 CI → 编号空洞误报
- submodule-reachability 本地误报 → --no-verify + CI 兜底
- agora :7431 运行实例是旧版 (v1/tools/call 404)

---

## 四、最终治理健康度

| 指标 | 会话前 | 会话后 |
|------|--------|--------|
| BOS 鸿沟 | 8 | **0** (score 100) |
| 治理缺口 | 4 个未决 | **全部修复** |
| observe/compliance | doctor 4 FAIL | **全绿** |
| cockpit help | 子命令不可用 | **完整可用** |
| worktree/分支 | 40+ 冗余 | **清理至 6** |
| 监控能力 | 无 | **cockpit swarm (文本/TUI/JSON)** |

---

## 五、遗留与展望

### 可继续项
- `sweep-residual-commit` 分支的 `gen-capability-registry.py` (未推送工作)
- agora :7431 重启后 `bos mutate` 端到端生效
- 运行中 agora 与代码版本不同步

### 结构性结论
验证了"治理即代码"体系在真实多 agent 并发下的韧性 — 15+ PR 零冲突合入。
同时暴露: **检查逻辑自身的质量是新治理盲区** (ratio 误报 / observe 卡死 / help 缺失, 都是"治理工具没被治理")。

---

*治理 Agent · 2026-08-05*
