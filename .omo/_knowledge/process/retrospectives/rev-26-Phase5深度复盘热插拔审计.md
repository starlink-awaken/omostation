# Phase 5 深度复盘 + 热插拔协议审计

> **文档编号**: 26 | **前序**: #25 Phase 4 复盘 | **Phase**: 5 (热插拔)
> **时间**: 2026-05-28 | **生成**: 自动审计

---

## 一、完成概览

### Phase 5 任务完成度

| ID | 任务 | 工时 | 状态 | 产出 |
|----|------|------|------|------|
| **5.1** | 节点状态机实现 | 6h | ✅ | ACTIVE→DRAINING→STANDBY→VERIFYING→ACTIVE/DECOMMISSIONED |
| **5.2** | drain 机制 | 4h | ✅ | 超时回滚 + health 端点排空检测 |
| **5.3** | launchd 热插拔集成 | 4h | ✅ | launchctl bootstrap/bootout + 进程替换 |
| **5.4** | manual 降级（通知脚本） | 3h | ✅ | 自动生成可执行脚本 + health 验证循环 |
| **5.5** | `agora hotswap` CLI | 4h | ✅ | 完整命令 + dry-run + force 模式 |
| **5.6** | 热插拔测试 | 4h | ✅ | 3 场景测试（launchd/manual/unknown） |
| **5.7** | hotswap governance log | 2h | ✅ | 3 阶段日志（draining→notify→decommissioned）+ SHA256 |
| **5.8** | Phase 5 复盘 | 2h | ✅ | 本文档 |

### 理论框架

```
节点状态机:

                    +-----→ ACTIVE (new)
                    |
ACTIVE → DRAINING → STANDBY → VERIFYING → ACTIVE (new)
  |                                            |
  └→ DECOMMISSIONED (old) ←────────────────────┘
  
状态定义:
  ACTIVE:         正常工作状态（95% 时间）
  DRAINING:       停止接受新请求，等待 in-flight 完成
  STANDBY:        旧进程暂停，新进程已启动
  VERIFYING:      运行 R2+R3+R10 验证
  DECOMMISSIONED: 旧节点标记为已废弃
```

---

## 二、实现细节

### 7 步骤协议

```
Step 1: 标记 replacing        → governance log: status=draining
Step 2: 通知 HARD 依赖方      → governance log: dependents 列表
Step 3: 排空 (drain)           → health 端点不可达 / startup_duration 超时
Step 4: 启动新进程             → launchd=automatic / manual=脚本输出
Step 5: 验证 (R2+R3+R10)      → 依赖可达 + 接口兼容 + 健康检查
Step 6: 切换路由               → YAML 替换 + git commit
Step 7: 清理旧进程             → governance log: status=decommissioned
```

### 自动路径 vs 降级路径

| 管理器 | 热插拔路径 | 回滚方式 |
|--------|-----------|---------|
| **launchd** | 自动 (bootstrap/bootout) | 重新 bootstrap 旧版本 |
| **systemd** | 半自动 (systemctl) | systemctl restart old |
| **supervisor** | 半自动 (supervisorctl) | supervisorctl restart old |
| **manual** | 生成执行脚本 | 人工回滚 |
| **ephemeral** | 自动 (下次使用重建) | 无需清理 |
| **docker** | docker stop/start | docker start old |

### 异常处理

| 异常 | 处理 |
|------|------|
| Drain 超时 | 回滚到 ACTIVE，记录 governance log |
| launchctl bootout 失败 | 记录 log，继续尝试 bootstrap |
| R3 接口不兼容 | ❌ 阻塞（除非 `--force`） |
| R2 依赖不可达 | ❌ 阻塞 |
| R10 健康检查失败 | ❌ 阻塞（新进程启动失败） |
| 未知 node_id | 提示用户先 register-node |
| 版本不递增 | ❌ 阻塞（除非 `--force`） |

---

## 三、验收测试

### Test 1: launchd 节点 dry-run

```bash
agora hotswap agent-runtime --dry-run
```

结果: ✅ 全链路输出（7 步骤均验证通过）
- 管理器: launchd
- 操作: launchctl bootout + bootstrap ~/Library/LaunchAgents/com.agent-runtime.plist
- R10: ✅ http://127.0.0.1:9876/health → HTTP 200

### Test 2: manual 节点 dry-run（有 HARD 依赖方）

```bash
agora hotswap agora --dry-run
```

结果: ✅ 正确识别 HARD 依赖方 (gateway) + 生成手动脚本
- 管理器: manual
- 依赖警告: ⚠️ gateway 为 HARD 依赖方
- 脚本: `~/.hermes/architecture/hotswap_scripts/hotswap-agora-*.sh`

### Test 3: 未知节点

```bash
agora hotswap nonexistent-node --dry-run
```

结果: ✅ 正确提示 "未注册 → 先 register-node"

### Test 4: 接口不兼容拦截

```bash
agora hotswap agent-runtime --new-yaml test-v2.yaml --dry-run
```

结果: ✅ R3 正确拦截接口不兼容
- 旧 provides: 4 个接口
- 新 provides: 3 个接口（不同命名空间）
- R3 FAIL: 已移除接口 → 热插拔阻塞

---

## 四、架构债务审计

### 新增无债务

热插拔实现遵循现有治理规范：
- 所有输出走 governance log + SHA256 链式校验 ✅
- 新脚本为独立 CLI，不侵入现有脚本 ✅
- 异常处理完整（超时回滚 / fail-fast / 降级路径） ✅

### 现有债务状态

