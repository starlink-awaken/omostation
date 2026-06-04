# W3.2: Test Aggregation Reporter

> 创建 `scripts/test-report.py`，运行各项目测试并用 rich.Table 汇总输出。

## 任务

创建 `/Users/xiamingxing/Workspace/scripts/test-report.py`，功能：

1. 运行 agentmesh + agora 测试
2. 解析 pytest/bun 输出，提取 pass/fail 计数
3. 输出 rich.Table 聚合报告

## 实现细节

- 内部 pip install rich（如果缺失）
- `subprocess.run(cmd, cwd=path, capture_output=True, timeout=N)`
- 正则 `(\\d+)\\s+passed` / `(\\d+)\\s+failed`
- 返回 0（报告器模式）

## 测试

```bash
python3 scripts/test-report.py
```

Delegate to Sisyphus-Junior (category: quick).
