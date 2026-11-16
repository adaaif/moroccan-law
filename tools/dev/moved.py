#!/usr/bin/env python3
"""Checks that splitting a Python module into several moved its code without changing it.

    python3 tools/dev/moved.py <git ref> <old file> <new file or folder> [more new files or folders…]

It reads the old file at the git ref and the new files in the working tree, and compares their top-level statements
(functions, classes, assignments, anything but imports and docstrings) as source text. Every old statement must be
found once, word for word, in the new files. It prints what is missing (changed or dropped) and what is new (added),
and exits 1 if anything is missing. Imports, module docstrings and `__all__` are not compared: a split rewrites them.
"""
import ast
import subprocess
import sys
from collections import Counter
from pathlib import Path


def statements(source: str) -> Counter:
    found = Counter()
    for node in ast.parse(source).body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__all__' for t in node.targets):
            continue
        found[ast.unparse(node)] += 1
    return found


def name(text: str) -> str:
    return text.split('\n', 1)[0][:110]


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    ref, old, new = sys.argv[1], sys.argv[2], sys.argv[3:]
    before = statements(subprocess.run(['git', 'show', f'{ref}:{old}'], capture_output=True, text=True, check=True).stdout)
    after = Counter()
    for path in map(Path, new):
        for file in ([path] if path.is_file() else sorted(path.rglob('*.py'))):
            after += statements(file.read_text(encoding='utf-8'))
    missing, added = before - after, after - before
    for text in missing:
        print(f'MISSING  {name(text)}')
    for text in added:
        print(f'new      {name(text)}')
    print(f'{sum(before.values())} statements before, {sum((before & after).values())} found unchanged, '
          f'{sum(missing.values())} missing, {sum(added.values())} new')
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
