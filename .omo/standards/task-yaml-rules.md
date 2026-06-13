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

---

## 规则 5: plan.yaml gate_status 单一字段 (CR-CS-06, 2026-06-13)

**禁止** plan.yaml (在 `.omo/tasks/planned/`) self-add 衍生状态字段, 包括但不限于:

- `readiness_status` (不得与 `gate_status` 并列)
- `cadence_status` (不得与 `gate_status` 并列)
- `sub_gate_status` (不得作为子级 gate_status)
- 任何 `*_status` 衍生字段 (除非白名单)

**唯一合法 status 字段**:
- `gate_status: not_yet_passed` (默认)
- `gate_status: conditionally_passed`
- `gate_status: passed`

**衍生信息只允许放在**:
- `gate_note: |` (YAML 块, 自由描述 readiness / cadence / drift 等)
- `assessment: |` (YAML 块, 含 drill-down 列表)

**为什么**: 2026-06-13 OPC P5-P7 8 阶段演练时, 我自加 `readiness_status: passed` + `cadence_status: not_yet_passed` 两个字段, 试图"细分" gate 状态, 但这破坏了 closeout 报告的可审计性, reviewer 一票否决。

**自动检查**: `omo governance audit` + `test_opc_phase_governance_alignment.py` (18 tests) 阻断 self-add 字段回归。

## 规则 6: fallback 不得硬编码 mode-specific 路径 (CR-CR-MODE-ENV-01, 2026-06-13)

**禁止** daemon / fallback 脚本内部硬编码:

```python
# ❌ 禁止
mode_specific_path = f"{date}-weekly.json"
if not os.path.exists(mode_specific_path):
    # fallback 双写
    with open(mode_specific_path, 'w') as f:
        json.dump(payload, f)
```

**必须** 通过 env 透传:

```python
# ✅ 正确
mode = os.environ.get("OPC_MODE", "weekly")
mode_specific_path = f"{date}-{mode}.json"
# 副本由 5repos.py (唯一 owner) 写, daemon 不双写
```

**为什么**: 2026-06-13 OPC P7-H3 closeout 时, `_run_fallback_5repos()` 硬编码 `weekly.json`, 导致 monthly/pre-release cron 复用 weekly 副本, evidence 不可审计。

**白名单**: 5repos.py (`scripts/opc_audit_rollout_5repos.py`) 是 `{date}-{mode}.json` 副本唯一 owner, 其他脚本不得再写该模式文件。

## 规则 7: multi-mode 副本单一 owner (CR-MODE-COPY-01, 2026-06-13)

**适用范围**: 任何生成 `{date}-{mode}.{json,md,yaml}` 命名约定的脚本。

**约束**:
- 副本写入权归一个脚本 (通常为 `*_5repos.py` 聚合器)
- 上层 daemon / orchestrator 只写 5repos 原始产物, 不得双写 mode-specific 副本
- 双写导致内容漂移, fallback chain 不可信

**检测方法**:
```bash
grep -l "{date}-{mode}" scripts/*.py
# 期望: 只有 opc_audit_rollout_5repos.py 命中
```

**违规示例**: `opc_p7_audit_rollout_daemon.py` 在 `_run_audit_rollout(fallback_ok path)` 内部曾写 `{date}-{mode}.json`, 2026-06-13 已撤回双写逻辑, 仅保留 5repos.json 原始产物。

## 参考 (新增 2026-06-13)

- `feedback_no_standard_weakening_20260612.md` — 禁止降标过关
- `feedback_opc_closeout_reviewer_acceptable_20260613.md` — 8 段硬结构
- `feedback_opc_cron_wrapper_trigger_injection_20260612.md` — cadence wrapper 注入
- `.omo/standards/opc-review-template.md` — 8 字段 review template
- `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml:opc_cadence_constraints` — 7 条新规
