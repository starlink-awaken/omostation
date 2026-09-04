---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# 里程碑薄文档 — 2026 Q3/Q4 战术编排

> 类型: 编排层（只放台账放不下的依赖关系与节律约定）
> 数字 SSOT: `docs/plans/3y-bet-ledger.yaml`（本文档不复制任何 bet 计数/状态值）
> 决策依据: SESSION-RETROSPECTIVE-20260814-15.md（六大失败模式）+ 2026-08-15 战略规划七问裁定
> 创建: 2026-08-15 · 评审节律: 每周 checkpoint 一次

## 0. 战略裁定（七问结论快照）

| # | 裁定 |
|---|------|
| 锚点 | 双轨制 — 制度可信+拓扑根治为主线, 窗口节律照走, Y1Q4 `code_loc<=690K` 标记「需重基线」 |
| 序列 | 并行双线 + 硬次序 — D2 启动 = T1-05A done AND T9-01 verify-diff 部分 merge |
| 挂账 | 一事一 bet — 新立 T2-03 / T1-03 / T1-04 / T9-01（Y1Q3） |
| Y1Q2 残留 | T7-01 补登 done; T1-01/02 顺延 Y1Q3; T1-18/19/20 blocked 待 Y1 末评审 |
| 节律 | 里程碑 + 周检查点（复用现有只读命令, 零新代码） |
| T2-03 时机 | 立账+诊断先行（已完成）, 修复留执行轮; T2-02 观察窗口在 T2-03 修复后重起算 |
| 文档形态 | 台账为 SSOT + 本薄文档（~100 行, 只写编排关系） |

## 1. 三大里程碑

### M1 清障（2026-08-15 → 08-22）

完成判据（全部机器可查）:
- `BET-Y1Q1-T1-05A` status=done（human_gate 确认 + `swarm-discipline-cli.py status --json` 快照贴 retro）
- `BET-Y1Q3-T2-03` 根因诊断已入账（diagnosis 字段）✅ 2026-08-15 已完成
- `BET-Y1Q3-T9-01` 的 verify diff 校验部分已 merge（D2 前置条件之一）
- `BET-Y1Q3-T1-03` surface numstat 净值口径上线

### M2 冲刺（2026-08-22 → 09-30）

硬次序: **T1-05 D2 启动条件 = T1-05A done AND T9-01 verify-diff 部分 merge**（两条件皆 CI/台账可查, 不靠自觉）

完成判据:
- T1-05 D2 完成（多 agent 独立 clone 迁移）+ D3 删三层旧纪律
- ~~T6-01 归并落地（gbrain+kairon→knowledge, 不可逆点, appetite 6 周需尽早启动）~~
  ✅ **2026-08-16 提前落地**（#1600 merged, 原 6 周 appetite 压缩 1 天; L3 停审
  awaiting human_gate; 去重 ~9.4K 行; 四坑入册 AGENT-BRIEF §8.5）
- Y1Q3 窗口待办清偿（口径以台账实时 status 为准）
- T2-03 done 后 T2-02 观察窗口重起算满 7 天
- 附: Y1Q4-T3-01/T5-01 已核实性收口 done (2026-08-17, #1622)

### M3 门评审（~2026-10-08）

- Y1Q3 年度门核验: `knowledge_loc < 500000` AND `mos_sole_path_weeks >= 8`（自 2026-08-14 起算）
- T1-04 重基线提案交人类拍板（human_gate: true）
- Y1 末 blocked 三兄弟（T1-18/19/20）统一处置

## 2. 周检查点（每周一跑, 贴周记）

```bash
uv run --with pyyaml python bin/plan/bet-ledger.py status          # 台账全景
python3 bin/gac/swarm-discipline-cli.py status --json               # 协调层快照
python3 bin/ssot/signal-poller.py --health --json                   # 感知面健康
```

三命令全只读。周 checkpoint 同时喂 `mos_sole_path_weeks` 累计证据（Y1Q3 门判据）。

## 3. 红线（继承 + 新增）

1. 时间窗口类 done_when 未满窗不置 done（T3-01 教训, 最高优先）
2. 状态变更与 commit 同 worktree（模式 1 教训, PR #1518）
3. 收口前三问: write_surfaces 含台账吗 / 变更路径在 write_surfaces 吗 / 不在则单开治理轮
4. 诊断三步法: ①时间戳 ②反驳证据 ③结论（T9-04 四件套之一, 落地前靠自觉）
5. 写操作测试必须 temp repo（模式 4 教训）
6. err 日志读前看 mtime（模式 6 教训, rotate 落地前过渡规则）

## 4. 显式不做（本规划期）

- 不动 PR gate bet-id 强制（人类拍板项, 汇报单列）
- 不动 legacy registry 删除（8+ 活跃消费者, 等 T1-05 后自然消解）
- 不扩 mof-deepen 实施面（T6-03 只按已立账范围执行）
- agent 不自行修改年度门数值（T1-04 human_gate）
