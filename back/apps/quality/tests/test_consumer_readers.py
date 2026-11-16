"""The readers and checks the consumer plan added (A2, A3, A7, A8, 24 Oct 2026): a quoted chapter stays in its article,
a footnote quoting another text's article is no heading, two copies' words are set side by side, a contents line is
found by its law's number."""
from types import SimpleNamespace

from apps.consolidation.services.adala import keep_quoted
from apps.corpus.services.issue_structure import running_head
from apps.quality.services.witness import _unsigned, _words_apart
from apps.sources.management.commands.sweep_contents import matches
from apps.translations.services.adala_fr import QUOTED, HEAD, NOTE_START


def _art(number, *lines):
    return SimpleNamespace(number=number, label=f'المادة {number}', lines=list(lines))


def test_a_chapter_a_law_adds_to_another_text_stays_in_the_article_that_adds_it():
    # Law 24.09 art. 65 completes the DOC with a chapter whose articles are 106-1 to 106-14; its next own article is 66.
    arts = [_art('64', 'نص.'), _art('65', 'يتمم … بالباب الرابع كالآتي:'), _art('106-1', 'يعتبر المنتج مسؤولا'),
            _art('106-2', 'يراد بمصطلح منتوج'), _art('66', 'ينسخ.')]
    out = keep_quoted(arts)
    assert [a.number for a in out] == ['64', '65', '66']
    assert 'المادة 106-1' in out[1].lines and 'يراد بمصطلح منتوج' in out[1].lines


def test_a_code_s_own_sub_numbered_articles_stay_its_own():
    # The DOC's 106-1 follows its 106: no jump, nothing quoted.
    arts = [_art('106', 'نص:'), _art('106-1', 'نص.'), _art('107', 'نص.')]
    assert [a.number for a in keep_quoted(arts)] == ['106', '106-1', '107']


def test_a_footnote_quoting_the_decree_is_not_a_heading_of_the_law():
    # Law 31.08's French footnotes copy decree 2.12.503: «Article 23 : « Le mode d'emploi … »».
    assert QUOTED.match('Article 23 :') and QUOTED.match('Article 25 : « Les factures')
    assert not QUOTED.match('Article 23') and HEAD.match('Article 23')
    assert NOTE_START.match('2-Voir articles 7, 23 et 24 du décret') and NOTE_START.match('15- Les dispositions')


def test_two_copies_words_apart_are_listed_in_their_order():
    only_a, only_b = _words_apart('تحدد بنص تنظيمي البيانات التي والم خلاصات', 'تحدد بنص تنظيمي البيانات التي والمخالصات')
    assert only_a == ['والم خلاصات'] and only_b == ['والمخالصات']


def test_a_contents_line_is_found_by_its_law_s_number_or_its_words():
    page = 'قرار لوزير الصناعة رقم 4.14 بتحديد القيمة القصوى\nمرسوم رقم 2.12.503 بتطبيق بعض أحكام القانون رقم 31.08 القاضي بتحديد تدابير لحماية المستهلك\nظهير بتعيين سفير'
    found = matches(page)
    assert len(found) == 1 and found[0]['numbers'] == ['31.08', '2.12.503'] and 'المستهلك' in found[0]['words']
    assert matches('قرار بتحديد سعر الفائدة القانونية لسنة 2014')[0]['words'] == ['سعر الفائدة القانونية']
    assert not matches('قرار رقم 131.08 بالترخيص')                  # 131.08 is not 31.08


def test_a_running_head_read_mid_column_or_in_pieces_is_no_line_of_the_text():
    # BO 5932 (law 31.08): a column read alone brought the head mid-article, cut in two or with the name in part.
    for line in ['عدد 5932 - 3 جمادى الأولى 1432 (7 أبريل 2011)', 'الجريدة الرسمية', '1089 الجريدة الرسمية',
                 'عدد 5932 - 3 جمادى الأولى 1432 (7 أبريل 2011) الرسمية', '1071 الجريدة الرسمية عدد 5932 - 3 جمادى الأولى 1432 (7 أبريل 2011)']:
        assert running_head(line, 5932), line
    for line in ['ينشر هذا القرار في الجريدة الرسمية.', '(1) يراجع الملحق في نشرة الترجمة الرسمية للجريدة الرسمية عدد 5932 بتاريخ 3 جمادى الأولى 1432 (7 أبريل 2011).',
                 'عدد 59320 - 1 يناير 2020']:
        assert not running_head(line, 5932), line


def test_a_signature_kept_in_the_last_article_is_no_word_of_it():
    # Order 2.14: Adala keeps «وحرر بالرباط … الإمضاء» in art. 4; the BO's cut puts it after the text.
    body = 'ينشر هذا القرار بالجريدة الرسمية.\nوحرر بالرباط في 29 من صفر 1435 (2 يناير 2014).\nالإمضاء: مولاي حفيظ العلمي.'
    assert _unsigned(body) == 'ينشر هذا القرار بالجريدة الرسمية.\n'
    assert _unsigned('يحرر المورد فاتورة.') == 'يحرر المورد فاتورة.'
