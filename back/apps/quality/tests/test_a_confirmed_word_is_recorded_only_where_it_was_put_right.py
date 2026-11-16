"""A suspect confirmed (FX9) is put right in its page and in the articles printed there, each «recorded as a correction
read against the page's image». An article that holds the word between other neighbours is not the place the person
read: nothing is put right there, so nothing may be recorded there either. A correction recorded there would be listed
on /corrections as put right in an article it never changed."""
from datetime import UTC, date, datetime

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.models import Correction, Suspect
from apps.quality.services import suspects
from apps.sources.models import Document, Issue, Page

pytestmark = pytest.mark.django_db


def test_an_article_where_the_word_has_other_neighbours_gets_no_correction(api):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='h30', path='30.pdf', mime='application/pdf',
                                  bytes=1, language='ar', fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    issue = Issue.objects.create(edition='general_ar', number=30, date=date(1913, 11, 28), document=doc)
    page = Page.objects.create(document=doc, index=7, printed_number=228, kind='scan',
                               text='بساسط الحدام ٢٫٥٠ التجار ثم الحدام ٣')
    text = Text.objects.create(akn_uri='/akn/ma/act/texte/1913-11-28/bo30-5', type='other', title_ar='بيان',
                               first_published_in=issue)
    v = Version.objects.create(text=text, language='ar', valid_from=date(1913, 11, 28), source_pages='228-228',
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='', eid='art_1', body='بساسط الحدام ٢٫٥٠ التجار')
    Article.objects.create(version=v, order=2, label='', eid='art_2', body='ثم الحدام ٣')
    s = Suspect.objects.create(page=page, word='الحدام', suggestion='الخدام', context='بساسط الحدام ٢٫٥٠ التجار',
                               signal='rare')
    assert suspects.confirm(s) == 1
    assert Article.objects.get(eid='art_2').body == 'ثم الحدام ٣'
    assert set(Correction.objects.values_list('path', flat=True)) == {
        '/bo/general_ar/30#p7', '/ma/texte/1913-11-28/bo30-5/art_1'}
    listed = api.get('/api/quality/corrections/').json()['applied']
    assert sorted(row['path'] for row in listed) == ['/bo/general_ar/30#p7', '/ma/texte/1913-11-28/bo30-5/art_1']
