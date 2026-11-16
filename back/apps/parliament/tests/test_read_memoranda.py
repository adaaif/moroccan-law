"""`read_memoranda`: each fetched bill's first pages read by the model in one batch (paid only under --write), the
memorandum cut from them and kept beside its law (`Explanation`); one that runs past the pages read gets two more,
a file that prints another bill's number is said and left. No test reaches the API: a fake client answers in its
place, in the API's own format."""
import hashlib
import io

import anthropic
import pytest
from anthropic.types import Message
from anthropic.types.messages import MessageBatch, MessageBatchIndividualResponse
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.parliament.models import Explanation
from apps.parliament.tests.pdfs import write_pdf
from apps.sources.models import Document, OcrRun, Page
from apps.sources.services.ocr import guard

pytestmark = pytest.mark.django_db

MODEL = 'claude-haiku-5-5'
LAW = '/akn/ma/act/loi/2026/013-26'
URL = 'https://www.chambredesrepresentants.ma/sites/default/files/loi/Projet_loi_013.26.pdf'
COVER = 'المملكة المغربية\nرئيس الحكومة\nمشروع قانون رقم 013.26\nبتغيير وتتميم القانون رقم 2.00'
MEMO = 'مذكرة تقديمية\nيأتي مشروع هذا القانون لملاءمة التشريع الوطني مع التطور الرقمي.\n2'
BILL = 'مشروع قانون رقم 013.26\nالمادة الأولى\nتغير أحكام المادة 8.'


