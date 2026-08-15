with open("bin/gac/gac-worktree.sh") as f:
    text = f.read()

target = """pattern = r'(  '$sub_name':\\n(?:    .*\\n)*?    version: \\").*?(\\")'"""
replacement = """pattern = r\"\"\"(  '$sub_name':\\n(?:    .*\\n)*?    version: \\").*?(\\")\"\"\""""

if target in text:
    with open("bin/gac/gac-worktree.sh", "w") as f:
        f.write(text.replace(target, replacement))
    print("Patched pattern")
else:
    print("Target not found")
