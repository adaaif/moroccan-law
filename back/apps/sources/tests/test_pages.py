"""FX4 of the mended-Bulletin review: printed page numbers put right."""
from datetime import UTC, date, datetime

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document, Issue, Page
from apps.sources.services import pages

pytestmark = pytest.mark.django_db


def bo(number, day, first, n, text=''):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'h{number}', path=f'BO_{number}.pdf',
                                  mime='application/pdf', bytes=number, language='ar', page_count=n,
                                  fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    issue = Issue.objects.create(edition='general_ar', number=number, date=day, document=doc, first_page_number=first)
    for k in range(n):
        Page.objects.create(document=doc, index=k, printed_number=(first or 1) + k, kind='scan', text=text)
    return issue


def text(issue, uri, first_page, pages_, article_pages):
    t = Text.objects.create(akn_uri=uri, type='order', title_ar='قرار وزيري', first_published_in=issue,
                            first_published_page=first_page)
    v = Version.objects.create(text=t, language='ar', valid_from=issue.date, source_pages=pages_,
                               consolidation=Consolidation.AS_PUBLISHED)
    for k, page in enumerate(article_pages, 1):
        Article.objects.create(version=v, order=k, label=f'الفصل {k}', eid=f'art_{k}', body='يعمل به', printed_page=page)
    return t


def september_1914():
    bo(72, date(1914, 9, 17), 379, 26)
    bo73 = bo(73, date(1914, 9, 18), 1, 5)
    bo(74, date(1914, 9, 28), 411, 11)
    return bo73


def test_an_issue_left_at_page_one_takes_its_start_from_the_issue_before():
    september_1914()
    [p] = pages.misnumbered()
    assert (p.issue.number, p.start, p.sure) == (73, 405, False)     # page 410 is not in the file: read it to be sure


def test_renumbering_moves_pages_texts_and_articles_together():
    bo73 = september_1914()
    t = text(bo73, '/akn/ma/act/arrete/1914-09-18/bo73-3', 4, '4-5', [4, 5])
    done = pages.renumber(bo73, 405)
    assert done['delta'] == 404
    assert list(Page.objects.filter(document=bo73.document).order_by('index').values_list('printed_number', flat=True)) \
        == [405, 406, 407, 408, 409]
    t.refresh_from_db()
    assert t.first_published_page == 408
    assert t.versions.get().source_pages == '408-409'
    assert sorted(Article.objects.values_list('printed_page', flat=True)) == [408, 409]


def test_a_text_starts_where_its_own_pages_begin():
    issue = bo(6856, date(2020, 2, 6), 829, 20)
    text(issue, '/akn/ma/act/decret/2-20-30', 830, '844-845', [844, 845])         # 830 is the contents page
    text(issue, '/akn/ma/act/decret/2-20-31', 845, '846-846', [846])          # a page off: the contents' word
    assert pages.text_pages(write=True) == [('/akn/ma/act/decret/2-20-30', 830, 844)]
    assert Text.objects.get(akn_uri='/akn/ma/act/decret/2-20-30').first_published_page == 844


def test_the_page_vote_runs_on_from_the_issue_before_when_it_reads_no_folio():
    from apps.sources.services.issue import number_pages
    bo(72, date(1914, 9, 17), 379, 26)
    bo73 = bo(73, date(1914, 9, 18), None, 5, text='الحمد لله وحده')
    assert number_pages(bo73) == 405
    assert Page.objects.get(document=bo73.document, index=2).printed_number == 407


def test_a_start_the_pages_print_is_confirmed(monkeypatch):
    bo73 = september_1914()
    [p] = pages.misnumbered()
    monkeypatch.setattr(pages, 'printed_numbers', lambda page, width=1400: {2: [407], 3: [408]}.get(page.index, []))
    assert pages.confirm(p) and p.start == 405
    q = pages.Proposal(bo73, 5, 404, sure=False)        # two pages agree on a start one page later
    assert pages.confirm(q) and q.start == 405


def test_renumbering_with_files_moves_the_issue_folder_too(tmp_path, settings):
    import json
    settings.CORPUS_DIR = tmp_path
    bo73 = september_1914()
    folder = tmp_path / 'reports' / 'issues' / '73'
    folder.mkdir(parents=True)
    (folder / 'texts.json').write_text(json.dumps([{'pages': [4, 5], 'toc': {'page': 4},
                                                     'articles': [{'page': 4}, {'page': 5}]}]))
    (folder / 'toc.json').write_text(json.dumps([{'page': 4}]))
    pages.renumber(bo73, 405, files=True)
    item = json.loads((folder / 'texts.json').read_text())[0]
    assert item['pages'] == [408, 409] and item['toc']['page'] == 408 and [a['page'] for a in item['articles']] == [408, 409]
    assert json.loads((folder / 'toc.json').read_text()) == [{'page': 408}]
    assert json.loads((folder / 'texts.before-renumber.json').read_text())[0]['pages'] == [4, 5]
