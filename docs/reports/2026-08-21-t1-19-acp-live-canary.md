# BET-Y1Q2-T1-19 ACP v1 stdio 真实 canary 报告

> 日期: 2026-08-21 · Operator: laowang (claude-code) · Run: 20260821T020119Z-bet-execution-f21e7fdc
> 目的: 解除 T1-19 `NOT_PROVEN` block — 产出真实 ACP 生命周期 live receipt 证据链

## 1. 结论

**Canary verdict: PASS** — 真实 codex-acp@0.16.0 进程全生命周期打通，并实证 4 个协议缺陷（已修复 + 回归测试保护）。

## 2. 环境

| 项 | 值 |
|----|-----|
| 包 | `@zed-industries/codex-acp@0.16.0`（spec 钉版，独立目录安装非全局） |
| bin sha256 | `1985e3e909d47e3e863f3c670f29265a6b97874b91032f70c82ed73f7294ccf0` |
| transport | ACP v1 over stdio (JSON-RPC, LSP 风格) |
| 认证 | `~/.codex/auth.json`（chatgpt 登录态，非 API key） |
| 模型 | gpt-5.6-luna（session/new configOptions 默认） |

## 3. 生命周期证据（live-receipt.json 摘要）

| 步骤 | 结果 | 证据 |
|------|------|------|
| initialize | PASS 0.07s | protocolVersion=1, agentInfo codex-acp 0.16.0 |
| session/new | PASS | sessionId 真实分配 |
| session/prompt (R0) | PASS 22.4s | 真实模型调用, stopReason=end_turn, agent_message_chunk 流式 |
| permission 矩阵 | PASS 5/5 | R0-allow / R1-glob-allow / R1-forbidden-deny / R2+-human / exec-human |
| cancel | PASS | state=cancelled |
| reap | PASS | TERM 回收, alive=false, returncode=-15 |

## 4. 实证缺陷与修复（PR omo#64）

| # | 缺陷 | 修复 |
|---|------|------|
| 1 | initialize 缺 `protocolVersion`/`clientCapabilities` params | 补齐必填 params |
| 2 | session/new 缺 `cwd`/`mcpServers`（且 mcpServers 必须序列非 map） | 补齐 + 类型修正 |
| 3 | session/prompt 缺 `sessionId`，prompt 须 content-block 数组；输出在 `sessionUpdate` 通知而非 result | 全部对齐 ACP v1 结构 |
| 4 | R1 权限 scope 不支持 `/**` glob | `_scope_matches()` 前缀匹配 + 3 条回归测试 |
| + | stderr PIPE 从不读 → 缓冲写满死锁风险 | DEVNULL |

**方法论价值**: 46 个 mock 测试全绿也拦不住这 4 个缺陷——只有真实进程握手才暴露协议层错误。这正是 spec §6 "fixture 只验证协议解析；真实 Codex ACP shadow/canary 才算数" 的意义。

## 5. 测试

- 49 passed（46 原有 + 3 新增 glob 回归保护）
- `ruff check --select I` + `ruff format --check` 干净

## 6. 与 spec 验收标准的对照

| spec §7 条目 | 状态 |
|--------------|------|
| 1. 完整生命周期/错误/EOF/cancel/timeout/reap 有 failure-injection 测试 | 部分（mock 层已有, live 层 cancel/reap 已证） |
| 2. R0/R1 权限策略绑定 + 脱敏 receipt | ✅（矩阵 5/5 + digest 化 scope） |
| 3. 真实 Codex ACP 非 marker canary 产生模型输出证据 | ✅（本轮 22.4s 真模型调用） |
| 4. 越权 permission 无 WorkflowVerified | ✅（R1-forbidden deny 实证） |
| 5. cutover 后仅 acp_stdio | 待 cutover 提交 |
| 6. T1-18 行为回归不下降 | 待独立 verifier |
| 7. surface 报告列新增/删除 + 指名减法 | 待 cutover 提交 |

**剩余缺口**: 独立 clone 中的真实 R1 变更（git delta + CompletionManifest）、独立 verifier accept、cutover 减法提交。canary 本轮已打通最大不确定项（协议正确性）。

## 7. 复现

```bash
# 钉版安装（非全局）
mkdir -p /tmp/acp-canary-pinned && cd $_ && npm init -y && npm i @zed-industries/codex-acp@0.16.0
# 驱动脚本（用 omo 的 AcpStdioSession）
python3 /tmp/acp-canary-pinned/run_canary.py
# 产物: live-receipt.json
```
