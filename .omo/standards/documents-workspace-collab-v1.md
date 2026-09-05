---
schema_version: standard/v1
standard: documents-workspace-collab-v1
created: 2026-08-30
last-reviewed: 2026-08-30
owner: governance-team
adr: ADR-0441
type: ssot
---

# DW 协同契约 v1（Documents↔Workspace 三原语）

> SSOT：本标准是三原语的契约面；ADR-0441 是决策面；registry 是实例登记面。

## 原语 1 — Bridge Shell（D→W 执行转发）

```python
# Documents 侧薄壳模板（≤2KB 硬门）
# l4-content-plane: workspace-bridge
#!/usr/bin/env python3
# l4-content-plane: workspace-bridge
"""Compatibility bridge to the Workspace-owned <owner>."""
import os, sys
from pathlib import Path
target = Path(os.environ.get("BOS_WORKSPACE_ROOT", Path.home() / "Workspace")) / "<owner_path>"
if not target.is_file():
    raise SystemExit(f"Workspace owner is unavailable: {target}")   # fail-loud 硬门
os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])
```

约束：
1. 标记行必须出现在文件头 3 行内；缺失标记的薄壳会被 L4 判为 runtime 而非 bridge。
2. 转发目标必须是 registry `bridge_shells` 认证路径；目标缺失 fail-loud，禁止内联重实现。
3. 薄壳 ≤2KB（薄壳只做转发，带逻辑即违规）；sha256 入 registry，供周期核验。

## 厇语 2 — Owner Job（W→D 受控访问）

约束：
1. aggregate-only / read-only / explicit_apply_only 三态，默认最严格。
2. 不把 Documents 内容（正文/正文片段）泄入 Workspace 日志、回执、测试 fixture。
3. 写 Documents 必须走 quarantine 事务协议，confirmation_gate 前置。

## 原语 3 — 边界仲裁三件套

1. L4 分类器是分类唯一真值；`workspace-bridge` 标记自动豁免 runtime 搬迁。
2. consumer audit 硬门：forbidden_executors=0 恒成立，violations 即回滚信号。
3. quarantine 是 Documents 文件移动唯一协议；BOS 路由 `bos://documents/*`。

## 实例登记（registry bridge_shells）

```yaml
bridge_shells:
  - shell: "@公共/_runtime/kems-materialize.py"
    target: "projects/runtime/scripts/kems-materialize.py"
    sha256: "<shell 当前 sha256>"
    owner: runtime
    adr: ADR-0441
```

首个实例：kems-materialize 薄壳（643B，execv 转发，实战验证于 #2711 收口复核）。
