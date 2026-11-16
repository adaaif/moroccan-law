"""FX8 of the mended-Bulletin review: how often an old reading is wrong."""
import json
from datetime import UTC, date, datetime

import pytest
from django.core.management import call_command

from apps.quality.services import rates
from apps.sources.models import Document, Issue, OcrRun, Page

# The vote of a cover read many times, and the readings set beside it (FX3).
VOTE = 'ظهير شريف في ضبط زرع الكيف'


def bo_page(number, year, *, printed=1, text='', edition='general_ar', suffix=''):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{edition}{number}{suffix}{printed}',
                                  path=f'BO_{number}{suffix}.pdf', mime='application/pdf', bytes=1, language='ar',
                                  fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    Issue.objects.create(edition=edition, number=number, suffix=suffix, date=date(year, 6, 1), document=doc)
    return Page.objects.create(document=doc, index=0, printed_number=printed, kind='scan', text=text)


def runs(page, *readings):
    """Readings of a page, oldest first: (engine, variant, text). Their times are set one minute apart, so the order a
    page's runs come in is the order they were read, whatever the clock's resolution."""
    for k, (engine, variant, text) in enumerate(readings):
        run = OcrRun.objects.create(page=page, engine=engine, variant=variant, text=text)
        OcrRun.objects.filter(pk=run.pk).update(created_at=datetime(2026, 11, 1, 10, k, tzinfo=UTC))


def test_errors_count_words_to_change_add_or_drop():
    ref = rates.words('ظهير شريف في ضبط زرع الكيف')
    assert rates.errors(ref, rates.words('ظهير شريف في ضبط درع الكيف')) == 1
    assert rates.errors(ref, rates.words('ظهير في ضبط زرع الكيف')) == 1
    # A window cut wide around a passage: its extra words at the edges are not errors.
    assert rates.errors(ref, rates.words('وحرر بالرباط ظهير شريف في ضبط زرع الكيف يعلم'), edges=False) == 0


def test_words_fold_as_search_does():
    assert rates.words('الأولى «إقليم» مدينة') == ['الاولي', 'اقليم', 'مدينه']


def test_periods():
    assert [rates.period(y) for y in (1914, 1925, 1926, 1955, 1956, 1999, 2000, 2020)] == [
        '1913–1925', '1913–1925', '1926–1955', '1926–1955', '1956–1999', '1956–1999', '2000–2026', '2000–2026']


@pytest.fixture
def voted(db):
    page = bo_page(610, 1925, text=VOTE)
    runs(page,
         ('vote', 'vote of 3', VOTE),
         # The model's remark on its method is no word of the page: out before counting.
         ('claude-haiku-5-5', 'page-1596', f'{VOTE}\n(القراءة من العمود الأيمن)'),
         ('claude-haiku-5-5', 'copy 611', 'ظهير شريف في ضبط درع الكيف'),
         ('claude-haiku-5-5', 'copy 612', 'ظهير في ضبط درع الكيف ابدا'),
         ('claude-haiku-5-5', 'copy 614', 'ظهير شريف في ربط درع الكيف'),
         ('tesseract-5', 'page', 'ظهر شرف'),            # the witness is no reading of the vote
         ('claude-haiku-5-5', 'copy 613', ''))          # a reading that failed
    later = bo_page(1960, 1960, text='قرار وزيري')
    # Voted twice (the cover's readings voted again): one page still.
    runs(later, ('vote', 'vote of 3', 'قرار وزيري'), ('vote', 'vote of 4', 'قرار وزيري'),
         ('claude-haiku-5-5', 'copy 1961', 'قرار وزيري'))
    # A vote with no Arabic word in it: its readings' words are all errors, out of no words.
    blank = bo_page(5000, 2001, text='IV')
    runs(blank, ('vote', 'vote of 3', 'IV'), ('claude-haiku-5-5', 'copy 5001', 'قرار'))
    # A page read twice is no vote of many.
    twice = bo_page(100, 1915, text=VOTE)
    runs(twice, ('vote', 'kept of 2 readings', VOTE), ('claude-haiku-5-5', 'page', 'ظهير'),
         ('claude-haiku-5-5', 'copy 101', 'ظهر'))


def test_each_reading_of_a_cover_is_set_beside_the_vote(voted):
    # 0, 1, 2 and 3 words wrong of 6: the median page is the upper middle one, not their mean (1/4) nor the worst (1/2).
    assert rates.votes() == {'1913–1925': (6, 24, 2 / 6), '1956–1999': (0, 2, 0.0), '2000–2026': (1, 0, None)}


def test_the_command_prints_and_keeps_each_measure_by_period(voted, tmp_path, capsys):
    out = tmp_path / 'rates.json'
    call_command('reading_rates', '--json', str(out))
    kept = json.loads(out.read_text())
    assert kept['vote of many'] == {
        '1913–1925': {'errors': 6, 'words': 24, 'rate': 25.0, 'median_page': 33.3},
        '1956–1999': {'errors': 0, 'words': 2, 'rate': 0.0, 'median_page': 0.0},
        '2000–2026': {'errors': 1, 'words': 0, 'rate': None, 'median_page': None}}
    # The page read twice: its two readings part on its one word, half an error kept as none; its page at 50 %.
    assert kept['two readings'] == {'1913–1925': {'errors': 0, 'words': 1, 'rate': 0.0, 'median_page': 50.0}}
    assert kept['pages read'] == {}          # none of the passages' issues is in this database
    printed = capsys.readouterr().out.splitlines()
    assert 'vote of many   1913–1925         24 words        6 wrong  25.0 %  (median page 33.3 %)' in printed
    assert 'vote of many   2000–2026          0 words        1 wrong  None %' in printed
    assert 'vote of many   1956–1999          2 words        0 wrong  0.0 %  (median page 0.0 %)' in printed
    call_command('reading_rates')                          # the same, kept nowhere
    assert capsys.readouterr().out.splitlines() == printed


