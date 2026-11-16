"""FX1 of the mended-Bulletin review: every fault counted, each check on a small Bulletin of its own."""
from datetime import UTC, date, datetime

import pytest
from django.core.management import call_command

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.services import health
from apps.sources.models import Document, Issue, Page

pytestmark = pytest.mark.django_db


def issue(number, day, first=None, pages=2, size=None, edition='general_ar', texts=()):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{edition}{number}', path=f'BO_{number}.pdf',
                                  mime='application/pdf', bytes=size or 1000 + number, language='ar', page_count=pages,
                                  fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    bo = Issue.objects.create(edition=edition, number=number, date=day, document=doc, first_page_number=first)
    for k in range(pages):
        Page.objects.create(document=doc, index=k, printed_number=(first or 1) + k, kind='scan',
                            text=texts[k] if k < len(texts) else 'ظهير شريف')
    return bo


def by_name(checks):
    return {c.name: c for c in checks}


def test_article_numbers_read_whatever_the_spelling():
    assert health.article_value('الفصل الثانى') == 2
    assert health.article_value('الفصل الحادى عشر') == 11
    assert health.article_value('المادة 3') == 3
    assert health.article_value('الفصل الأول') == 1
    assert health.article_value('فصل فريد') is None


def test_copies_are_counted_until_folded():
    cover = issue(610, date(1925, 1, 6), first=1, size=3112268, pages=3)
    copies = [issue(n, date(1925, 1, 6), first=1, size=3112268, pages=3) for n in (611, 612)]
    assert health.copies().count == 2
    Issue.objects.filter(pk__in=[c.pk for c in copies]).update(copy_of=cover)
    assert health.copies().count == 0


def test_an_issue_that_starts_at_one_in_september_is_counted():
    issue(72, date(1914, 9, 17), first=379, pages=26)          # pages 379–404
    issue(73, date(1914, 9, 18), first=1, pages=5)             # should be 405–409
    issue(74, date(1914, 9, 28), first=411, pages=11)
    issue(1, date(1915, 1, 4), first=1, pages=8)               # a year's first issue starts at 1
    wrong, unclear = health.page_one()
    assert (wrong.count, wrong.sample, unclear.count) == (1, ['general_ar 73'], 0)


