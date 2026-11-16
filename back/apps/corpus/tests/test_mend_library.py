"""`mend_library` (W11 of the library-search review): what the library said wrong about its own books, reported, and with
--write mended; run again, what is right is left alone. The tax code's headings need the DGI's edition on the disk,
and are said to be left as they are without it."""
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.corpus.models import Consolidation, Text, Version
from apps.search.models import SearchEntry
from apps.sources.models import Document

pytestmark = pytest.mark.django_db
TITLE = 'قانون تنظيمي رقم 113.14 يتعلق بالجماعات'


@pytest.fixture(autouse=True)
def books_read_afresh():
    """The library's books are kept in the process for a generation (find.kept): each test reads its own rows."""
    from apps.corpus.services.find import kept
    kept._KEPT.clear()
    yield
    kept._KEPT.clear()


def run(*args) -> list[str]:
    out = StringIO()
    call_command('mend_library', *args, stdout=out)
    return out.getvalue().splitlines()


def test_the_library_is_mended_once_and_left_alone_after(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    doc = Text.objects.create(akn_uri='/akn/ma/act/code/doc', type='code', title_ar='قانون الالتزامات والعقود',
                              status='unknown')
    Version.objects.create(text=doc, language='ar', valid_from=date(2024, 1, 1), consolidation=Consolidation.ADALA)
    communes = Text.objects.create(akn_uri='/akn/ma/act/loi-organique/113-14', type='organic_law', number='113-14',
                                   title_ar=f'{TITLE} قسم تمهيدي أحكام عامة')
    Text.objects.create(akn_uri='/akn/ma/act/loi/1-1', type='law', title_ar='قانون أحكام عامة')      # too short left
    said = run()
    assert said[0] == '1. the tax code is not held here'
    assert '2. /akn/ma/act/code/doc: signed on 1913-08-12 (9 رمضان 1331), was no day' in said
    [title] = [line for line in said if line.startswith('3. ')]
    assert title.startswith('3. /akn/ma/act/loi-organique/113-14: «…') and title.endswith(f' → «…{TITLE[-24:]}»')
    assert 'بالجماعات قسم تمهيدي أحكام عامة» → ' in title
    assert '4. /akn/ma/act/code/doc: status unknown' in said
    assert '4. /akn/ma/act/loi-organique/113-14: status unknown' in said
    assert said[-1] == 'nothing written (run with --write)'
    assert Text.objects.get(pk=doc.pk).signed_on is None

    said = run('--write')
    doc.refresh_from_db()
    communes.refresh_from_db()
    assert (doc.signed_on, doc.signed_on_hijri) == (date(1913, 8, 12), '9 رمضان 1331')
    assert communes.title_ar == TITLE
    assert said[-2:] == ['search entries written again: 2', 'written']
    assert SearchEntry.objects.filter(text_path='/ma/loi-organique/113-14', kind='text').exists()

    Text.objects.filter(pk__in=[doc.pk, communes.pk]).update(status='in_force')
    said = run('--write')
    assert said[1:] == ['2. the two compiled codes carry their signing day', "3. no title ends on its text's first heading",
                        '4. every book of the library has a status', 'written']


def test_the_tax_codes_headings_wait_for_its_edition_on_the_disk(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    cgi = Text.objects.create(akn_uri='/akn/ma/act/code/cgi', type='code', title_ar='المدونة العامة للضرائب')
    edition = Document.objects.create(source='dgi', kind='code', sha256='c' * 64, path='sources/dgi/cgi_2026_ar.pdf',
                                      mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now())
    Version.objects.create(text=cgi, language='ar', valid_from=date(2026, 1, 1), consolidation=Consolidation.ADALA,
                           source_document=edition)
    assert run()[0] == ("1. the tax code's edition is not on this disk "
                        f"({tmp_path}/sources/dgi/cgi_2026_ar.pdf): its headings are left as they are")
