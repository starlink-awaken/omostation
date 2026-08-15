import sys

with open('bin/gac/gac-worktree.sh', 'r') as f:
    lines = f.readlines()

insert_idx = -1
for i, line in enumerate(lines):
    if line.startswith("  bump-pointer)"):
        insert_idx = i
        break

bump_fast_code = """
  bump-fast)
    sub="${2:-}"
    arg2="${3:---latest-main}"
    [ -z "$sub" ] && echo "用法: bump-fast <submodule-path> [--sha <sha>|--latest-main]" >&2 && exit 1
    
    # 1. Extract URL
    sub_url=$(git config --file .gitmodules --get "submodule.$sub.url" || true)
    [ -z "$sub_url" ] && { echo "❌ 找不到子模块 $sub 的 URL 配置" >&2; exit 1; }
    
    # 2. Check reachability via ls-remote
    main_tip=$(git ls-remote "$sub_url" refs/heads/main | awk '{print $1}')
    [ -z "$main_tip" ] && { echo "❌ 无法通过 ls-remote 访问远端 main" >&2; exit 1; }
    
    if [ "$arg2" = "--latest-main" ]; then
        new_sha="$main_tip"
    elif [[ "$arg2" == --sha* ]]; then
        if [ "$arg2" = "--sha" ]; then
            new_sha="${4:-}"
        else
            new_sha="${arg2#--sha=}"
        fi
        [ -z "$new_sha" ] && { echo "❌ 缺少 sha 值" >&2; exit 1; }
        
        if [ "$new_sha" != "$main_tip" ]; then
            echo "❌ SHA $new_sha 在远端 main 不可达 (与 main tip $main_tip 不匹配)" >&2
            exit 1
        fi
    else
        echo "❌ 未知参数: $arg2" >&2
        exit 1
    fi
    
    # 3. Update cacheinfo
    git update-index --cacheinfo 160000,"$new_sha","$sub"
    echo "✅ 指针已更新: $sub → $new_sha (bump-fast)"
    
    # 4. Sync version in project-registry.yaml
    sub_name=$(basename "$sub")
    if grep -q "^  $sub_name:" docs/project-registry.yaml 2>/dev/null; then
        if [[ "$sub_url" == *github.com* ]]; then
            raw_url=$(echo "$sub_url" | sed 's|github.com|raw.githubusercontent.com|' | sed 's|\\.git$||')
            pyproject=$(curl -sf "$raw_url/$new_sha/pyproject.toml" || true)
            if [ -n "$pyproject" ]; then
                version=$(echo "$pyproject" | grep -m1 "^version =" | cut -d'"' -f2 | cut -d"'" -f2 || echo "")
                if [ -n "$version" ]; then
                    python3 -c "
import re
with open('docs/project-registry.yaml', 'r') as f:
    text = f.read()
pattern = r'(  '$sub_name':\\n(?:    .*\\n)*?    version: \").*?(\")'
new_text = re.sub(pattern, r'\\g<1>'$version'\\g<2>', text)
with open('docs/project-registry.yaml', 'w') as f:
    f.write(new_text)
"
                    echo "   ✅ 同步更新 docs/project-registry.yaml 中的 version 到 $version"
                fi
            fi
        fi
    fi
    ;;
"""

if insert_idx != -1:
    lines.insert(insert_idx, bump_fast_code)
    with open('bin/gac/gac-worktree.sh', 'w') as f:
        f.writelines(lines)
    print("Patched successfully")
else:
    print("Could not find bump-pointer)")
    sys.exit(1)
