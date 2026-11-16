#!/usr/bin/env python3
"""The gate before publishing: finds what must not leave with the code.

    python3 tools/publish/scan.py [paths…] [--list] [--class NAME]

It reads every text file under the given paths (the repository's root by default) and looks for the classes of
private material listed in `private-words.txt`, a file that sits beside this script in the private repository only.
Each line of that file is `class<TAB>mode<TAB>regular expression`; `mode` is `fail` (the export stops) or `note`
(listed for a person to judge: these patterns also match harmless lines).

In a git checkout, paths marked `export-ignore` are skipped: they never reach the public tree. Without the word list
(in a public clone) the script has nothing to look for and says so.

Exit status: 0 when no `fail` class matched, 1 otherwise.
"""
import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORDS = HERE / 'private-words.txt'
# Folders never read: build output, tools' caches and reports, and installed packages anywhere, and the working folders at
# the root (the corpus,
# readers' files, a local database, logs), which are links or ignored. A folder named `data` deeper in the tree is code's
# data and is read like everything else.
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'dist', 'dist-ssr', 'target', '__pycache__', '.pytest_cache', 'staticfiles',
             '.ruff_cache', '.reports'}
SKIP_AT_ROOT = {'data', 'uploads', 'pg', '.logs'}
BINARY = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.otf', '.pdf', '.mmdb',
          '.onnx', '.gz', '.zip', '.docx', '.m4a', '.mp4', '.lock'}
# Compiled files a build writes paths into (a compiler records where each source file was): read as the runs of
# printable characters inside them, one a line, and held to the `fail` classes only.
COMPILED = {'.wasm'}
PRINTABLE = re.compile(rb'[\x20-\x7e]{6,}')
# What starts a comment or a wrapped line: taken off before two lines are read together.
LEAD = re.compile(r'^\s*(?:#+|//+|/?\*+|--+|<!--|;+|>+)?\s*')
# Prose and data: only the `fail` classes are looked for there, since `note` patterns are about code comments.
DATA = {'.json', '.yaml', '.yml', '.csv', '.tsv', '.txt', '.md', '.svg', '.html'}


def patterns():
    out = []
    for line in WORDS.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, mode, expression = line.split('\t', 2)
        out.append((name, mode, re.compile(expression)))
    return out


def ignored(root):
    """The files git would leave out of an archive (export-ignore), relative to `root`; empty unless `root` is the top
    of a checkout (an exported tree inside another repository is read whole)."""
    try:
        top = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], capture_output=True, check=True)
        if Path(top.stdout.decode().strip()).resolve() != Path(root).resolve():
            return set()
        listed = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True, check=True).stdout
        checked = subprocess.run(['git', '-C', str(root), 'check-attr', '-z', '--stdin', 'export-ignore'], input=listed,
                                 capture_output=True, check=True).stdout.split(b'\0')
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {checked[i].decode() for i in range(0, len(checked) - 2, 3) if checked[i + 2] == b'set'}


def files(paths, root):
    out = set()
    for path in paths:
        path = Path(path).resolve()
        found = [path] if path.is_file() else (p for p in path.rglob('*') if p.is_file())
        for file in found:
            relative = file.relative_to(root)
            folders = relative.parts[:-1]
            if not SKIP_DIRS.intersection(folders) and not (folders and folders[0] in SKIP_AT_ROOT) \
                    and file.suffix.lower() not in BINARY and not file.is_symlink() and file.name != '.git':
                out.add(file)
    return sorted(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--list', action='store_true', help='print every hit, not only the counts')
    parser.add_argument('--class', dest='only', help='look for one class only')
    parser.add_argument('--root', help='the tree the paths belong to (default: the repository this script is in)')
    options = parser.parse_args()
    if not WORDS.exists():
        print('scan: no private word list here (a public clone has none); nothing to look for')
        return 0
    root = Path(options.root).resolve() if options.root else HERE.parent.parent
    skip = ignored(root)
    wanted = [p for p in patterns() if not options.only or p[0] == options.only]
    counts, failed = Counter(), Counter()
    for file in files(options.paths or [root], root):
        relative = file.relative_to(root).as_posix()
        if relative in skip or file == WORDS:
            continue
        compiled = file.suffix.lower() in COMPILED
        try:
            lines = ([run.decode('ascii') for run in PRINTABLE.findall(file.read_bytes())] if compiled
                     else file.read_text(encoding='utf-8').splitlines())
        except (UnicodeDecodeError, OSError):
            continue
        prose = compiled or file.suffix.lower() in DATA
        for number, line in enumerate(lines, 1):
            # The end of the line before and the start of this one, its comment marks taken off: words a comment
            # wraps from one line to the next («the» / «owner») are read together.
            seam = lines[number - 2][-60:] + ' ' + LEAD.sub('', line)[:60] if number > 1 else ''
            for name, mode, expression in wanted:
                if prose and mode == 'note':
                    continue
                if expression.search(line) or (seam and expression.search(seam)
                                                and not expression.search(lines[number - 2])):
                    counts[name] += 1
                    if mode == 'fail':
                        failed[name] += 1
                    if options.list:
                        print(f'{name}\t{relative}:{number}\t{line.strip()[:160]}')
    for name, mode, _ in wanted:
        print(f'scan: {name:<10} {mode:<5} {counts[name]:>5}', file=sys.stderr)
    if failed:
        print(f'scan: {sum(failed.values())} lines must change before publishing', file=sys.stderr)
        return 1
    print('scan: nothing that stops publishing', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
