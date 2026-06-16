# Handoff: team-plan → team-exec (P44 W1 Completion)

**日期**: 2026-06-16
**任务**: 完成 P44 W1 kickoff 后续 4 件事
**关联规划**: `Plans/c2g-enchanted-coral.md`
**关联 SSOT**: `.omo/state/system.yaml` + `.omo/state/health.yaml`
**关联 P43 试点**: `.omo/_knowledge/management/retrospective-2026-06-16-p43-w0-c2g-pilot.md`

---

## Decided (4 任务分解)

### Worker-1: 修 c2g 架构脱节 (executor, sonnet)
**任务**: 装 c2g [ecos] extras + 验证 end-to-end + L0 校验
**步骤**:
1. `cd projects/c2g && uv pip install -e .[ecos]` 或 `pip install omo`
2. 验证 `from omo.omo_task_schema import validate_task_data` 可 import
3. 跑 `c2g --adapter ecos bet` 走通端到端 (用 Pitch-Valid.md)
4. 验证 eCOS 路径直接走通 (证据: c2g CLI 不输出 "Falling back to 'local' adapter" 警告字符串)
5. L0 校验: 任务 YAML 符合 `.omo/standards/task-yaml-rules.md` 7 规则
6. 关闭 `DEBT-C2G-20260616034031.yaml` (omo-debt close 命令)
7. commit + push

**验收**:
- [ ] `c2g --adapter ecos bet <pitch>` 走通,无 secondary adapter 警告
- [ ] eCOS task 落 `.omo/tasks/planned/`
- [ ] DEBT 关闭
- [ ] commit SHA 在交付 message 里

**X1-X4 治理**:
- X1 (审计): 全程 git commit, hook 阻断
- X2 (保鲜): 任务 YAML mtime < 24h
- X3 (价值栈): P0/P1 严格区分
- X4 (一致性): system.yaml / health.yaml / c2g 输出三处一致

### Worker-2: 启动 llm-gateway (executor, sonnet)
**任务**: 启动 llm-gateway:9290 + 验证 c2g 走 LLM 真路径
**步骤**:
1. 找 llm-gateway 项目位置 (`projects/llm-gateway/`)
2. 检查端口 9290 注册 (`protocols/port-registry.yaml`)
3. 启动服务 (后台或前台,记 PID)
4. 验证 endpoint `curl http://localhost:9290/v1/generate`
5. 回归 c2g: `c2g --adapter local bet Pitch-Valid.md` 应走真 LLM, 不再走 mock 应急路径
6. L0 校验: 端口在 registry,服务在 runtime 监控里
7. commit (如改了 registry)

**验收**:
- [ ] llm-gateway:9290 健康
- [ ] c2g bet 输出"提取任务成功"无 "回退到 Mock 逻辑"
- [ ] 端口注册在 port-registry.yaml
- [ ] 验证 command 输出粘贴到 evidence

**X1-X4 治理**:
- X1: 服务启动日志审计
- X2: 服务心跳保鲜
- X3: 端口合规
- X4: 跟 c2g 输出格式一致

### Worker-3: P44 W2 planned 任务分类 + gc (executor, sonnet)
**任务**: radar 分类 60 planned + gc 真跑 28d 滞留
**步骤**:
1. 跑 `python3 bin/compass_radar.py` 看当前 60 planned 状态
2. 按 priority/risk/phase/owner 分类,产出 `.omo/_delivery/p44-w2-classification.yaml`
3. 跑 `c2g --adapter local gc` (真跑,非 dry-run),归档 28d+ 滞留 Pitch
4. L0 校验: 归档的 pitch 真有 28d+ mtime
5. 验证: planned 任务数从 60 → < 30(归档 + 分类)
6. 写 `.omo/_delivery/p44-w2-planned-cleanup.md` evidence
7. commit (元数据 + decayed/ 目录)

**验收**:
- [ ] classification.yaml 60 → < 30 分类完整
- [ ] gc 真跑,decayed/ 目录有新归档
- [ ] evidence 文档含 before/after 数字
- [ ] commit 含 SSOT 改动

**X1-X4 治理**:
- X1: 分类逻辑可审计
- X2: mtime 校验严格
- X3: P0/P1/P2/P3 价值栈明确
- X4: 跟 radar 输出对得齐

