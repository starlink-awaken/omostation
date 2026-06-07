# 任务 YAML 编写规范

> 治理债务永久化. P32-W0 / P34-W4 / P35-W3 三次教训.

## 规则 1: deliverables 必须为文件路径

`deliverables:` 列表的**每一项**必须是真实文件路径, 相对于工作区根 (`/Users/xiamingxing/Workspace/`).

### 允许

```yaml
deliverables:
  - ".omo/_knowledge/management/decision-p30-architecture-final.md"
  - "projects/kairon/packages/protocols-layer/src/protocols_layer/__init__.py"
  - "projects/omo/src/omo/omo_bos.py"
  - "scripts/release.sh"
  - "VERSION"
```

### 不允许

```yaml
deliverables:
  - "21 条新增 BOS URI"           # ❌ 描述式, 不是文件
  - ".omo/_knowledge/bos-registry.json (40 URI)"  # ❌ 括号描述
  - "projects/agora/src/agora/mcp/bos_resolver.py (升级 respawn)"  # ❌ 括号描述
  - "5 kairon __main__.py POC"      # ❌ 描述式
  - "scripts/release.sh 等"          # ❌ "等" 字结尾
```

## 规则 2: description 写明改动范围

`description:` 字段应说明任务实际做了什么, **不重复 deliverables 列表**.

### 允许

```yaml
description: |
  P35-W1 战役 4: agora spawn 真替代.
  - is_alive 自动清理死进程
  - respawn_dead 批量恢复
  - invoke_stdio 遇死进程自动 respawn
  守 P32/P33/P34 修复.
```

## 规则 3: 单元测试数声明

如任务涉及代码改动, **明确声明**单元测试数:

```yaml
deliverables:
  - "新增 3 单元测试 (respawn_dead / invoke_respawn / batch)"
```

## 规则 4: 文件路径用相对工作区根的相对路径

不要绝对路径如 `/Users/xiamingxing/Workspace/...`, 用 `.omo/...` 或 `projects/...` 形式.

## 自动检查

`omo governance audit` 自动检查:
- 0 missing deliverables (task_consistency 100)
- 所有 deliverables 路径存在

`P35-W2 CI workflow` (`.github/workflows/omostation-governance.yml`) 自动阻断描述式回归.

## 参考

- P32-W0-DELIVERABLES 修复
- P34-W4-FIX-AUDIT 修复
- P35-W3-FIX-AUDIT 修复

## 验收

P36-W0 验收:
- [x] 文档写入 .omo/standards/
- [x] omo governance audit 检查项引用本规范
- [x] 未来 P36+ 任务 YAML 严格遵守
