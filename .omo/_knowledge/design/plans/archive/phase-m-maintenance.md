# Phase M — 运维保障方案

> 目标: 在 8.8/10 的基础上稳住，防止退化
> 原则: 不建新功能，只做运维、测试、文档、安全

---

## TL;DR

```
问题: 24 项目经过 ~17h 迭代达到 8.8/10，但运维成熟度提升最快 (=也最容易退化)
方案: 3 个 Sprint，每个 Sprint 一个维度

Sprint M1 — 运维保障 (~3h)
  cron 实际运行验证 + 备份恢复演练 + 健康检查巡检

Sprint M2 — 测试维持 (~2h)
  阈值自动化 + 退化告警 + 测试覆盖率报告

Sprint M3 — 文档同步 (~2h)
  AGENTS.md 季度刷新 + CLEANUP 执行 + Secrets 轮换
```

## Sprint 架构

```
M1 运维保障 (Wave M1.1-M1.3, 3h)
├── M1.1 cron 运行验证 + 日志检查 [1h]
├── M1.2 备份恢复演练 [1h]
└── M1.3 健康检查巡检全服务 [1h]

M2 测试维持 (Wave M2.1-M2.2, 2h)
├── M2.1 TST-01 阈值自动化 + CI 集成 [1h]
└── M2.2 退化告警脚本 + 周报模板 [1h]

M3 文档同步 (Wave M3.1-M3.2, 2h)
├── M3.1 AGENTS.md 审计 + CLEANUP 执行 [1h]
└── M3.2 API Key 轮换 + SECRETS 快照 [1h]

总工时: ~7h | 可并行: M1.1 + M2.1 + M3.1 (3 并行)
```

---

## TODOs

- [ ] 1. cron 运行验证 + 日志检查

  **What to do**:
  - 检查 crontab 中 freshness/backup cron 是否实际执行过
  - `ls -la ~/.hermes/logs/x2-freshness.log ~/.hermes/logs/x2-backup.log`
  - 如果日志文件为空或不存在，手动触发 cron 一次：
    `python3 ~/.hermes/scripts/x2-freshness-cron --dry-run`
    `python3 ~/.hermes/scripts/x2-backup-brain`
  - 检查日志中是否有报错
  - 如果 cron 未生效，重新安装 crontab

  **Acceptance**:
  - [ ] freshness 日志有最近执行记录
  - [ ] backup 日志有最近备份记录 (43+ files)

  **Agent**: quick

- [ ] 2. 备份恢复演练

  **What to do**:
  - 找一个已备份的 SQLite 文件，验证可以恢复
  ```bash
  BACKUP=$(ls -t ~/Workspace/SharedBrain/data/db/backup/*/core/messages.db 2>/dev/null | head -1)
  if [ -n "$BACKUP" ]; then
    # 验证备份文件完整性
    sqlite3 "$BACKUP" "PRAGMA integrity_check;"
    echo "Backup restore test: file valid"
  fi
  ```
  - 验证最近的备份不是空文件（size > 0）
  - 报告最早和最新备份的日期

  **Acceptance**:
  - [ ] 至少一个备份文件 integrity_check 通过
  - [ ] 备份目录有时间范围记录

  **Agent**: quick

- [ ] 3. 健康检查巡检全服务

  **What to do**:
  - 运行 `~/.hermes/scripts/validate-HP-health-check` 验证所有 HTTP 服务的 /healthz
  - 对每个未运行的服务（端口未监听），检查其代码中的启动配置是否正常
  - 记录哪些服务实际在运行，哪些是代码就绪但未启动
  - 输出巡检报告：
  ```
  服务巡检报告 (2026-05-28)
  agentmesh Gateway(:3000): 代码就绪/未运行
  Agora(:7430):             代码就绪/未运行
  minerva(:8765):           代码就绪/未运行
  hermes-webui(:8787):      代码就绪/未运行
  ```

  **Acceptance**:
  - [ ] 巡检脚本执行完成不报错
  - [ ] 输出 4 个服务的健康状态

  **Agent**: quick

- [ ] 4. TST-01 阈值自动化

  **What to do**:
  - 将 `validate-TST-minimal-coverage` 集成到项目 CI 中
  - 对每个有 CI 的项目，在 CI 配置中添加一步：
    `python3 ~/.hermes/scripts/validate-TST-minimal-coverage --ci`
  - 对没有 CI 的项目（Iris/SSOT/hermes-scripts/Forge），在 pre-commit 中添加检查
  - 确保 `validate-TST-minimal-coverage` 在测试数低于阈值时 exit code 1

  **Acceptance**:
  - [ ] 有 CI 的项目 CI 配置文件包含测试阈值检查
  - [ ] `validate-TST-minimal-coverage --ci` 在测试低于阈值时返回 1

  **Agent**: quick

- [ ] 5. 退化告警脚本 + 周报模板

  **What to do**:
  - 创建 `~/.hermes/scripts/x2-health-report`
  - 功能: 每周运行一次，生成系统健康报告
  - 检查项:
    - 各项目测试数是否仍高于阈值
    - 最近备份日期是否 < 7 天
    - freshness cron 最近执行是否 < 7 天
    - /healthz 端点是否可达（按 1.3 巡检结果）
  - 输出格式:
  ```
  === 系统健康周报 ===
  日期: 2026-05-28
  
  ✅ 测试覆盖: 所有项目高于阈值
  ✅ 备份状态: 最近备份 <7 天
  ⚠️ 服务运行: 4/4 代码就绪, 0/4 在运行
  ✅ 保鲜执行: <7 天
  ```

  **Acceptance**:
  - [ ] `x2-health-report` 可执行
  - [ ] 输出包含测试/备份/服务/保鲜四维状态

  **Agent**: quick

- [ ] 6. AGENTS.md 审计 + CLEANUP 执行

  **What to do**:
  - 对照 AGENTS.md 中的项目列表，逐一验证：
    - 项目目录是否存在
    - AGENTS.md 中的定位是否准确
    - 是否有新项目未被收录
  - 如果有归档项目（如 AggreSearch）已无任何引用，标记删除
  - 执行 CLEANUP.md 中的清理命令（删除 30 天前的旧计划/总结文件）

  **Acceptance**:
  - [ ] AGENTS.md 当前审查通过（无过期条目）
  - [ ] CLEANUP 已执行（30天前的旧文件已删除）

  **Agent**: quick

- [ ] 7. API Key 轮换 + SECRETS 快照

  **What to do**:
  - 运行 `python3 ~/.hermes/scripts/setup-auth-keys` 生成新密钥
  - 更新 `~/.hermes/secrets/{service}/.env` 中的密钥
  - 创建当前 Secret 的快照（不含值的目录结构快照）到 `SECRETS_INVENTORY.md`
  - 更新 SECRETS_INVENTORY.md 中的 `Last Rotated` 日期

  **Acceptance**:
  - [ ] 所有服务的 .env 已更新新密钥
  - [ ] SECRETS_INVENTORY.md 中 Last Rotated 为当前日期

  **Agent**: quick

---

## 执行并行度

```
Wave M1: ─┬─ M1.1 cron验证 + M1.2 备份演练 + M1.3 巡检 (3 并行)
           │   全部完成后
Wave M2: ─┬─ M2.1 阈值自动化 + M2.2 周报模板 (2 并行)
           │   全部完成后  
Wave M3: ─┬─ M3.1 AGENTS审计 + CLEANUP + M3.2 Key轮换 (2 并行)

总串行: 3 Wave | 每 Wave 内并行
总工时: ~7h
```
