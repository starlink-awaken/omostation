
with open('/Users/xiamingxing/Workspace/projects/ecos/src/ecos/ssot/mof/m3.yaml', 'r') as f:
    lines = f.readlines()

# Extract lines 435-561 (0-indexed 434 to 561)
start_idx = 434
end_idx = 561
extracted = lines[start_idx:end_idx]

# Remove extracted lines
lines = lines[:start_idx] + lines[end_idx:]

# Find where to insert (before # §2 关系本体)
insert_idx = 0
for i, line in enumerate(lines):
    if "§2 关系本体" in line:
        insert_idx = i - 1
        break

lines = lines[:insert_idx] + extracted + lines[insert_idx:]

with open('/Users/xiamingxing/Workspace/projects/ecos/src/ecos/ssot/mof/m3.yaml', 'w') as f:
    f.writelines(lines)
