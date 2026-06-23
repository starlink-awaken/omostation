## 2026-06-23T02:26:37Z

【任务：项目全局代码探测与重构方案调研】
你是一个 Read-only exploration agent（teamwork_preview_explorer）。
你的身份是：survey_explorer_1。
你的工作目录是：/Users/xiamingxing/Workspace/.agents/teamwork_preview_explorer_survey_1/。

请根据原始需求（/Users/xiamingxing/Workspace/.agents/ORIGINAL_REQUEST.md），调研并分析以下三项重构任务在当前代码库中的具体位置、实现和 API 依赖，并输出一份完整的调研报告。

具体调研内容：
1. 【R1: ECOS 跨层 subprocess 调用】
- 定位 ECOS 工作流中对 AetherForge Swarm（命令行、subprocess 直调等）调用的地方。
- 分析当前调用的方式、传参、被调用的脚本路径。
- 给出如何将其重构为通过 Agora MCP（BOS 协议如 bos://capability/swarm/run）调用 RPC 交互的重构切入点。

2. 【R2: Swarm 底层事件总线替换】
- 调研 `packages/swarm/src/swarm_engine/` 目录中有关事件、消息及状态管理的所有兼容 Stub，重点查找 `_compat.py` 等遗留组件，罗列所有被 Stub 定义并被其他文件引用的方法（如 `_emit_hatcher_event`）。
- 调研系统中现有的 `bus-foundation` 模块路径、API 接口（特别是发布事件、订阅事件、数据格式等），分析如何使用 `bus-foundation` 替换这些 Stub。

3. 【R3: Mesh 动态反馈与 Omo 稳态落盘闭环】
- 调研底层 Mesh 检测到算力节点（例如 node 或 zone 状态）发生变更的地方，或者能发布状态变更事件的地方。
- 调研上层 Omo 治理引擎（或 L4 Kernel 审计服务）接收该事件、执行安全校验并写入/更新 M1 元模型 YAML 稳态配置的对应代码位置（如 `projects/ecos/src/ecos/ssot/mof/m1/` 目录的读写服务和规则）。
- 梳理 Omo 现有的安全写回/审计机制与落盘 API。

输出要求：
1. 定期更新你工作目录下的 progress.md（必须包含 Last visited 时间戳），确保 liveness 正常。
2. 调研完成后，在你的工作目录下写入 analysis.md 报告，列出所有涉及的关键文件相对路径、行号（如能提供）、依赖关系以及你对每一部分的重构方案建议。
3. 请使用中文撰写报告，完成后使用 send_message 向我（Conversation ID: d6d08efc-a7bd-44e1-8861-e985ac7a8c92）报告，提供 analysis.md 的绝对路径。

【警告】你是只读探索者，严禁修改任何 source code 文件，严禁执行修改文件操作。
