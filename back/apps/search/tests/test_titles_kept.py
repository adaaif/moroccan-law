"""RD13 of the readers review: the suggestions' titles are read from the table once a corpus generation and kept in a
file, so a new worker reads the file instead of every title again."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.search.models import SearchEntry
from apps.search.services.search import titles

pytestmark = pytest.mark.django_db


def _fresh_worker():
    titles._TITLES.update(generation=None, rows=[], blob='', starts=[])


def test_a_new_worker_reads_the_titles_from_the_file_not_the_table(monkeypatch, tmp_path):
    from apps.corpus.services import generation
    monkeypatch.setattr(titles.tempfile, 'gettempdir', lambda: str(tmp_path))
    monkeypatch.setattr(generation, 'current', lambda *scopes: 'g1')
    SearchEntry.objects.create(kind=SearchEntry.Kind.TEXT, text_path='/ma/loi/65-99', path='/ma/loi/65-99', title='مدونة الشغل',
                               title_folded='مدونه الشغل', weight=1.5, year=2003)
    SearchEntry.objects.create(kind=SearchEntry.Kind.TEXT, text_path='/ma/loi/70-03', path='/ma/loi/70-03', title='مدونة الأسرة',
                               title_folded='مدونه الاسره', weight=1.5, year=None)
    _fresh_worker()
    with CaptureQueriesContext(connection) as first:
        rows, blob, starts = titles._title_rows()
    assert len(first) == 1 and sorted(blob.split('\n')) == ['مدونه الاسره', 'مدونه الشغل'] and len(starts) == 2
    assert sorted(r[1:] for r in rows) == [('/ma/loi/65-99', 'مدونه الشغل', 1.5, 2003), ('/ma/loi/70-03', 'مدونه الاسره', 1.5, None)]
    # Another worker, the same generation: the file, no query, the same rows as tuples.
    _fresh_worker()
    with CaptureQueriesContext(connection) as second:
        again = titles._title_rows()
    assert len(second) == 0 and again == (rows, blob, starts)
    # The corpus moved: the table is read once more, and the answer follows it.
    SearchEntry.objects.filter(text_path='/ma/loi/70-03').delete()
    monkeypatch.setattr(generation, 'current', lambda *scopes: 'g2')
    with CaptureQueriesContext(connection) as third:
        assert len(titles._title_rows()[0]) == 1
    assert len(third) == 1


def test_titles_are_read_from_the_table_when_no_file_can_be_kept(monkeypatch, tmp_path):
    from apps.corpus.services import generation
    blocked = tmp_path / 'a-file'
    blocked.write_text('x')                                    # a file where the folder should be: nothing can be kept
    monkeypatch.setattr(titles.tempfile, 'gettempdir', lambda: str(blocked))
    monkeypatch.setattr(generation, 'current', lambda *scopes: 'g1')
    SearchEntry.objects.create(kind=SearchEntry.Kind.TEXT, text_path='/ma/loi/65-99', path='/ma/loi/65-99', title='مدونة الشغل',
                               title_folded='مدونه الشغل', weight=1.5, year=2003)
    _fresh_worker()
    assert [r[1] for r in titles._title_rows()[0]] == ['/ma/loi/65-99']