def test_remarks_and_glued_words_are_counted():
    issue(593, date(1924, 1, 1), first=1, pages=2, texts=['وانه يملكه\n\nLet me redo this carefully.\n\nوانه يملكه',
                                                          'اوائل شعباeffective الثاني'])
    text = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-69-249', type='dahir', title_ar='ظهير')
    v = Version.objects.create(text=text, language='ar', valid_from=date(1969, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=19, label='الفصل 19', number='19', eid='art_19',
                           body='| 1 |\n\nNote: The page has a table with three columns.')
    checks = by_name(health.readings())
    assert checks['remarks_pages'].count == 1
    assert checks['remarks_articles'].count == 1
    assert checks['mixed_words'].count == 1


def make_text(uri, labels, preamble='', bo=None, title='قرار وزيري في تعيين كاتب', signed=None):
    text = Text.objects.create(akn_uri=uri, type='dahir', title_ar=title, first_published_in=bo, signed_on=signed)
    v = Version.objects.create(text=text, language='ar', valid_from=date(1960, 1, 1), preamble=preamble,
                               consolidation=Consolidation.AS_PUBLISHED)
    for k, label in enumerate(labels, 1):
        Article.objects.create(version=v, order=k, label=label, eid=f'art_{k}', body='يعمل به')
    return text


def test_texts_without_their_first_article_are_counted_by_kind():
    make_text('/akn/ma/act/dahir/1-60-138', ['الفصل الثانى'])
    make_text('/akn/ma/act/arrete/1161-78', ['الفصل الثانى', 'الفصل الاول'])
    make_text('/akn/ma/act/arrete/1330-75', ['الفصل الثاني'], preamble='بناء على … الفصل الأول : يعين')
    make_text('/akn/ma/act/arrete/1-1', ['الفصل الأول', 'الفصل الثاني'])
    checks = by_name(health.articles())
    assert checks['first_article_missing'].sample == ['/akn/ma/act/dahir/1-60-138']
    assert checks['first_article_late'].sample == ['/akn/ma/act/arrete/1161-78']
    assert checks['first_article_in_preamble'].sample == ['/akn/ma/act/arrete/1330-75']


def test_empty_texts_impossible_dates_bare_titles_and_twins():
    bo = issue(1120, date(1934, 4, 13), first=475, pages=2)
    make_text('/akn/ma/act/dahir/1934-04-13/bo1120-1', [], bo=bo, title='ظهير شريف ينطبق بموجبه في الامور الجنائية')
    make_text('/akn/ma/act/dahir/1934-04-13/bo1120-4', ['الفصل الأول'], bo=bo,
              title='ظهير شريف ينطبق بموجبه في الأمور الجنائية')
    make_text('/akn/ma/act/dahir/1944-02-25/bo1635-4', ['الفصل الأول'], title='ظهير شريف')
    make_text('/akn/ma/act/dahir/x', ['الفصل الأول'], bo=bo, title='ظهير في شيء آخر تماما', signed=date(1934, 5, 1))
    checks = by_name(health.texts())
    assert checks['title_only'].count == 1
    assert checks['dated_after_issue'].sample == ['/akn/ma/act/dahir/x']
    assert checks['bare_titles'].sample == ['/akn/ma/act/dahir/1944-02-25/bo1635-4']
    assert checks['twin_texts'].count == 1


def test_the_command_fails_above_its_baseline(tmp_path, capsys):
    issue(610, date(1925, 1, 6), first=1, size=5, pages=1)
    base = tmp_path / 'base.json'
    call_command('data_health', '--only', 'copies', '--json', str(base))
    call_command('data_health', '--only', 'copies', '--baseline', str(base))
    assert capsys.readouterr().out.splitlines()[-1] == 'No count above the baseline.'
    issue(611, date(1925, 1, 6), first=1, size=5, pages=1)
    with pytest.raises(SystemExit):
        call_command('data_health', '--only', 'copies', '--baseline', str(base))
    assert 'Above the baseline: copies 0 → 1' in capsys.readouterr().err


def test_a_label_with_no_word_has_no_number():
    assert health.article_value('') is None and health.article_value('  ') is None


def test_an_issue_at_page_one_whose_neighbours_say_nothing_is_unclear():
    issue(1, date(1920, 1, 2), first=1, pages=2)
    issue(2, date(1920, 1, 9), first=1, pages=3)             # nothing after it to tell
    issue(3, date(1921, 1, 7), first=1, pages=4)              # a year's first
    issue(4, date(1921, 1, 14), first=1, pages=2)             # a volume that starts here: the next runs on from it
    issue(5, date(1921, 1, 21), first=3, pages=2)
    wrong, unclear = health.page_one()
    assert (wrong.count, unclear.count, unclear.sample) == (0, 1, ['general_ar 2'])


def test_the_examples_are_eight_whatever_the_count():
    remark = 'وانه يملكه\n\nLet me redo this carefully.\n\nوانه يملكه شعباeffective'
    for n in range(9):
        issue(600 + n, date(1924, 1, 1 + n), first=1, pages=1, texts=[remark])
    issue(700, date(1924, 2, 1), first=1, pages=1, edition='translation_fr', texts=['Le dahir.\n\nLet me redo this carefully.\n\nLe dahir.'])
    text = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-69-249', type='dahir', title_ar='ظهير')
    v = Version.objects.create(text=text, language='ar', valid_from=date(1969, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    for n in range(10):
        Article.objects.create(version=v, order=n, label=f'الفصل {n}', number=str(n), eid=f'art_{n}',
                               body='| 1 |\n\nNote: The page has a table with three columns.' if n else 'يطبق قانون ORMVA')
    checks = by_name(health.readings())
    assert (checks['remarks_pages'].count, len(checks['remarks_pages'].sample)) == (10, 8)
    assert (checks['mixed_words'].count, len(checks['mixed_words'].sample)) == (9, 8)
    assert checks['mixed_words'].sample[0] == 'general_ar 600·0: شعباeffective'
    assert (checks['remarks_articles'].count, len(checks['remarks_articles'].sample)) == (9, 8)


def test_the_command_runs_every_check_and_keeps_them(tmp_path, capsys):
    import json
    issue(610, date(1925, 1, 6), first=1, size=5, pages=1)
    for n in range(611, 616):
        issue(n, date(1925, 1, 6), first=1, size=5, pages=1)
    out = tmp_path / 'health.json'
    call_command('data_health', '--json', str(out))
    kept = json.loads(out.read_text())
    assert list(kept) == ['copies', 'page_one', 'page_one_unclear', 'remarks_pages', 'remarks_articles', 'mixed_words',
                          'first_article_missing', 'first_article_late', 'first_article_in_preamble', 'title_only',
                          'dated_after_issue', 'bare_titles', 'twin_texts']
    assert kept['copies'] == {'count': 5, 'means': "issues stored from another issue's file and not folded into it",
                              'sample': ['general_ar 610 ×6']}
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == 'copies                              5  issues stored from another issue\'s file and not folded into it'
    assert printed[1] == ' ' * 38 + 'general_ar 610 ×6'
    # Each check a line, with up to four examples under it: the copies' cover, and the last issue at page 1.
    assert len(printed) == 15 and printed[4] == ' ' * 38 + 'general_ar 615'
    call_command('data_health', '--only', 'pages, texts')
    assert [line.split()[0] for line in capsys.readouterr().out.splitlines() if not line.startswith(' ')] == [
        'page_one', 'page_one_unclear', 'title_only', 'dated_after_issue', 'bare_titles', 'twin_texts']
