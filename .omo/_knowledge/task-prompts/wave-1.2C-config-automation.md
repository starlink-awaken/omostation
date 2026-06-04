# Task Prompt: Wave 1.2.C — 配置管理自动化

> 类型: P9 → P8 Task Prompt | 状态: ready (depends on Wave 1.2.A) | 预估: 1h

## 一、目标

建立配置变更审计机制，使 agora 配置被污染时自动预警，防止 Phase 1 的工作白费。

## 二、范围

| 事项 | 说明 |
|------|------|
| `make check-config` | Makefile target 检测 services.json 中是否有 192.0.2.x 地址 |
| `start-agora.sh` 自检 | 启动前先 check-config，有污染时退出 |
| 配置快照 | 每次修改 `agora-services.json` 前自动备份到 `.omo/backups/` |
| JSON Schema 校验 | `agora-services.json` 格式校验 |

## 三、验收标准

```
☐ `make check-config` 在 services.json 有 192.0.2.x 时 exit 1
☐ `make check-config` 在 services.json 洁净时 exit 0
☐ `start-agora.sh` 启动前自动运行 check-config
☐ `ls .omo/backups/` 有带时间戳的配置备份
☐ services.json 的 JSON Schema 校验通过
```

## 四、依赖

- **前置**: Wave 1.2.A 已完成（ruff 清零）
- **Wave 1.1.A** 已产出洁净的 services.json 作为基线

## 五、执行步骤

### Step 1: 添加 make check-config

在 `agora/Makefile` 添加：

```makefile
.PHONY: check-config
check-config:
	python3 -c "
import json, sys
d = json.load(open('agora-services.json'))
bad = [s['name'] for s in d['services'] if '192.0.2.' in s.get('mcp_endpoint','')]
if bad:
    print(f'❌ 测试服务残留: {bad}')
    sys.exit(1)
print('✅ 配置洁净: %d 个真实服务' % len(d['services']))
"
```

### Step 2: 更新 start-agora.sh

在启动 `agora web` 之前加入：

```bash
echo "🔍 配置自检..."
make -C "$AGORA_DIR" check-config 2>/dev/null || {
  echo "❌ 配置被污染，请先清理。运行: make -C $AGORA_DIR check-config"
  exit 1
}
```

### Step 3: 添加配置快照机制

创建一个 pre-commit hook 或 Makefile target：

```bash
#!/bin/bash
# .git/hooks/pre-commit 或 scripts/backup-config.sh
BACKUP_DIR="$PWD/.omo/backups"
mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d-%H%M%S)
cp agora-services.json "$BACKUP_DIR/$TS-services.json"
cp agora-routes.json "$BACKUP_DIR/$TS-routes.json"
```

### Step 4: 添加 JSON Schema

在 `agora/` 创建 `agora-services.schema.json`，规范服务注册表格式。

### Step 5: 验证

```bash
cd ~/Workspace/agora && make check-config

# 注入测试数据验证检测
python3 -c "
import json
d = json.load(open('agora-services.json'))
d['services'].append({'name':'test','mcp_endpoint':'http://192.0.2.99:3000'})
json.dump(d, open('agora-services.json','w'))
" && make check-config && echo "FAIL" || echo "PASS: 检测成功"

# 恢复
cd ~/Workspace/agora && git checkout agora-services.json
```

## 六、输出

| 文件 | 操作 |
|------|------|
| `agora/Makefile` | 添加 check-config |
| `agora/scripts/start-agora.sh` | 添加配置自检 |
| `agora/agora-services.schema.json` | 新增 Schema |
| `.omo/backups/` | 首次快照 |
| `.omo/TASK_POOL.md` | T025-T027 → done |
| `.omo/STATE.md` | 更新进度 |

## 七、Phase 1 门禁检查

Phase 1 完成标志：

```
☐ agora list 输出 9 真实服务无测试数据
☐ make check-config 可用且有效
☐ 所有活跃项目 ruff 0 errors
☐ MetaOS/SSOT 决策已记录
☐ agentmesh engine/toolkit 标记 experimental
☐ E2E 测试可重复运行
```

全部通过后 → **触发 Phase 2 所有 Wave**。
