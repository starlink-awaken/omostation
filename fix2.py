with open("bin/gac/gac-worktree.sh", "r") as f:
    lines = f.readlines()

new_lines = []
in_python = False
for i, line in enumerate(lines):
    if "python3 -c" in line and "import re" in lines[i+1]:
        in_python = True
        new_lines.append('                    python3 - "$sub_name" "$version" << \'PYEOF\'\n')
        new_lines.append('import sys, re\n')
        new_lines.append('sub_name = sys.argv[1]\n')
        new_lines.append('version = sys.argv[2]\n')
        new_lines.append('with open("docs/project-registry.yaml", "r") as f:\n')
        new_lines.append('    text = f.read()\n')
        new_lines.append('pattern = r"(  " + sub_name + r":\\n(?:    .*\\n)*?    version: \\\").*?(\\\")"\n')
        new_lines.append('new_text = re.sub(pattern, r"\\g<1>" + version + r"\\g<2>", text)\n')
        new_lines.append('with open("docs/project-registry.yaml", "w") as f:\n')
        new_lines.append('    f.write(new_text)\n')
        new_lines.append('PYEOF\n')
        continue
    if in_python:
        if line.strip() == '"' or line.strip() == 'PYEOF':
            in_python = False
        continue
    if not in_python:
        new_lines.append(line)

with open("bin/gac/gac-worktree.sh", "w") as f:
    f.writelines(new_lines)
