这些任务文件曾错误地落在 `.omo/tasks/done/`，但其 `status` 仍是 `pending/review`。

处理原则：
- 若 `registry/done/` 已存在同 ID 的 `completed`/`done` 正式记录，则此处仅保留为历史影子。
- 未完成任务已迁回 `.omo/tasks/planned/` 作为当前 SSOT。

本目录仅用于保留治理漂移的历史痕迹，不参与 live task 统计。
