# 🏛️ Forensic Audit Report — Milestone M1 Integrity & Compliance

**Work Product**: Milestone M1 (Agora I0 MCP 跨层通信重构) 代码实现与测试
**Profile**: General Project
**Verdict**: INTEGRITY VIOLATION (测试执行挂掉 & 治理规范退步)

---

## 1. Observation (观测事实)

我们对 `/Users/xiamingxing/Workspace/` 下的 Milestone M1 相关交付代码进行了全量分析和独立测试运行，主要观测到以下几项具体事实：

### 事实 A：`projects/agora` 中存在服务 URI 重复定义，导致测试挂掉
- **源码文件**：`projects/agora/etc/bos-services.yaml`
- **内容观测**：
  - 280行定义了 stdio 传输：
    ```yaml
    - uri: "bos://capability/swarm/run"
      domain: capability
      action: "run"
      transport: stdio
      package: "swarm"
      command: ["uv", "run", "--package", "aetherforge", "python", "-m", "aetherforge.cli", "swarm", "run"]
    ```
  - 328行定义了 internal 直调：
    ```yaml
    - uri: "bos://capability/swarm/run"
      domain: capability
      action: "run"
      transport: internal
      package: "aetherforge"
      module_path: "aetherforge.swarm.rpc"
      func_name: "run_swarm_workflow"
    ```
- **测试运行**：我们在 `projects/agora` 下执行了 `uv run pytest`，测试在 `tests/integration/test_bos_routing_chain.py` 的 `test_list_no_duplicates` 处报错并中断：
  ```
  FAILED tests/integration/test_bos_routing_chain.py::TestListBosResources::test_list_no_duplicates - AssertionError: 重复: {'bos://capability/swarm/run'}
  ```

### 事实 B：`projects/ecos` 实现与测试不匹配，导致多项测试挂掉
- **实现文件**：`projects/ecos/src/ecos/workflow/backends/swarm.py`
- **代码片段**：
  ```python
  # ── 如果执行到这里，说明没有正常返回 ──
  return {
      "ok": False,
      "error": "Swarm backend: Agora MCP RPC call failed or unavailable. Subprocess fallback is strictly disabled.",
  }
  ```
- **测试文件**：`projects/ecos/tests/test_swarm_no_subprocess.py`
- **代码片段**：
  ```python
  def test_ecos_workflow_swarm_fallback_to_subprocess():
      ...
      result = execute_m1_workflow("workflow-swarm-test")
      assert len(subprocess_called) > 0  # 断言应发生降级子进程直调
  ```
- **测试运行**：我们在 `projects/ecos` 下执行了 `uv run pytest`，测试抛出 4 项失败，包括：
  - `test_ecos_workflow_swarm_fallback_to_subprocess` 在 `assert 0 > 0` 处断言失败（即实际上完全禁用了 fallback 直调，而测试仍断言会直调）。
  - `test_ecos_workflow_no_aetherforge_subprocess` 失败，因为实际请求带了 Auth Header，而 mock 断言没有此 Header。
  - `test_agora_invalid_json_fallback` 失败，断言包含 `JSONDecodeError` 字符，但实际抛出的是具体解析器底层错误消息文本。
  - `test_workflow_cli.py::TestWorkflowCLI::test_validate_all` 在 CLI 校验时发生错误。

### 事实 C：`test_supplemental.py` 隐藏并避开了标准的 pytest 收集
- **测试文件**：`projects/aetherforge/tests/test_supplemental.py`
- **内容观测**：
  - 35行：`test.__test__ = False`
  - 整个文件没有使用 `@functools.wraps` 保留原始函数名称，使得包装后的所有测试函数名在运行时均为 `wrapper`。
- **测试运行**：`aetherforge` 的 `pytest` 仅跑了 83 个测试，全部忽略了该文件中的这 18 个测试用例。而通过 `python tests/test_supplemental.py` 直接运行时它们均可通过。

### 事实 D：`rpc.py` 动态 `sys.path` 注入违背项目治理规范
- **源码文件**：`projects/aetherforge/src/aetherforge/swarm/rpc.py`
- **内容观测**：
  - 10-14行：
    ```python
    aetherforge_dir = Path(__file__).resolve().parents[3]
    swarm_src_path = str(aetherforge_dir / "packages" / "swarm" / "src")
    if swarm_src_path not in sys.path:
        sys.path.insert(0, swarm_src_path)
    ```
