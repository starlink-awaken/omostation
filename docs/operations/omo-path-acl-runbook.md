# OMO Path ACL 运维 Runbook（Scheme C 5c）

> ADR: 0186 · 0187 · 0189 · 0194 · 0196 · 0198 · **0199**（doctor 日常节奏）

日检 cron（ADR-0200）: `bin/gac/omo-doctor-cron.py` → `runtime/cron/omo-doctor-latest.json`  
控制台: `GET /api/omo/doctor` + Wave2 横幅（ADR-0201，streak≥3 标 ALERT）  
新机清单: [omo-bootstrap-checklist.md](./omo-bootstrap-checklist.md)

## 1. 每日 / 巡检

```bash
# 一站式（含 path-acl warn）
uv run --project projects/omo python -m omo.cli doctor
uv run --project projects/omo python -m omo.cli doctor --json | jq '.checks[] | select(.id=="path-acl")'

# 专检
uv run --project projects/omo python -m omo.cli lint path-acl --workspace-root . --json
```

- doctor 中 `path-acl` **warn 不阻断** exit（与其它 warn 一致）
- 发现 world-writable / 0777 时 detail 会提示 `omo acl plan`

## 2. 修复流程（显式 opt-in）

```bash
# A. 审阅 chmod 计划
omo acl plan --json

# B. 审阅命名 ACE 脚本（setfacl / chmod +a）
omo acl plan --acl --json

# C. 仅 chmod 修复 other-write
export OMO_OS_ACL=1
omo acl apply --yes

# D. chmod + 命名 ACE
export OMO_OS_ACL=1
omo acl apply --yes --acl
```

**红线**

| 禁止 | 原因 |
|------|------|
| CI 设置 `OMO_OS_ACL=1` | 会改 runner 主机权限 |
| 无 `--yes` 的 apply | 防手滑 |
| 对 `.omo/_truth` 写 ACE | git-owned SSOT |

## 3. 建议节奏

| 时机 | 动作 |
|------|------|
| 每日 doctor / `omo watch` | 自动带 path-acl warn |
| 合并治理 PR 后 | `omo acl plan --json` 抽查 |
| 新机 bootstrap | `plan --acl` 审阅后 `apply --yes --acl` |
| 多 agent 撞权限 | 先 doctor，再 plan，勿直接 chmod -R |

## 4. 故障分流

| 症状 | 处理 |
|------|------|
| doctor path-acl warn | `omo acl plan` → 确认 → `OMO_OS_ACL=1 apply --yes` |
| Linux 无 setfacl | apply --acl 会 soft-skip ACE，仍 strip other-write |
| macOS chmod +a 失败 | 检查用户/组是否存在；组 `omo-writers` 需运维预建 |
| 误 apply | 无自动回滚；从 plan 反向 `chmod` / `setfacl -b` 手工恢复 |

## 5. 相关命令速查

```text
omo doctor
omo lint path-acl [--strict] [--json]
omo acl plan [--acl] [--json]
omo acl apply --yes [--acl]     # needs OMO_OS_ACL=1
omo acl status                  # alias of lint path-acl
```

## 6. macOS host 验证记录（ADR-0205 · 2026-07-15）

| 项 | 结果 |
|----|------|
| 主机 | Darwin arm64 · macOS 26.5.1 |
| `setfacl` | 不存在（预期） |
| `chmod +a` 探针 | OK（temp file + `ls -le` 可见 ACE） |
| `lint path-acl` 工作树 | 5 surface 全 ok / 0 warn（mode 0o755） |
| `acl plan` | 0 chmod action |
| `acl plan --acl` | 生成 broker user `chmod +a` + optional group `omo-writers` |
| 本机 `apply --yes --acl` | **未执行**（保留 ops 窗口；需 `OMO_OS_ACL=1`） |

刷新 digest / 重验：见 ADR-0205。group ACE 前请确认 `omo-writers`（或 `OMO_ACL_GROUP`）已存在。
