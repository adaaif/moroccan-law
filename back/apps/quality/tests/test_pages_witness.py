"""RD1 of the readers review: a text held from a file's layer, set against the Bulletin's own pages."""
from datetime import date

from django.utils import timezone

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.services.pages_witness import compare, slips, words
from apps.sources.models import Document, Edition, Issue, Page

pytestmark = pytest.mark.django_db

PRINTED = ('الفصل 41 الملك، أمير المؤمنين وحامي حمى الملة والدين، والضامن لحرية ممارسة الشؤون الدينية. يرأس الملك، أمير المؤمنين، '
           'المجلس العلمي الأعلى، الذي يتولى دراسة القضايا التي يعرضها عليه. ويعتبر المجلس الجهة الوحيدة المؤهلة لإصدار الفتاوى '
           'التي تعتمد رسميا، في شأن المسائل المحالة إليه، استنادا إلى مبادئ وأحكام الدين الإسلامي الحنيف، ومقاصده السمحة. '
           'الفصل 98 إذا وقع حل أحد المجلسين، فلا يمكن حل المجلس الذي يليه إلا بعد مضي سنة على انتخابه، ما عدا في حالة تعذر توفر '
           'أغلبية حكومية داخل مجلس النواب الجديد. ')
LAYER_41 = ('الملك، أمير المؤمنين وحامي حمى لالمة والدين، والضامن لحرية ممارسة الشؤون الدينية. يرأس الملك، أمير المؤمنين، '
            'المجلس العلمي الأعلى، الذي يتولى دراسة القضايا التي يعرضها عليه. ويعتبر المجلس الجهة الوحيدة المؤهلة لإصدار الفتاوى '
            'التي تعتمد رسميا، في شأن المسائل المحالة إليه، استنادا إلى مبادئ وأحكام الدين الإسلامي الحنفي، ومقاصده السمحة.')
LAYER_98 = ('إذا وقع حل أحد المجلسين، فال يمكن حل المجلس الذي يليه إلا بعد مضي سنة على انتخابه، ما عدا في حالة تعذر توفر '
            'أغلبية حكومية داخل مجلس النواب الجديد.')


def _constitution(signed=date(2011, 7, 29)):
    text = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-11-91', type='dahir', number='1-11-91', title_ar='الدستور',
                               signed_on=signed)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2011, 7, 30), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='الفصل 41', number='41', eid='art_41', body=LAYER_41)
    Article.objects.create(version=v, order=2, label='الفصل 98', number='98', eid='art_98', body=LAYER_98)
    Article.objects.create(version=v, order=3, label='الفصل 180', number='180', eid='art_180',
                           body='مع مراعاة المقتضيات الانتقالية الواردة في هذا الباب، ينسخ نص الدستور المراجع الصادر بتنفيذه الظهير الشريف.')
    return text


def _issue(day=date(2011, 7, 30)):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='a' * 64, path='issues/bo_ar/BO_5964-bis_ar.pdf',
                                  page_count=2, bytes=1, fetched_at=timezone.now())
    Issue.objects.create(edition=Edition.GENERAL_AR, number=5964, suffix='bis', date=day, document=doc)
    Page.objects.create(document=doc, index=0, kind='scan', text='الجريدة الرسمية عدد 5964 مكرر ' + 'تصدير ' * 300)
    Page.objects.create(document=doc, index=1, kind='scan', text=PRINTED * 4)
    return doc


def test_the_pages_witness_what_the_layer_turned_round_and_swapped():
    text = _constitution()
    _issue()
    r = compare(text)
    # Two articles stand in the pages; the third is not printed there, so nothing is said of it.
    assert (r['layer'], r['articles'], r['witnessed'], r['agree']) == ('adala', 3, 2, 0)
    assert {(s['number'], s['layer'], s['bulletin']) for s in r['slips']} == {
        ('41', 'لالمة', 'الملة'), ('41', 'الحنفي', 'الحنيف'), ('98', 'فال', 'فلا')}
    assert '[الحنفي]' in next(s['around'] for s in r['slips'] if s['layer'] == 'الحنفي')


