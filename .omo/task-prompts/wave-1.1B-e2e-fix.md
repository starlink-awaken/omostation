# Task Prompt: Wave 1.1.B — E2E 测试修复

> 类型: P9 → P8 Task Prompt | 状态: ready (depends on Wave 1.1.A) | 预估: 45min

## 一、目标

修复 `agora` 项目的端到端测试套件，消除硬编码宿主路径，使测试可在任意环境重复运行。

## 二、范围

| 文件 | 操作 |
|------|------|
| `agora/tests/e2e/test_cross_project.py` | 路径硬编码 → `shutil.which()` + `@pytest.mark.skipif` |
| `agora/tests/test_cli.py` | 同 test_cross_project 模式修复 |
| `agora/tests/test_*` — 有硬编码路径的 | 全部扫描并修复 |

## 三、验收标准

```
☐ `cd ~/Workspace/agora && python -m pytest tests/e2e/ -q` — 无失败，正确 skip
☐ `cd ~/Workspace/agora && python -m pytest tests/ -q` — 通过率 ≥ 之前
☐ 所有 `shutil.which()` 外部命令加了 skipif
☐ tests 目录下再无硬编码 `/Users/xiamingxing/` 路径
```

## 四、依赖

- **前置**: Wave 1.1.A 已完成（配置洁净，`agora health` 正常）
- **确认命令**: `agora list` 输出 9 服务无污染 && `agora health` 不崩溃

## 五、执行步骤

### Step 1: 扫描硬编码路径

```bash
cd ~/Workspace/agora && grep -rn '/Users/' tests/ --include='*.py'
cd ~/Workspace/agora && grep -rn '\.venv/bin/' tests/ --include='*.py'
```

### Step 2: 修复 `test_cross_project.py`

```python
# 替换
AGORA = "/Users/xxx/Workspace/agora/.venv/bin/agora"
ONTODERIVE = "/Users/xxx/Workspace/ontoderive/.venv/bin/ontoderive"

# 为
import shutil
import pytest

AGORA = shutil.which("agora")
ONTODERIVE = shutil.which("ontoderive")

# 每个测试类加 class-level skipif
@pytest.mark.skipif(not AGORA, reason="agora CLI not found on PATH")
class TestAgoraE2E: ...
```

### Step 3: 检查 `test_cli.py` 和其他测试文件

同样模式修复所有硬编码路径。

### Step 4: 运行验证

```bash
cd ~/Workspace/agora && python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

### Step 5: 扫描残余

```bash
cd ~/Workspace/agora && grep -rn '/Users/' tests/ --include='*.py' && echo "CLEAN" || echo "还有残留"
```

## 六、输出

| 文件 | 操作 |
|------|------|
| `agora/tests/e2e/test_cross_project.py` | 修改 |
| `agora/tests/test_cli.py` | 修改（如有需要） |
| `.omo/TASK_POOL.md` | T006-T008 → done |
| `.omo/STATE.md` | 更新进度 |

## 七、→ 下一个 Wave

完成后触发 **Wave 1.2.A (ruff 清零)**。验证：测试套件可重复运行。
