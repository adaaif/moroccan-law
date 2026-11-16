"""FX10 of the mended-Bulletin review: a second reading weighed against the first."""
from collections import Counter
from datetime import UTC, date, datetime

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.models import Suspect
from apps.sources.models import Document, Issue, OcrRun, Page
from apps.sources.services import rereads

COUNTS = Counter({'الخدام': 300, 'بساسط': 40, 'شعبان': 900, 'الوتد': 60, 'السديد': 70})


def test_a_glued_word_gives_way_to_the_clean_one():
    text, changes, _doubts, fuller = rereads.weigh('اوائل شعباeffective 1329', 'اوائل شعبان 1329', COUNTS)
    assert text == 'اوائل شعبان 1329' and changes[0].why == 'glued' and not fuller


def test_a_word_seen_once_gives_way_to_its_common_dotted_twin():
    text, changes, _, _ = rereads.weigh('المعلم ٥ بساسط الحدام ٢٫٥٠', 'المعلم ٥ بساسط الخدام ٢٫٥٠', COUNTS)
    assert text == 'المعلم ٥ بساسط الخدام ٢٫٥٠' and changes[0].why == 'rare' and changes[0].before == 'بساسط'


def test_two_plausible_words_are_left_to_a_person():
    text, changes, doubts, _ = rereads.weigh('نظرنا الوتد بالله', 'نظرنا الوبد بالله', Counter({'الوتد': 60, 'الوبد': 30}))
    assert text == 'نظرنا الوتد بالله' and not changes and doubts[0][:2] == ('الوتد', 'الوبد')


def test_a_fuller_reading_takes_the_page():
    old = ' '.join(f'كلمة{i}' for i in range(100))
    new = old + ' ' + ' '.join(f'زيادة{i}' for i in range(60))
    text, _, _, fuller = rereads.weigh(old, new, Counter())
    assert fuller and text == new


@pytest.mark.django_db
def test_merging_puts_the_page_and_its_articles_right_and_runs_again_alike():
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='h30', path='30.pdf', mime='application/pdf',
                                  bytes=1, language='ar', page_count=8, fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    issue = Issue.objects.create(edition='general_ar', number=30, date=date(1913, 11, 28), document=doc, first_page_number=221)
    page = Page.objects.create(document=doc, index=7, printed_number=228, kind='scan', text='المعلم ٥ بساسط الحدام ٢٫٥٠')
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='page-1596', text='المعلم ٥ بساسط الحدام ٢٫٥٠')
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='reread: page-1596', text='المعلم ٥ بساسط الخدام ٢٫٥٠')
    text = Text.objects.create(akn_uri='/akn/ma/act/texte/1913-11-28/bo30-5', type='other', title_ar='بيان',
                               first_published_in=issue)
    v = Version.objects.create(text=text, language='ar', valid_from=issue.date, source_pages='228-228',
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='', eid='art_1', body='بساسط الحدام ٢٫٥٠ للنهار')
    done = rereads.merge(page, COUNTS, write=True)
    assert done['words'] == 1 and done['articles'] == 1
    page.refresh_from_db()
    assert page.text == 'المعلم ٥ بساسط الخدام ٢٫٥٠'
    assert Article.objects.get().body == 'بساسط الخدام ٢٫٥٠ للنهار'
    # Again (after a reload reset the article): the same word is found and given back.
    Article.objects.update(body='بساسط الحدام ٢٫٥٠ للنهار')
    assert rereads.merge(page, COUNTS, write=True)['articles'] == 1
    assert page.ocr_runs.filter(engine='vote', variant='merged with a reread').count() == 1
    assert not Suspect.objects.exists()


def test_how_common_words_are_settles_most_dots_but_not_two_common_words():
    counts = Counter({'وسرقا': 38, 'وشرقا': 167164, 'المنعقد': 14154, 'المتعقد': 24, 'سته': 26376, 'سنه': 918292,
                      'رسوم': 5000})
    text, changes, doubts, _ = rereads.weigh('جوفا بغداد وسرقا احميدة', 'جوفا بغداد وشرقا احميدة', counts)
    assert text.endswith('وشرقا احميدة') and changes[0].why == 'rare'
    text, changes, doubts, _ = rereads.weigh('الغاء البيع المنعقد بشأن', 'الغاء البيع المتعقد بشأن', counts)
    assert text == 'الغاء البيع المنعقد بشأن' and not changes and not doubts
    text, changes, doubts, _ = rereads.weigh('بمقتضى ستة رسوم', 'بمقتضى سنة رسوم', counts)
    assert text == 'بمقتضى ستة رسوم' and not changes and doubts[0][:2] == ('ستة', 'سنة')