@pytest.mark.django_db
def test_two_readings_of_a_page_disagree_twice_as_often_as_one_errs():
    first = bo_page(70, 1914, text=VOTE)
    runs(first, ('vote', 'kept of 2 readings', VOTE),
         ('claude-haiku-5-5', 'page', 'ظهير شريف في ضبط زرع الكيف بالمغرب'),     # 7 words, read first
         ('claude-haiku-5-5', 'columns', 'ظهير شريف في ضبط درع الكيف'))           # 6 words, read last
    second = bo_page(900, 1930, text='قرار')
    runs(second, ('vote', 'kept of 2 readings', 'قرار'), ('vote', 'kept of 2 readings', 'قرار'),
         ('claude-haiku-5-5', 'page', 'ظهير ملكي من ضبط'), ('claude-haiku-5-5', 'columns', 'قرار وزيري في ضبط'))
    # Read once beside Tesseract: no pair.
    alone = bo_page(71, 1914, text=VOTE)
    runs(alone, ('vote', 'kept of 2 readings', VOTE), ('claude-haiku-5-5', 'page', VOTE), ('tesseract-5', 'page', 'ظهير'))
    # The newest reading holds no Arabic word: half an error, out of no words.
    latin = bo_page(5000, 2001, text='IV')
    runs(latin, ('vote', 'kept of 2 readings', 'IV'), ('claude-haiku-5-5', 'page', 'قرار'), ('claude-haiku-5-5', 'columns', 'IV'))
    # The newest reading is the one counted in words; 1.5 errors are kept as 2.
    assert rates.pairs() == {'1913–1925': (1, 6, 1 / 6), '1926–1955': (2, 4, 1.5 / 4), '2000–2026': (0, 0, None)}


@pytest.mark.django_db
def test_passages_read_on_their_pages_are_set_beside_the_models_own_reading(tmp_path):
    passage = 'تتكلف لجن جماعات اليهود باعانة الفقراء وبتدبير الاوقاف'
    # Another edition's and a second issue's 266, both later: the passage's page is the Arabic issue's own.
    bo_page(266, 1918, printed=557, edition='translation_fr', text=passage)
    bo_page(266, 1918, printed=557, suffix='bis', text=passage)
    page = bo_page(266, 1917, printed=557, text=f'وحرر بالرباط ظهير شريف {passage} انتهى')
    runs(page,
         ('claude-haiku-5-5', 'copy 267', 'تتكلف لجان جماعات اليهود'),    # a copy's reading is not this page's
         # Two words read into the passage: the stretch set beside it reaches past them, to its last word.
         ('claude-haiku-5-5', 'page',
          'وحرر بالرباط ظهير شريف تتكلف لجن جماعات اليهود الكبرى بالمدينة باعانة الفقراء وبتدبير الاوقاف انتهى'),
         ('claude-haiku-5-5', 'reread', f'ظهير {passage}'))            # read again later: not the model's first word
    # Only a copy read this page: the copy stands for it.
    copied = bo_page(300, 1930, printed=12, text='')
    runs(copied, ('claude-haiku-5-5', 'copy 301', 'يمنع على الهود الانخراط في الوظائف العمومية'))
    # Never read by the model: the page's own text.
    bo_page(1500, 1941, printed=4, text='كل من يقيم بالمنطقة الفرنسوية')
    bo_page(1501, 1941, printed=9, text='')                                      # a page left unread
    # The passage printed twice on one page, the second time with «الكيف» read as another of its words: both stretches
    # hold five of its words, and the first is the one set beside it.
    bo_page(1600, 1960, printed=7, text='يمنع زرع الكيف في المنطقة ظهير شريف رقم مائة وعشرون سنة يمنع زرع في في المنطقة')
    # A copy of 1500 under its own number: its pages are the cover's, never read on their own.
    bo_page(1502, 1941, printed=4, text='صفحة اخرى')
    Issue.objects.filter(number=1502).update(copy_of=Issue.objects.get(number=1500))
    gold = tmp_path / 'gold.yaml'
    gold.write_text('passages:\n'
                    f'- {{issue: 266, page: 557, words: {passage}}}\n'
                    '- {issue: 300, page: 12, words: يمنع على اليهود الانخراط في الوظائف العمومية}\n'
                    '- {issue: 1500, page: 4, words: يعتبر كل من يقيم بالمنطقة الفرنسوية}\n'
                    '- {issue: 1501, page: 9, words: ظهير شريف}\n'
                    '- {issue: 1502, page: 4, words: يعتبر كل من يقيم بالمنطقة الفرنسوية}\n'
                    '- {issue: 1600, page: 7, words: يمنع زرع الكيف في المنطقة}\n'
                    '- {issue: 266, page: 999, words: صفحة لم تقرأ}\n'          # no such page
                    '- {issue: 4321, page: 1, words: عدد لم يقرأ}\n', encoding='utf-8')     # no such issue
    # Two words too many beside 8, one misread of 7 (the copy) and of 6 (the page's text lacks the passage's first word);
    # an unread page misses every word.
    assert rates.gold(gold) == {'1913–1925': (2, 8, None), '1926–1955': (4, 15, None), '1956–1999': (0, 5, None)}
