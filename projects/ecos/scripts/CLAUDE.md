# eCOS 运营脚本

> v1.0 | 2026-06-07
> 本目录是 `~/.ecos/scripts/` 的核心子集 + git 版本管理副本。

## 与 ~/.ecos/scripts/ 的关系

| | ~/.ecos/scripts/ | ecos/scripts/ |
|:--|:-----------------|:--------------|
| **角色** | 运行时路径（所有 33 脚本） | 版本管理副本（14 核心脚本） |
| **修改** | 直接编辑（无版本管理） | git 管理 |
| **同步** | 手动复制 `cp ecos/scripts/*.py ~/.ecos/scripts/` |

**原则**: 新开发 → 在 `ecos/scripts/` 改 → 复制到 `~/.ecos/scripts/` 上线。

## 核心脚本清单

| 脚本 | 功能 | daemon 周期 |
|------|------|:-----------:|
| `ecos-daemon.py` | 自治运维守护进程 (6h) | 主循环 |
| `ecos-weekly-digest.py` | 每周健康摘要 | 每 28 周期 |
| `ecos-sla-tracker.py` | SLA 记录 | 每周期 |
| `ecos-healer.py` | 自治愈 | 有错误时 |
| `bos-registry-daemon.py` | BOS 路由自动同步 | 手动/定时 |
| `check-disk-usage.py` | SharedDisk 空间告警 | 每周期 |
| `ecos-onboard.py` | 新机器引导 | 一次性 |
| `ecos-bootstrap.py/sh` | 冷启动安装 | 一次性 |

## 迁移

```bash
# 修改后同步到运行路径
cp scripts/*.py ~/.ecos/scripts/

# 新增脚本注册
cp new-script.py ~/.ecos/scripts/
git add scripts/new-script.py
```


## 架构变更 2026-06-07

**之前**: ~/.ecos/scripts/ 独立目录 (33 脚本, 无版本管理)
**之后**: ~/.ecos/scripts/ → symlink → ecos/scripts/ (39 脚本, git 版本管理)

修改后直接生效, 无需复制:
  vim scripts/ecos-daemon.py
  python3 ~/.ecos/scripts/ecos-daemon.py --once
  git add scripts/ && git commit -m "fix daemon paths"

回滚: ~/.ecos/scripts.bak/ 是原始备份
