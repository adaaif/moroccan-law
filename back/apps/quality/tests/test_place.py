"""Where a doubtful word stands on its printed page (services/place.py): its context looked for loosely among Tesseract's
lines, the best window kept only when it is clearly ahead, and the strip cut around the word."""
import io

import pytest
from django.core.management import call_command

from apps.quality.models import Suspect
from apps.quality.services import place
from apps.quality.tests.words_helpers import line, page_with, suspect, tsv, write_boxes
from apps.sources.services import regions

CONTEXT = 'عن الملك المسمى بلاد المرنسي الكائن بمركز مراصة قلعة'


def sheet(*lines):
    return place.sheet_of(tsv(*lines))


def test_words_are_compared_folded_and_without_their_dots():
    assert place.norm('«المرنسي»،') == 'المرنسي' and place.norm('٢٤') == '24' and place.norm('ی') == 'ي'
    assert place.alike('فرقة', 'فرفه')                     # dots and a final ة: one shape
    assert place.alike('الجنوبية', 'الجنوية')               # a letter lost, from five letters
    assert not place.alike('بعلي', 'علي')                   # three or four letters: the same shape, no letter lost
    assert not place.alike('في', 'فى') and place.alike('في', 'في')
    assert not place.alike('فبراير', '27فبراير') and place.alike('1943', '1943')     # a day run into its month


def test_a_word_found_with_its_neighbours_is_placed_and_marked():
    # Tesseract cut the word in two («المر نسي») and misread a neighbour's dots («بمرلز»); the line runs on below.
    s = sheet(line('خلاصة اصلاحية تتعلق بملك اخر', 100, number=1),
              line('عن الملك المسمى بلاد المر نسي الكائن بمرلز', 140, number=2),
              line('مراصة قلعة ملاس بقبيلة بلاس', 180, number=3))
    p = place.find(s, CONTEXT, 'المرنسي', 'المرنيسي')
    assert p['found'] == 9 and p['of'] == 9 and p['ahead']['words'] >= 2
    width, height = p['size']
    left, top, right, bottom = (p['box'][0] * width, p['box'][1] * height, p['box'][2] * width, p['box'][3] * height)
    mark_left, mark_right = p['mark'][0] * width, p['mark'][1] * width
    # The mark spans both pieces of the word, inside the strip; the strip holds the line above and the line below.
    words = {w.text: w for r in s.rows for w in r.words}
    assert round(mark_left) == words['نسي'].left and round(mark_right) == words['المر'].right
    assert left < mark_left < mark_right < right
    assert top < 140 - 20 and bottom > 140 + 28 + 20
    assert place.STRIP_LEAST <= round(right - left) <= place.STRIP_MOST


def test_two_words_tesseract_ran_together_are_both_found():
    s = sheet(line('عن الملك المسمىبلاد المرنسي الكائن بمركز مراصة قلعة', 140))
    p = place.find(s, CONTEXT, 'المرنسي', 'المرنيسي')
    assert p['found'] == 9 and p['mark']


def test_a_word_is_never_joined_across_two_lines():
    # «المر» ends a line and «نسي» starts the next: not one word cut in two, and never marked as one.
    s = sheet(line('عن الملك المسمى بلاد المر', 140, number=1), line('نسي الكائن بمركز مراصة قلعة', 180, number=2))
    p = place.find(s, CONTEXT, 'المرنسي', 'المرنيسي')
    assert p['found'] == 8 and p['mark'] is None


def test_a_line_found_without_the_word_is_placed_with_no_mark_where_the_word_should_stand():
    s = sheet(line('عن الملك المسمى بلاد ححححح الكائن بمركز مراصة قلعة', 140))
    p = place.find(s, CONTEXT, 'المرنسي', 'المرنيسي')
    assert p['mark'] is None and p['found'] == 8
    unread = next(w for r in s.rows for w in r.words if w.text == 'ححححح')
    width = p['size'][0]
    assert p['box'][0] * width < unread.left and unread.right < p['box'][2] * width


def test_without_the_word_a_line_must_hold_two_thirds_of_its_context():
    # The page's formula with another surface in it: five words of nine and the word itself not there.
    s = sheet(line('الجديدة الذى مساحته 2110 مترأ مربعا والحدود شمالا يزئقة', 140))
    assert place.find(s, 'الذي مساحته تسعمايه وثلاثين متر مربع والمحدود شمالا بالمسيو', 'متر', 'مثر') == {}


