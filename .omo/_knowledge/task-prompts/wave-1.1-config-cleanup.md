---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 1.1 — Phase 1 基础设施清理

> 类型: P9 → P8 Task Prompt | 状态: ready | 预估: 2h

---

## 一、目标

完成 Workspace 治理 Phase 1 Sprint 1.1（配置洁净 + E2E 测试修复），使 `agora` 的 services/routes/events 配置不再被测试数据污染，所有 E2E 测试可通过 `shutil.which` 适配宿主环境。

**为什么这是最高优先级：** 配置混乱导致 agora dashboard 显示虚假服务、`agora health` 检测不存在的端点、`agora sync` 注册垃圾路由。这是所有后续工作的前提条件。

---

## 二、范围

### 包含

- `agora/agora-services.json` — 确保无 192.0.2.x 测试地址、无重复服务、仅保留真实服务
- `agora/agora-routes.json` — 删除测试路由，仅保留真实服务路由
- `agora/agora-events.json` — 清空测试事件和测试订阅
- `agora/tests/e2e/test_cross_project.py` — 路径硬编码改为 `shutil.which()` + skipif 标记
- `agora/src/agora/cli.py` — 确保 `agora health` 全路径覆盖
- 配置变更审计机制 — 每次配置修改自动备份

### 不包含

- 任何新功能开发（如 workspace research 持久化）
- 非 agora 项目的代码修改
- agentmesh / MetaOS / SSOT 审计（那是 Wave 1.2.B）
- ruff 清零（那是 Wave 1.2.A）

### 已完成的背景

以下工作之前会话已完成，但需验证持久性：

| 事项 | 状态 | 验证方式 |
|------|------|---------|
| `agora-services.json` 清洗至 9 服务 | ✅ 可能又被污染 | `agora list` 检查 |
| `agora-routes.json` 清洗 | ✅ 可能又被污染 | 读 routes 文件检查 |
| cli.py await bug 修复 | ✅ 已确认 | `agora health` 正常 |
| enhanced_health.py 全量 bug 修复 | ✅ 已确认 | `agora health` 正常 |
| monitoring 文件名修复 | ✅ 已确认 | import 正常 |
| governance 规则写入 CLAUDE.md | ✅ 已确认 | 读文件验证 |

---

## 三、验收标准

```
☐ `agora list` 输出 = 9 个真实服务，无 192.0.2.x 地址
☐ `agora routes` 输出仅含真实服务路由
☐ `agora-events.json` events 数组为空，subscriptions 为空
☐ `cd agora && python -m pytest tests/e2e/ -q` — 所有测试 pass 或正确 skip
☐ `cd agora && python -m pytest tests/ -q` — 所有 unit test pass
☐ `make check-config` 检测到 192.0.2.x 时 exit 1
☐ `ls .omo/backups/` 有配置变更前的时间戳快照
```

---

## 四、依赖

### 前置依赖（开始前必须满足）

- [ ] `agora web` 不在运行（防止运行时配置文件覆盖）
- [ ] Python 3.14 可用 (`/opt/homebrew/bin/python3`)
- [ ] `pip install -e ~/Workspace/agora` 已执行

### 外部依赖

| 依赖 | 用途 | 获取方式 |
|------|------|---------|
| `python3` | 运行 CLI | 系统自带 |
| `ruff` | 代码检查 | `pip install ruff` |
| `pytest` | 测试运行 | `pip install pytest` |
| `shutil.which` (stdlib) | 路径查找 | Python 内置 |

---

## 五、输出产物

| 文件 | 操作 | 说明 |
|------|------|------|
| `agora/agora-services.json` | 修改 | 确保 9 服务无污染 |
| `agora/agora-routes.json` | 修改 | 确保 9 真实路由 |
| `agora/agora-events.json` | 修改 | 清空 events + subscriptions |
| `agora/tests/e2e/test_cross_project.py` | 修改 | shutil.which + skipif |
| `agora/Makefile` | 新增或修改 | 添加 check-config target |
| `.omo/backups/<timestamp>-services.json` | 新增 | 配置快照 |
| `.omo/backups/<timestamp>-routes.json` | 新增 | 配置快照 |
| `.omo/TASK_POOL.md` | 修改 | 更新 T001~T008 状态 |
| `.omo/STATE.md` | 修改 | 更新进度 + session 记录 |

---

## 六、执行步骤

### Step 1: 读取当前状态

```bash
# 1.1 读取当前配置
cat ~/Workspace/agora/agora-services.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
bad = [s['name'] for s in d['services'] if '192.0.2.' in s.get('mcp_endpoint','')]
print(f'Services: {len(d[\"services\"])}, Test entries: {bad if bad else \"none\"}')"

# 1.2 读取 routes
cat ~/Workspace/agora/agora-routes.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
test_routes = [k for k in d['routes'] if k in ('test.tool','api','grpc-svc','ws-svc','stdio-svc','bad-proto','bad-ws','down-svc','retry-api','mcp-svc.tool','ssrf.tool','err.tool','rest-api.create','rest-ssrf','exhaust.get','bad-req.get','crash.tool','bos')]
print(f'Routes: {len(d[\"routes\"])}, Test routes: {test_routes if test_routes else \"none\"}')"

# 1.3 检查 events
cat ~/Workspace/agora/agora-events.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Events: {len(d.get(\"events\",[]))}, Subs: {len(d.get(\"subscriptions\",[]))}')"
```

