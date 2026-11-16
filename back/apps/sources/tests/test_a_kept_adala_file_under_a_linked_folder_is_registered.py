"""`fetch_adala --kept` registers a file already fetched, under CORPUS_DIR. The corpus's folders may be links to a
larger disk (`sources`, `issues/bo_ar` and `samples` under CORPUS_DIR often are), so a path is checked by its own parts, as
`ingest.corpus_path` checks it, never by resolving the links: resolved, every kept file of `sources/` lay «outside» the
corpus and was refused, the command's own example among them."""
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.sources.models import Document
from apps.sources.tests.bo import DECREE, write_pdf

pytestmark = pytest.mark.django_db

ADALA = 'https://adala.justice.gov.ma/api/uploads/2026/02/10/2.10.420.pdf'


def test_a_kept_file_in_a_folder_linked_to_another_disk_is_registered(settings, tmp_path):
    corpus, disk = tmp_path / 'data', tmp_path / 'hdd'
    write_pdf(disk / 'sources' / 'road' / 'adala_2_10_420_ar_2026.pdf', [DECREE, DECREE])
    corpus.mkdir()
    (corpus / 'sources').symlink_to(disk / 'sources', target_is_directory=True)
    settings.CORPUS_DIR = corpus
    out = io.StringIO()
    call_command('fetch_adala', ADALA, '--kept', 'sources/road/adala_2_10_420_ar_2026.pdf', stdout=out)
    doc = Document.objects.get()
    assert (doc.path, doc.url, doc.source, doc.page_count) == ('sources/road/adala_2_10_420_ar_2026.pdf', ADALA, 'adala', 2)
    assert out.getvalue().startswith('sources/road/adala_2_10_420_ar_2026.pdf: 2 pages, sha256 ')


@pytest.mark.parametrize('kept', ['../../etc/x.pdf', '/etc/x.pdf', 'sources/../../x.pdf'])
def test_a_kept_path_that_climbs_out_of_the_corpus_is_still_refused(settings, tmp_path, kept):
    settings.CORPUS_DIR = tmp_path / 'data'
    write_pdf(tmp_path / 'x.pdf', [DECREE])
    with pytest.raises(CommandError, match='not under CORPUS_DIR'):
        call_command('fetch_adala', ADALA, '--kept', kept)
    assert not Document.objects.exists()
