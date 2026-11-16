"""`read_regions`, the night's reading of the word boxes (N13 of the read-and-trusted review): the pages readers asked for
first, then the named texts' documents, then the issues; each page once, a page read already passed over, and the list of
pages asked for left with only those still to read. Tesseract and the files are real."""
import io
from datetime import date

import pytest
from django.core.management import call_command

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document
from apps.sources.services import regions
from apps.sources.services.ingest import ingest_file
from apps.sources.tests.bo import register, write_pdf

pytestmark = [pytest.mark.django_db, pytest.mark.needs('tesseract')]
NO_WORDS = '; 0 pages of doubtful words read, 0 words placed'


def run(*args) -> str:
    out = io.StringIO()
    call_command('read_regions', *args, stdout=out)
    return out.getvalue().strip()


def test_the_night_reads_the_pages_asked_for_then_the_named_texts_then_the_issues(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    # The constitution's issue, its page with words; the DOC's Adala file and an issue of the week, blank pages.
    bo = register(tmp_path, 5964, [['المادة 1', 'المملكة المغربية دولة إسلامية ذات سيادة كاملة']],
                  day=date(2011, 7, 30), suffix='bis')
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1-11-91', type='dahir', title_ar='الدستور', first_published_in=bo)
    adala = ingest_file(write_pdf(tmp_path / 'sources' / 'adala' / 'doc.pdf', [[]]), source='adala', kind='text',
                        language='ar')
    doc = Text.objects.create(akn_uri='/akn/ma/act/code/doc', type='code', title_ar='قانون الالتزامات والعقود')
    version = Version.objects.create(text=doc, language='ar', valid_from=date(2026, 1, 1), source_document=adala,
                                     consolidation=Consolidation.ADALA)
    Article.objects.create(version=version, order=1, label='الفصل 1', eid='art_1', body='يعمل به')
    week = register(tmp_path, 7600, [[]], day=date(2026, 11, 2))
    page = bo.document.pages.get()
    regions.wanted_path().parent.mkdir(parents=True, exist_ok=True)
    regions.wanted_path().write_text(f'not a page\npage seven\n999 0\n{week.document_id} 0\n{bo.document_id} 7 3\n')

    # A night with no time left reads nothing; the list keeps the page asked for, and drops what is no page.
    assert run('--minutes', '-1') == '0 pages read, 0 without words; 1 asked for still to read' + NO_WORDS
    assert regions.wanted_path().read_text() == f'{week.document_id} 0\n'

    # The page asked for is read only with --wanted-only: blank, it has no words.
    assert run('--wanted-only') == '0 pages read, 1 without words; 0 asked for still to read' + NO_WORDS
    assert regions.read_yet(week.document.pages.get()) and not regions.read_yet(page)
    assert regions.wanted_path().read_text() == ''

    # The night goes on: the named texts' pages, the constitution's with its words in their boxes.
    assert run() == '1 pages read, 1 without words; 0 asked for still to read' + NO_WORDS
    words = [w for line in regions.parse(regions.boxes_path(page).read_text()) for w in line.words]
    assert words and regions.read_yet(adala.pages.get())
    assert run() == '0 pages read, 0 without words; 0 asked for still to read' + NO_WORDS
    assert Document.objects.count() == 3