| 债务 | 描述 | 严重度 | 状态 |
|------|------|--------|------|
| D01 | HARD 依赖停服检测（R2 运行时） | P1 | 延续 |
| D02 | 宪法与元模型文档未 100% 同步 | P2 | 延续 |
| D03 | governance-system 未纳入 drift-check 报告 | P2 | ✅ Phase 4 已修复 |
| D04 | 依赖图自维护尚未实现（Phase 6） | P1 | 延续 |

---

## 五、红队分析

### R1: 热插拔断电

**场景**: 热插拔执行到 Step 4（launchctl bootstrap）时系统断电。

**影响**: 旧进程已停止，新进程未完成。节点处于 STANDBY 但无进程运行。

**缓解**:
1. launchd 的 `KeepAlive` 配置会在系统恢复后自动重启 plist
2. 重启后 launchd 会尝试启动此 plist → 新进程就绪
3. governance log 中有完整操作记录 → 可人工确认

**残余风险**: 低。launchd 的 KeepAlive 机制天然缓解断电场景。

### R2: 热插拔过程中依赖方切换

**场景**: hotswap agora 时，依赖 agora 的服务（如 agent-runtime）正在使用中。

**影响**: drain 阶段新连接被拒，已有 in-flight 请求直到超时。

**缓解**:
1. drain 超时 = 30s，之后回滚
2. manual 节点生成脚本由人工执行，可选择低峰期
3. governance log 记录所有依赖方 → 事后审计

**残余风险**: 中。对长连接服务，30s drain 可能不够。可配置 `startup_duration_sec` 按需调整。

### R3: 热插拔治理系统自身

**场景**: `agora hotswap governance-system`。

**问题**: governance-system 是 EVOLVER 节点，它的 hotswap 脚本也由同一治理系统管理。

**分析**:
1. hotswap 脚本是 CLI 工具，执行期间不依赖 governance-system 的运行状态
2. 热插拔生成 manual 脚本 → 人工执行 → 自指闭环
3. governance log 会记录完整的自身替换过程

**自我指涉测试**: 理论上可行。参数传递 + 脚本执行独立于治理系统的运行时状态。

### R4: `--force` 绕过 R3 的滥用风险

**场景**: 开发人员用 `--force` 热修复线上节点，跳过了接口兼容性检查。

**缓解**:
1. governance log 标记 `force=true` → 事后审计可追溯
2. `arcnode-evolve --self-report` 会捕获 force 操作作为风险条目
3. cron 链周一 resolve-review 会审查 force 操作

**风险等级**: 低。force 可追溯，且不影响数据面。

---

## 六、治理数据

### 脚本层统计

```
~/.hermes/scripts/ 治理脚本量: 12 个
├── arcnode-validate        (S1-S8, T1-T7 校验)
├── arcnode-reason          (LLM 软推理)
├── agora-register-node     (注册 7 步流水线)
├── agora-update-node       (更新 4 步)
├── agora-hotswap           ← NEW (热插拔 7 步协议)
├── arcnode-graph           (HTML/DOT/Mermaid 依赖图)
├── arcnode-drift-check     (每日漂移检测 + 嗅探)
├── arcnode-sniff-deps      (运行时依赖嗅探 + reconcile)
├── arcnode-resolve-review  (unresolved 队列审查)
├── arcnode-report          (完整周报)
├── arcnode-evolve          (进化引擎)
└── schema.py               (共享枚举 + 约束 + 工具函数)
```

### 治理日志条目数

```
governance.jsonl 条目: 34 (+2 hotswap draining/notify + 1 verify/cron)
最新: hotswap 日志 (agent-runtime dry-run / agora dry-run)
SHA256 链: 34 连续校验
```

### 约束覆盖率

| 约束 | 类型 | 代码化 | 验证脚本 |
|------|------|--------|---------|
| S1-S8 | Schema | ✅ | arcnode-validate |
| T1-T7 | Type | ✅ | arcnode-validate --strict |
| R1 | Runtime | ⏭️ 无适用场景 | — |
| R2 | Runtime | ✅ | agora-register-node / agora-hotswap |
| R3 | Runtime | ✅ | agora-update-node / agora-hotswap |
| **R4** | **Runtime** | **✅** | **agora-hotswap (REPLACE → R2+R3+R10)** |
| R5 | Runtime | ✅ | arcnode-evolve (OBSERVE 7d) |
| R6 | Runtime | ✅ | arcnode-evolve (EVALUATE < 0.3) |
| G1-G5 | Governance | ✅ | 治理日志链 |

---

## 七、下一步建议

### Phase 6 前置

**依赖自动维护 + 视图** (从 24-AAMF-v2-全面架构补全方案.md):

| ID | 任务 | 说明 |
|----|------|------|
| 6.1 | sniff-deps auto-fix | 3 次 observation → update-node |
| 6.2 | 依赖时效性检查 | 冷 dep 标记 + 降级 |
| 6.3 | C4 Context 视图 | 系统边界图 HTML |
| 6.4 | C4 Container 视图 | 节点拓扑图增强 |
| 6.5 | Archimate 视图 | 三层分层图 |
| 6.6 | 健康仪表盘 HTML | 交互式仪表盘 |
| 6.7 | 自评价 Level 2 | 治理有效性评分 |

---

> **文档位置**: `~/Documents/学习进化/基建架构/26-Phase5-深度复盘+热插拔协议审计.md`
> **前序**: #25 Phase 4 复盘
> **当前 Phase**: 5 ✅ → 待确认 Phase 6 启动