def bill(pages: list[str] | None, *, uri=LAW, number='013.26', count=None, path='') -> Document:
    """A fetched bill whose pages are `pages`; None for a page the model has not read yet."""
    doc = Document.objects.create(
        source='parliament', kind='parliament', url=URL, sha256=hashlib.sha256(uri.encode()).hexdigest(),
        path=path or f'sources/parliament/bill_{number}.pdf', mime='application/pdf', bytes=1, language='ar',
        page_count=count or len(pages), fetched_at=timezone.now(), meta={'text_uri': uri, 'bill': number})
    for index, text in enumerate(pages):
        page = Page.objects.create(document=doc, index=index, kind='scan')
        if text is not None:
            OcrRun.objects.create(page=page, engine=MODEL, text=text)
    return doc


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    call_command('read_memoranda', *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def test_the_memorandum_of_pages_read_before_is_kept_beside_its_law_and_nothing_is_paid():
    doc = bill([COVER, MEMO, BILL])
    # The page read again since by the model, then by Tesseract: the model's newest reading counts.
    page = doc.pages.get(index=1)
    OcrRun.objects.create(page=page, engine=MODEL, text='مذكرة تقديمية\nيأتي هذا المشروع لحماية أفضل للمؤلفين.')
    OcrRun.objects.create(page=page, engine='tesseract-5', text='مذكرة تقديمية\nقراءة الشاهد.')
    said, err = run()
    memo = Explanation.objects.get(text_uri=LAW)
    assert (memo.kind, memo.source_url, memo.document_sha, memo.pages) == ('memorandum', URL, doc.sha256, '1-3')
    assert memo.body == 'يأتي هذا المشروع لحماية أفضل للمؤلفين.'
    assert said == '1 memoranda kept\n' and err == ''


def test_a_bill_explained_before_or_registered_for_no_law_is_not_read_again():
    # Their pages are unread and their files absent: reading them would stop the run.
    Explanation.objects.create(text_uri=LAW, body='مذكرة سابقة', source_url=URL, document_sha='a' * 64)
    bill([None, None], uri=LAW)
    sample = bill([None], uri='/akn/ma/act/loi/2025/041-25', number='041.25')
    sample.meta = {'sample': True}
    sample.save()
    assert run() == ('1 memoranda kept\n', '')
    assert Explanation.objects.get().body == 'مذكرة سابقة'


def test_a_file_that_prints_another_bills_number_is_said_and_left():
    bill([COVER.replace('013.26', '013.25'), MEMO, BILL.replace('013.26', '013.25')])
    said, err = run()
    assert err == f"013.26: the file read is another bill's ({URL})\n"
    assert said == '0 memoranda kept\n' and not Explanation.objects.exists()


def test_a_bill_with_no_memorandum_keeps_nothing():
    bill([COVER, BILL])
    assert run() == ('0 memoranda kept\n', '')


@pytest.mark.parametrize('pages, count, kept', [
    # Past the three pages read, two more were read before: the memorandum ends on the fifth.
    ([COVER, MEMO, 'فقرة ثانية.', 'فقرة ثالثة.', BILL], 5, ('1-5', 'فقرة ثالثة.')),
    # Its end is never found: kept as far as the file goes…
    ([COVER, MEMO, 'فقرة ثانية.'], 3, ('1-3', 'فقرة ثانية.')),
    # …or as far as the second look reads.
    ([COVER, MEMO, 'فقرة ثانية.', 'فقرة ثالثة.', 'فقرة رابعة.'], 9, ('1-5', 'فقرة رابعة.')),
])
def test_a_memorandum_that_runs_past_the_pages_read_gets_two_more(pages, count, kept):
    bill(pages, count=count)
    run('--pages', '3')
    memo = Explanation.objects.get()
    assert (memo.pages, memo.body.splitlines()[-1]) == kept


def test_pages_not_read_yet_are_never_sent_without_write(monkeypatch, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    monkeypatch.setattr(guard, '_SPENDING', False)
    monkeypatch.setattr(anthropic, 'Anthropic', lambda **kw: pytest.fail('a client was made'))
    write_pdf(tmp_path / 'sources' / 'parliament' / 'bill_013.26.pdf', [[], [], []])
    bill([None, None, None])
    with pytest.raises(CommandError, match='--write'):
        run()
    assert not OcrRun.objects.exists() and not Explanation.objects.exists()


class Batches:
    """The Message Batches API: a batch made of the requests sent, ended at once, each page answered by `read`."""

    def __init__(self, read: dict[str, str]):
        self.read, self.sent = read, []

    def _batch(self, status):
        return MessageBatch.model_validate({
            'id': 'msgbatch_01', 'type': 'message_batch', 'processing_status': status,
            'request_counts': {'processing': 0, 'succeeded': len(self.sent), 'errored': 0, 'canceled': 0,
                               'expired': 0},
            'created_at': '2026-11-13T10:00:00Z', 'expires_at': '2026-11-14T10:00:00Z', 'ended_at': None,
            'archived_at': None, 'cancel_initiated_at': None, 'results_url': None})

    def create(self, requests):
        self.sent = requests
        return self._batch('in_progress')

    def retrieve(self, batch_id):
        return self._batch('ended')

    def results(self, batch_id):
        for r in self.sent:
            yield MessageBatchIndividualResponse.model_validate({'custom_id': r['custom_id'], 'result': {
                'type': 'succeeded', 'message': Message.model_validate({
                    'id': f'msg_{r["custom_id"]}', 'type': 'message', 'role': 'assistant', 'model': MODEL,
                    'content': [{'type': 'text', 'text': self.read[r['custom_id']]}], 'stop_reason': 'end_turn',
                    'stop_sequence': None, 'usage': {'input_tokens': 1700, 'output_tokens': 400}})}})


def test_with_write_the_unread_pages_go_in_one_batch_and_the_memorandum_is_cut_from_them(monkeypatch, settings,
                                                                                         tmp_path):
    from apps.sources.services.ocr import batches
    settings.CORPUS_DIR, settings.ANTHROPIC_API_KEY = tmp_path, 'sk-ant-not-a-key'
    monkeypatch.setattr(guard, '_SPENDING', False)
    monkeypatch.setattr(batches.time, 'sleep', lambda s: None)
    write_pdf(tmp_path / 'sources' / 'parliament' / 'bill_013.26.pdf', [[], [], [], []])
    doc = bill([None, None, None, None])
    pages = list(doc.pages.order_by('index'))
    api = Batches({f'p{p.pk}': text for p, text in zip(pages, [COVER, MEMO, BILL])})
    monkeypatch.setattr(anthropic, 'Anthropic', lambda **kw: type('Client', (), {
        'messages': type('Messages', (), {'batches': api})()})())
    said, _ = run('--write')
    # The three first pages, in one batch, each its own request; the fourth is not paid for.
    assert [r['custom_id'] for r in api.sent] == [f'p{p.pk}' for p in pages[:3]]
    assert {(r['params']['model'], r['params']['max_tokens']) for r in api.sent} == {(MODEL, 6000)}
    assert said.startswith('reading 3 pages of 1 bills\n') and said.endswith('1 memoranda kept\n')
    runs = OcrRun.objects.filter(page__document=doc).order_by('page__index')
    assert [(r.page.index, r.engine, r.batch_id, r.text) for r in runs] == [
        (0, MODEL, 'msgbatch_01', COVER), (1, MODEL, 'msgbatch_01', MEMO), (2, MODEL, 'msgbatch_01', BILL)]
    memo = Explanation.objects.get(text_uri=LAW)
    assert memo.body == 'يأتي مشروع هذا القانون لملاءمة التشريع الوطني مع التطور الرقمي.' and memo.pages == '1-3'
