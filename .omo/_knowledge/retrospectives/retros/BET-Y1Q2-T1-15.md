---
lifecycle: history
owner: governance-team
last_updated: 2026-08-13
title: BET-Y1Q2-T1-15 复盘
type: retro
---

# BET-Y1Q2-T1-15 复盘

## 交付与真实回执

本轮把外部 Specification 从 WorkPacket 的可选说明升级为 v2 不可缺失的跨语言合同，并保持 v1
canonical hash 不变。ECOS 以独立 `SpecificationBinding` 值对象承载 `spec_ref/spec_version/
content_digest/decision_ref`，MOF 编译器将同一条件要求生成到 JSON Schema、Pydantic、Zod 与 SQLite。

OMO 在收集候选和接受独立验证前，重新读取仓库规范字节、核对声明的 read surface，并要求权威 BET
条目显式列出同一 `spec_ref/version/digest`。BMAD bridge 改为全批次解析和 registry identity 预检；缺
test plan/evidence、重复标题、unsupported checkbox、内容漂移或任一任务映射冲突均保持零写入。

## Q1 实际耗时 vs appetite？

约半天，低于 2 days appetite。主要时间用在两轮独立红队和对生成器的反证，而不是业务代码量。

## Q2 done_when 是否全部通过？

全部通过。ECOS 定向 101 tests、OMO 合同定向 86 tests、独立仓平台等价全量 1368 tests 通过；
生成产物 freshness、双方 Ruff、format 和 `git diff --check` 通过。独立 reviewer 首轮提出三个 HIGH，
最终逐项复现关闭并给出 WATCH/APPROVE：

1. v2 缺 binding 在生成 Pydantic/JSON Schema 中直接拒绝，Zod 具备等价 `superRefine`；
2. 任意 done BET 或调用方注入的伪 workspace 不再构成采纳证据，决策必须精确绑定规范摘要；
3. 第二个 registry source_ref 冲突时，第一项不会残留。

根台账 lint 仍报告 25 个既有 T6 草案问题；T1-15 本身未新增 lint 错误。本轮没有借机扩修该基线。

## Q3 与计划不符的事实

1. 最初只在 `work_packet_compiler.canonicalize` 做 v2 检查，定向测试虽绿，但生成的 Pydantic/JSON/Zod
   仍把 binding 当 optional；这是典型的“一个消费者真拦、其他消费者假接线”。
2. `validationRules` 不是生成器的执行合同，不能靠塞 Python 表达式冒充跨语言规则；最终新增了受限、
   声明式 `conditionalRequirements`，只表达 discriminator 等值条件下的必填字段。
3. Bridge 只预检 task YAML 不够；broker 的 runtime ingress registry 同样拥有 identity，必须在批次写入前
   一次性检查两面。

## Q4 净增减与必要性

新增一个无状态 M2 值对象、一个通用条件要求 IR，以及生成器中四种产物的最小 emitter 支持；未新增
数据库、任务队列、scheduler、服务、UI 或第二套 Specification 真相。OMO 只加强现有 coordinator 和
bridge 边界。新增测试均为真实模型加载、生成产物导入、临时 ledger/registry 与 Mesh 副作用断言。

## Q5 后续提示

后续 WorkPacket v2 producer 必须先由已完成 BET 的 `accepted_specifications` 明确采纳规范版本和摘要；
不能把 `status: done`、文件存在或 adapter 自报当作 binding。若要支持 ADR 作为 decision_ref，应先定义
同样可机器验证的 ADR→spec/digest 绑定字段，再扩展 resolver，禁止恢复前缀式信任。
