# Codex Exec Unattended Worker 设计

> 日期：2026-08-13  
> 状态：accepted  
> BET：BET-Y1Q2-T1-17

## 1. 问题

Orca 内置 `codex` worker 启动交互式 TUI。Orca 的 process `ready` 或 TUI idle
只能证明进程可交互，不能证明审批已经自动处理，也不能证明任务已经完成。因此 git、
MCP 或 shell 工具调用仍会等待人工点击，无法承担受监督的无人值守 Dispatch。

当前 Codex CLI 0.147.0 已提供非交互入口：

```text
codex exec --approve-for-me --ephemeral --ignore-user-config --json -C <workspace> <prompt>
```

`--approve-for-me` 将审批交给 Codex 的自动审查，并保持 `workspace-write` 沙箱；它不是
`--dangerously-bypass-approvals-and-sandbox`。后者不进入本设计。

## 2. 选择

在根仓新增一个 bounded adapter，复用 Pi/Oh My Pi 已有的“registry admission + 固定
argv + 父进程 timeout/reap + privacy-safe receipt”模式。OMO 继续拥有任务、WorkPacket、
write surfaces 和完成判定；Orca 只拥有 Run/Task/Dispatch/terminal transport；Codex
只产生文件改动和候选输出。

不修改 Orca 本体，不新建调度器，不把 Orca `ready`、Codex exit 0 或模型自报 done 当作
`WorkflowVerified`。

## 3. 运行合同

生产 argv 固定为：

```text
<codex-bin> exec --approve-for-me --ephemeral --ignore-user-config --json
  --color never -C <verified-independent-clone> <prompt>
```

约束：

1. workspace 必须是非 symlink 的真实目录，`.git/agent-clone-identity.json` 必须存在且
   `clone_root` 与 workspace 精确一致；linked worktree 和共享 Workspace 拒绝。
2. `codex --version` 必须成功并符合 `codex-cli <semver>`；执行文件必须解析到真实普通文件。
3. adapter 不提供 arbitrary argv、profile、model、add-dir、resume、dangerous bypass 或 shell
   拼接入口；`subprocess` 始终 `shell=False`。
4. 从子进程环境删除 token/key/proxy/SSH/AWS/GitHub 等敏感变量。Codex 仅可使用本机
   `CODEX_HOME` 认证文件；认证不可用时诚实失败。
5. 子进程独立 process group。超时后 TERM，短等待后 KILL，并 `wait()` 回收；无法确认回收
   时结果为 `cleanup_unconfirmed`。
6. adapter 捕获 JSONL，不原样持久化工具输出；stdout 只转发最终 assistant message。回执只含
   schema、worker、Codex 版本、时间、状态、exit code、最终输出 SHA-256、相对 changed paths、
   sandbox/ephemeral/config 边界和错误码。
7. 可选 `--expect-exact` 用于真实 admission smoke；不匹配即失败。
8. `--receipt` 只能创建在系统临时目录中、父目录必须已存在、目标不得已存在。

## 4. OMO 与 Orca 接线

worker registry 中 `codex` 从 declared 晋升为 admitted 的前提是：

- adapter 定向测试、Ruff、diff check 通过；
- 一次真实 `codex exec` smoke 零手工审批并得到约定 marker；
- 一次 Orca Run/Task/Dispatch 由该 adapter 执行，产生可查询 `worker_done`；
- 独立 reviewer 直接测量 argv、回收、越界拒绝和回执，而不是相信 worker 自报。

正式 transport：

```text
/usr/bin/python3 "{workspace_root}/bin/gac/codex-worker-adapter.py" run
  --execute --timeout-seconds 900 --workspace-root "{workspace_root}" --prompt "{prompt}"
```

worker 维持 L1、`task_declared_only`、显式 capability、敏感域禁止。任务写面仍由 OMO
envelope 和独立 verifier 决定；adapter 不取得战略、promotion、merge 或主线写权限。

## 5. 失败语义

| 条件 | 稳定错误 | 副作用判定 |
|---|---|---|
| 共享/linked/symlink workspace | `workspace_not_independent_clone` | Codex 不启动 |
| Codex 缺失/版本非法 | `codex_unavailable` / `codex_identity_invalid` | Codex 不启动 |
| 超时 | `worker_timeout` | TERM→KILL→wait |
| 非零退出 | `worker_nonzero` | 不宣称成功 |
| JSONL 非法/无最终消息 | `worker_output_invalid` | 不宣称成功 |
| exact marker 不匹配 | `marker_mismatch` | 不宣称成功 |
| 进程或 receipt 清理不可确认 | `cleanup_unconfirmed` / `receipt_write_failed` | 不宣称成功 |

## 6. 验收

- 单元测试使用 fake process 覆盖 argv、环境、workspace、timeout/reap、JSONL、marker、receipt。
- 真实 read-only smoke 返回 `CODEX_UNATTENDED_SMOKE_OK:BET-Y1Q2-T1-17`，期间零人工确认。
- Orca 可查询同一 Run/Task/Dispatch 的 succeeded `worker_done`；`ready` 不作为完成证据。
- 用户/共享 Workspace、会话配置、MCP 配置和非声明写面不被修改。
- 只有独立 reviewer 通过后才把 registry 改为 admitted。