def test_an_amended_article_is_no_witness_and_a_text_without_its_day_says_so():
    # An article the law has since rewritten shares too few words with the page that printed its first wording.
    rewritten = words('لا يمكن حل المجلسين معا، ويحدد قانون تنظيمي شروط الحل وآجال انتخاب المجلس الجديد وكيفيات دعوته إلى الانعقاد.')
    assert slips(rewritten, words(PRINTED * 4)) is None
    text = _constitution(signed=None)
    _issue()
    assert 'no day' in compare(text)['error']
    held = Text.objects.create(akn_uri='/akn/ma/act/loi/1-1', type='law', number='1-1', title_ar='قانون', signed_on=date(2020, 1, 1))
    assert compare(held)['error'] == 'not held from a file'


def test_two_readings_that_say_the_same_words_agree():
    text = _constitution()
    doc = _issue()
    Page.objects.filter(document=doc, index=1).update(text=(PRINTED.replace('الملة', 'لالمة').replace('الحنيف', 'الحنفي')
                                                            .replace('فلا يمكن', 'فال يمكن')) * 4)
    r = compare(text)
    assert (r['witnessed'], r['agree'], r['slips']) == (2, 2, [])


# ── RD5: where a book held from a file was first printed ─────────────────────────────────────────────────────────

ART_1 = 'تسري أحكام هذه المدونة على جميع المغاربة ولو كانوا حاملين لجنسية أخرى، وعلى اللاجئين بمن فيهم عديمو الجنسية.'
ART_2 = 'الخطبة تواعد رجل وامرأة على الزواج، وتتحقق بتعبير طرفيها بأي وسيلة متعارف عليها تفيد التواعد على الزواج.'


def _family_code():
    from apps.quality.services.pages_witness import first_print, signed_day
    code = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', number_as_printed='70.03',
                               title_ar='القانون رقم 70.03 بمثابة مدونة الأسرة')
    v = Version.objects.create(text=code, language='ar', valid_from=date(2021, 7, 29), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', body=ART_1)
    Article.objects.create(version=v, order=2, label='المادة 5', number='5', eid='art_5', body=ART_2)
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='b' * 64, path='issues/bo_ar/BO_5184_ar.pdf',
                                  page_count=4, bytes=1, fetched_at=timezone.now())
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=5184, date=date(2004, 2, 5), document=doc)
    pages = ['السنة الثالثة والتسعون عدد 5184 ISSN 0851 - 1195 فهرست ظهير شريف رقم 1.04.22 بتنفيذ القانون رقم 70.03 بمثابة مدونة الأسرة 418',
             'نصوص عامة ظهير شريف رقم 1.04.22 صادر في 12 من ذي الحجة 1424 (3 فبراير 2004) بتنفيذ القانون رقم 70.03 بمثابة مدونة الأسرة '
             'الحمد لله وحده ' + 'ينشر بالجريدة الرسمية عقب ظهيرنا الشريف هذا القانون كما وافق عليه مجلس النواب ومجلس المستشارين. ' * 12,
             'الديباجة ' + 'لقد جعل مولانا أمير المؤمنين النهوض بحقوق الإنسان في صلب المشروع المجتمعي الديمقراطي الحداثي. ' * 14,
             f'المادة 1 {ART_1} المادة 5 {ART_2} ' + 'تطبق أحكام هذه المدونة أمام أقسام قضاء الأسرة بالمحاكم الابتدائية. ' * 14]
    for n, body in enumerate(pages):
        Page.objects.create(document=doc, index=n, printed_number=417 + n, kind='scan', text=body, text_source='llm')
    return code, issue, first_print, signed_day


def test_a_books_first_issue_and_page_are_found_from_its_words():
    code, issue, first_print, signed_day = _family_code()
    # Its heading names no day: two decrees that cite it in their visas do.
    for n in (1, 2):
        decree = Text.objects.create(akn_uri=f'/akn/ma/act/decret/2-04-{n}', type='decree', number=f'2-04-{n}')
        Version.objects.create(text=decree, language='ar', valid_from=date(2004, 6, 1), consolidation='as_published',
                               preamble='بناء على القانون رقم 70.03 بمثابة مدونة الأسرة الصادر بتنفيذه الظهير الشريف رقم 1.04.22 '
                                        'بتاريخ 12 من ذي الحجة 1424 (3 فبراير 2004) ؛')
    assert signed_day(code) == date(2004, 2, 3)
    found = first_print(code)
    # Page 417 is the cover and its table of contents; the code begins on 418, its articles on 420.
    assert (found['issue'], found['page'], found['found'], found['articles']) == (issue.pk, 418, 2, 2)


def test_a_laws_day_is_read_on_the_bulletins_page_when_nothing_cites_it():
    code, _, _, signed_day = _family_code()
    assert signed_day(code) == date(2004, 2, 3)          # «ظهير شريف رقم 1.04.22 صادر في … (3 فبراير 2004) بتنفيذ القانون رقم 70.03»


