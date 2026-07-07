---
name: ci-silent-fail-debug-chain
description: interface-check step 用 cmd || FAILED=1 累积模式, silent return 1 无 ❌ 输出难定位 — set -x + cat 重定向输出 + 解析 violation 字段的系统定位法
triggers:
  - "One or more governance checks failed"
  - "interface-check failure"
  - "silent fail CI"
  - "FAILED=1 exit 1"
  - "check pass but CI fail"
  - "本地全 pass CI fail"
---

# CI Silent Fail Debug Chain

## The Insight

omostation 的 interface-check step（`.github/workflows/governance-check.yml`）用 **累积 fail 模式**：

```bash
FAILED=0
python3 scripts/check-X.py || FAILED=1   # 20+ 个 check
uv run python -m omo.cli lint Y || FAILED=1
if [ $FAILED -ne 0 ]; then exit 1; fi
```

这个模式的**致命问题**：某个 check `return 1` 时只设 `FAILED=1`，**不显示是哪个 check fail**。如果该 check 的 stderr/stdout 被重定向（`> /tmp/file`）或 check 自己无 ❌ 输出（silent return 1），CI log 看起来**所有 check 都 pass**，但 step `exit 1`。

这不是 check bug，是**累积模式的可见性缺陷**。

## Why This Matters

本次会话花了 **6 轮 dig** 才定位到 `omo governance surfaces --json > /tmp/file` 这条命令 return 非 0（它的 violation 输出到 /tmp，被重定向隐藏）。本地跑所有 check 全 pass（环境差异），CI 环境特有 fail。grep `❌`/`Error`/`Traceback` 全无果（silent）。

## Recognition Pattern

定位此问题的信号（满足全部 = 本 skill 适用）：
1. CI step 报 `❌ One or more governance checks failed.` + `exit 1`
2. CI log 里**所有可见 check 输出 ✅ PASS**
3. 本地跑相同 check-*.py **全 pass**（环境差异）
4. grep `❌`/`Error`/`FAIL` 在 CI log **无匹配**（silent）

## The Approach（3 步 debug 链法）

### Step 1: `set -x` 定位哪个命令 return 非 0

在 step 开头加：
```yaml
run: |
  set -x  # 打印每个命令 + 让 FAILED=1 赋值可见
  FAILED=0
  ...
```
CI 跑后 grep `+ FAILED=1`（set -x 打印的赋值），其**前一条 `+ cmd` 就是 silent fail 的命令**。

### Step 2: `cat` fallback 暴露重定向输出

如果 fail 的命令输出被重定向（`> /tmp/file`），加 cat fallback：
```bash
cmd > /tmp/out.json || { echo "=== cmd FAIL, output: ==="; cat /tmp/out.json; FAILED=1; }
```
这样 fail 时 CI log 显示 /tmp 内容。

### Step 3: 解析 violation 字段

重定向输出通常是 JSON（如 `omo governance surfaces --json`）。cat 后找 violation 字段：
- `missing_registered_roots` — 未注册的 roots
- `unregistered_top_levels` — 未注册的 top levels
- `drift` / `violations` — 不一致

这些字段直接告诉你**具体缺什么**。

## Example

本次会话定位 interface-check silent fail：
1. `set -x` → 发现 `+ uv run ... omo.cli governance surfaces --json` 后 `+ FAILED=1`
2. `cat /tmp/omo-governance-surfaces.json` → 暴露 JSON 含 `missing_registered_roots`
3. 字段内容 → 10 个 .omo/ roots（_delivery/_generated/_log/capabilities/evidence/pitches/tests/workers + bets.json/tasks.json）未在 `omo-governance-surfaces.yaml` 注册

修复：补 yaml 的 assets 注册（或确认并发 agent 已补）。

## Anti-Pattern

❌ **不要降级 check 解 CI**（`return 1` → `return 0`）— 制造执行鸿沟（memory `decl-exec-gap-meta-pattern`），是 grader gaming
❌ **不要盲目补数据**（如骨架文档）— 需先确认是 silent fail 还是真 violation
✅ **定位 → 验证 violation 真实性 → 正式修复**（补注册或修 check 逻辑）

## 关联

- [[decl-exec-gap-meta-pattern]] — silent fail 是声明/执行鸿沟的 CI 表现
- [[concurrent-agent-contention]] — main 移动靶可能引入新 silent fail
