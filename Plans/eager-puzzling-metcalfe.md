# 全面推进实施计划 — 蓝图 W2/W3 阶段清偿（2026-08-16 →）

> 授权基线：用户指令「忽略时间限制，完成后续剩余所有工作，决策按最优解」+ 分级授权（直接执行/通报面/保留面三档）。时间窗口类 done_when 依事实判断（窗口期证据已满的立即收口，未满的标注等待、不造假）。
> 执行模式：老王亲推为主（subagent 挂单率 9/10），每 bet 独立 worktree + workflow + CI 绿 merge + retro + 台账，阶段性清 worktree/分支。

## Context

蓝图六文档已发布为治理基线；G-1 门 6/6 PASS（SR-06 六轮生产链实证），W0/W1 完成。当前站在 W2（OMO 主权）门口，蜂群开闸待用户 G-1 §7 签名（保留面，不代签）。本计划覆盖台账 Y1Q3 剩余 9 项 + Y1Q4 全部 6 项 + 4 个 SR-06 产品缺口 follow-up + 感知面真实修复 + 制度/门禁/文档同步更新。Y2/Y3 窗口 bet（13 项）不动——前向依赖未解，提前做即 T3-01 镜像错误。

## 依赖拓扑（已实测）

```
Y1Q2-T1-02 (model-driven 判定 ADR, L1, 无依赖) ──┐
                                                ├─→ Y1Q2-T1-01 (omo-debt+c2g 并入, L3) ─→ Y1Q4-T6-01 (aetherforge 并入) ─→ Y1Q4-T1-01 (年度盘点)
Y1Q3-T3-02 (Neo4j, L2, 依赖已done) ─→ Y1Q3-T3-03 (mem0 退役) ─┐
                                    └─→ Y1Q3-T6-01 (gbrain+kairon 归并, L3) ──────────┤
Y1Q2-T7-01 (in_progress, 08-19 窗) ─→ Y1Q4-T4-01 (评测集)                            ├─→ Y1Q4-T1-01
Y1Q4-T3-01 (自主性阶梯, 依赖已done) ─→ Y1Q4-T7-01 (公文 format_check)                │
无依赖: Y1Q3-T6-02 (cockpit 清债) / Y1Q3-T7-01 (召回指标) / Y1Q3-T2-01 (第二管子) / Y1Q4-T5-01 (fork/join) / Y1Q3-T1-04 (年度门提案)
```

关键判定：**T6-01 归并与 T1-01 并入是两个 L3 不可逆大件**，但 Y1Q4-T1-01（年度盘点门）同时依赖两者——必须真实完成才能解锁年度门，不可绕。

## 执行批次（8 批，按依赖序 + 风险梯度）

### 批次 1 — 快胜群（无依赖，并行 worktree，今日）
1. **Y1Q2-T1-02** model-driven 判定 ADR：实测调用链（rg 调用方 + codebase-memory MCP），产出 ADR-0411+（接入主链/降库/归档三选一），判定依据=实测非意图
2. **Y1Q3-T7-01** 召回被引用率：埋点「召回 N 条/成稿引用 M 条」→ /outcomes 面板 + 首月基线值
3. **Y1Q3-T6-02** cockpit 清债：cockpit_mcp 残留 import 清理、l4bridge try/except 降级移除、audit worktree 指针同步、六模块无参运行验证
4. **Y1Q4-T5-01** 并行会签 fork/join：按 bet done_when 实现（依赖已 done）
5. **Y1Q4-T3-01** 自主性阶梯 L0-L3：四级硬门判据 + OMO 事件 + 降级可测（注入 rejected 即降级）

### 批次 2 — 感知面真实修复（T2-01 + T2-03 收口，今日）
- **实测发现**：netease 容器真名是 `com.netease.macmail`（注册表写的 `com.netease.mailmaster` 永远 unreachable）；`@感知信号` 目录空且 8/9 后无新信号（无真实投递习惯=第二管子名存实亡）
- 处置：①netease 路径修正→probe_depth 适配→验证真实信号 ②T2-01 重新定义「第二根管子」=邮箱大师（真名修正后即真实在跑）而非投递文件夹 ③每周≥10 信号以 apple_mail+netease 双源计 ④T2-03 落盘 24h 证据已足（信号持续 08-15→08-16）→ 按事实收口 done
- 门禁更新：signal-sources.yaml 路径修正 + health_must_not 契约随真实状态对齐

