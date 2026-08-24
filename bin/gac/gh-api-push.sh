#!/bin/bash
# gh-api-push.sh — 通过 GitHub API 推送交付物到分支 (内置 base_tree 完整快照 + workflows 校验)
#
# 背景: BASE-TREE-SNAPSHOT golden rule (2026-08-24 T10 验收会话).
#   GitHub Git Data API 的 tree 参数是"完整快照"不是 patch —— base_tree=None 时
#   只列变更 blobs 会删除其余整棵树 (曾把 .github/workflows 整个删掉 → CI 0 runs).
#   本脚本把所有安全行为内置: base_tree=父 commit 完整 tree + 变更 blobs +
#   推送后验证 .github/workflows 存在, 防止复发.
#
# 用法:
#   gh-api-push.sh <owner> <repo> <branch> <base-ref> "<commit-msg>" <file1> [file2 ...]
#
# 示例:
#   bash bin/gac/gh-api-push.sh starlink-awaken omostation work/xxx main \
#     "chore: deliver xxx" docs/xxx.md bin/xxx.sh
#
# 前置: gh CLI 已认证 (gh auth status), 对目标 repo 有写权限.
# 依赖: gh api (Git Data API), python3 (JSON 处理).

set -euo pipefail

if [ "$#" -lt 6 ]; then
  echo "用法: gh-api-push.sh <owner> <repo> <branch> <base-ref> <commit-msg> <file...>" >&2
  exit 2
fi

OWNER="$1"; REPO="$2"; BRANCH="$3"; BASE_REF="$4"; COMMIT_MSG="$5"; shift 5

if [ "$#" -lt 1 ]; then
  echo "❌ 至少需要一个文件" >&2
  exit 2
fi

# base-ref 可以是 ref 名 (main) 或完整 sha
BASE_SHA="$(gh api "repos/${OWNER}/${REPO}/git/ref/heads/${BASE_REF}" --jq .object.sha 2>/dev/null \
  || gh api "repos/${OWNER}/${REPO}/git/commits/${BASE_REF}" --jq .sha 2>/dev/null)"
if [ -z "$BASE_SHA" ]; then
  echo "❌ 无法解析 base-ref: $BASE_REF" >&2
  exit 1
fi
echo "🧭 base: $BASE_REF @ ${BASE_SHA:0:12}"

# 1) 若分支不存在则基于 base 创建
if ! gh api "repos/${OWNER}/${REPO}/git/ref/heads/${BRANCH}" >/dev/null 2>&1; then
  gh api -X POST "repos/${OWNER}/${REPO}/git/refs" \
    -f "ref=refs/heads/${BRANCH}" -f "sha=${BASE_SHA}" >/dev/null
  echo "🌿 分支创建: $BRANCH"
fi

# 2) 父 commit = 当前分支头 (若分支 == base, 用 base sha)
PARENT_SHA="$(gh api "repos/${OWNER}/${REPO}/git/ref/heads/${BRANCH}" --jq .object.sha)"
# 3) 父 commit 的完整 tree —— base_tree 必须指向它
BASE_TREE="$(gh api "repos/${OWNER}/${REPO}/git/commits/${PARENT_SHA}" --jq .tree.sha)"
echo "🌳 base_tree: ${BASE_TREE:0:12} (父 commit 完整快照)"

# 4) 上传变更 blobs
python3 - "$OWNER" "$REPO" "$BASE_TREE" "$@" <<'PY'
import base64, json, subprocess, sys
owner, repo, base_tree = sys.argv[1], sys.argv[2], sys.argv[3]
files = sys.argv[4:]

def gh(*a):
    r = subprocess.run(["gh", "api", *a], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {a[0]} failed: {r.stderr[:300]}")
    return json.loads(r.stdout)

blobs = []
for f in files:
    try:
        content = open(f, "rb").read()
    except OSError as e:
        raise RuntimeError(f"读取失败 {f}: {e}")
    b = gh("-X", "POST", f"repos/{owner}/{repo}/git/blobs",
           "-f", "encoding=base64", "-f", f"content={base64.b64encode(content).decode()}")
    blobs.append({"path": f, "mode": "100644", "type": "blob", "sha": b["sha"]})
    print(f"  blob {f} {b['sha'][:10]}")

body = {"base_tree": base_tree, "tree": blobs}
r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{owner}/{repo}/git/trees",
                    "--input", "-"], input=json.dumps(body), capture_output=True, text=True)
if r.returncode != 0:
    raise RuntimeError(f"tree 创建失败: {r.stderr[:400]}")
tree = json.loads(r.stdout)
print(f"🌲 tree: {tree['sha'][:12]} (base={base_tree[:12]})")
sys.stdout.flush()
import os
os.makedirs("artifacts", exist_ok=True)
json.dump({"base_tree": base_tree, "tree_sha": tree["sha"]},
          open("artifacts/gh-api-push-state.json", "w"))
PY

TREE_SHA="$(python3 -c "import json; print(json.load(open('artifacts/gh-api-push-state.json'))['tree_sha'])")"

# 5) 建 commit (parent = 分支头) 并更新分支 ref
COMMIT_SHA="$(python3 - "$OWNER" "$REPO" "$TREE_SHA" "$PARENT_SHA" "$COMMIT_MSG" <<'PY'
import json, subprocess, sys
owner, repo, tree, parent, msg = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
body = {"message": msg, "tree": tree, "parents": [parent]}
r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{owner}/{repo}/git/commits",
                    "--input", "-"], input=json.dumps(body), capture_output=True, text=True)
if r.returncode != 0:
    raise RuntimeError(f"commit 失败: {r.stderr[:400]}")
print(json.loads(r.stdout)["sha"])
PY
)"
echo "📦 commit: ${COMMIT_SHA:0:12}"

gh api -X PATCH "repos/${OWNER}/${REPO}/git/refs/heads/${BRANCH}" \
  -F "sha=${COMMIT_SHA}" -F "force=true" >/dev/null
echo "🔗 ref 更新: $BRANCH → ${COMMIT_SHA:0:12}"

# 6) 关键验证: .github/workflows 必须存在 (BASE-TREE-SNAPSHOT 铁律)
WF_COUNT="$(gh api "repos/${OWNER}/${REPO}/contents/.github/workflows?ref=${BRANCH}" --jq 'length' 2>/dev/null || echo 0)"
if [ "$WF_COUNT" -lt 1 ]; then
  echo "❌ .github/workflows 不存在 (branch=${BRANCH})! base_tree 可能不是完整快照, 立即停止." >&2
  exit 1
fi
echo "✅ 验证: .github/workflows 存在 ($WF_COUNT 个 workflow) — CI 可正常触发"

echo "🎉 推送完成: $BRANCH @ ${COMMIT_SHA:0:12}"
