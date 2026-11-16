"""The commands of the mended-Bulletin review (FX3–FX5, FX10): each says what it would do and writes only with --write, then
puts the search index right and lets no kept answer outlive what it changed."""
import io
import json
from collections import Counter
from datetime import UTC, date, datetime

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.services import generation
from apps.corpus.services.addresses import text_path
from apps.quality.models import Suspect
from apps.search.models import SearchEntry, SearchPassage
from apps.sources.models import Document, Issue, OcrRun, Page
from apps.sources.tests import test_copies, test_pages
from apps.sources.tests.bo import write_pdf

pytestmark = pytest.mark.django_db


def run(*args) -> str:
    out = io.StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


@pytest.fixture
def answers(settings):
    """The answers' cache as Redis keeps it on a server (the suite's keeps nothing), so a command's bump shows."""
    settings.CACHES = {**settings.CACHES, 'answers': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                                      'LOCATION': 'sources-mending'}}
    return generation


def law(uri, issue=None, body='يعمل به', preamble='', closing='', consolidation=Consolidation.AS_PUBLISHED, pages='',
        page=None):
    text = Text.objects.create(akn_uri=uri, type='order', title_ar='قرار وزيري', first_published_in=issue)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 11, 2), consolidation=consolidation,
                               preamble=preamble, closing=closing, source_pages=pages)
    Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', body=body, printed_page=page)
    return text


def entries(text: Text) -> int:
    return SearchEntry.objects.filter(text_path=text_path(text.akn_uri)).count()


# ── clean_remarks ──────────────────────────────────────────────────────────────────────────────────────────────────

NOTICE = ('وصرح طالب التسجيل بان ليس فى علمه على الملك المذكور ادنى تحمل\nاو حق عقاري حالي او طاري.\n\n'
          'وانه يملكه بمقتضى خمسة رسوم منها اربعة مثبتة الاول بتاريخ اوائل شعبان 1320 موافق 28 يوليو 1911\n\n'
          'المحافظ على الاملاك العقارية بمكناس بالنيابة صاليل')
RETRY = ('مطلب عدد 36\n\n' + NOTICE + '\n\nوانه يملكه بقتضى خمسة رسوم منها اربعة مبتة الاول بتاريخ\n'
         'اوائل شعباeffective...\n\nLet me redo this carefully.\n\n'
         'وانه يملكه بمقتضى خمسة رسوم منها اربعة مثبتة الاول بتاريخ اوائل شعبان 1320 موافق 28 يوليو 1911\n\nمطلب عدد 37')


def test_clean_remarks_takes_the_model_s_remarks_out_only_with_write(tmp_path, answers):
    bo = test_pages.bo(7600, date(2026, 11, 2), 1, 0)
    noted = Page.objects.create(document=bo.document, index=0, kind='scan',
                                text='ظهير شريف\n\nNote: the table below is transcribed as printed.\n\n| 1 | 2 |')
    retried = Page.objects.create(document=bo.document, index=1, kind='scan', text=RETRY)
    french = Page.objects.create(document=bo.document, index=2, kind='scan', text='Article premier du dahir')
    loose = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='loose', path='loose.pdf', bytes=1,
                                    mime='application/pdf', language='ar', fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    unfiled = Page.objects.create(document=loose, index=0, kind='scan', text='عدد 5\n\nLet me redo this carefully.\n\nعدد 5')
    said = law('/akn/ma/act/arrete/2026-11-02/1', bo, body='يعمل به\n\nLet me transcribe carefully.\n\nمن تاريخ نشره',
               preamble='إن الوزير،\n\nNote: the page is read from right to left.')
    official = law('/akn/ma/act/arrete/2026-11-02/2', bo, body='يعمل به\n\nLet me transcribe carefully.',
                   consolidation=Consolidation.SGG)
    # A remark in its closing only, its preamble and articles clean.
    signed = law('/akn/ma/act/arrete/2026-11-02/3', bo, preamble='إن الوزير،',
                 closing='وحرر بالرباط في 2 نوفمبر 2026.\n\nNote: the page above is transcribed as printed.')
    before = {p.pk: p.text for p in Page.objects.all()}
    kept = {v.pk: (v.preamble, v.closing) for v in Version.objects.all()}

    review = tmp_path / 'retries.txt'
    out = run('clean_remarks', '--review', str(review))
    assert out.splitlines()[0].startswith('3 pages, 1 articles, 2 preambles or closings; by kind: ')
    assert f'2 retry cuts written to {review}' in out
    notes = review.read_text().split('\n\n')
    assert notes[0].startswith(f'=== general_ar 7600 p.1: {len(RETRY)} → ') and '-Let me redo this carefully.' in notes[0]
    assert notes[1].startswith(f'=== page {unfiled.pk}: ')
    assert {p.pk: p.text for p in Page.objects.all()} == before           # a dry run writes nothing
    assert {v.pk: (v.preamble, v.closing) for v in Version.objects.all()} == kept

    gen = answers.current('corpus')
    run('clean_remarks', '--write')
    texts = {p.pk: p.text for p in Page.objects.all()}
    assert texts[noted.pk] == 'ظهير شريف\n\n| 1 | 2 |'
    assert 'effective' not in texts[retried.pk] and texts[retried.pk].endswith('مطلب عدد 37')
    assert texts[french.pk] == 'Article premier du dahir' and texts[unfiled.pk] == 'عدد 5'
    assert Article.objects.get(version__text=said).body == 'يعمل به\n\nمن تاريخ نشره'
    assert said.versions.get().preamble == 'إن الوزير،'
    assert (signed.versions.get().preamble, signed.versions.get().closing) == ('إن الوزير،', 'وحرر بالرباط في 2 نوفمبر 2026.')
    assert 'Let me' in Article.objects.get(version__text=official).body   # the SGG's consolidation is its words
    assert entries(said) > 0 and entries(signed) > 0 and entries(official) == 0     # the texts changed indexed again
    assert answers.current('corpus') != gen


