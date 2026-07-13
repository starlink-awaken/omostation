# A2 修正方案 + 本次清理日志

> 日期: 2026-07-13 · 承接 review 后的直接处理

## 本次已完成的清理（工作树止血）

Cowork 删除权限授权后，已实际清除 agy 会话留下的锁死状态：
- ✅ 删除野生错位目录 `~/Workspace/ecos/`（内容是 `projects/ecos` 里更完整版本的旧残本，已 diff 核对可删）。
- ✅ 清除 6 个陈旧 `.git/index.lock`：gbrain / family-hub / metaos / ecos / runtime + `.git/modules/projects/c2g`。
- ✅ 清除 uv `projects/omo/.venv/.lock`。

P60 锁堵已解除。**注意**：agy 散在 7 个子模块的未提交业务改动（agora 限流/熔断埋点、runtime cron 总线事件等）**未动**——需你逐个决定去留（见前一条 review 的第 4 步命令）。

## 为什么 A3 活体重扫 / A2 活体验证没在这里跑

`projects/omo/.venv` 是 **macOS-native**（sandbox 报 "virtual environment linked to non-existent Python interpreter"），我的 Linux 沙箱无法复用/重建它——重建时 uv 在这个挂载上 rename 失败（`os error 2`）。这不是权限问题，是**跨平台**。

→ **A3 活体健康重扫（`omo state sync`）、A2 活体 resolve 验证，必须在你的 Mac 上跑**（你本人，或本机的 Claude Code agent）。我的沙箱擅长读/分析/规划/轻量清理，但依赖 venv 的运行时命令要落到本机。

## A2 修正方案（比原派单更准，已按真实协议核对）

**原派单假设错了**（"改 `-m X.cli` → `-m X`"）。读了 `kairon_utils/stdio_rpc.py` 后确认真实协议：

- `transport: stdio` 适配器往子进程 stdin 写一行 `{"args":..., "kwargs":...}`，读一行 stdout。
- action 从**命令行 argv 尾参**来（如 `... -m core_models.cli schema` 里的 `schema`），不是 stdin payload。
- `core_models`/`health_profile` 只有 `__main__.serve()`（`run_stdio_dispatch` 循环，action 从 payload 取），**没有** argv 版 `cli.py` → 声明与实现不匹配。

**正确修法**：给两个包各补一个薄 `cli.py`，argv 取 action + stdin 取 `{"args","kwargs"}` → 复用已有 `_call_action` → 打印 JSON。correct-by-construction：

`projects/kairon/packages/core-models/src/core_models/cli.py`（health-profile 同构，把 import 换成 `health_profile`）:

```python
"""stdio CLI shim: argv action + stdin {"args","kwargs"} → _call_action → JSON 行.
匹配 agora BOS transport=stdio 适配器 (写 {"args","kwargs"} 到 stdin, 读一行 JSON)。"""
from __future__ import annotations
import json
import sys
from core_models.__main__ import _call_action  # health_profile: 换成 health_profile.__main__


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    action = argv[0] if argv else "default"
    raw = sys.stdin.readline()
    try:
        req = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        req = {}
    args = req.get("kwargs") or req.get("args") or {}
    if not isinstance(args, dict):
        args = {}
    result = _call_action(action, args)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`protocols-layer/trigger`（bos-services.yaml:1112）：kairon 无 `protocols_layer` 包 → 在 description 前加 `[UNIMPLEMENTED]` 或从 registry 移除。

## ⚠️ 关键前置：先跑活体 resolve 建立真值，再决定修哪些

A1 静态审计有盲区：`kos` 这个被判 "OK" 的 stdio 服务**同样没有 `cli.py`**。这说明"43 条 OK"可能虚高，`.cli` 这一模式可能**系统性**没在活体跑通，而不止这 4 条。所以：

**Mac 上先跑一次真实 resolve**（对所有 stdio `.cli` 声明），拿到真正跑通/跑不通的名单，再决定是"给每个补 cli.py"还是"这一整套 stdio 分发协议要重修"。**不要**照静态名单盲补——那会重蹈 agy 的未验证改动覆辙。

建议 Mac 上的验证命令（示意）:
```bash
cd ~/Workspace
# 对单条活体验证 resolve（示意，具体入口看 agora CLI）
echo '{"args":[],"kwargs":{}}' | uv run --directory projects/kairon python -m core_models.cli schema
# 期望: 打印一行 JSON 结果而非 ModuleNotFoundError
```

## 交接状态
- A2: 修正方案 + 薄 cli.py 已备好（本文件），**待 Mac 活体验证后应用**。
- A3: 清理已做；活体重扫待 Mac 执行。
- hermes 注销 / A4 GaC：仍需 Mac launchctl + broker（见 ADR 草案）。