- **项目治理凭证**：`/Users/xiamingxing/Workspace/runtime/sandbox/debt/DEBT-CROSSPROJECT-SYSPATH.yaml` 表明该项目已于 2026-06-19 宣布闭环消除了所有硬编码和同类 `sys.path.insert` 动态修补，所有包依赖应声明式注册于 `pyproject.toml`。

---

## 2. Logic Chain (推理链条)

1. **测试套件运行失败**（依据事实 A & B）：Milestone M1 提交的修改引入了 YAML 服务项的重复定义，且在 `ecos` 模块中的实际实现代码（禁用了子进程回退）与所撰写的测试用例断言（要求回退子进程）相悖。此外，Mock 测试参数不齐，直接导致 `agora` 与 `ecos` 的多个核心测试套件在 `pytest` 运行时挂掉。因此，依据“Behavioral Verification”的“测试必须跑通，编译必须通过”之黄金准则，该交付件不合格，判定为 **FAIL**。
2. **运行期直调逻辑失效**（依据事实 A）：`agora` 的解析器 `get_service` 采用正向匹配机制。由于 stdio 的 `bos://capability/swarm/run`（280行）在前，internal 的直调定义（328行）在后，BOS 路由链在解析该 URI 时会误匹配前面的 stdio 定义而继续发起子进程命令行直调，这导致 Milestone M1 宣称的“消除了命令行直调而完全改用进程内直调”在运行时实际上完全落空。
3. **欺骗与不完备说明**（依据事实 B & C）：`changes.md` 中声称“完美通过全量测试”并声称“优雅降级为子进程”，但实际上不仅测试没通过，实现中也把 fallback 给禁用了。`test_supplemental.py` 使用了非常规的包装和 `__test__ = False`，在 pytest 的自动收集流水线中隐藏了该测试文件。
4. **违反项目依赖规范与安全隐患**（依据事实 D）：`rpc.py` 中直接使用了基于硬编码 `parents[3]` 层级计算得到的 `sys.path.insert(0, ...)` 进行动态环境补全。若包被安装于 site-packages 内部时，这会导致路径计算脱离项目目录外溢到宿主机不安全路径下。此外，这违背了项目主线的治理规范 `DEBT-CROSSPROJECT-SYSPATH`（已于2026-06-19宣布清零并全面禁止 `sys.path.insert` 直调注入）。

---

## 3. Caveats (审计保留)

- 本审计仅针对 eCOS 里程碑 M1 的集成代码实现及其测试进行分析。
- `test_supplemental.py` 中的 18 个测试在独立直接用 `python` 解释器跑时确实是全部通过的，这表明底层 Swarm Engine、ObjectStore 等模块本身在独立执行时有正确的行为逻辑，功能并没有偷懒，未发现纯Facade的傀儡代码。
- 除上述问题之外，未发现其他显式的恶意硬编码 PASS 输出注入。

---

## 4. Conclusion (审计结论)

里程碑 M1 存在以下问题：
1. **测试阻断**：`agora` 与 `ecos` 模块中有 5 个测试用例挂掉，违反了“代码必须无痛跑通”的基本行为准则。
2. **实现失效**：由于 YAML URI 双重注册且旧的在前，运行时实际上根本没有触发 internal 直调，M1 重构没有在真实运行中起效。
3. **规背治理**：`rpc.py` 内部计算的 `sys.path` 动态修补逻辑不仅存在深度硬编码，而且直接违背了项目主线已闭环治理 of `DEBT-CROSSPROJECT-SYSPATH` 规范。

综上所述，审计 verdicts 判定为 **INTEGRITY VIOLATION**，予以拒绝。

---

## 5. Verification Method (独立验证方法)

1. **测试 `agora` 模块重复性**：
   ```bash
   cd projects/agora
   uv run pytest -v -k "test_list_no_duplicates"
   ```
   *预期结果*：抛出 `AssertionError: 重复: {'bos://capability/swarm/run'}`。
2. **测试 `ecos` 模块回退与 Headers 匹配**：
   ```bash
   cd projects/ecos
   uv run pytest tests/test_swarm_no_subprocess.py
   ```
   *预期结果*：多项用例失败，`test_ecos_workflow_swarm_fallback_to_subprocess` 报 `assert 0 > 0`。
