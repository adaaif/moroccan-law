"""The query loops' gate (config/queryloops.py, tools/ci/loops.sh): the kept list names functions, not lines, and a
function the run found that is not on it fails the check."""
import json

from config import queryloops


def row(line, repeats=3):
    return {'line': line, 'tests': 1, 'max': repeats, 'total': repeats, 'via': ['apps/x/api/views.py:9 get'],
            'example': 'apps/x/tests/test_x.py::test_it', 'called_from': 'apps/x/tests/test_x.py:4',
            'shapes': [['SELECT "x"."id" FROM "x" WHERE "x"."id" = %s', repeats]], 'by_test': {}}


def test_a_function_is_kept_by_its_file_and_name_whatever_its_line():
    assert queryloops.key('apps/x/services/desk.py:120 Desk.queue') == 'apps/x/services/desk.py::Desk.queue'
    assert queryloops.key('apps/x/services/desk.py:7 Desk.queue') == 'apps/x/services/desk.py::Desk.queue'


def test_only_a_function_that_is_not_kept_fails(tmp_path, capsys):
    found = tmp_path / 'loops.json'
    found.write_text(json.dumps([row('apps/x/services/desk.py:120 Desk.queue', 9), row('apps/x/services/desk.py:31 Desk.queue'),
                                 row('apps/y/services/news.py:5 recent')]))
    kept = tmp_path / 'kept.txt'
    kept.write_text('# a comment\napps/x/services/desk.py::Desk.queue\napps/z/gone.py::old\n')
    assert queryloops.main(['check', str(found), '--kept', str(kept)]) == 1
    out = capsys.readouterr().out
    assert 'NEW apps/y/services/news.py::recent' in out and 'Desk.queue' not in out.split('NEW')[1]
    assert 'no longer found (drop it with --update): apps/z/gone.py::old' in out
    assert queryloops.main(['update', str(found), '--kept', str(kept)]) == 0
    assert queryloops.kept(kept) == {'apps/x/services/desk.py::Desk.queue', 'apps/y/services/news.py::recent'}
    assert queryloops.main(['check', str(found), '--kept', str(kept)]) == 0


def test_the_kept_list_is_one_sorted_function_a_line():
    lines = [ln for ln in queryloops.KEPT.read_text(encoding='utf-8').splitlines() if not ln.startswith('#')]
    assert lines == sorted(set(lines)) and all('::' in ln and ':' not in ln.split('::')[0] for ln in lines)
