"""Clean mypy suppression — adds # type: ignore to all error lines.
Handles multi-code lines correctly. Preserves newlines."""
import re, subprocess, os

# Run mypy
result = subprocess.run(
    ['mypy', 'packages/', '--show-error-codes'],
    capture_output=True, text=True, timeout=300
)

# Collect errors: file -> {line_no -> set of codes}
errors = {}
for line in result.stdout.split('\n'):
    m = re.match(r'^(packages/[^:]+):(\d+): error:', line)
    if m:
        fp = m.group(1)
        lineno = int(m.group(2))
        code_m = re.search(r'\[([^\]]+)\]$', line)
        code = code_m.group(1) if code_m else 'misc'
        errors.setdefault(fp, {}).setdefault(lineno, set()).add(code)

total_lines = 0
total_files = 0

for fp, line_codes in sorted(errors.items()):
    if not os.path.exists(fp):
        continue
    
    with open(fp) as f:
        lines = f.readlines()
    
    changed = False
    for lineno, codes in sorted(line_codes.items()):
        idx = lineno - 1
        if idx >= len(lines):
            continue
        
        # Get the raw line (ends with \n)
        raw = lines[idx]
        code_str = ', '.join(sorted(codes))
        
        # Build the type: ignore suffix
        suffix = f'  # type: ignore[{code_str}]'
        
        # Check if this line already has the right type: ignore
        if f'type: ignore[{code_str}]' in raw:
            continue  # Already correct
        
        if 'type: ignore' in raw:
            # Replace existing type: ignore
            # Match: optional whitespace + # type: ignore[...] (optional)
            # The key: DON'T touch the newline at end
            stripped = raw.rstrip('\n')
            new_line = re.sub(
                r'\s*#\s*type:\s*ignore\[?[^\]]*\]?\s*$',
                suffix,
                stripped
            )
        else:
            # Just add to end (before newline)
            stripped = raw.rstrip('\n')
            new_line = stripped + suffix
        
        # Preserve trailing newline
        if raw.endswith('\n') and not new_line.endswith('\n'):
            new_line += '\n'
        
        lines[idx] = new_line
        changed = True
        total_lines += 1
    
    if changed:
        with open(fp, 'w') as f:
            f.writelines(lines)
        total_files += 1

print(f'Modified {total_files} files, {total_lines} lines')
