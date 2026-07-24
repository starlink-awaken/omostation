# STRAT-P81 Batch 2 大工单 — 常态化运营 + 物理恢复预备（用户已批准派发）

> Status: **CLOSED** · 2026-07-24 · Appetite: **2-3 周** · Closeout: `.omo/_knowledge/audits/2026-07-24-batch2-closeout.md`
> 上位: STRAT-P81 + ADR-0228 + **ADR-0232**（G-DEL.2b 官方达标 + 本批批准）
> 交接单: `.omo/plans/strat-p81-agent-execution-brief.md`（启动序列/红线/升级协议全部适用）
> 前批: Batch 1（CLOSED, 11 done + C2 partial, closeout: `audits/2026-07-24-batch1-closeout.md`）
> **用户授权范围**: 工单内全部任务一次性授权, 含既有 PR 流程落 main。例外见 §F。**11 任务, A→E 波次。**

---

## A 波 · 落档与回填（先做, ~0.5 天）

### A1 · ADR-0232 生效动作
- `phase-scope.yaml` G-DEL.2b 回填 `meets_gate=true`（引用 ADR-0232 + measure audit）
- 关闭 `needs-human-batch1-g-del-2b-application` 与 `needs-human-batch1-batch2-proposal` 两卡（引用 ADR-0232）
- run `20260724T064622Z-governance-state-mutation-5246576d` 补 verify+closeout; 本批新文件按 PR 流程落 main; **PR #483 若仍未合并, 先合并**
- **验收**: phase-scope 回填有 evidence; 两卡关闭; git 收口

### A2 · STRAT-P81 §1 进度表刷新
- S2 标注 "G-DEL.2b ✅ ADR-0232"; C2 partial 状态如实保留
- **验收**: brief 解锁表与实际一致

## B 波 · 多角色常态化运营（主菜之一, ~1 周）

### B1 · C2 补账: 调度 harness 三天 cron 史
- 让 Batch 1 已接的 sim harness 自然跑满**连续 3 个真实天**, 产出趋势报告（禁止把 3 次手动跑冒充 3 天）
- **验收**: 3 天 wall-clock 报告入 audits, C2 翻 done

### B2 · 角色协作转常态: 真实 backlog 周清
- 3 角色管线接管日常 backlog（debt 卡/doc 修复/测试补齐）, 本批内完成 **≥30 个**真实任务
- 完成率/成本周报进 BRIEF（复用 B5 管线）
- **验收**: ≥30 任务 + 周报两期; 完成率 <90% 触发归因卡

### B3 · 角色扩容评估（不实装）
- 评估第 4/5 角色候选（如 research / delivery）: 价值/边界/风险一页纸, 交 Inbox 供下批拍板
- **验收**: 评估页入 audits + 提案卡

## C 波 · 物理恢复预备包（机器仍挂起, 全部"预备不宣称", ~3 天)

### C1 · 一键恢复脚本
- `bin/delivery/physical-recovery.sh`: 机器恢复后一条命令完成 探测→注册回填→G-DEL.3 两机测量→G-DEL.1 四机预检, 全程 evidence 自动落 audits
- **验收**: dry-run 通过; 文档一页; **不产生任何 meets_physical_gate=true**

### C2 · 恢复后验收清单卡
- 写好"机器恢复日"的验收清单（探测→G-DEL.3→G-DEL.1→S1 物理 KPI 解锁）挂 Inbox, 与周提醒并联
- **验收**: 清单卡在 Inbox 可见

## D 波 · 纵贯线深化（~1 周, 与 B/C 并行）

### D1 · KOS 质量深化（量已超, 转质量）
- 5193 篇基础上: 抽检扩到 ≥50 篇, 修复格式/断链/重复; 检索命中率基线测量（为 2027Q2 图谱 PoC 打底）
- **验收**: 质量报告 + 命中率基线入 audits

### D2 · X3 交付冲刺（7 月软门禁 4/8）
- 把 B2 角色管线完成的合格工作产出按既有规则登记交付卡（真实交付, 禁止凑数——不合规产出宁可不记）
- **验收**: 月底交付计数如实更新; 若仍 <8, 软门禁预警保留并写月度归因

### D3 · 治理周巡检 x2
- 本批覆盖两个周期: compliance + P74 + health 核对 + 物理挂起重申确认
- **验收**: 两期巡检报告

## E 波 · 收尾复盘（~1 天）

### E1 · Batch 2 closeout + Batch 3 提案
- 11 项对账入 audits; brief §1 刷新; Batch 3 提案卡进 Inbox（若期间机器已恢复, 提案以物理 KPI 冲刺为主轴; S3 涌现类如提案, 必须附 kill-switch 评审申请）
- **验收**: 审计 + 提案卡; 本工单改 CLOSED

---

## §F 仍需人类逐项拍板（不在本次授权内）

1. 物理机"恢复"宣称与 G-DEL.1/3 官方达标（脚本只预备, 达标须真机 evidence + 人类确认）
2. S3/涌现类任何实装（B3 只交评估）
3. 第 4/5 角色实装（B3 只交提案）
4. KOS 新数据源接入

## 熔断条件

- health < 95 · 单项超支 30% · B2 完成率 < 80% · 任何 sim/预备产物出现物理达标字段（立即停批, 最高级违规）

---

*生成: 2026-07-24 · run: 20260724T064622Z-governance-state-mutation-5246576d · Appetite 2-3 周 · 11 任务*
