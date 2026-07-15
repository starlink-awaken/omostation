# macOS `omo-writers` 组创建说明（ADR-0207 残留）

> **Agent 禁止**自动创建/修改系统组。本页仅供**人类运维**在确认多用户写面需求后执行。

## 背景

`omo acl apply --yes --acl` 会尝试：

```text
chmod +a "group:omo-writers allow list,add_file,search,..." .omo/_delivery
```

若组不存在，macOS 报：`Unable to translate 'omo-writers' to a UUID`（非致命；用户 ACE 仍可成功）。

2026-07-15 主机 apply：`applied_ok=6`，`applied_fail=1`（仅 group 条）。

## 选项 A — 创建专用组（推荐多 agent 本机）

```bash
# 1) 创建组（需管理员）
sudo dseditgroup -o create -r "OMO write surfaces" omo-writers

# 2) 把写面主体加入组（示例：当前用户 + 服务账号）
sudo dseditgroup -o edit -a "$(id -un)" -t user omo-writers

# 3) 验证
dscl . -read /Groups/omo-writers
dsmemberutil checkmembership -U "$(id -un)" -G omo-writers

# 4) 再跑 ACE apply
export OMO_OS_ACL=1
bash bin/gac/omo-acl-ops-window.sh --workspace-root="$HOME/Workspace" --apply --yes --acl
ls -led .omo/_delivery
```

## 选项 B — 复用已有组（**单人 macOS 推荐 · ADR-0208**）

无需 sudo。本机用户通常已在 `staff`：

```bash
id -Gn | tr ' ' '\n' | head   # 确认含 staff
export OMO_ACL_GROUP=staff
export OMO_OS_ACL=1
bash bin/gac/omo-acl-ops-window.sh --workspace-root="$HOME/Workspace" --apply --yes --acl
ls -led .omo/_delivery
```

**实证（2026-07-15）**：`applied_ok=7` / `applied_fail=0`；  
`.omo/_delivery` 上同时有 `group:staff` + `user:<broker>` ACE。

> 注意：`staff` 面较宽，仅适合个人开发机。多用户生产机请用选项 A。

配置也可写在 `projects/omo/etc/omo-path-acl.yaml` 的 ACL entries（若已支持 group 字段覆盖）— 以 profile SSOT 为准。

## 选项 C — 暂不建组

可接受：仅 broker 用户 ACE 已落地（ADR-0207）。  
group ACE 失败不影响用户 ACE。若需要 group ACE 又无 sudo，优先选项 B。

## 回滚（谨慎）

```bash
# 查看
ls -led .omo/state .omo/_control .omo/_delivery

# 移除某条 ACE（示例：需按 ls -le 序号）
# chmod -a# 0 .omo/_delivery
```

无自动回滚；操作前建议 Time Machine / 快照。

## 相关

- ADR-0207 · ADR-0206 · [omo-path-acl-runbook.md](./omo-path-acl-runbook.md)
