#!/usr/bin/env python3
"""Count mypy errors per package."""
import subprocess, re, os, sys

base = '/Users/xiamingxing/Workspace/projects/kairon'
os.chdir(base)

packages = sorted(d for d in os.listdir('packages') if os.path.isdir(f'packages/{d}'))

results = []
for pkg in packages:
    result = subprocess.run(
        ['mypy', '--namespace-packages', '--explicit-package-bases',
         '--exclude', '/tests/', '--exclude', '/build/',
         f'packages/{pkg}'],
        capture_output=True, text=True, timeout=300
    )
    m = re.search(r'Found (\d+) errors?', result.stdout)
    count = int(m.group(1)) if m else 0
    results.append((count, pkg))
    print(f'{pkg}: {count} errors')

print(f'\nTotal: {sum(r[0] for r in results)} errors across {len(results)} packages')
print(f'\nTop packages by error count:')
for count, pkg in sorted(results, reverse=True)[:10]:
    print(f'  {pkg}: {count}')