def test_the_command_records_them_once(capsys):
    from django.core.management import call_command
    code, issue, *_ = _family_code()
    call_command('find_first_issues', code.akn_uri, write=True)
    code.refresh_from_db()
    assert (code.signed_on, code.first_published_in, code.first_published_page) == (date(2004, 2, 3), issue, 418)
    assert 'BO 5184 of 2004-02-05, page 418: 2 of 2 articles' in capsys.readouterr().out
    # Found again: what the text names already stays, and nothing is written.
    call_command('find_first_issues', code.akn_uri, write=True)
    assert capsys.readouterr().out.splitlines() == [
        '/akn/ma/act/loi/70-03: signed 2004-02-03 · BO 5184 of 2004-02-05, page 418: 2 of 2 articles',
        '1 texts: 0 days and 0 first issues recorded']


def test_a_day_must_fit_the_year_the_number_carries():
    from apps.quality.management.commands.find_first_issues import fits
    decree = Text(akn_uri='/akn/ma/act/decret/2-04-143', type='decree', number='2-04-143')
    assert not fits(decree, date(1913, 8, 12)) and fits(decree, date(2004, 12, 29)) and fits(decree, date(2005, 1, 3))
    labour = Text(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99')
    assert fits(labour, date(2003, 9, 11)) and not fits(labour, date(1913, 8, 12)) and not fits(labour, date(2010, 1, 1))
    assert fits(Text(type='dahir', number='1-58-250'), date(1958, 9, 6))
    assert fits(Text(type='code', number=''), date(1913, 8, 12))              # no number to judge by
    assert not fits(Text(type='dahir', number=''), date(1913, 8, 12))         # a dahir is numbered: no number, no day
    # A royal decree «514.65» or an order «1319.15»: its year, or the two after.
    royal = Text(type='royal_decree', number='514-65')
    assert not fits(royal, date(1964, 12, 31)) and fits(royal, date(1965, 1, 1)) and fits(royal, date(1967, 12, 31))
    assert not fits(royal, date(1968, 1, 1))
    assert not fits(Text(type='decree', number='2-2004-5'), date(2004, 1, 1))   # a year of four figures is no number


# ── the commands ─────────────────────────────────────────────────────────────────────────────────────────────────────


def test_witness_pages_prints_each_difference_and_keeps_the_list(settings, tmp_path, capsys):
    import json

    from django.core.management import call_command
    settings.CORPUS_DIR = tmp_path
    text = _constitution()
    _issue()
    call_command('witness_pages', text.akn_uri, '--show', '2')
    out = capsys.readouterr().out.splitlines()
    assert out[0] == '/akn/ma/act/dahir/1-11-91: 2 of 3 articles witnessed by the pages, 0 agree word for word, 3 small differences'
    assert out[1:] == ['    41: «لالمة» / the Bulletin «الملة»   … المؤمنين وحامي حمى [لالمة] والدين والضامن لحرية',
                       '    41: «الحنفي» / the Bulletin «الحنيف»   … واحكام الدين الاسلامي [الحنفي] ومقاصده السمحة']
    kept = json.loads((tmp_path / 'reports' / 'witness' / 'akn_ma_act_dahir_1-11-91.pages.json').read_text())
    assert (kept['witnessed'], len(kept['slips'])) == (2, 3)


def test_witness_pages_reads_the_librarys_books_held_from_a_file(settings, tmp_path, capsys):
    from django.core.management import call_command
    settings.CORPUS_DIR = tmp_path
    constitution = _constitution()
    # Held from two files: still one book.
    Version.objects.create(text=constitution, language='ar', valid_from=date(2011, 7, 29), consolidation=Consolidation.SGG)
    _issue()
    _family_code()                                   # held from a file, with no day of its own to find its issue by
    # Held only as the Bulletin printed it: nothing to witness.
    printed = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', title_ar='مدونة الشغل')
    Version.objects.create(text=printed, language='ar', valid_from=date(2003, 12, 8), consolidation='as_published')
    call_command('witness_pages', '--library', '--show', '0')
    assert capsys.readouterr().out.splitlines() == [
        '/akn/ma/act/dahir/1-11-91: 2 of 3 articles witnessed by the pages, 0 agree word for word, 3 small differences',
        '/akn/ma/act/loi/70-03: no day recorded: its issue cannot be found',
        '2 texts: 2 articles witnessed, 0 agree, 3 small differences']


def test_witness_pages_needs_a_text_it_holds():
    from django.core.management import call_command
    from django.core.management.base import CommandError
    with pytest.raises(CommandError, match='name a text, or --library'):
        call_command('witness_pages')
    with pytest.raises(CommandError, match='/akn/ma/act/loi/1-1: not in the corpus'):
        call_command('witness_pages', '/akn/ma/act/loi/1-1')


def test_find_first_issues_reads_the_library_and_writes_nothing_unasked(capsys):
    from django.core.management import call_command
    _constitution()
    code, *_ = _family_code()
    call_command('find_first_issues', '--library')
    assert capsys.readouterr().out.splitlines() == [
        '/akn/ma/act/dahir/1-11-91: signed 2011-07-29 · no page read near 2011-07-29',
        '/akn/ma/act/loi/70-03: signed 2004-02-03 · BO 5184 of 2004-02-05, page 418: 2 of 2 articles',
        '2 texts: 1 days and 1 first issues found (not written)']
    code.refresh_from_db()
    assert (code.signed_on, code.first_published_in) == (None, None)


def test_find_first_issues_needs_a_text_it_holds():
    from django.core.management import call_command
    from django.core.management.base import CommandError
    with pytest.raises(CommandError, match='name a text, or --library'):
        call_command('find_first_issues')
    with pytest.raises(CommandError, match='/akn/ma/act/loi/1-1: not in the corpus'):
        call_command('find_first_issues', '/akn/ma/act/loi/1-1')


# ── which differences count ──────────────────────────────────────────────────────────────────────────────────────────

LETTERS = 'بتثجحخدذرزسشصضطظعغفقكلمن'
PAGE = [f'م{a}{b}ل' for a in LETTERS[:12] for b in LETTERS[:10]]           # 120 words, each its own


def test_only_small_differences_inside_the_article_count():
    p = PAGE
    split, dotted = [p[19][:2], p[19][2:]], p[40][:-1] + 'ن'
    layer = (['و' + p[0]] + p[1:5]                      # at the article's edge: not compared
             + ['مستشفيات'] + p[6:10]                   # three letters longer or more: another word
             + ['قطظل'] + p[11:15]                      # three letters apart
             + [p[15] + p[16]] + p[17:19]               # the Bulletin's reading spaced it: no slip of the file
             + split + p[20:24]                         # the file cut it: a slip
             + [p[24][:2], p[24][2:], p[25][:2], p[25][2:]] + p[26:40]   # cut in four pieces: not a small difference
             + [dotted] + p[41:80])                     # a letter apart: a slip
    assert [(s['layer'], s['bulletin']) for s in slips(layer, PAGE)] == [(' '.join(split), p[19]), (dotted, p[40])]
    assert slips(PAGE[:7], PAGE) is None                            # too short to be found by its runs of words
    # Found by its runs of words, but a third of it is not on the page: the law changed it since.
    assert slips(PAGE[:40] + [f'قصة{c}' for c in LETTERS[:20]], PAGE) is None


def test_a_day_is_read_after_the_texts_own_number_and_never_guessed():
    from apps.quality.services.pages_witness import cited_day, promulgated_day, signed_day
    decree = Text.objects.create(akn_uri='/akn/ma/act/decret/2-10-312', type='decree', number='2-10-312',
                                 title_ar='مرسوم رقم 2.10.312 صادر في 20 من شوال 1431 (29 سبتمبر 2010) بتطبيق القانون رقم '
                                          '52.05 الصادر بتنفيذه الظهير الشريف رقم 1.10.07 بتاريخ 26 من صفر 1431 (11 فبراير 2010)')
    assert signed_day(decree) == date(2010, 9, 29)              # its own day, not the road code's
    order = Text.objects.create(akn_uri='/akn/ma/act/arrete/1-11', type='order', number='1-11', title_ar='قرار رقم 1.11')
    assert signed_day(order) is None and promulgated_day(order) is None
    old = Text.objects.create(akn_uri='/akn/ma/act/dahir/1913-08-12', type='dahir', number='',
                              title_ar='الظهير الشريف الصادر في 9 رمضان 1331 (12 أغسطس 1913) بشأن التحفيظ العقاري')
    assert signed_day(old) == date(1913, 8, 12) and cited_day(old) == (None, 0)
    # A visa whose brackets hold no day says nothing; two that agree give the day.
    for n, said in enumerate(('(الجريدة الرسمية)', '(18 فبراير 2011)', '(18 فبراير 2011)')):
        cites = Text.objects.create(akn_uri=f'/akn/ma/act/decret/2-12-{n}', type='decree', number=f'2-12-{n}')
        Version.objects.create(text=cites, language='ar', valid_from=date(2012, 1, 1), consolidation='as_published',
                               preamble=f'بناء على المرسوم رقم 2.10.312 صادر في 20 من شوال 1431 {said} ؛')
    assert cited_day(decree) == (date(2011, 2, 18), 2)


def test_a_promulgating_dahir_printed_long_after_its_day_gives_none():
    from apps.quality.services.pages_witness import promulgated_day
    law = Text.objects.create(akn_uri='/akn/ma/act/loi/67-12', type='law', number='67-12', title_ar='القانون رقم 67.12')
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='c' * 64, path='issues/bo_ar/BO_6900_ar.pdf',
                                  bytes=1, fetched_at=timezone.now())
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=6900, date=date(2015, 2, 1), document=doc)
    heading = 'ظهير شريف رقم 1.13.111 صادر في 15 من محرم 1435 (19 نوفمبر 2013) بتنفيذ القانون رقم 67.12'
    Page.objects.create(document=doc, index=0, kind='scan', text=heading)          # printed 14 months after: a citation
    assert promulgated_day(law) is None
    issue.date = date(2013, 12, 19)
    issue.save()
    assert promulgated_day(law) == date(2013, 11, 19)


