# Handoff Report

## Observation
1. **测试断言宽泛与测试假通过倾向**：
   在 `projects/agora/tests/unit/test_bos_resolver.py` 中，存在多处断言逻辑对真实的错误进行了包容处理，导致无论底层是否成功启动或通信，测试都会通过。
   - 第 350-352 行的 `test_invoke_stdio_success`：
     ```python
     r = invoke_stdio("bos://memory/kos/search", "search", ["hello"], {"q": "test"})
     # status 可能 ok 或 error (eof_no_response 因为 kairon __main__ 不处理 stdin)
     assert "status" in r
     ```
   - 第 370-371 行的 `test_invoke_stdio_minerva`：
     ```python
     assert r.get("status") in ("ok", "error")
     assert "result" in r or "error" in r
     ```
   这些断言只要返回字典包含 `"status"` 即可通过，即使状态是 `"error"` 也是如此。

2. **不规范的 `sys.path` 运行时修改**：
   在 `projects/agora/src/agora/mcp/resolver/api.py` 的第 137-140 行的 `resolve_bos_uri` 函数中，对 `internal` transport 会尝试修改 `sys.path`：
   ```python
   if service.package and service.package != "agora":
       pkg_path = str(Path(_WS) / "projects" / service.package / "src")
       if pkg_path not in sys.path:
           sys.path.insert(0, pkg_path)
   ```
   而在 `projects/agora/src/agora/mcp/resolver/services.py` 默认注册表或 `etc/bos-services.yaml` 中，`internal` 服务如 `bos://meta/discover` 和 `bos://memory/vault/search` 的 `package` 字段分别为 `"meta"` 和 `"memory"`。
   这导致在运行时系统会去动态添加并不存在的物理目录 `projects/meta/src` 和 `projects/memory/src` 到 `sys.path`，该行为破坏了项目治理规范中的静态依赖管理规则。

3. **测试中的 Stdio 降级行为**：
   在 `projects/agora/tests/conftest.py` 第 78-88 行中，测试套件会在运行时将所有 `mcp_stdio` 协议的服务强行修改为 `stdio` 协议：
   ```python
   for svc in br.POC_SERVICES:
       if hasattr(svc, "transport") and svc.transport == "mcp_stdio":
           monkeypatch.setattr(svc, "transport", "stdio")
   ```
   由于 `stdio` 的 `StdioAdapter` 通信使用的是非标准 JSON-RPC 格式（即 `{"args": args, "kwargs": kwargs}` ），而 `mcp_stdio` 的底层原本期望标准的 JSON-RPC 2.0 格式（如 `tools/call` 等），这种强行降级使得测试用例发送了错误格式的 payload 却因上述宽泛断言（如 `assert "status" in r`）并未暴露通信不兼容的缺陷。

4. **物理运行治理验证通过**：
   运行 `make governance-verify`，返回的日志输出表明所有门禁和回归测试均为通过状态：
   ```
   bash bin/verify-omo.sh
   [1/5] Syncing .omo state
   [2/5] Running governance lint gates
   ...
   Gatekeeper: 958 files checked — PASS
   ...
   [4/5] Running governance regression tests
   135 passed in 1.63s
   [5/5] Running legacy .omo regression tests
   1 passed in 0.01s
   ```

## Logic Chain
1. 从 **Observation 1** 可以看出，测试设计中采取了“无论成功与否均认为测试通过”的宽泛断言策略。这使得在 CI 或本地依赖不完整、底层子进程崩溃的情况下，测试依然可以返回成功（Green Status）。
2. 从 **Observation 3** 结合 **Observation 1** 可以看出，由于强行进行 `mcp_stdio` 到 `stdio` 的降级，且二者请求 payload 的格式完全不同（非标准 JSON 格式 vs 标准 JSON-RPC 2.0），如果真实进行数据交互本应该发生解析错误。但正是由于宽泛断言 `assert "status" in r`，即使子进程报错返回 `"error"` 状态，依然满足了断言，掩盖了真实通信协议不兼容的潜在漏洞。
3. 从 **Observation 2** 可以看出，`resolve_bos_uri` 对 `internal` 服务的处理中，强行使用了与物理目录结构不一致的 `package` 名称进行 `sys.path` 插入，导致运行时修改指向了不存在的目录，这不符合严谨的项目依赖管理规范。
4. 从 **Observation 4** 可以看出，当前的 `make governance-verify` 等治理自动化门禁无法识别此类逻辑层面的断言放宽或冗余 `sys.path` 修补，因此在 CI 系统中会误判为完全 CLEAN。

## Caveats
1. 本审计基于当前子模块的静态代码分析及本机的 `make governance-verify` 执行。
2. 未针对开启多进程并发执行测试（如 `pytest -n`）时的 `ProcessPool` 端口或 stdio 文件描述符抢占行为进行压力测试。
3. 假设 `projects/kairon` 部分在测试运行时处于非完整安装状态为测试设计妥协的主因。

## Conclusion
**Verdict**: **CLEAN** (法医完整性通过，未发现硬编码测试结果、Facade伪装等主观恶意作弊或伪造数据的完整性违规行为，当前治理校验链路整体运行正常。)

**但存在以下防作弊及代码质量缺陷**：
1. **测试断言过宽导致的“假通过”**：`test_invoke_stdio_success` 等测试只要返回 dict 包含 `status` 键即可通过，未真实校验通信正常与否，掩盖了 `mcp_stdio` 强行降级为 `stdio` 后协议格式不兼容的逻辑漏洞。
2. **`sys.path` 冗余插入**：`internal` 协议运行时根据假包名（`meta`, `memory`）去动态修改 `sys.path`，指向了不存在的路径，属于逻辑冗余且破坏了静态依赖规范。

建议：
- 细化 `test_invoke_stdio_success` 与 `test_invoke_stdio_minerva` 的断言，显式断言 `"status" == "ok"`，并在环境不满足时使用 `pytest.mark.skip` 或 `pytest.mark.xfail` 明确标识，而不是通过放宽断言来实现假通过。
- 修复 `internal` transport 中对 `sys.path` 的修补逻辑，如果属于同一 package (`agora`)，应避免多余的目录插入。

## Verification Method
1. 运行 `make governance-verify` 验证治理大门和测试套件是否全部通过。
2. 检查 `projects/agora/tests/unit/test_bos_resolver.py` 第 350 行及 370 行的断言语句，确认其是否只校验了 `"status" in r`。
3. 检查 `projects/agora/src/agora/mcp/resolver/api.py` 第 137-140 行，确认是否在调用 `internal` transport 时对 `sys.path` 进行了不存在路径的 `insert`。