### Worker-4: P44 W1 复盘 + 战略 SSOT 更新 (executor, sonnet)
**任务**: 写 P44 W1 复盘 + 更新战略 SSOT 状态
**步骤**:
1. 等 worker-1,2,3 完成 (读 git log + state)
2. 写 `.omo/_knowledge/management/retrospective-2026-06-16-p44-w1.md` (复盘, 8 字段硬性)
3. 更新 `.omo/_knowledge/management/strategic-governance-p42.md`:
   - BET-RADAR-CRON 状态: 📋 → ✅ (P44 W0 完成)
   - BET-GC-CRON 状态: 📋 → ✅ (P44 W1 完成)
   - P44 W1 evidence 段落
4. 跑 `python3 bin/compass_radar.py` 刷 health (复盘前)
5. L0 校验: 复盘结构对齐 (8 字段: 目标/状态/evidence/真问题/风险/验收/引用/签字)
6. X1-X4 治理自评

**验收**:
- [ ] 复盘 8 字段完整
- [ ] 战略 SSOT 状态更新
- [ ] health.yaml 反映新状态
- [ ] commit 含复盘 + 战略更新

**X1-X4 治理**:
- X1: 复盘可审计(commit + state)
- X2: 状态保鲜(每日更新)
- X3: 价值栈跟踪(BET 状态)
- X4: 跨文档一致(战略 + 复盘 + health)

---

## Rejected (替代方案)

- **5 个 worker 并行** (worker-1+2+3+4+verifier): 太多, 协调成本高
- **串行执行 4 个**: 浪费并行能力, W1 复盘才需要等 1-3, W1 修 c2g 和 llm-gateway 独立
- **合并 worker-4 进 worker-1**: 复盘是独立视角, 不能由修代码者自评
- **不写 P44 W1 复盘**: 用户明确要求, 不写 = 治理断链

---

## Risks (风险)

1. **worker-1 装 [ecos] 失败** (c2g omo 依赖缺): 写"已知阻塞"到交付 + 升级 debt severity
2. **worker-2 llm-gateway 启不起来** (依赖 ollama/searxng): 验证 e2e 走 mock 流程 + 交付里标注 mock 限制
3. **worker-3 误删 active 任务**: 跑前 grep 验证, 28d 阈值严格
4. **worker-4 跟 worker-1-3 抢 commit**: 串行 commit (worker-4 最后)
5. **LLM 跑 gc 误删**: 走 local adapter, 28d 阈值不用 LLM

---

## Files (关键文件)

### 复用
- `bin/compass_radar.py` — radar 包装
- `bin/check_health_ssot.py` — SSOT 校验
- `scripts/` 已有工具链 (omc-debt, omo CLI)
- `.omo/standards/task-yaml-rules.md` — 任务 YAML 规则
- `.omo/standards/C2G-Decoupling-Audit.md` — c2g 架构背景

### 修改
- `projects/c2g/.venv/` — 装 [ecos] extras (worker-1)
- `protocols/port-registry.yaml` — 端口注册 (worker-2 如缺)
- `.omo/debt/items/DEBT-C2G-20260616034031.yaml` — 关闭 (worker-1)
- `.omo/state/health.yaml` — 每次 radar 刷
- `.omo/_knowledge/management/strategic-governance-p42.md` — 更新 (worker-4)

### 新建
- `.omo/_delivery/p44-w2-classification.yaml` (worker-3)
- `.omo/_delivery/p44-w2-planned-cleanup.md` (worker-3)
- `.omo/_knowledge/management/retrospective-2026-06-16-p44-w1.md` (worker-4)
- `.omc/handoffs/team-verify-p44-w1.md` (verifier 写)
- `runtime/sandbox/decayed/*.md` (worker-3)

---

## Remaining (留给 team-verify)

- [ ] 端到端 SSOT 一致性 (system.yaml / health.yaml / c2g 输出)
- [ ] 4 个 worker 各自的 evidence 复核
- [ ] 文档完整性 (复盘 8 字段)
- [ ] 债务清理确认 (DEBT-C2G-20260616034031 关闭)
- [ ] 治理打分 (X1-X4)
- [ ] P44 W1 复盘可读性

---

*Plan: 老王 · 2026-06-16 · 状态: ready for team-exec*