### Step 2: 验证 agora health 正常

```bash
agora health 2>&1 | head -5
# 确认无 SyntaxError, AttributeError, ModuleNotFoundError
```

### Step 3: 执行配置清洗

**services.json 保留清单（9 个）：**
```
minerva, sophia, agora, eidos, iris, kronos, bos-daemon, ontoderive, bos-skill-cli
```

规则：
- 删除所有 `mcp_endpoint` 包含 `192.0.2.` 的服务
- 删除 `bos`（与 `bos-daemon` 同端点，已移除）
- 每次修改前先备份到 `.omo/backups/`

**routes.json 保留清单：**
```
minerva.*, minerva, sophia.*, sophia, ontoderive.*, ontoderive, agora.*, agora,
eidos.*, iris.*, kronos.*, bos-daemon.*, bos-daemon,
codeanalyze.*, kos.*, forge.*, bos-skill-cli, eidos, iris, kronos
```

规则：
- 删除所有 test/api/grpc/ws/bad/down/crash 路由
- 删除 `bos` 路由

**events.json：**
```json
{"events": [], "subscriptions": [], "max_events": 1000}
```

### Step 4: 修复 E2E 测试

编辑 `agora/tests/e2e/test_cross_project.py`：

```python
# 将硬编码路径:
AGORA = "/Users/xxx/Workspace/agora/.venv/bin/agora"
ONTODERIVE = "/Users/xxx/Workspace/ontoderive/.venv/bin/ontoderive"

# 改为:
import shutil
import pytest

AGORA = shutil.which("agora")
ONTODERIVE = shutil.which("ontoderive")

# 每个测试方法加:
@pytest.mark.skipif(not AGORA, reason="agora CLI not found on PATH")
```

### Step 5: 添加配置审计

在 `agora/Makefile` 添加：

```makefile
.PHONY: check-config
check-config:
	@python3 -c "
import json
d = json.load(open('agora-services.json'))
bad = [s['name'] for s in d['services'] if '192.0.2.' in s.get('mcp_endpoint','')]
if bad:
    print(f'❌ Test entries found: {bad}')
    exit(1)
print('✅ Config clean')
	"
```

### Step 6: 验证

```bash
# 6.1 验证 services
agora list

# 6.2 验证 routes
agora routes

# 6.3 验证 health
agora health

# 6.4 验证测试
cd ~/Workspace/agora && python -m pytest tests/ -q
cd ~/Workspace/agora && python -m pytest tests/e2e/ -q

# 6.5 验证 check-config
make check-config  # 应该 exit 0
# 手动引入测试数据验证检测
python3 -c "
import json
d = json.load(open('agora-services.json'))
d['services'].append({'name':'test','mcp_endpoint':'http://192.0.2.99:3000'})
json.dump(d, open('agora-services.json','w'))
"
make check-config && echo "FAIL: should have detected" || echo "PASS: detected test data"
# 恢复
git checkout agora-services.json  # 或重新清洗
```

### Step 7: 记录状态

更新 `.omo/TASK_POOL.md` 和 `.omo/STATE.md`，标记 T001~T008 状态：

```
T001: done
T002: done
T003: done
T004: done (check-config 机制)
T005: done (JSON Schema 校验 — 可选)
T006: done
T007: done
T008: done
```

---

## 七、错误处理

| 错误场景 | 处理方式 |
|---------|---------|
| `agora health` 崩溃 | 先修运行时错误（SyntaxError / ImportError / AttributeError），再继续 |
| `agora list` 与预期不符 | 直接读 JSON 文件验证，不依赖 CLI 输出 |
| `pytest` 失败 | 检查是否因测试数据 skip 条件变化，修正测试 |
| 配置清理后又出现测试数据 | 检查是否有后台进程在写配置（如 `agora web`） |

## 八、工时估计

| 阶段 | 预估 | 并行度 |
|------|------|-------|
| Step 1-2: 读状态 + 验证 health | 5min | 串行 |
| Step 3: 配置清洗 | 15min | 串行 |
| Step 4: 修复 E2E 测试 | 20min | 串行 |
| Step 5: 配置审计 | 15min | 独立 |
| Step 6: 验证 | 15min | 串行 |
| Step 7: 记录状态 | 5min | 串行 |
| **Total** | **~75min** | |

---

## 九、关键注意事项

1. **不要重写 agora-services.json 从零** — 保留现有 9 个服务，只删除测试条目。删除前先备份。
2. **agora web 可能正在运行** — 如果运行中，配置修改会被进程覆写。优先停掉再改，或者改完重启。
3. **`make check-config` 要作为 pre-commit hook** — 不只是 Makefile target，最好注册到 `.git/hooks/pre-commit`
4. **验证比修复重要** — 每一步修改后都要验证 CLI 输出，不要全部改完再验证
5. **遇到不认识的服务名不要猜** — 检查项目目录是否存在。不存在的一律删除。