def test_a_box_that_runs_over_its_neighbours_marks_nothing():
    rows = line('عن الملك المسمى بلاد', 140) + line('الكائن بمركز مراصة قلعة', 140, right=1000)
    rows.append('5\t1\t1\t1\t1\t9\t960\t140\t180\t28\t40\tالمرنسي')     # over «بلاد» and «الكائن»
    p = place.find(place.sheet_of(tsv(rows)), CONTEXT, 'المرنسي', 'المرنيسي')
    assert p['found'] == 9 and p['mark'] is None


def test_a_formula_printed_twice_is_not_placed_on_either():
    formula = 'وصرح طالب التسجيل بانه لا علم له بوجود ادنى تحمل او حق عقاري'
    s = sheet(line(formula, 300, number=1), line('على الملك المذكور', 340, number=2),
              line(formula, 900, number=3), line('على الملك المذكور', 940, number=4))
    assert place.find(s, 'التسجيل بانه لا علم لة بوجود ادنى تحمل او', 'لة', 'له') == {}


def test_too_little_of_the_context_is_not_a_place():
    s = sheet(line('الملك بلاد شيء اخر تماما هنا', 140))
    assert place.find(s, CONTEXT, 'المرنسي', 'المرنيسي') == {}
    assert place.find(s, CONTEXT, 'غائبة', 'غائبه') == {}                 # a word its context does not hold
    assert place.find(place.Sheet([], (1596, 2000), [], 28), CONTEXT, 'المرنسي', 'x') == {}


def test_in_two_columns_the_strip_stays_in_its_column():
    # The right column speaks of something else at the same height; Tesseract ran one line across the gutter.
    right = line('وبعد فان المحافظ على الاملاك العقارية يعلن', 140, right=1480, block=1)
    across = line('ان عمليات التحديد ستجري', 180, right=1480, block=2) + \
        line('عن الملك المسمى بلاد المرنسي الكائن بمركز مراصة قلعة', 180, right=760, block=2)
    s = sheet(right, across, line('مراصة قلعة ملاس', 220, right=760, block=3),
              line('سطر اخر في العمود الايسر', 100, right=760, block=4))
    gutter = [r for r in s.rows if r.top == 180]
    assert len(gutter) == 2                                     # cut at the gutter
    left_column = min(gutter, key=lambda r: r.left)
    p = place.find(s, CONTEXT, 'المرنسي', 'المرنيسي')
    width = p['size'][0]
    word = next(w for w in left_column.words if w.text == 'المرنسي')
    assert round(p['mark'][0] * width) == word.left
    assert p['box'][2] * width <= left_column.right + 13       # never into the right column


def test_a_page_without_words_has_no_sheet():
    assert place.sheet_of(tsv()) is None
    assert place.page_size('level\n') is None


def test_the_rank_says_where_an_unread_word_stands():
    # Words 0..2 found on tokens 0..2, word 3 (the doubtful one) not, 4 found on token 5: token 3.
    assert place._by_rank({0: [0], 1: [1], 2: [2], 4: [5]}, 3, 8) == 3
    assert place._by_rank({4: [5], 5: [6]}, 3, 8) == 4                      # nothing before it: back from the next
    assert place._by_rank({2: [2], 4: [3]}, 3, 8) == 2                      # no token between: the nearer one
    assert place._by_rank({4: [0], 5: [1]}, 3, 8) is None                   # it stands before the window's first word
    assert place._by_rank({1: [6], 2: [7]}, 3, 8) is None                   # or after its last


def test_a_word_whose_line_is_not_in_the_window_is_not_placed():
    # Its neighbours after it start the line; the word ended the line above, which Tesseract did not read.
    s = sheet(line('الكائن بمركز مراصة قلعة ملاس بقبيلة بلاس', 140))
    assert place.find(s, 'المرنسي الكائن بمركز مراصة قلعة', 'المرنسي', 'المرنيسي') == {}


