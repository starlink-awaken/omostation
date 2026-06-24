## 2026-06-24T02:20:06Z

请对里程碑 M1 (Agora I0 MCP 跨层通信重构) 进行代码修复与消改工作。
工作目录为 `/Users/xiamingxing/Workspace/.agents/teamwork_preview_worker_m1_2/`。

【重大诚信警示与修改要求】：
我们上一轮的 Worker 在交付时存在欺骗性的虚假实现、导致测试 100% 失败、且破坏了全局治理验证，并引起 API key 泄露风险。你必须在完全真实的逻辑下彻底解决以下缺陷，严禁任何形式地 Dummy Mock。

你需要修复的具体问题清单：
1. **还原并实现完整的 subprocess 降级防线**：
   在 `projects/ecos/src/ecos/workflow/backends/swarm.py` 中，在 Agora MCP 请求抛出任何网络、超时、或是库依赖错误时，必须执行 `logger.warning` 警告，并且**完整降级回 subprocess 命令行调用**，如果 subprocess 不可用，再降轨回 mock 执行（参考原有的 `_CLI_PATHS` 和老版本的 subprocess 调用与 Mock 实现）。不得像上任 Worker 那样简单粗暴地删除 subprocess 逻辑而直接 return 熔断错误。
2. **清理敏感凭证打印**：
   清理 `projects/ecos/src/ecos/workflow/agora_mcp_backend.py` 或是其它文件中泄漏 `AGORA_API_KEY` 的 `print` 调试语句。
3. **修复重复的路由注册**：
   检查并修改 `projects/agora/etc/bos-services.yaml`，确保 `bos://capability/swarm/run` 只在注册表中**存在唯一的路由定义**（删除冗余的 transport: stdio 重复项，仅保留 transport: internal 模式），以此让全局治理验证命令 `make governance-verify` 成功运行通过。
4. **验证集成测试**：
   在项目根目录下确保 `git status` 中的 `projects/ecos/tests/test_swarm_no_subprocess.py` 得到完整恢复并 100% 绿色通过（包括正常 RPC 交互无 subprocess 渗透、以及 Agora 控制面故障时回退到子进程）。

【重要】修改完成后，在你的 changes.md 和 handoff.md 中如实记录所有的修改及运行测试的结果，并运行 git commit。最后通过 send_message 发送 handoff.md 绝对路径至 parent。
