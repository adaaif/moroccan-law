"""A text held without the page it was printed on (`Text.first_published_page` empty) is counted like any other, its
mentions with no page. The mentions go to PostgreSQL's COPY through a csv writer that doubles every backslash, as COPY's
text format wants; it doubled the NULL marker's too, and COPY read «\\N» as a page number: build_places failed."""
import io
import json
from datetime import date

import pytest
from django.core.management import call_command
from django.db import connection

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.places.models import Mention
from apps.places.services import build
from apps.sources.models import Edition, Issue

pytestmark = [pytest.mark.django_db,
              pytest.mark.skipif(connection.vendor != 'postgresql', reason="the swap is PostgreSQL's COPY (TEST_DATABASE_URL)")]


def test_a_text_without_its_page_is_counted(tmp_path, monkeypatch):
    listed = tmp_path / 'places.json'
    listed.write_text(json.dumps([r for r in build.gazetteer() if r['slug'] == 'france'], ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(build, 'DATA', listed)
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=6340, date=date(2015, 3, 1))
    text = Text.objects.create(akn_uri='/akn/ma/act/dahir/2015/1-15-1', type='dahir', number='1-15-1', title_ar='ظهير شريف رقم 1.15.1',
                               first_published_in=issue)
    version = Version.objects.create(text=text, language='ar', valid_from=date(2015, 3, 1), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=version, order=1, label='المادة 1', number='1', eid='art_1', body='اتفاق مع فرنسا')
    out = io.StringIO()
    call_command('build_places', stdout=out)
    assert out.getvalue().endswith("{'texts': 1, 'articles': 1, 'mentions': 1, 'places': 1, 'years': 1}\n")
    assert list(Mention.objects.values_list('place__slug', 'eid', 'page', 'form')) == [('france', 'art_1', None, 'فرنسا')]