# ── fold_copies ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_fold_copies_lists_the_covers_and_folds_them_with_write(answers):
    cover = test_copies.issue(537, 1514091, cover='عدد 537 – و538')
    copy = test_copies.issue(538, 1514091)
    test_copies.issue(700, 5000)                                          # alone under its cover
    mine = test_copies.text(cover, 1, 'قرار وزيري في تعيين كاتب')
    fuller = test_copies.text(copy, 1, 'قرار وزيرى فى تعيين كاتب', articles=2)
    missed = test_copies.text(copy, 2, 'ظهير شريف في احداث جماعة لقبيلة بني ورياجل', articles=1)
    SearchEntry.objects.create(kind='text', text_path=text_path(fuller.akn_uri), path=text_path(fuller.akn_uri))
    for gone_or_kept in (fuller, mine):               # each text's passages, as the meaning model wrote them
        SearchPassage.objects.create(path=f'{text_path(gone_or_kept.akn_uri)}/art_1',
                                     text_path=text_path(gone_or_kept.akn_uri), model='bge-m3', vector=[0.5] * 1024)

    out = run('fold_copies')
    assert out.splitlines() == ['1 covers, 1 copies',
                                "  general_ar 537 ×2 (1923-08-14): texts {'537': 1, '538': 2} → 2 printed texts"]
    copy.refresh_from_db()
    assert copy.copy_of is None and Text.objects.count() == 3
    assert run('fold_copies', '--only', '538').splitlines() == ['0 covers, 0 copies']

    gen = answers.current('corpus')
    out = run('fold_copies', '--write')
    copy.refresh_from_db()
    assert copy.copy_of == cover
    assert out.splitlines()[-1] == '2 texts kept, 2 addresses now lead to them'
    assert not SearchEntry.objects.filter(text_path=text_path(fuller.akn_uri)).exists()     # gone: out of search
    assert list(SearchPassage.objects.values_list('text_path', flat=True)) == [text_path(mine.akn_uri)]
    kept = Text.objects.get(title_ar=missed.title_ar)
    assert entries(Text.objects.get(pk=mine.pk)) > 0 and entries(kept) > 0
    assert answers.current('corpus') != gen
    assert run('fold_copies', '--write').splitlines() == ['0 covers, 0 copies']


