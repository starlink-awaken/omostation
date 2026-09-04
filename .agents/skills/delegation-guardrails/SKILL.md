---
type: ssot
name: delegation-guardrails
description: "委托机制加固的两条硬规则：①「只叙述不落盘」是模型路由故障信号（不是 worker 偷懒）——只叙述不改文件 = 错误/不可达模型端点返回空内容，禁止 blind retry，必须跑 5 步诊断序列；② 终验波次子代理结论矛盾时，编排者用直接测量（read/grep/wc/stat）仲裁，不信报告质量。当 spawned worker 只叙述不改文件、委托返回空内容、subagent 没落盘、终验子代理结论矛盾、或需要跑 delegation preflight 时使用。Triggers on: 只叙述不落盘, narrate-without-edit, 委托故障, delegation failure, subagent 没落盘, delegation preflight, 终验矛盾, final verification wave, direct measurement, 空内容, empty content, model routing fault, model-scheduler, 调度器。"

last-reviewed: 2026-08-26---

# Delegation Guardrails — 委托机制加固

**来源**: `start-work` SKILL.md L196-197（`~/.cache/opencode/packages/oh-my-openagent@latest/node_modules/oh-my-openagent/dist/skills/start-work/SKILL.md`，运行时缓存，未版本控制——本技能是其工作区版本化副本）
**完整 runbook**: `.omo/_knowledge/patterns/delegation-infra-diagnosis-pattern.md`（规范路径；随 PR #1128 落主仓，合并前仅在 worktree）
**工具交付**: PR #1128（delegation-infra-reliability）→ `bin/delegation-alias-check.py` + `bin/delegation-preflight.py`

---

## 0. 两条规则概览

| 规则 | 触发信号 | 强制动作 |
|------|----------|----------|
| **规则一**：只叙述不落盘 = 模型路由故障信号 | spawned worker 返回计划式叙述但 **ZERO 文件改动** | 禁止 blind retry 同一委托路径；跑 §1 的 5 步诊断序列 |
| **规则二**：终验矛盾用直接测量仲裁 | 并行终验子代理对同一产物报告矛盾结论（一个 PASS、一个 NOT CLOSED） | 直接测量产物（read/grep/wc/stat）定案；禁止按报告质量选边 |

**下面的规则不是建议。** 每一条都来自 `start-work` 的硬规则（L196-197），是对真实委托事故的固化。

---

## 1. 规则一：只叙述不落盘 = 模型路由故障信号

### 信号定义

一个 spawned worker 返回了计划式叙述（plan-style narration），但对目标文件**零改动**。
这不是 worker 偷懒，**这是模型路由故障信号**：被派发的模型端点大概率不可达或返回空内容
（empty-content response）——worker 拿到的是空 prompt 响应，只能叙述不能执行。

### 禁止动作

**不要 blind retry 同一条委托路径。** 同一个坏端点重试多少次都是空内容，
只会浪费时间并掩盖根因。正确动作是转诊断。

### 强制动作：5 步诊断序列

```
① 读配置    read opencode.json 的 provider/agent 模型绑定
            （provider.omlxc + agent.*.model）
② 端点冒烟  curl 目标模型端点：omitted-model vs with-model 对照
③ 路由核对  grep litellm-config.yaml 的 model_list（网关路由）
④ 跑工具    bin/delegation-alias-check.py + bin/delegation-preflight.py
⑤ 查调度器  git -C ~/.config/opencode log
            —— scripts/model-scheduler.sh 是权威写入者
```

### 关键环境事实（冒烟与核对用）

| 端点 | 端口 | 行为 |
|------|------|------|
| omlx-server | 8000 | **接受** model 字段 |
| mlx_lm | 8092 | **拒绝** model 字段 |
| gateway | 100.96.126.35:4000 | litellm 网关，`model_list` 定义路由 |

> **注意**：`~/.config/opencode` 是独立 git 仓库。调度器（`scripts/model-scheduler.sh`）
> 是模型绑定的**权威写入者**，用 `git -C ~/.config/opencode log` 看它最近改了什么
> ——不要凭印象判断当前生效的是哪个模型。

### 工具状态

`bin/delegation-alias-check.py` 和 `bin/delegation-preflight.py` 由 PR #1128
（delegation-infra-reliability）交付主仓。**合并前**这两个文件只在 worktree 里：
引用时说明「随 PR #1128 落主仓」，不要假设主仓 bin/ 已有。

### 完整 runbook

诊断细节、4 层故障分类、端口语义见
`.omo/_knowledge/patterns/delegation-infra-diagnosis-pattern.md`（PR #1128 合入后可用）。

---

## 2. 规则二：终验矛盾用直接测量仲裁

### 信号定义

并行 final-verification wave 的多个子代理对**同一产物**报告**矛盾结论**
（一个 PASS，另一个 NOT CLOSED）。例如一个说文件已落盘，另一个说文件不存在。

### 禁止动作

**永远不要按报告质量选边。** 子代理报告只是**某一时刻的视图**
（a view at a moment in time）——并发写入会让它立刻过期；
报告写得漂亮与否和产物真实状态无关。

### 强制动作：直接测量产物

```
read <artifact>     # 读文件本体
grep <pattern> <artifact>
wc -l <artifact>    # 行数/字节
stat <artifact>     # mtime/size，判断写入时间与并发窗口
```

以测量结果定案：文件在不在、内容对不对、时间戳合不合理。
证据优先于任何子代理的自述。

---

## 3. 何时触发

- spawned worker 返回计划式叙述但文件零改动 → 规则一
- 委托结果疑似空内容 / endpoint 不可达 → 规则一
- `bin/delegation-preflight.py` 报错、或需要跑诊断工具 → 规则一
- 终验波次子代理结论矛盾（PASS vs NOT CLOSED）→ 规则二
- 任何「我该信哪个子代理」的时刻 → 规则二，直接测量

---

## 4. 一句话总则

**叙述不改文件 = 先查路由，不要重试；结论打架 = 先量产物，不要选边。**
