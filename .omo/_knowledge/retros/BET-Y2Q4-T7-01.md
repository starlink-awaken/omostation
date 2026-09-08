---
bet: BET-Y2Q4-T7-01
title: 生命科学与大模型架构前沿文献自动精读与技术选型沙盘
phase: Phase 1
date: 2026-09-08
status: done
---

# BET-Y2Q4-T7-01 复盘

## Q1 实际耗时 vs appetite？
- appetite: 3 days
- 实际: 1 个 session 内完成（认领 → spec → pipeline 实现 → 测试 → 场景卡 → 收尾）。
  远低于 appetite，因为本 bet 交付的是**机制**（pipeline + 场景卡 shadow），
  不是 30 天真实运行采集。

## Q2 done_when 是否全部通过？
- ① docs/scene-cards/research-deep-synthesis.yaml 场景卡晋级 assisted：**未通过**
  （场景卡已建，处于 **shadow**；assisted 需 30-sample + calibration ≥0.6 +
  `workflow-mesh/*-scene-trials.jsonl` 真实运行证据，短期不可达）
- ② 每日自动过滤并精读 3 篇相关性最高前沿论文：**机制已交付**（pipeline 的
  filter_relevant + select_top_n(top_n=3)，离线自测通过；真实每日运行需网络+调度）
- ③ 自动生成系统架构技术选型备选矩阵：**通过**（technology_matrix 实现 + 测试）

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **verify 命令 CWD 缺陷**：台账 verify `uv run python -m domain.research.
   test_synthesis_pipeline` 在根 CWD 必然失败（`domain` 包在
   `projects/domain-cartridges/research/`，未注册为根可解析包）。已修：
   加 `cd projects/domain-cartridges/research &&` 前缀（台账配置修正）。
2. **done_when ① assisted 与 appetite 不匹配**：assisted 硬门是 30 个真实样本 +
   calibration ≥0.6 + journey-runner trial 日志——3 天 appetite 内无法真实采集。
   这是台账目标与 appetite 的固有张力（T7-SCENE 场景卡生命周期设计如此）。
   场景卡诚实停在 shadow，未伪造 trials（D1）。
3. **domain-cartridges 是未注册项目**：不在 layer-contract 项目列表，claim 系统
   无法认领 `projects/domain-cartridges/` 路径（D3 越权防护盲区）。closeout 时
   记录，建议后续把 domain-cartridges 注册为 layer-contract 项目。
4. **profile 与写面不匹配**：bet 写面横跨 docs+code+governance_state 三 lane，
   无单一 agent profile 覆盖。用户拍板用 engineering-agent（code 为主）。
5. **gac-local-gate soft warn**：`active_runs=1`（并行 agent T10-140 活跃）
   + governance-evolution release_ready=false——环境状态，与本次交付无关。

## Q4 净增减
| 项 | 新增 |
|---|---|
| 代码文件 | +9（domain-cartridges/research 包，~330 行） |
| 场景卡 | +1（research-deep-synthesis.yaml，shadow） |
| spec | +1（设计文档） |
| 测试 | +1（test_synthesis_pipeline，10 自测项全过） |
| GaC 规则 / ADR / 脚本 | 0（未新增） |

**净增表面积说明**：T7-SCENE 场景建设轨道，bet 是台账既定计划（用户确认执行），
依赖 T6-02（减法 9,097 LOC）已 done 作为对冲。pipeline 复用标准库（urllib/xml/json），
无第三方依赖。

## Q5 下一个认领本 track 的 agent 需要知道什么？
- **assisted 晋级路径**：pipeline 真实运行（network 源）+ journey-runner 落
  `workflow-mesh/shadow-scene-trials.jsonl`（scene_id=research-deep-synthesis）+
  30-sample + calibration ≥0.6，然后 `scene-card-lifecycle.py transition --tier assisted`。
- **verify 命令**已修（需 CWD 到 research 目录），后续 bet 勿回退。
- **domain-cartridges 未注册**：改它需同时考虑 layer-contract 注册，否则 claim
  盲区（closeout 可能被 D3 拦）。
- pipeline 入口：`cd projects/domain-cartridges/research && uv run python -m
  domain.research.pipeline --topics "..."`。