# ── renumber_pages ─────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.needs('tesseract')
def test_renumber_pages_numbers_the_sure_issues_and_those_their_pages_confirm(settings, tmp_path, answers):
    settings.CORPUS_DIR = tmp_path
    test_pages.bo(72, date(1914, 9, 17), 379, 26)
    bo73 = test_pages.bo(73, date(1914, 9, 18), 1, 6)                     # 405–410: the next issue starts at 411
    test_pages.bo(74, date(1914, 9, 28), 411, 3)
    moved = test_pages.text(bo73, '/akn/ma/act/arrete/1914-09-18/bo73-3', 4, '4-5', [4, 5])
    test_pages.bo(80, date(1915, 1, 5), 1, 10)
    test_pages.bo(81, date(1915, 1, 12), 1, 2)                            # its second page prints 12: it starts at 11
    write_pdf(tmp_path / 'BO_81.pdf', [[], ['12']])
    test_pages.bo(90, date(1916, 1, 5), 1, 4)
    test_pages.bo(91, date(1916, 1, 12), 1, 2)                            # prints nothing: left as it is
    write_pdf(tmp_path / 'BO_91.pdf', [[], []])
    off = test_pages.text(test_pages.bo(6856, date(2020, 2, 6), 829, 20), '/akn/ma/act/decret/2-20-30', 830,
                          '844-845', [844, 845])

    out = run('renumber_pages').splitlines()
    assert out[:4] == ['3 issues left at page 1 mid-year: 1 sure from their neighbours, 2 to read on the page',
                       '  general_ar 73 (1914-09-18, 6 pages): 1 → 405 [sure]',
                       '  general_ar 81 (1915-01-12, 2 pages): 1 → 11 [left]',
                       '  general_ar 91 (1916-01-12, 2 pages): 1 → 5 [left]']
    assert out[4:] == ['1 texts whose first page is not where their pages begin',
                       '  /akn/ma/act/decret/2-20-30: 830 → 844']
    assert Issue.objects.get(pk=bo73.pk).first_page_number == 1

    work = tmp_path / 'reports' / 'issues' / '73'                  # the issue's cut, moved with --files
    work.mkdir(parents=True)
    (work / 'toc.json').write_text(json.dumps([{'page': 4}]))
    gen = answers.current('corpus')
    out = run('renumber_pages', '--write', '--files').splitlines()
    assert out[1] == '  general_ar 73 (1914-09-18, 6 pages): 1 → 405 [sure] — 1 texts, 2 articles moved'
    assert out[2] == '  general_ar 81 (1915-01-12, 2 pages): 1 → 11 [confirmed] page 2 prints 12 — 0 texts, 0 articles moved'
    assert out[3] == '  general_ar 91 (1916-01-12, 2 pages): 1 → 5 [left] no page number read'
    assert out[4] == '1 texts whose first page is not where their pages begin — put right'
    assert [i.first_page_number for i in Issue.objects.filter(number__in=[73, 81, 91]).order_by('number')] == [405, 11, 1]
    moved.refresh_from_db()
    off.refresh_from_db()
    assert moved.first_published_page == 408 and off.first_published_page == 844
    assert moved.versions.get().source_pages == '408-409'
    assert sorted(Article.objects.filter(version__text=moved).values_list('printed_page', flat=True)) == [408, 409]
    assert list(bo73.document.pages.order_by('index').values_list('printed_number', flat=True)) == list(range(405, 411))
    assert json.loads((work / 'toc.json').read_text()) == [{'page': 408}]
    assert entries(moved) > 0 and entries(off) > 0
    assert answers.current('corpus') != gen


# ── merge_rereads ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_merge_rereads_weighs_each_page_read_again_and_writes_with_write(answers):
    bo = test_pages.bo(30, date(1913, 11, 28), 221, 0)
    page = Page.objects.create(document=bo.document, index=7, printed_number=228, kind='scan',
                               text='في اوائل شعباeffective 1329 بمقتضى رسوم')
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='page-1596', text=page.text)
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='reread: page-1596',
                          text='في اوائل شعبان 1329 بمقتضى رسوم')
    other = Page.objects.create(document=bo.document, index=8, printed_number=229, kind='scan', text='نص لم يقرأ ثانية')
    stale = Suspect.objects.create(page=other, word='الحدام', suggestion='الخدام', signal='rare')
    standing = Suspect.objects.create(page=other, word='ثانية', suggestion='تانية', signal='rare')
    text = law('/akn/ma/act/texte/1913-11-28/bo30-5', bo, body='في اوائل شعباeffective 1329', pages='228-228')
    # Another issue's page read again in full (a column the first reading lost): no word put right, no article on it
    # changed, yet its issue's texts are indexed again.
    bo31 = test_pages.bo(31, date(1913, 12, 5), 233, 0)
    short = ' '.join(f'كلمة{i}' for i in range(60))
    longer = Page.objects.create(document=bo31.document, index=0, printed_number=233, kind='scan', text=short)
    OcrRun.objects.create(page=longer, engine='claude-haiku-5-5', variant='page-1596', text=short)
    OcrRun.objects.create(page=longer, engine='claude-haiku-5-5', variant='reread: columns-3192',
                          text=short + ' ' + ' '.join(f'زيادة{i}' for i in range(50)))
    other_law = law('/akn/ma/act/texte/1913-12-05/bo31-1', bo31, pages='240-240')

    out = run('merge_rereads').splitlines()
    assert out == ['counting every word of the Bulletin…', 'articles 0, doubts 0, fuller 1, pages 2, words 1']
    page.refresh_from_db()
    assert 'شعباeffective' in page.text

    gen = answers.current('corpus')
    out = run('merge_rereads', '--write').splitlines()
    assert out[1] == 'articles 1, doubts 0, fuller 1, pages 2, words 1'
    assert out[2] == '1 suspects whose word is gone from its page taken out of the queue'
    page.refresh_from_db()
    assert page.text == 'في اوائل شعبان 1329 بمقتضى رسوم'
    assert Article.objects.get(version__text=text).body == 'في اوائل شعبان 1329'
    assert list(Suspect.objects.values_list('pk', flat=True)) == [standing.pk] and stale.pk != standing.pk
    longer.refresh_from_db()
    assert longer.text.endswith('زيادة49') and longer.text.startswith(short)
    assert entries(text) > 0 and entries(other_law) > 0 and answers.current('corpus') != gen


