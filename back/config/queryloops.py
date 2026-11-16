"""Queries inside loops, found by the test suite: `pytest --query-loops` records, for each test, every SQL shape
(config.querylog's: the statement with its literals out) that one line of the code ran more than `--query-loops-over`
times (querylog's REPEATS by default) in one call from the test into the code (a request, through its outermost
middleware; a command's `handle`; a service), with that line and the two lines that called it. A view or a service
the test calls three times is not a loop; a loop of the code's own is. At the end of the run the lines are ranked by
how many tests reach them and how often they repeat; `--query-loops-json PATH` writes the whole list. The line is the
innermost frame in `apps/` or `config/` that is not a test: a query a test runs itself is not counted. Off unless
asked, since it walks the stack at every query; queries run in another thread are not seen.

    pytest -n 4 --query-loops --query-loops-over=2 --query-loops-json=/tmp/loops.json

The gate (tools/ci/loops.sh): the functions known today are kept in `queryloops-kept.txt` beside this file, one
`<file>::<function>` a line, so an edit above a function leaves its entry as it is. `check` fails on a function the
run found that is not kept; `update` writes the list again from a run:

    python -m config.queryloops check /tmp/loops.json
    python -m config.queryloops update /tmp/loops.json"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

import pytest

OVER = 5                      # config.querylog.REPEATS: one shape more often than this in one call is a loop
_SKIP = ('config/querylog.py', 'config/queryloops.py')   # the SQL hooks themselves
_QUIET = ('SAVEPOINT', 'RELEASE SAVEPOINT', 'ROLLBACK TO SAVEPOINT')
SHOWN = 40                    # lines printed at the end of the run
KEPT = Path(__file__).with_name('queryloops-kept.txt')


def pytest_addoption(parser):
    group = parser.getgroup('query-loops', 'queries inside loops')
    group.addoption('--query-loops', action='store_true', default=False,
                    help='record the SQL shapes a line of the code repeats in a test, and rank the lines at the end')
    group.addoption('--query-loops-over', type=int, default=OVER, metavar='N',
                    help=f'a shape counts once a line runs it more than N times in one call (default {OVER})')
    # Given as --query-loops-json=PATH: pytest reads a separate path that exists as a path to test.
    group.addoption('--query-loops-json', default=None, metavar='PATH', help='write every repeated line there as JSON')


def pytest_configure(config):
    if config.getoption('query_loops') and not hasattr(config, 'workerinput'):
        config.pluginmanager.register(Ranking(config), 'query-loops-ranking')


def _lines():
    """The code's frames that led to this query, innermost first; the outermost of them (the call from the test); and
    the test line that made that call."""
    code, outer, test = [], None, None
    frame = sys._getframe(2)
    while frame is not None:
        name = frame.f_code.co_filename
        at = name.rfind('/back/')
        rel = name[at + 6:] if at >= 0 else ''
        if rel.startswith(('apps/', 'config/')):
            if '/tests/' in rel or rel.endswith('conftest.py'):
                test = f'{rel}:{frame.f_lineno}'
                break
            if not rel.endswith(_SKIP):
                code.append(f'{rel}:{frame.f_lineno} {frame.f_code.co_qualname}')
                outer = frame
        frame = frame.f_back
    return code, outer, test


@pytest.fixture(autouse=True)
def _query_loops(request):
    if not request.config.getoption('query_loops'):
        yield
        return
    from django.db import connections

    from config.querylog import shape

    seen: Counter = Counter()          # (line, shape, call) → runs
    first: dict = {}
    calls: dict = {}                   # each call's outermost frame, held to the test's end so no other takes its id

    def watch(execute, sql, params, many, context):
        if not sql.lstrip().upper().startswith(_QUIET):
            code, outer, test = _lines()
            if code:
                calls.setdefault(id(outer), outer)
                key = (code[0], shape(sql))
                seen[(*key, id(outer))] += 1
                if key not in first:
                    first[key] = (code[1:3], test)
        return execute(sql, params, many, context)

    with ExitStack() as stack:
        for alias in connections:
            stack.enter_context(connections[alias].execute_wrapper(watch))
        yield
    calls.clear()
    most: Counter = Counter()
    for (line, sql, _), n in seen.items():
        most[(line, sql)] = max(most[(line, sql)], n)
    over = request.config.getoption('query_loops_over')
    rows = [[line, sql[:600], n, *first[(line, sql)]] for (line, sql), n in most.items() if n > over]
    if rows:
        request.node.user_properties.append(('query_loops', rows))


class Ranking:
    """On the run's main process (with xdist, the controller): the tests' rows gathered and ranked."""

    def __init__(self, config):
        self.config = config
        self.lines: dict = defaultdict(lambda: {'tests': {}, 'max': 0, 'total': 0, 'shapes': {}, 'via': None,
                                                'example': None, 'called_from': None})

    def pytest_runtest_logreport(self, report):
        if report.when != 'teardown':
            return
        for name, rows in report.user_properties:
            if name != 'query_loops':
                continue
            for line, sql, n, via, test in rows:
                seen = self.lines[line]
                seen['tests'][report.nodeid] = max(seen['tests'].get(report.nodeid, 0), n)
                seen['total'] += n
                if n > seen['max']:
                    seen['max'], seen['example'], seen['via'], seen['called_from'] = n, report.nodeid, via, test
                seen['shapes'][sql] = max(seen['shapes'].get(sql, 0), n)

    def ranked(self) -> list[dict]:
        rows = [{'line': line, 'tests': len(s['tests']), 'max': s['max'], 'total': s['total'], 'via': s['via'],
                 'example': s['example'], 'called_from': s['called_from'],
                 'shapes': sorted(s['shapes'].items(), key=lambda kv: -kv[1]), 'by_test': s['tests']}
                for line, s in self.lines.items()]
        return sorted(rows, key=lambda r: (-r['tests'], -r['max'], r['line']))

    def pytest_terminal_summary(self, terminalreporter):
        rows = self.ranked()
        over = self.config.getoption('query_loops_over')
        terminalreporter.section(f'queries inside loops: {len(rows)} lines repeat a shape more than {over} times')
        for r in rows[:SHOWN]:
            terminalreporter.write_line(f"{r['tests']:4} tests  {r['max']:5}× at most  {r['line']}")
            terminalreporter.write_line(f"           {r['shapes'][0][0][:150]}")
            terminalreporter.write_line(f"           ← {' ← '.join([*r['via'], r['called_from'] or '?'])}")
        if path := self.config.getoption('query_loops_json'):
            with open(path, 'w', encoding='utf-8') as out:
                json.dump(rows, out, ensure_ascii=False, indent=1)
            terminalreporter.write_line(f'every line: {path}')


# ── the gate ──────────────────────────────────────────────────────────────────────────────────────────────────────────

HEADER = """\
# The functions known to run one SQL statement many times in one call from a test (config/queryloops.py), one
# <file>::<function> a line. tools/ci/loops.sh fails when the suite finds a function that is not listed here; one that
# is listed and no longer found is only reported. `tools/ci/loops.sh --update` writes this file again from a run, whose
# JSON (back/.reports/loops.json) has each function's query, how often it repeats and a test that reaches it.
"""


def key(line: str) -> str:
    """`apps/x.py:120 Desk.queue` → `apps/x.py::Desk.queue`: the function, not its line."""
    where, _, name = line.partition(' ')
    return f"{where.rsplit(':', 1)[0]}::{name}"


def kept(path: Path) -> set[str]:
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    return {ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith('#')}


def found(path: Path) -> dict[str, dict]:
    """Each function the run found, with its most reached line (the run ranks its lines most reached first)."""
    out: dict[str, dict] = {}
    for row in json.loads(path.read_text(encoding='utf-8')):
        out.setdefault(key(row['line']), row)
    return out


def check(run: dict[str, dict], known: set[str]) -> int:
    new = [k for k in run if k not in known]
    gone = sorted(known - set(run))
    print(f'query loops: {len(run)} functions found, {len(known)} kept, {len(new)} new, {len(gone)} no longer found')
    for k in gone:
        print(f'  no longer found (drop it with --update): {k}')
    for k in new:
        r = run[k]
        print(f'  NEW {k}')
        print(f"      at {r['line']}, {r['max']} times at most in one call, in {r['tests']} test(s), e.g. {r['example']}")
        print(f"      {r['shapes'][0][0][:200]}")
        print(f"      called from {' <- '.join([*r['via'], r['called_from'] or '?'])}")
    return 1 if new else 0


def update(run: dict[str, dict], path: Path) -> None:
    path.write_text(HEADER + ''.join(f'{k}\n' for k in sorted(run)), encoding='utf-8')
    print(f'query loops: {len(run)} functions written to {path}')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='python -m config.queryloops',
                                     description='Compare the query loops a run found with the kept list.')
    parser.add_argument('action', choices=('check', 'update'))
    parser.add_argument('found', type=Path, help='the JSON a run wrote with --query-loops-json')
    parser.add_argument('--kept', type=Path, default=KEPT, help=f'the kept list (default {KEPT.name} beside this file)')
    args = parser.parse_args(argv)
    run = found(args.found)
    if args.action == 'update':
        update(run, args.kept)
        return 0
    return check(run, kept(args.kept))


if __name__ == '__main__':
    sys.exit(main())
