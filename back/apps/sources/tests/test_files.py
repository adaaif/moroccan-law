"""The source files the site hands out: only the law's own files (a Bulletin issue, an official consolidation or text,
a bill), a PDF in the browser's viewer, anything else as a sandboxed download; everything else kept stays on disk."""
import pytest
from django.core.exceptions import SuspiciousFileOperation
from django.utils import timezone

from apps.sources.models import Document, Page
from apps.sources.services.ingest import corpus_path

pytestmark = pytest.mark.django_db


@pytest.fixture
def corpus(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    return tmp_path


def kept(corpus, path, content, *, kind, source, mime):
    file = corpus / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(content)
    doc = Document.objects.create(source=source, kind=kind, sha256=path.ljust(64, '0')[:64], path=path, mime=mime,
                                  bytes=len(content), language='ar', page_count=1, fetched_at=timezone.now())
    Page.objects.create(document=doc, index=0, kind='text_layer', text='نص الصفحة', text_source='layer')
    return doc


def test_a_bulletin_issue_opens_in_the_browser(api, corpus):
    doc = kept(corpus, 'issues/BO_7533_ar.pdf', b'%PDF-1.4 issue', kind='bo_issue', source='sgg_bo',
               mime='application/pdf')
    r = api.get(f'/api/sources/documents/{doc.pk}/file/')
    assert r.status_code == 200 and r['Content-Type'] == 'application/pdf'
    assert r['Content-Disposition'].startswith('inline') and r['X-Content-Type-Options'] == 'nosniff'
    assert not r.has_header('Content-Security-Policy')
    assert b''.join(r.streaming_content) == b'%PDF-1.4 issue'


def test_a_saved_web_page_leaves_as_a_download_that_never_runs_as_the_site(api, corpus):
    # A page saved from Parliament's site, with its scripts: it must never run from this site's address.
    doc = kept(corpus, 'sources/parliament/proposal.html', b'<script src="https://example.org/gtm.js"></script>',
               kind='parliament', source='parliament', mime='text/html')
    r = api.get(f'/api/sources/documents/{doc.pk}/file/')
    assert r.status_code == 200
    assert r['Content-Disposition'].startswith('attachment') and 'proposal.html' in r['Content-Disposition']
    assert r['Content-Security-Policy'] == 'sandbox' and r['X-Content-Type-Options'] == 'nosniff'
    r.close()


@pytest.mark.parametrize('kind, source, path, mime', [
    ('court_decision', 'constitutional_court', 'samples/court/d1.html', 'text/html'),     # the parties' names
    ('code_page', 'other', 'samples/other/code.htm', 'text/html'),
    ('text', 'other', 'sources/habous/statement.html', 'text/html'),                        # another site's page
    ('bulletin', 'other', 'sources/hcp/indicators.pdf', 'application/pdf'),                 # a statistics report
])
def test_a_file_the_site_does_not_publish_answers_404_and_so_do_its_pages(api, corpus, kind, source, path, mime):
    doc = kept(corpus, path, b'kept as evidence', kind=kind, source=source, mime=mime)
    assert api.get(f'/api/sources/documents/{doc.pk}/file/').status_code == 404
    assert api.get(f'/api/sources/documents/{doc.pk}/pages/0/').status_code == 404
    assert api.get(f'/api/sources/documents/{doc.pk}/pages/0/image/').status_code == 404


def test_a_row_whose_file_is_gone_answers_404(api, corpus):
    doc = kept(corpus, 'issues/BO_1_ar.pdf', b'%PDF-1.4', kind='bo_issue', source='sgg_bo', mime='application/pdf')
    (corpus / doc.path).unlink()
    assert api.get(f'/api/sources/documents/{doc.pk}/file/').status_code == 404


@pytest.mark.parametrize('escape', ['absolute', '../server.env', 'issues/../../server.env'])
def test_a_documents_path_never_leaves_the_corpus_folder(api, corpus, settings, escape):
    # A row's path pointed at a file beside the corpus: the endpoint would have served the server's secrets.
    inside = corpus / 'corpus'
    secret = corpus / 'server.env'
    secret.write_text('SECRET_KEY=never-out')
    doc = kept(inside, 'issues/BO_2_ar.pdf', b'%PDF-1.4', kind='bo_issue', source='sgg_bo', mime='application/pdf')
    Document.objects.filter(pk=doc.pk).update(path=str(secret) if escape == 'absolute' else escape)
    settings.CORPUS_DIR = inside
    r = api.get(f'/api/sources/documents/{doc.pk}/file/')
    assert r.status_code == 404 and b'never-out' not in b''.join(getattr(r, 'streaming_content', [r.content]))
    with pytest.raises(SuspiciousFileOperation):
        corpus_path(Document.objects.get(pk=doc.pk))


def test_a_corpus_folder_that_is_a_link_to_another_disk_still_serves(api, corpus, tmp_path_factory):
    # The corpus's folders may be links to another disk: the check reads the path, it does not resolve links.
    disk = tmp_path_factory.mktemp('disk')
    (disk / 'BO_3_ar.pdf').write_bytes(b'%PDF-1.4 elsewhere')
    (corpus / 'issues').symlink_to(disk, target_is_directory=True)
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='3' * 64, path='issues/BO_3_ar.pdf',
                                  mime='application/pdf', bytes=18, language='ar', fetched_at=timezone.now())
    r = api.get(f'/api/sources/documents/{doc.pk}/file/')
    assert r.status_code == 200 and b''.join(r.streaming_content) == b'%PDF-1.4 elsewhere'


def test_the_admin_never_edits_where_a_file_lies_nor_adds_one(admin_client, corpus):
    doc = kept(corpus, 'issues/BO_4_ar.pdf', b'%PDF-1.4', kind='bo_issue', source='sgg_bo', mime='application/pdf')
    form = admin_client.get(f'/admin/sources/document/{doc.pk}/change/').content.decode()
    assert 'name="path"' not in form and 'name="mime"' not in form and 'name="sha256"' not in form
    admin_client.post(f'/admin/sources/document/{doc.pk}/change/', {
        'source': 'sgg_bo', 'kind': 'bo_issue', 'path': '/etc/passwd', 'mime': 'text/plain', 'sha256': 'x', 'bytes': 1,
        'language': 'ar', 'title': 'a title', 'url': '', 'producer': '', 'meta': '{}',
        'fetched_at_0': '2026-11-12', 'fetched_at_1': '10:00:00'})
    doc.refresh_from_db()
    assert (doc.path, doc.mime) == ('issues/BO_4_ar.pdf', 'application/pdf')
    assert admin_client.get('/admin/sources/document/add/').status_code == 403
