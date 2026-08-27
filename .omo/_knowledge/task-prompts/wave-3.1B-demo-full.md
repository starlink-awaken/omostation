---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 3.1.B — workspace demo 完整版

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Wave 3.1.A) | 预估: 1h

## 一、目标

将 workspace demo 从 3 步扩展到 4 步：health → research → list → status，成为真正的 30 秒上手指南。

## 二、范围

```bash
workspace demo
  Step 1/4: ✅ 系统健康 — workspace status
  Step 2/4: ✅ 发起研究 — workspace research "transformer"
  Step 3/4: ✅ 研究历史 — workspace research list
  Step 4/4: ✅ 系统全景 — workspace status（包含研究记录）
  ──────────────────────────────────────────
  体验完成！接下来可以：
    workspace research "<topic>"  — 研究新主题
    workspace status              — 查看系统状态
    workspace help                — 查看所有命令
```

## 三、验收标准

```
☐ workspace demo 4 步全部成功
☐ 总耗时 < 30 秒
☐ 缺少组件时自动提示：agora 未启动 → "请先运行 start-agora.sh"
☐ 结束后输出引导建议
```

## 四、依赖

- **前置**: Wave 3.1.A 已完成

## 五、执行步骤

### Step 1: 增强 Wave 2.2.C 的 demo

从 3 步扩展到 4 步，加入 setup check：

```python
def _check_prerequisites():
    checks = [
        ("agora", shutil.which("agora") is not None),
        ("minerva", shutil.which("minerva") is not None),
        ("agora web", _is_port_open(7430)),
    ]
    missing = [name for name, ok in checks if not ok]
    if missing:
        print(f"⚠️  缺少: {', '.join(missing)}")
        if "agora web" in missing:
            print("   启动: bash ~/Workspace/agora/scripts/start-agora.sh")
        return False
    return True
```

### Step 2: 添加引导输出

demo 完成后输出建议命令列表。

## 六、输出

| 文件 | 操作 |
|------|------|
| `workspace/commands/demo.py` | 修改 |
| `.omo/TASK_POOL.md` | T045-T047 → done |

## 七、→ 下一个 Wave

完成后触发 **Wave 3.2.A (AgentMesh 链路验证)**。
