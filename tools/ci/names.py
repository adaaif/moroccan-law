#!/usr/bin/env python3
"""The project's earlier names must not come back: `tools/ci/names.py [paths…]`.

The site was called «Matn», then «Qanoun» / «9anoun». Readers now see «3adala» in Latin letters and «قانون» in Arabic,
and the code's own names use `law`, never a brand (docs/rules.md, «Names»). This reads every tracked text file that
goes into the public tree and fails on a line that carries an earlier name, unless `names-allowed.txt` beside this
script allows it: the words that only look like one (how people type «القانون» in Latin letters, two web addresses) and
the few places that must name the past to move away from it.

Exit status: 0 when nothing is found, 1 otherwise. It needs git and the standard library only.
"""
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ALLOWED = Path(__file__).with_name('names-allowed.txt')
EARLIER = re.compile(r'matn|qanoun|9anoun|«متن»|عن متن|متن ·', re.IGNORECASE)
BINARY = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.otf', '.wasm', '.pdf', '.mmdb',
          '.onnx', '.gz', '.zip', '.docx', '.m4a', '.mp4', '.lock'}


def allowed():
    """(path pattern, expression) pairs: a hit inside a match of the expression, in a file the pattern names, passes."""
    out = []
    for line in ALLOWED.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#'):
            pattern, expression = line.split('\t', 1)
            out.append((pattern, re.compile(expression)))
    return out


def tracked(paths):
    """The tracked files under `paths` that the public tree holds (not marked export-ignore), relative to the root. It
    reads git's list of files: outside a clone (a downloaded archive) it says so and stops."""
    try:
        listed = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--', *paths], capture_output=True,
                                check=True).stdout
        checked = subprocess.run(['git', '-C', str(ROOT), 'check-attr', '-z', '--stdin', 'export-ignore'], input=listed,
                                 capture_output=True, check=True).stdout.split(b'\0')
    except (OSError, subprocess.CalledProcessError):
        sys.exit("names.py reads git's list of files: run it in a clone of the repository, not in a downloaded archive")
    private = {checked[i].decode() for i in range(0, len(checked) - 2, 3) if checked[i + 2] == b'set'}
    return [name for name in listed.decode().split('\0') if name and name not in private]


def main():
    rules = allowed()
    found = 0
    for name in tracked(sys.argv[1:] or ['.']):
        path = ROOT / name
        if path.suffix.lower() in BINARY or path.is_symlink() or path == ALLOWED:
            continue
        if EARLIER.search(name):
            found += 1
            print(f'{name}: the file\'s own name')
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        mine = [expression for pattern, expression in rules if fnmatch.fnmatch(name, pattern)]
        for number, line in enumerate(lines, 1):
            # What the allowed expressions cover is taken off the line; an earlier name still there is a finding.
            rest = line
            for expression in mine:
                rest = expression.sub(' ', rest)
            if EARLIER.search(rest):
                found += 1
                print(f'{name}:{number}: {line.strip()[:150]}')
    if found:
        print(f'names: {found} lines carry an earlier name of the project (tools/ci/names-allowed.txt says what may)',
              file=sys.stderr)
        return 1
    print('names: no earlier name of the project', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