### 批次 3 — SR-06 四缺口 follow-up（新立 bet，今日）
立 BET-Y1Q3-T5-04（P1，打包四件，T1-18 retro Q3 转正）：
- admission TTL 续期/幂等重放语义（workflow_dispatch.py）
- completion report filesModified 契约强制（prompt contract 层）
- collect 越界检测补 untracked 扫描（blueprint_control.py）
- supervisor terminal fallback limit 200→自适应（orca-codex-supervisor.py）
每件带 RED→GREEN 测试，复用 test_blueprint_control.py 既有模式

### 批次 4 — Y1Q2-T1-01 归并（L3 大件一，依赖批次 1 的判定 ADR）
- 按 ADR 结论执行：omo-debt+c2g 内包进 omo、子模块条目移除、去重清单逐项可复核、src 下降量=清单合计、test_loc≥基线、CLI 兼容迁移说明
- human_gate: true——**实施完成停在接受审**，不自行置 done（L3 保留面）
- gitlink/CI/AGENTS.md/ARCHITECTURE.md/layer-contract.yaml/project-registry.yaml 同步

### 批次 5 — Y1Q3-T3-02 Neo4j（L2，human_gate）
- NEO4J_URI 配置生效、7474/7687 入 port-registry、temporal_fact/entity_relation 真图路径、不可达降级可见不静默
- 本地 docker 起 Neo4j（资源受限：mem cap 512M）跑通生产路径后收口

### 批次 6 — T3-03 mem0 退役 + T6-01 gbrain+kairon 归并（依赖批次 5）
- T3-03：消费者清点→迁移→删（1 周量）
- **T6-01（最大件，L3 不可逆）**：6 周窗口按用户指令压缩推进，但质量红线不降——去重清单/净值核算（复用 T1-03 numstat 口径）/test_loc 保护/单一 knowledge 项目/全消费者迁移。分 4 子 PR：迁移设计 spec → gbrain 侧内包 → kairon 侧内包 → 子模块条目移除+全仓指针/文档/门禁更新
- 两个 L3 完成后 human_gate 停审

### 批次 7 — Y1Q4 收尾群（依赖解锁后）
- Y1Q4-T6-01 aetherforge 并入（批次 4 后）
- Y1Q4-T4-01 评测集≥200 条（T7-01 08-19 窗口后真实样本；adjudication 资产已存在 test_omo_adjudication.py 可复用）
- Y1Q4-T7-01 公文 format_check L2（批次 1 的 T3-01 后）
- Y1Q4-T1-01 年度盘点与门（全部解锁后；与 T1-04 提案合并出最终年度门修订包→human_gate）

### 批次 8 — 制度面同步（贯穿，每批完随批走）
- G-1 证据包/全量交接手册 §13 增量滚动更新
- AGENT-BRIEF：新增「L3 归并操作规程」（去重清单模板/净值核算/test_loc 保护三件套）
- MILESTONES 文档更新实际节拍；capability-registry 刷新（新工具入库）
- 每批次收口后 worktree/分支清理（janitor 三条件）

## 日历锁定项（不可强推，只做证据采集）
- T1-05A：08-21 窗满 → 导 status --json 快照 + human_gate（协调层 6/6 心跳持续记录中）
- T7-01：08-19 窗满 → 按真实样本裁决
- MOS 双栈 T3-01：10-08 满（不动）
- D2：08-21 T1-05A done 后渐进周启动 → 08-28 硬收口（guard 激活）

## 验证总纲
- 每 bet：verify 命令实跑贴输出 + gac-local-gate 44 checks + CI 全绿 merge + retro 五问 + 台账 lint 零错
- 归并类：去重清单行数 == src 下降量；test_loc 前后对比（降即回滚）；全仓 grep 零残留引用
- 感知面：health 输出全绿 + 每周信号计数实测
- 阶段复盘：每 2 批次出一次 session retro（模式/成本/制度缺口），迭代下一批

## 红线（不变）
- 时间窗口 done_when 未满不置 done（证据够即收，不够即等）
- human_gate 项（T6-01/T1-01/T3-02/T2-01/T1-04/年度门/G-1 签名）实施完停审，不代签
- test_loc 是保护量；归并 test_loc 下降=回滚
- 主仓不直接工作；L3 大件独立 clone/隔离 worktree；janitor 清理
