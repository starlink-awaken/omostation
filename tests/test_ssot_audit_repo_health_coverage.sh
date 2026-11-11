#!/usr/bin/env bash
set -euo pipefail
# repo-health-daily 的告警覆盖面必须可见 (缺生可见)。
#
# 缺陷 (2026-11-11 自证): repo-health-daily.yml 用 `--limit 5` 跑审计, 但报告与
# issue 都不提覆盖面 —— 仓组共 17 个仓库 (1 主 + 16 子模块), 读者会以为告警覆盖
# 全部, 实际只有前 5 个; 排在第 6 位之后的高风险仓库永远不会被点名。
#
# 判据: 报告输出 total_repos / audited_repos, markdown 明写 N/M, 且 limit 生效时
# audited < total。
#
# 本测试 stub 掉 `gh` (脚本对 gh 失败是 fail-soft), 全程无网络。

repo_root=$(cd "$(dirname "$0")/.." && pwd)
script="$repo_root/bin/ssot/audit-repo-health.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/bin"
cat > "$tmp/bin/gh" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
chmod +x "$tmp/bin/gh"
export PATH="$tmp/bin:$PATH"

make_repo() {
  local path="$1" origin="$2"
  mkdir -p "$path"
  git -C "$path" init -q
  git -C "$path" config user.email test@example.com
  git -C "$path" config user.name test
  touch "$path/tracked.txt"
  git -C "$path" add tracked.txt
  git -C "$path" commit -qm init
  git -C "$path" remote add origin "$origin"
}

parent="$tmp/parent"
sub="$tmp/sub"
make_repo "$sub" "git@github.com:owner/sub-repo.git"
make_repo "$parent" "git@github.com:owner/parent-repo.git"
git -C "$parent" -c protocol.file.allow=always submodule add "$sub" sub >/dev/null 2>&1
git -C "$parent/sub" remote set-url origin "git@github.com:owner/sub-repo.git"

# 1) markdown 必须明写覆盖面
md=$(cd "$parent" && bash "$script" --markdown --limit 1 2>/dev/null)
printf '%s\n' "$md" | grep -Fq "覆盖面: 1/2 个仓库" || {
  printf 'markdown 未写明覆盖面 (期望 1/2):\n%s\n' "$md" >&2
  exit 1
}

# 2) json 必须带 total_repos / audited_repos, 且 limit 生效
json=$(cd "$parent" && bash "$script" --json --limit 1 2>/dev/null)
printf '%s' "$json" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['total_repos'] == 2, f\"total_repos={d['total_repos']}\"
assert d['audited_repos'] == 1, f\"audited_repos={d['audited_repos']}\"
assert len(d['repos']) == 1, f\"repos={len(d['repos'])}\"
"

# 3) 反例保护: 不限量时 audited == total
json_all=$(cd "$parent" && bash "$script" --json --limit 99 2>/dev/null)
printf '%s' "$json_all" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['total_repos'] == 2, f\"total_repos={d['total_repos']}\"
assert d['audited_repos'] == 2, f\"audited_repos={d['audited_repos']}\"
assert len(d['repos']) == 2, f\"repos={len(d['repos'])}\"
"

echo "ok: repo-health coverage visible"
