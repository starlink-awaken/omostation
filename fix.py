import re

with open("bin/gac/gac-worktree.sh", "r") as f:
    lines = f.readlines()

new_lines = []
in_python = False
for i, line in enumerate(lines):
    if "python3 -c" in line and "import re" in lines[i+1]:
        in_python = True
        new_lines.append(line)
        new_lines.append(lines[i+1]) # import re
        new_lines.append(lines[i+2]) # with open
        new_lines.append(lines[i+3]) # text =
        new_lines.append('pattern = r"""(  \'$sub_name\':\\n(?:    .*\\n)*?    version: \\").*?(\\")"""\n')
        new_lines.append('new_text = re.sub(pattern, r\'\\g<1>$version\\g<2>\', text)\n')
        new_lines.append(lines[i+6]) # with open write
        new_lines.append(lines[i+7]) # f.write
        new_lines.append(lines[i+8]) # "
        continue
    if in_python:
        if line.strip() == '"':
            in_python = False
        continue
    if not in_python:
        new_lines.append(line)

with open("bin/gac/gac-worktree.sh", "w") as f:
    f.writelines(new_lines)
