with open("bin/gac/gac-worktree.sh") as f:
    text = f.read()

target = """        if [[ "$sub_url" == *github.com* ]]; then
            raw_url=$(echo "$sub_url" | sed 's|github.com|raw.githubusercontent.com|' | sed 's|\\.git$||')
            pyproject=$(curl -sf "$raw_url/$new_sha/pyproject.toml" || true)
            if [ -n "$pyproject" ]; then"""

replacement = """        if [[ "$sub_url" == *github.com* ]]; then
            repo_path=$(echo "$sub_url" | sed -E 's|.*github\\.com[:/]([^/]+/[^/]+)(\\.git)?|\\1|' | sed 's|\\.git$||')
            pyproject=$(gh api "repos/$repo_path/contents/pyproject.toml?ref=$new_sha" -q .content 2>/dev/null | base64 -D 2>/dev/null || base64 -d 2>/dev/null || true)
            if [ -n "$pyproject" ]; then"""

if target in text:
    with open("bin/gac/gac-worktree.sh", "w") as f:
        f.write(text.replace(target, replacement))
    print("Patched")
else:
    print("Target not found")