# ── import_rereads ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_import_rereads_keeps_each_reading_once_by_issue_and_place(tmp_path):
    bo = test_pages.bo(30, date(1913, 11, 28), 221, 2)
    copy = test_pages.bo(31, date(1913, 11, 28), 221, 2)          # stored under the next number: its cover's pages count
    Issue.objects.filter(pk=copy.pk).update(copy_of=bo)
    reading = 'المعلم ٥ بساسط الخدام ' * 12                       # longer than the 200 letters a reading is known by
    row = {'edition': 'general_ar', 'number': 30, 'suffix': '', 'index': 1, 'engine': 'claude-haiku-5-5',
           'variant': 'columns-3192 read again in strips at 1596 px', 'text': reading, 'prompt_version': 'v1',
           'image_px': '1596w/4', 'input_tokens': 2000, 'output_tokens': 400, 'cost_usd': '0.0026',
           'batch_id': 'msgbatch_01', 'stop_reason': 'end_turn'}
    elsewhere = {**row, 'number': 32, 'cost_usd': '1'}
    of_the_copy = {**row, 'number': 31, 'cost_usd': '1'}
    file = tmp_path / 'rereads.json'
    file.write_text(json.dumps([row, elsewhere, of_the_copy], ensure_ascii=False))
    with pytest.raises(CommandError, match='no such file'):
        run('import_rereads', str(tmp_path / 'none.json'))

    assert run('import_rereads', str(file)).strip() == '1 readings kept ($0.00), 2 pages not found here'
    run_ = OcrRun.objects.get()
    assert (run_.page.document.issue, run_.page.index, run_.text, str(run_.cost_usd)) == (bo, 1, reading, '0.002600')
    assert run_.variant == 'reread: columns-3192 read again in strip'          # cut to its column, 40 letters
    assert (run_.engine, run_.prompt_version, run_.image_px) == ('claude-haiku-5-5', 'v1', '1596w/4')
    assert (run_.input_tokens, run_.output_tokens, run_.batch_id, run_.stop_reason) == (2000, 400, 'msgbatch_01', 'end_turn')
    assert run('import_rereads', str(file)).strip() == '0 readings kept ($0.00), 2 pages not found here'
    assert OcrRun.objects.count() == 1


def test_the_readings_kept_add_up_their_cost(tmp_path):
    test_pages.bo(30, date(1913, 11, 28), 221, 2)
    rows = [{'edition': 'general_ar', 'number': 30, 'suffix': '', 'index': k, 'engine': 'claude-haiku-5-5',
             'variant': 'page-1596', 'text': f'صفحة {k}', 'prompt_version': 'v1', 'image_px': '1596w',
             'input_tokens': 1, 'output_tokens': 1, 'cost_usd': cost, 'batch_id': 'b', 'stop_reason': ''}
            for k, cost in ((0, '0.75'), (1, '0.5'))]
    (tmp_path / 'r.json').write_text(json.dumps(rows, ensure_ascii=False))
    assert run('import_rereads', str(tmp_path / 'r.json')).strip() == '2 readings kept ($1.25), 0 pages not found here'
    assert Counter(OcrRun.objects.values_list('page__index', flat=True)) == {0: 1, 1: 1}
