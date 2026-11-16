"""`draw_pages`: the reading images of the pages the shelf's named texts stand on, drawn ahead of their first reader;
a page drawn already is passed over, one that cannot be drawn is said and passed. The files are real PDFs."""
import io
from datetime import date

import pytest
from django.core.management import call_command
from django.db.models import F
from PIL import Image

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Page
from apps.sources.services.ingest import ingest_file
from apps.sources.tests.bo import DECREE, register, write_pdf

pytestmark = pytest.mark.django_db


def run(*args) -> tuple[str, str]:
    out, err = io.StringIO(), io.StringIO()
    call_command('draw_pages', *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def named(uri, consolidation, pages, issue=None, document=None):
    text = Text.objects.create(akn_uri=uri, type='code', title_ar='مدونة', first_published_in=issue)
    old = Version.objects.create(text=text, language='ar', valid_from=date(2000, 1, 1), consolidation=consolidation,
                                 source_document=document)
    Article.objects.create(version=old, order=1, label='الفصل 1', eid='art_1', body='نص قديم', printed_page=99)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 1, 1), consolidation=consolidation,
                               source_document=document)
    for k, page in enumerate(pages, 1):
        Article.objects.create(version=v, order=k, label=f'الفصل {k}', eid=f'art_{k}', body='يعمل به', printed_page=page)
    return text


def test_the_named_texts_pages_are_drawn_once_ahead_of_their_readers(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    # The Constitution as the BO printed it: its articles on the issue's folios 3601 and 3602.
    bo = register(tmp_path, 5964, [DECREE, DECREE, DECREE], day=date(2011, 7, 30), suffix='bis')
    Page.objects.filter(document=bo.document).update(printed_number=F('index') + 3600)
    named('/akn/ma/act/dahir/1-11-91', Consolidation.AS_PUBLISHED, [3601, 3602, 3602], issue=bo)
    # The DOC from Adala's own file: its pages by position (article 1 on the file's first page).
    adala = ingest_file(write_pdf(tmp_path / 'sources' / 'adala' / 'doc.pdf', [DECREE, DECREE]), source='adala',
                        kind='text', language='ar')
    named('/akn/ma/act/code/doc', Consolidation.ADALA, [1], document=adala)
    # The tax code's file was never fetched here: its page cannot be drawn.
    gone = ingest_file(write_pdf(tmp_path / 'sources' / 'dgi' / 'cgi.pdf', [DECREE]), source='dgi', kind='text',
                       language='ar')
    (tmp_path / 'sources' / 'dgi' / 'cgi.pdf').unlink()
    named('/akn/ma/act/code/cgi', Consolidation.DGI, [1], document=gone)
    Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='مدونة الأسرة')   # no version

    out, err = run('--limit', '1')
    assert out.splitlines() == ['4 texts, 4 pages to have at 900 px', 'done: 1 drawn, 0 already there, 0 failed, at 900 px']
    out, err = run()
    assert out.splitlines()[1] == 'done: 2 drawn, 1 already there, 1 failed, at 900 px'
    assert err.startswith(f'{gone.pk}/0: ')
    drawn = {p.relative_to(tmp_path / 'renders').as_posix() for p in (tmp_path / 'renders').rglob('*.webp')}
    assert drawn == {f'{adala.sha256[:16]}/0000-900.webp', f'{bo.document.sha256[:16]}/0001-900.webp',
                     f'{bo.document.sha256[:16]}/0002-900.webp'}
    with Image.open(tmp_path / 'renders' / f'{adala.sha256[:16]}/0000-900.webp') as image:
        assert image.format == 'WEBP' and image.width == 900
    out, _ = run('--width', '1600')
    assert out.splitlines()[1] == 'done: 3 drawn, 0 already there, 1 failed, at 1600 px'
    assert run()[0].splitlines()[1] == 'done: 0 drawn, 3 already there, 1 failed, at 900 px'
