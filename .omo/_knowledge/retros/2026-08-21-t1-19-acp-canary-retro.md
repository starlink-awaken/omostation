---
type: bet-retro
lifecycle: history
owner: laowang-agent
last_updated: 2026-08-21
bet: BET-Y1Q2-T1-19
date: 2026-08-21
operator: laowang (claude-code)
runs:
  - 20260821T020119Z-bet-execution-f21e7fdc (closed ok)
title: BET-Y1Q2-T1-19 Retro — ACP stdio cutover 的三轮真 canary
---

# BET-Y1Q2-T1-19 Retro — ACP stdio cutover 的三轮真 canary

> 五问复盘（bet-retro 惯例），附本轮制度产出。

## 1. 计划 vs 实际

计划：合代码 → 标 done。实际走了三轮 canary、两轮时序竞态急救、一次自伤（误 checkout）。
核心原因：**mock 测试全绿给了虚假信心**——协议实现从头到尾没和真实 codex-acp 报文对上过，
直到真进程握手才层层暴露。

## 2. 真实发现（按轮次）

| 轮 | 发现 | 缺陷数 |
|----|------|--------|
| R1（协议握手） | initialize 缺 params / session-new 类型错 / prompt 格式错 / R1 glob 不支持 | 4 |
| R2（权限路径） | 报文结构完全对不上（toolCall.title+options vs 假设的 operation/scope）· 响应须 tagged-enum result · shell 链分类 · reject 优先级 · scope 剥 cwd 前缀 | 5 |
| R2 附带 | `~/.codex` 全局 workspace-write 沙箱下 codex 从不发 permission——canary 必须 `-c sandbox_mode=read-only -c approval_policy=untrusted` 会话级覆盖（不碰用户全局配置，spec 断路器红线守住了） | 1 |
| A-3（cutover） | cli_prompt 隐式默认 6 处（3 文件）；测试 fixture 需双 transport 对齐 | — |

**9 个协议缺陷，mock 一个都没拦住。** 每一轮"以为对了"都在下一轮被打脸，直到抓到原始报文
（JSON-RPC error 的 data 字段精确到 serde enum 名）才真正读懂协议。

## 3. 成本

- 真模型调用 ~6 次 × 15-70s（pong / 探针 / 3 轮写任务）
- 时序竞态（ecos#33 vs 消费方修复滞留）：3 个 PR 连环红，cherry-pick + 子模块 bump 解锁
- 自伤 1 次：`git checkout -- .` 清掉自己在独立 clone 的未提交补丁，重打（教训：**在脏
  工作树里永远别裸奔 checkout**，哪怕"顺手清理"）

## 4. 制度产出（本 retro 的行动项）

1. ✅ git-discipline skill §4.1：删子模块远程分支前 merge-base 查悬空（本轮 40 分钟事故代价）
2. ✅ git-discipline skill §4.2：跨仓强校验竞态——消费方先合、生产方后合
3. 建议 ADR：**canary 前置**——涉及外部协议的 transport 代码，mock 全绿不算证据，真实
   进程握手是 done_when 的必要条件（本 BET 的 NOT_PROVEN 判定完全正确，是治理体系赢了）

## 5. 遗留

- PR #67（5 协议修复 + A-3 cutover）合入后，T1-19 才具备置 done 的完整证据链
  （R1 canary PASS + 独立 verifier ACCEPT_WITH_NOTES + cutover 减法 + live receipt）
- verifier NOTES 里的 fixture 双 transport 建议已随 A-3 落地
- `test_actual_worker_process_acknowledges` 在 no-project uv 环境的预存失败（子进程无
  PYTHONPATH）与本 BET 无关，建议另立小债
