# OMO / omostation 新机 Bootstrap 清单

> 配套: [omo-path-acl-runbook.md](./omo-path-acl-runbook.md) · ADR-0199 · ADR-0200

## 0. 前置

- [ ] macOS / Linux 开发机，git + uv + python ≥ 3.13
- [ ] 克隆 monorepo（含 submodule 策略按仓库说明）
- [ ] `WORKSPACE` 默认 `~/Workspace`（与 crontab 一致）

```bash
cd ~/Workspace   # or your clone root
git submodule update --init projects/omo projects/ecos projects/agora projects/c2g
```

## 1. 工具与钩子

```bash
make install-hooks   # pre-push / GaC hooks（如仓库提供）
uv run --project projects/omo python -m omo.cli --help
```

- [ ] `omo doctor` 可跑
- [ ] `omo lint path-acl --json` 可跑
- [ ] `bin/gac/omo-doctor-cron.py --no-write` 可跑

## 2. 治理写面权限（5c）

```bash
omo doctor --json | jq '.checks[]|select(.id=="path-acl")'
omo acl plan --json
omo acl plan --acl --json    # 审阅 setfacl / chmod +a 脚本
```

仅在审阅通过后：

```bash
export OMO_OS_ACL=1
omo acl apply --yes          # chmod only
# omo acl apply --yes --acl  # + named ACE（组 omo-writers 需已存在）
```

- [ ] path-acl 无 world-writable / 0777（或已知可接受）
- [ ] **未**在 CI / 共享 runner 上 export `OMO_OS_ACL=1`

## 3. Operating-rhythm（可选安装）

```bash
# 预览
cat .omo/cron/operating-rhythm-crontab
# 安装（会替换用户 crontab — 先 crontab -l 备份）
# crontab .omo/cron/operating-rhythm-crontab
```

每日 09:20 会跑 `omo-doctor-cron.py`，产物：

- `runtime/cron/omo-doctor-latest.json`
- `runtime/cron/omo-doctor-history.jsonl`
- 日志：`runtime/cron/operating-rhythm-daily.log`

- [ ] 需要日检时已安装 crontab 或改用 launchd 等价条目

## 4. Wave2 演示（可选）

```bash
uv run --directory projects/c2g python -m c2g.demo_seed \
  --data-dir runtime/c2g/outcomes --reset
# Cockpit Wave2 面板 →「加载演示数据」
```

- [ ] dashboard 有 pitch / 热力 / 提案（非空基线）

## 5. 验收一分钟

```bash
omo doctor
test -f runtime/cron/omo-doctor-latest.json || \
  uv run --with pyyaml python bin/gac/omo-doctor-cron.py
jq '.highlights' runtime/cron/omo-doctor-latest.json
```

期望：`path_acl_status` 为 `ok` 或可解释的 `warn`；无 `fail`/`error`。

## 6. 红线速记

| 做 | 不做 |
|----|------|
| doctor / plan 可常跑 | CI 自动 apply ACL |
| apply 双门禁 env+yes | 对 `_truth` 写 ACE |
| cron 写 runtime/ | cron 写 `.omo/_truth` |