def test_a_text_without_its_pages_or_its_day_says_so():
    from apps.quality.services.pages_witness import first_print
    text = _constitution()
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='a' * 64, path='issues/bo_ar/BO_5964-bis_ar.pdf',
                                  bytes=1, fetched_at=timezone.now())
    Issue.objects.create(edition=Edition.GENERAL_AR, number=5964, suffix='bis', date=date(2011, 7, 30), document=doc)
    Page.objects.create(document=doc, index=0, kind='scan', text=PRINTED)            # a page, too few words to tell
    assert compare(text)['error'] == 'no page read near 2011-07-29'
    assert first_print(text)['error'] == 'no page read near 2011-07-29'
    plain = Text.objects.create(akn_uri='/akn/ma/act/loi/2-2', type='law', number='2-2', title_ar='قانون')
    assert first_print(plain) == {'text': plain.akn_uri, 'day': None, 'error': 'not held from a file'}
    held = Text.objects.create(akn_uri='/akn/ma/act/loi/3-3', type='law', number='3-3', title_ar='قانون')
    Version.objects.create(text=held, language='ar', valid_from=date(2020, 1, 1), consolidation=Consolidation.SGG)
    assert first_print(held) == {'text': held.akn_uri, 'day': None, 'error': 'no day found'}


def test_an_issue_that_holds_the_articles_but_never_names_the_text_is_not_its_first():
    from apps.quality.services.pages_witness import first_print
    code, issue, *_ = _family_code()
    for page in Page.objects.filter(document=issue.document):
        page.text = page.text.replace('70.03', '')
        page.save()
    found = first_print(code, day=date(2004, 2, 3))
    assert found['error'] == 'no issue read after that day holds its articles and names it'
    # Named again, but one article of two found there: too few to take the issue for its first.
    for page in Page.objects.filter(document=issue.document, index=1):
        page.text += ' القانون رقم 70.03'
        page.save()
    Article.objects.filter(eid='art_5').update(body='تطبق أحكام هذا الباب على كل نزاع لم يرد فيه نص خاص في هذه المدونة إطلاقا')
    assert first_print(code, day=date(2004, 2, 3))['error'].endswith('and names it')
    Page.objects.filter(document=issue.document).update(text='نص لا صلة له ' * 200)
    assert first_print(code, day=date(2004, 2, 3))['error'] == 'no issue read after that day holds its articles'


