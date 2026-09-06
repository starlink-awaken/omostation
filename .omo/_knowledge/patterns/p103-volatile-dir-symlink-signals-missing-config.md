---
type: ssot
owner: governance-team
last-reviewed: 2026-09-06
---

# P103 — `/var/run` 符号链接是"缺配置项"的信号，不是修复

**Pattern observed**: 2026-09-06，omlxc `doctor` 报 5 个看似独立的探测失败
（顶层 tailscale 身份检查 + mac-mini/y7000p 共 4 个远程后端），追下去是同一个根因。

## Problem

第三方守护进程（这次是 Homebrew 装的 `tailscaled`）不监听某个 CLI 工具编译内置的
默认路径时，常见的临时解法是在那个默认路径手动建一个符号链接指向真实位置。

`/var/run` 在 macOS 上是易失目录——**不保证在重启后还留着手动放进去的东西**。
这类符号链接因此有个特征：**第一次修复时看起来彻底解决了问题，过一段时间
（这次是机器重启）又会以完全相同的症状复发**，而且复发时排查者往往已经忘了
上次的手动步骤，得重新诊断一遍。

## Symptom

- `tailscale status --json`（不带 `--socket`）报
  `dial unix /var/run/tailscaled.socket: connect: no such file or directory`
- 但 `tailscale --socket=<真实路径> status --json` 完全正常，daemon 本身在线
- 依赖这次身份快照做鉴权的**所有**下游检查一起失败，报的都是同一句笼统的错误
  （这次是 "read-only probe failed"），看不出它们共享一个根因

## Root Cause

工具本身其实支持配置真实路径（`tailscale --socket=<path>`是全局 flag），
但**调用方代码没有把这个能力暴露成配置项**——于是只能靠操作系统层面的符号链接
去"骗"工具走到默认路径上。符号链接是运行时状态，配置项是声明式状态；
把运行时状态当配置在用，就会在运行时状态被清空（reboot、TCC 重置、
外置盘 unmount 等）时无预警地复发。

## Fix Pattern

1. **先确认真正的能力入口**：绝大多数守护进程/CLI 都有等价的显式覆盖参数
   (`--socket`、`--config`、环境变量等)。先查工具自己的 `--help`，不要
   默认"只能建符号链接绕"。
2. **把它做成配置项，不是运行时 hack**：schema 加一个可选字段
   （本例：`TailscaleConfig.socket_path`），默认值保持现状行为不变
   （未配置时 argv 和之前完全一样，纯增量），配置时才追加显式参数。
3. **验证参数顺序/语法，不要凭经验写**：global flag 和 subcommand flag
   的位置要求不同（`tailscale --socket=X status` 对，`tailscale status
   --socket=X` 错——会被 CLI 拒绝）。写代码前先拿真实二进制测一次。
4. **端到端在真实环境验证，不只是单测**：这类 bug 的本质是"配置和运行时
   环境的落差"，跑一遍真实机器上的完整闭环（改配置 → 重装 → 重启 →
   重新探测）才能确认真的解决，单元测试只能证明"参数拼对了"。

## Detection

代码里搜 `/var/run`、`/tmp`、`/private/var` 等易失路径的**手动**符号链接
依赖（不是系统/包管理器自己管理的，比如 Docker Desktop 自己维护的
`docker.sock` 符号链接不算）：

```bash
find /var/run -maxdepth 1 -type l -exec ls -la {} \;
grep -rn "/var/run\|/private/var/run" <代码库路径>
```

命中一条，先问："这个工具本身是不是有等价的显式覆盖参数？把符号链接换成配置项。"

## Related

- [[p100-unified-memory-wired-ceiling]] — 同一批工程投入里发现的物理约束陷阱
- [[p73-truth-driven-engineering-pattern]] — 声明/执行鸿沟母题（这次是"运行时状态
  被误当配置"的一个具体形态）
