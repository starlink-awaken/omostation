---
schema: bet-retro/v1
bet_id: fix-pre-existing-tests
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-16
type: ephemeral
---

# fix-pre-existing-tests retrospective — 4016 窗口 3 pre-existing test fail 修复

## Q1. What was intended?

PR #3811 描述中标注的 3 个 pre-existing test fail:

1. `tests/test_gen_service_configs.py::test_check_skips_byte_comparison_when_host_observer_is_unavailable` — TypeError: lambda 不接参数
2. `tests/test_gen_service_configs.py::test_observer_unavailable_does_not_mask_malformed_declarations` — 同上
3. `tests/test_ops_cli.py::TestGetCmd::test_python3_interpreter` — AssertionError: 拿到 python3.14 而非 python/python3

## Q2. What happened?

### 1+2. observer 测试 lambda 签名修复

`load_services(path=None)` 在 PR #3518 (#3781) 改过签名, 但 2 个 observer
测试的 lambda 没跟上, 仍是 `lambda: [...]`. 修法: `lambda path=None: [...]`
匹配当前签名.

修完 2 个 PASS.

### 3. cli._get_cmd stable-python3 走 sys.executable 是真 bug

不是测试问题, 是 cli bug. cli 用 `sys.executable` 拿当前 python 解释器,
在 `uv run` / venv 启动时拿到 python3.14 全路径, 与 gen-service-configs 的
`_stable_python3()` 返 `/opt/homebrew/bin/python3` (固定 homebrew 路径)
**不一致**.

后果: plist 生成 (gen-service-configs 跑) 用 homebrew python3, plist 执行
(cli 调 _get_cmd) 用 venv python3.14 — "stable" 语义失效, plist 实际指向
两个不同 python, 谁先 update 谁版本就漂移.

修法: 让 cli 复用 gen-service-configs._stable_python3 (避免代码重复,
两份稳定 python 解析逻辑的 drift 是新的 leak 风险).

具体:
- `bin/ops/cli.py` 顶部 import 段后用 `importlib.util.spec_from_file_location`
  加载 gen-service-configs 模块, 拿 `_stable_python3` 函数
- `_get_cmd` 中 `stable-python3` 分支: `return [sys.executable, entry]` →
  `return [_stable_python3(), entry]`
- 退化路径: import 失败时退回 sys.executable (不阻断启动, 但行为退化)

加新测试 `test_stable_python3_uses_dedicated_function_not_sys_executable`
防回归.

修完 1 个 PASS.

## Q3. What went well?

1. **3 个 fail 全部修好**, 全套 37 个相关测试 0 fail.
2. **复用 gen-service-configs._stable_python3 而不是复制逻辑**:
   单一真相源, 防未来两份 stable-python3 解析逻辑 drift.
3. **加防回归测试**: 新测试不仅断言 cmd[0] 是 python, 还断言必须走
   `_stable_python3()`, 防止有人"为了测试通过"把代码退回到 sys.executable.

## Q4. What went poorly?

1. **未修 14 个 TestEnvConfig pre-existing fail**: `tests/test_ops_comprehensive.py`
   14 个测试期望 `ops env show/list` 等子命令存在, 但 cli 没有 env 子命令.
   跟本任务无关, 留后续 lane 修 (要么实现 env 子命令, 要么删测试).
2. **cli 顶部 import 段增加 _stable_python3 加载代码**: 是 importlib 动态加载
   而非普通 `from bin.mof.gen_service_configs import _stable_python3`,
   因为 bin/mof/gen-service-configs.py 是顶层脚本 (有 `if __name__ == "__main__"`)
   不能直接 import. 动态加载 + 退化路径, 增加了一点点复杂度.
3. **PR #3815 之后 main 又推了 PR #3816 / #3817** — 4016 期间并行 lane 推了
   2 个 PR, 我需要在 worktree claim 后再 fetch. 已处理, 无冲突.

## Q5. What will we do differently?

1. **预 push 跑完整测试套** (不是只跑相关的): 避免遗漏类似 TestEnvConfig
   14 个 fail 跟本任务无关但被 PR 评论 / CI 抓到.
2. **加新 cli 子命令时同步更新 test_ops_comprehensive**: 删 env show/list
   等 dead 测试 (或实现对应子命令).
3. **跨 bin 工具的复用 (gen-service-configs → cli) 应抽到 bin/_lib/**:
   未来可能还有 ops 其他工具需要 stable-python3 解析, 抽到 lib 避免
   多个工具各自 importlib 加载.

## Evidence

- 改动文件:
  - `bin/ops/cli.py`: +15 / -1 (新 import 段 + _get_cmd stable-python3 分支)
  - `tests/test_gen_service_configs.py`: +2 / -2 (2 个 observer lambda 加 path=None)
  - `tests/test_ops_cli.py`: +18 / -0 (新防回归测试)
  - `.omo/_knowledge/retros/fix-pre-existing-tests.md`: +60 (retro)

- 验证:
  - `python3 -m pytest tests/test_gen_service_configs.py tests/test_ops_cli.py
     tests/test_ops_liveness.py -v` → **37/37 PASS** (0 fail)
  - `python3 bin/ops/cli.py check-signals` → 0 drift (cli 改动不破坏 ops 行为)
  - `python3 bin/mof/gen-service-configs.py --validate` → 0 violations