ARTS_1913 = ['يؤسس بمقتضى هذا الظهير الشريف نظام للتحفيظ العقاري يجري العمل به في جميع أنحاء المنطقة',
             'التحفيظ اختياري غير أنه يكون إجباريا في الأحوال المنصوص عليها في هذا الظهير الشريف وفي غيره',
             'يترتب على التحفيظ إقامة رسم الملكية وبطلان ما عداه من الرسوم وتطهير الملك من جميع الحقوق السالفة',
             'يجب على طالب التحفيظ أن يودع بالمحافظة العقارية مطلبا موقعا عليه منه أو من وكيله يتضمن ما يأتي']


def test_a_text_with_no_number_is_found_by_its_articles_alone_and_too_few_are_not_recorded(capsys):
    from django.core.management import call_command
    old = Text.objects.create(akn_uri='/akn/ma/act/dahir/1913-08-12', type='dahir', number='',
                              title_ar='الظهير الشريف الصادر في 9 رمضان 1331 (12 أغسطس 1913) بشأن التحفيظ العقاري')
    v = Version.objects.create(text=old, language='ar', valid_from=date(2020, 1, 1), consolidation=Consolidation.ADALA)
    for k, body in enumerate(ARTS_1913, 1):
        Article.objects.create(version=v, order=k, label=f'الفصل {k}', number=str(k), eid=f'art_{k}', body=body)
    for number, day, holds in ((50, date(1913, 9, 1), ARTS_1913[0]), (51, date(1913, 10, 1), ARTS_1913[1])):
        doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{number}' * 32, path=f'BO_{number}.pdf',
                                      bytes=1, fetched_at=timezone.now())
        Issue.objects.create(edition=Edition.GENERAL_AR, number=number, date=day, document=doc)
        Page.objects.create(document=doc, index=0, printed_number=number * 10, kind='scan', text='إعلان رسمي ' * 150)
        # Art. 4's first words alone stand there too: one run of words is no witness.
        Page.objects.create(document=doc, index=1, printed_number=number * 10 + 1, kind='scan',
                            text=f'يجب على طالب التحفيظ أن يتقدم {holds} انتهى')
    call_command('find_first_issues', old.akn_uri, '--write')
    assert capsys.readouterr().out.splitlines() == [
        '/akn/ma/act/dahir/1913-08-12: signed 1913-08-12 · BO 50 of 1913-09-01, page 501: 1 of 4 articles '
        '(next: BO 51 with 1)  [too few: not recorded]',
        '1 texts: 0 days and 0 first issues recorded']
    old.refresh_from_db()
    assert (old.signed_on, old.first_published_in) == (None, None)


