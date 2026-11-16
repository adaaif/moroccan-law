"""H5 of the housing plan: a title keeps the BO's heading; articles read as one are cut apart."""
import json
from datetime import date

import pytest
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.services import glued
from apps.corpus.services.titles import full_title, restore
from apps.sources.models import Document, Edition, Issue

pytestmark = pytest.mark.django_db
HEAD = 'مرسوم رقم 2.23.350 صادر في فاتح جمادى الأولى 1445 (15 نوفمبر 2023) بتحديد أشكال إعانة الدولة لدعم السكن.'


def test_the_contents_heading_wins_over_the_models_short_title():
    assert full_title('بتحديد أشكال إعانة الدولة لدعم السكن', HEAD, '', '2.23.350') == HEAD.rstrip('.')
    assert full_title('مرسوم رقم 2.23.350 بتحديد', HEAD, '', '2.23.350') == 'مرسوم رقم 2.23.350 بتحديد'   # already headed
    assert full_title('بتحديد أشكال', 'بلاغ', '', '2.23.350') == 'بتحديد أشكال'                         # nothing better


def test_restore_reads_the_issues_contents(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='7250' * 16, path='BO_7250_ar.pdf',
                                  mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now(), page_count=2)
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7250, date=date(2023, 11, 23), document=doc)
    text = Text.objects.create(akn_uri='/akn/ma/act/decret/2-23-350', type='decree', number='2-23-350',
                               number_as_printed='2.23.350', title_ar='بتحديد أشكال إعانة الدولة لدعم السكن',
                               first_published_in=issue)
    work = tmp_path / 'reports' / 'issues' / '7250'
    work.mkdir(parents=True)
    (work / 'texts.json').write_text(json.dumps([{'toc': {'title': HEAD, 'number_as_printed': '2.23.350'}, 'front': HEAD,
        'data': {'number_as_printed': '2.23.350', 'title': 'بتحديد أشكال إعانة الدولة لدعم السكن'}}], ensure_ascii=False))
    assert restore(log=lambda *a: None, write=True)['restored'] == 1
    text.refresh_from_db()
    assert text.title_ar == HEAD.rstrip('.')


def test_two_articles_read_as_one_are_cut_apart():
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/58-25', type='law', number='58-25', title_ar='قانون رقم 58.25')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 2, 23), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة 466', number='466', eid='art_466',
                           body='إذا كان تنفيذ السند متوقفا على القيام بعمل.\nالمادة467\nيبلغ المفوض القضائي السند.')
    Article.objects.create(version=v, order=2, label='المادة 468', number='468', eid='art_468', body='نص.')
    assert glued.repair(log=lambda *a: None, write=True) == 1
    assert list(v.articles.values_list('eid', 'body')) == [
        ('art_466', 'إذا كان تنفيذ السند متوقفا على القيام بعمل.'), ('art_467', 'يبلغ المفوض القضائي السند.'), ('art_468', 'نص.')]