@pytest.mark.django_db
def test_a_pages_words_are_placed_in_two_queries(settings, tmp_path, django_assert_num_queries):
    settings.CORPUS_DIR = tmp_path
    page = page_with()
    write_boxes(page, tsv(line('عن الملك المسمى بلاد المرنسي الكائن بمركز مراصة قلعة', 140),
                          line('شيء لا علاقة له بالموضوع البتة هنا', 600, number=2)))
    found = suspect(page, 'المرنسي', 'المرنيسي', CONTEXT)
    lost = suspect(page, 'غائبة', 'غائبه', 'كلمات لا توجد في هذه الصفحة غائبة ابدا ولا في غيرها')
    glued = suspect(page, 'شعباeffective', '', 'اوائل شعباeffective سنة', signal='glued')
    done = suspect(page, 'الملك', 'الملل', CONTEXT.replace('المرنسي', 'الملك'), status='rejected')
    with django_assert_num_queries(2):
        assert place.place_page(page) == 1
    found.refresh_from_db(), lost.refresh_from_db(), glued.refresh_from_db(), done.refresh_from_db()
    assert found.place['mark'] and lost.place == {} and glued.place is None and done.place is None
    assert place.place_page(page) == 0                                      # each word looked for once


@pytest.mark.django_db
def test_a_page_not_read_places_nothing(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    page = page_with()
    suspect(page, 'المرنسي', 'المرنيسي', CONTEXT)
    assert place.place_page(page) == 0 and Suspect.objects.get().place is None


@pytest.mark.django_db
def test_the_command_reads_the_pages_of_a_second_reading_first(settings, tmp_path, monkeypatch):
    settings.CORPUS_DIR = tmp_path
    read_already = page_with(1)
    rare = page_with(2)
    second = page_with(3)
    gone = page_with(4)
    unreadable = page_with(5)
    write_boxes(read_already, tsv(line(CONTEXT, 140)))
    for p in (read_already, rare, second, gone, unreadable):
        suspect(p, 'المرنسي', 'المرنيسي', CONTEXT, signal='rare' if p in (read_already, rare) else 'reread')
    for p in (rare, second, unreadable):
        (tmp_path / p.document.path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / p.document.path).write_bytes(b'%PDF')
    order = []

    def lines_of(page):            # Tesseract, replaced: the page's boxes written as the night would
        order.append(page.document.issue.number)
        if page.pk != unreadable.pk:
            write_boxes(page, tsv(line(CONTEXT, 140)) if page.pk == second.pk else tsv(line('لا شيء هنا', 140)))
        return [], (1596, 2000)
    monkeypatch.setattr(regions, 'lines_of', lines_of)

    out = io.StringIO()
    call_command('place_words', '--minutes', '5', stdout=out)
    assert order == [3, 5, 2]               # the second reading's page, then the rare one; the missing file passed over
    said = out.getvalue()
    assert said.startswith('2 pages read, 3 pages looked at, 1 passed over (no file here)')
    assert '2 words placed, 1 not found' in said
    assert '  reread: 1 placed, 0 not found (100% placed)' in said and '  rare: 1 placed, 1 not found (50% placed)' in said
    assert said.rstrip().endswith('2 askable words not looked for yet')
    assert Suspect.objects.get(page=second).place['mark'] and Suspect.objects.get(page=rare).place == {}

    # A limit of pages read, and one signal: nothing left to read for `rare`, the unreadable page tried again.
    order.clear()
    out = io.StringIO()
    call_command('place_words', '--signal', 'reread', '--limit', '0', stdout=out)
    assert order == [] and out.getvalue().startswith('0 pages read, 0 pages looked at')


@pytest.mark.django_db
def test_no_time_left_reads_nothing(settings, tmp_path, monkeypatch):
    settings.CORPUS_DIR = tmp_path
    suspect(page_with(), 'المرنسي', 'المرنيسي', CONTEXT)
    monkeypatch.setattr(regions, 'lines_of', lambda page: pytest.fail('read with no time left'))
    assert place.run(0) == {'read': 0, 'pages': 0, 'missing': 0, 'placed': 0}


@pytest.mark.django_db
def test_a_document_outside_the_corpus_is_passed_over(settings, tmp_path, monkeypatch):
    settings.CORPUS_DIR = tmp_path
    page = page_with()
    page.document.path = '../elsewhere.pdf'
    page.document.save()
    suspect(page, 'المرنسي', 'المرنيسي', CONTEXT)
    monkeypatch.setattr(regions, 'lines_of', lambda page: pytest.fail('read a file outside the corpus'))
    assert place.run(float('inf')) == {'read': 0, 'pages': 0, 'missing': 1, 'placed': 0}