def test_an_issue_that_names_the_text_and_holds_a_fifth_of_its_articles_is_recorded(capsys):
    from django.core.management import call_command
    code, issue, *_ = _family_code()
    version = code.versions.get()
    for n in range(6, 10):                        # four articles more, none printed in the issue's pages read here
        Article.objects.create(version=version, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                               body=f'نص المادة رقم {n} من هذه المدونة كما ورد في الجريدة الرسمية بعد التعديل الأخير')
    call_command('find_first_issues', code.akn_uri, '--write')
    assert capsys.readouterr().out.splitlines()[0] == (
        '/akn/ma/act/loi/70-03: signed 2004-02-03 · BO 5184 of 2004-02-05, page 418: 2 of 6 articles')
    code.refresh_from_db()
    assert (code.first_published_in, code.first_published_page) == (issue, 418)


def test_a_day_one_visa_alone_gives_is_kept_only_with_its_issue(capsys):
    from django.core.management import call_command
    labour = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', title_ar='مدونة الشغل')
    Version.objects.create(text=labour, language='ar', valid_from=date(2026, 7, 16), consolidation=Consolidation.ADALA)

    def cited_by(n):
        decree = Text.objects.create(akn_uri=f'/akn/ma/act/decret/2-04-{n}', type='decree', number=f'2-04-{n}')
        Version.objects.create(text=decree, language='ar', valid_from=date(2004, 12, 29), consolidation='as_published',
                               preamble='بناء على القانون رقم 65.99 المتعلق بمدونة الشغل الصادر بتنفيذه الظهير الشريف رقم '
                                        '1.03.194 بتاريخ 14 من رجب 1424 (11 سبتمبر 2003) ؛')

    cited_by(1)
    call_command('find_first_issues', labour.akn_uri, '--write')
    assert capsys.readouterr().out.splitlines() == [
        '/akn/ma/act/loi/65-99: signed 2003-09-11 · no page read near 2003-09-11',
        '1 texts: 0 days and 0 first issues recorded']
    cited_by(2)
    # Two visas agree, and the day fits the year its number carries: kept without its issue.
    call_command('find_first_issues', labour.akn_uri, '--write')
    assert capsys.readouterr().out.splitlines()[-1] == '1 texts: 1 days and 0 first issues recorded'
    labour.refresh_from_db()
    assert labour.signed_on == date(2003, 9, 11)
